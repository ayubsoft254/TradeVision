from celery import shared_task
from django.utils import timezone
from django.db import transaction as db_transaction
from django.db.models import Sum, Count, F
from django.conf import settings
from decimal import Decimal
import logging
from datetime import timedelta

from .models import Trade, Investment, ProfitHistory, TradingPackage
from apps.payments.models import Wallet, Transaction
from apps.core.models import SystemLog, SiteConfiguration
from apps.accounts.models import User

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3)
def process_completed_trades(self):
    """
    Process trades that have completed their 24-hour cycle.
    This is the CORE task that makes the trading platform work.
    Runs every minute to check for completed trades.
    """
    try:
        now = timezone.now()
        current_weekday = now.weekday()
        
        # Only process on weekdays (Monday=0 to Friday=4)
        if current_weekday >= 5:
            logger.info("Skipping trade processing - weekend")
            return {
                'status': 'skipped',
                'reason': 'weekend',
                'processed_count': 0
            }
        
        # Get all running trades that have completed their 24-hour cycle
        completed_trades = Trade.objects.filter(
            status='running',
            end_time__lte=now
        ).select_related(
            'investment',
            'investment__user',
            'investment__user__wallet',
            'investment__package'
        )
        
        processed_count = 0
        failed_count = 0
        total_profits = Decimal('0')
        
        for trade in completed_trades:
            try:
                with db_transaction.atomic():
                    # Process individual trade
                    result = process_single_trade(trade)
                    if result['success']:
                        processed_count += 1
                        total_profits += result['profit_amount']
                        logger.info(f"Successfully processed trade {trade.id} - Profit: {result['profit_amount']}")
                    else:
                        failed_count += 1
                        logger.error(f"Failed to process trade {trade.id}: {result['error']}")
                        
            except Exception as e:
                failed_count += 1
                logger.error(f"Error processing trade {trade.id}: {str(e)}")
                
                # Mark trade as failed if it's a critical error
                try:
                    trade.status = 'failed'
                    trade.save()
                except:
                    pass
        
        # Log the batch processing result
        logger.info(f"Trade processing completed: {processed_count} successful, {failed_count} failed")
        
        # Update platform statistics if trades were processed
        if processed_count > 0:
            update_platform_statistics.delay()
        
        return {
            'status': 'completed',
            'processed_count': processed_count,
            'failed_count': failed_count,
            'total_profits': float(total_profits),
            'timestamp': now.isoformat()
        }
        
    except Exception as e:
        logger.error(f"Critical error in process_completed_trades: {str(e)}")
        
        # Retry the task if it failed
        if self.request.retries < self.max_retries:
            logger.info(f"Retrying process_completed_trades, attempt {self.request.retries + 1}")
            raise self.retry(countdown=60, exc=e)
        
        return {
            'status': 'failed',
            'error': str(e),
            'processed_count': 0
        }

def process_single_trade(trade):
    """
    Process a single completed trade.
    This function handles the core business logic of profit distribution.
    """
    try:
        # Validate trade can be completed
        if trade.status != 'running':
            return {'success': False, 'error': 'Trade is not in running status'}
        
        # Update trade status
        trade.status = 'completed'
        trade.completed_at = timezone.now()
        trade.save()
        
        # Create profit history record
        profit_record = ProfitHistory.objects.create(
            user=trade.investment.user,
            investment=trade.investment,
            trade=trade,
            amount=trade.profit_amount,
            profit_rate=trade.profit_rate
        )
        
        # Update investment total profits
        trade.investment.total_profits = F('total_profits') + trade.profit_amount
        trade.investment.save()
        
        # Update user wallet profit balance
        wallet = trade.investment.user.wallet
        wallet.profit_balance = F('profit_balance') + trade.profit_amount
        wallet.save()
        
        # Refresh wallet to get updated balance
        wallet.refresh_from_db()
        
        # Create profit transaction record
        Transaction.objects.create(
            user=trade.investment.user,
            transaction_type='profit',
            amount=trade.profit_amount,
            currency=wallet.currency,
            status='completed',
            net_amount=trade.profit_amount,
            description=f'Daily profit from {trade.investment.package.display_name}',
            metadata={
                'trade_id': str(trade.id),
                'investment_id': str(trade.investment.id),
                'profit_rate': str(trade.profit_rate)
            }
        )
        
        # Log the profit generation
        SystemLog.objects.create(
            user=trade.investment.user,
            action_type='trade',
            level='INFO',
            message=f'Trade completed: {trade.profit_amount} {wallet.currency} profit generated',
            metadata={
                'trade_id': str(trade.id),
                'profit_amount': str(trade.profit_amount),
                'profit_rate': str(trade.profit_rate)
            }
        )
        
        return {
            'success': True,
            'profit_amount': trade.profit_amount,
            'trade_id': str(trade.id)
        }
        
    except Exception as e:
        logger.error(f"Error processing single trade {trade.id}: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }

@shared_task(bind=True, max_retries=3)
def auto_initiate_daily_trades(self):
    """
    Automatically initiate new trades for active investments.
    Runs every hour during trading hours (8 AM - 6 PM, Monday-Friday).
    """
    try:
        now = timezone.now()
        current_weekday = now.weekday()
        current_hour = now.hour
        
        # Only run on weekdays between 8 AM and 6 PM
        if current_weekday >= 5:
            logger.info("Skipping auto trade initiation - weekend")
            return {
                'status': 'skipped',
                'reason': 'weekend',
                'initiated_count': 0
            }
        
        if current_hour < 8 or current_hour > 18:
            logger.info(f"Skipping auto trade initiation - outside trading hours (current: {current_hour})")
            return {
                'status': 'skipped',
                'reason': 'outside_trading_hours',
                'initiated_count': 0
            }
        
        # Get active investments without running trades
        eligible_investments = Investment.objects.filter(
            status='active'
        ).exclude(
            trades__status__in=['pending', 'running']
        ).select_related('package', 'user', 'user__wallet')
        
        # Filter investments that haven't had a trade today
        today = now.date()
        eligible_investments = eligible_investments.exclude(
            trades__created_at__date=today
        )
        
        initiated_count = 0
        failed_count = 0
        
        for investment in eligible_investments:
            try:
                with db_transaction.atomic():
                    # Generate random profit rate for this trade
                    profit_rate = investment.package.get_random_profit_rate()
                    
                    # Create new trade
                    trade = Trade.objects.create(
                        investment=investment,
                        trade_amount=investment.total_investment,
                        profit_rate=profit_rate,
                        status='running',
                        start_time=now
                    )
                    
                    # Log the auto-initiated trade
                    SystemLog.objects.create(
                        user=investment.user,
                        action_type='trade',
                        level='INFO',
                        message=f'Auto-initiated trade for {investment.package.display_name}',
                        metadata={
                            'trade_id': str(trade.id),
                            'investment_id': str(investment.id),
                            'profit_rate': str(profit_rate),
                            'auto_initiated': True
                        }
                    )
                    
                    initiated_count += 1
                    logger.info(f"Auto-initiated trade {trade.id} for investment {investment.id}")
                    
            except Exception as e:
                failed_count += 1
                logger.error(f"Error auto-initiating trade for investment {investment.id}: {str(e)}")
        
        logger.info(f"Auto trade initiation completed: {initiated_count} initiated, {failed_count} failed")
        
        return {
            'status': 'completed',
            'initiated_count': initiated_count,
            'failed_count': failed_count,
            'timestamp': now.isoformat()
        }
        
    except Exception as e:
        logger.error(f"Critical error in auto_initiate_daily_trades: {str(e)}")
        
        # Retry the task if it failed
        if self.request.retries < self.max_retries:
            logger.info(f"Retrying auto_initiate_daily_trades, attempt {self.request.retries + 1}")
            raise self.retry(countdown=300, exc=e)  # Retry in 5 minutes
        
        return {
            'status': 'failed',
            'error': str(e),
            'initiated_count': 0
        }

@shared_task(bind=True, max_retries=3)
def check_investment_maturity(self):
    """
    Check for investments that have reached maturity (365 days) and unlock principal.
    Runs daily to process matured investments.
    """
    try:
        now = timezone.now()
        
        # Get investments that have matured but haven't been processed
        matured_investments = Investment.objects.filter(
            status='active',
            maturity_date__lte=now,
            is_principal_withdrawable=False
        ).select_related('user', 'user__wallet', 'package')
        
        processed_count = 0
        failed_count = 0
        total_unlocked = Decimal('0')
        
        for investment in matured_investments:
            try:
                with db_transaction.atomic():
                    # Update investment status
                    investment.is_principal_withdrawable = True
                    investment.status = 'completed'
                    investment.save()
                    
                    # Update wallet - move locked balance to available balance
                    wallet = investment.user.wallet
                    
                    # Only move the principal amount (not the bonus)
                    principal_to_unlock = investment.principal_amount
                    
                    wallet.locked_balance = F('locked_balance') - investment.total_investment
                    wallet.balance = F('balance') + principal_to_unlock
                    wallet.save()
                    
                    # Refresh wallet to get updated balances
                    wallet.refresh_from_db()
                    
                    # Create transaction record for principal unlock
                    Transaction.objects.create(
                        user=investment.user,
                        transaction_type='investment',
                        amount=principal_to_unlock,
                        currency=wallet.currency,
                        status='completed',
                        net_amount=principal_to_unlock,
                        description=f'Principal unlocked from matured {investment.package.display_name}',
                        metadata={
                            'investment_id': str(investment.id),
                            'maturity_unlock': True
                        }
                    )
                    
                    # Log the maturity processing
                    SystemLog.objects.create(
                        user=investment.user,
                        action_type='investment',
                        level='INFO',
                        message=f'Investment matured: {principal_to_unlock} {wallet.currency} principal unlocked',
                        metadata={
                            'investment_id': str(investment.id),
                            'principal_amount': str(principal_to_unlock),
                            'maturity_date': investment.maturity_date.isoformat()
                        }
                    )
                    
                    processed_count += 1
                    total_unlocked += principal_to_unlock
                    logger.info(f"Processed matured investment {investment.id} - Unlocked: {principal_to_unlock}")
                    
            except Exception as e:
                failed_count += 1
                logger.error(f"Error processing matured investment {investment.id}: {str(e)}")
        
        logger.info(f"Investment maturity check completed: {processed_count} processed, {failed_count} failed")
        
        # Update platform statistics if investments were processed
        if processed_count > 0:
            update_platform_statistics.delay()
        
        return {
            'status': 'completed',
            'processed_count': processed_count,
            'failed_count': failed_count,
            'total_unlocked': float(total_unlocked),
            'timestamp': now.isoformat()
        }
        
    except Exception as e:
        logger.error(f"Critical error in check_investment_maturity: {str(e)}")
        
        # Retry the task if it failed
        if self.request.retries < self.max_retries:
            logger.info(f"Retrying check_investment_maturity, attempt {self.request.retries + 1}")
            raise self.retry(countdown=3600, exc=e)  # Retry in 1 hour
        
        return {
            'status': 'failed',
            'error': str(e),
            'processed_count': 0
        }

@shared_task(bind=True, max_retries=3)
def update_wallet_balances(self):
    """
    Recalculate and update wallet balances for consistency.
    Runs twice daily to ensure data integrity.
    """
    try:
        updated_count = 0
        error_count = 0
        
        # Get all users with wallets
        users_with_wallets = User.objects.filter(
            wallet__isnull=False
        ).select_related('wallet')
        
        for user in users_with_wallets:
            try:
                with db_transaction.atomic():
                    wallet = user.wallet
                    
                    # Calculate locked balance from active investments
                    locked_balance = user.investments.filter(
                        status='active'
                    ).aggregate(
                        total=Sum('total_investment')
                    )['total'] or Decimal('0')
                    
                    # Calculate profit balance from unwithrawn profits
                    profit_balance = user.profit_history.filter(
                        is_withdrawn=False
                    ).aggregate(
                        total=Sum('amount')
                    )['total'] or Decimal('0')
                    
                    # Check if update is needed
                    needs_update = (
                        wallet.locked_balance != locked_balance or
                        wallet.profit_balance != profit_balance
                    )
                    
                    if needs_update:
                        # Log the discrepancy
                        logger.warning(
                            f"Wallet balance discrepancy for user {user.id}: "
                            f"locked_balance {wallet.locked_balance} -> {locked_balance}, "
                            f"profit_balance {wallet.profit_balance} -> {profit_balance}"
                        )
                        
                        # Update wallet balances
                        wallet.locked_balance = locked_balance
                        wallet.profit_balance = profit_balance
                        wallet.save()
                        
                        updated_count += 1
                        
                        # Log the correction
                        SystemLog.objects.create(
                            user=user,
                            action_type='system_error',
                            level='WARNING',
                            message='Wallet balance corrected by system maintenance',
                            metadata={
                                'old_locked_balance': str(wallet.locked_balance),
                                'new_locked_balance': str(locked_balance),
                                'old_profit_balance': str(wallet.profit_balance),
                                'new_profit_balance': str(profit_balance)
                            }
                        )
                        
            except Exception as e:
                error_count += 1
                logger.error(f"Error updating wallet for user {user.id}: {str(e)}")
        
        logger.info(f"Wallet balance update completed: {updated_count} updated, {error_count} errors")
        
        return {
            'status': 'completed',
            'updated_count': updated_count,
            'error_count': error_count,
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Critical error in update_wallet_balances: {str(e)}")
        
        # Retry the task if it failed
        if self.request.retries < self.max_retries:
            logger.info(f"Retrying update_wallet_balances, attempt {self.request.retries + 1}")
            raise self.retry(countdown=1800, exc=e)  # Retry in 30 minutes
        
        return {
            'status': 'failed',
            'error': str(e),
            'updated_count': 0
        }

@shared_task
def update_platform_statistics():
    """
    Update platform-wide statistics in SiteConfiguration.
    Called after significant trading events.
    """
    try:
        # Get or create site configuration
        site_config, created = SiteConfiguration.objects.get_or_create(
            pk=1,
            defaults={
                'site_name': 'TradeVision',
                'site_description': 'Smart Trading Platform'
            }
        )
        
        # Calculate current statistics
        total_users = User.objects.filter(is_active=True).count()
        
        total_invested = Investment.objects.filter(
            status__in=['active', 'completed']
        ).aggregate(
            total=Sum('principal_amount')
        )['total'] or Decimal('0')
        
        total_profits_paid = ProfitHistory.objects.aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0')
        
        # Update site configuration
        site_config.total_users = total_users
        site_config.total_invested = total_invested
        site_config.total_profits_paid = total_profits_paid
        site_config.save()
        
        logger.info(f"Platform statistics updated: {total_users} users, {total_invested} invested, {total_profits_paid} profits")
        
        return {
            'status': 'completed',
            'total_users': total_users,
            'total_invested': float(total_invested),
            'total_profits_paid': float(total_profits_paid)
        }
        
    except Exception as e:
        logger.error(f"Error updating platform statistics: {str(e)}")
        return {
            'status': 'failed',
            'error': str(e)
        }

@shared_task
def cleanup_failed_trades():
    """
    Clean up trades that have been stuck in pending/running state for too long.
    Runs daily for maintenance.
    """
    try:
        now = timezone.now()
        
        # Find trades stuck in pending state for more than 1 hour
        stuck_pending = Trade.objects.filter(
            status='pending',
            created_at__lt=now - timedelta(hours=1)
        )
        
        # Find trades stuck in running state for more than 25 hours
        stuck_running = Trade.objects.filter(
            status='running',
            start_time__lt=now - timedelta(hours=25)
        )
        
        cleaned_count = 0
        
        # Clean up stuck pending trades
        for trade in stuck_pending:
            trade.status = 'failed'
            trade.save()
            cleaned_count += 1
            logger.warning(f"Marked stuck pending trade {trade.id} as failed")
        
        # Clean up stuck running trades
        for trade in stuck_running:
            trade.status = 'failed'
            trade.save()
            cleaned_count += 1
            logger.warning(f"Marked stuck running trade {trade.id} as failed")
        
        if cleaned_count > 0:
            logger.info(f"Cleaned up {cleaned_count} stuck trades")
        
        return {
            'status': 'completed',
            'cleaned_count': cleaned_count
        }
        
    except Exception as e:
        logger.error(f"Error in cleanup_failed_trades: {str(e)}")
        return {
            'status': 'failed',
            'error': str(e)
        }

@shared_task(bind=True, max_retries=3)
def initiate_manual_trade(self, investment_id, user_id, ip_address=None):
    """
    Initiate a trade manually (user-requested).
    This is called when a user clicks 'Start Trade' button.
    """
    try:
        from apps.accounts.models import User
        from apps.core.models import SystemLog
        
        # Get user and investment
        user = User.objects.select_related('wallet').get(id=user_id)
        investment = Investment.objects.select_related('package', 'user').get(
            id=investment_id,
            user=user,
            status='active'
        )
        
        # Check if there's already a pending/running trade
        existing_trade = Trade.objects.filter(
            investment=investment,
            status__in=['pending', 'running']
        ).first()
        
        if existing_trade:
            logger.warning(f"Trade already exists for investment {investment_id}")
            return {
                'status': 'error',
                'error': 'There is already an active trade for this investment',
                'trade_id': str(existing_trade.id)
            }
        
        with db_transaction.atomic():
            # Generate random profit rate
            profit_rate = investment.package.get_random_profit_rate()
            
            # Create new trade
            start_time = timezone.now()
            end_time = start_time + timedelta(hours=24)
            
            trade = Trade.objects.create(
                investment=investment,
                trade_amount=investment.total_investment,
                profit_rate=profit_rate,
                status='running',
                start_time=start_time,
                end_time=end_time
            )
            
            # Log the trade initiation
            SystemLog.objects.create(
                user=user,
                action_type='trade',
                level='INFO',
                message=f'User manually initiated trade for {investment.package.display_name}',
                ip_address=ip_address,
                metadata={
                    'trade_id': str(trade.id),
                    'investment_id': str(investment.id),
                    'profit_rate': str(profit_rate),
                    'manual_initiation': True
                }
            )
            
            logger.info(f"Successfully initiated manual trade {trade.id} for user {user_id}")
            
            return {
                'status': 'success',
                'trade_id': str(trade.id),
                'profit_amount': str(trade.profit_amount),
                'profit_rate': str(profit_rate),
                'end_time': end_time.isoformat(),
                'message': f'Trade initiated successfully! Expected profit: {trade.profit_amount} {user.wallet.currency}'
            }
            
    except Investment.DoesNotExist:
        error_msg = 'Investment not found or not owned by user'
        logger.error(f"Investment {investment_id} not found for user {user_id}")
        return {
            'status': 'error',
            'error': error_msg
        }
        
    except User.DoesNotExist:
        error_msg = 'User not found'
        logger.error(f"User {user_id} not found")
        return {
            'status': 'error',
            'error': error_msg
        }
        
    except Exception as e:
        logger.error(f"Error initiating manual trade for user {user_id}, investment {investment_id}: {str(e)}")
        
        # Retry the task if it failed
        if self.request.retries < self.max_retries:
            logger.info(f"Retrying initiate_manual_trade, attempt {self.request.retries + 1}")
            raise self.retry(countdown=30, exc=e)
        
        return {
            'status': 'error',
            'error': str(e)
        }

# Task to send profit notifications (placeholder for future email/SMS integration)
@shared_task
def send_profit_notifications():
    """
    Send notifications to users about their daily profits.
    This can be extended to send emails, SMS, or push notifications.
    """
    try:
        # Get recent profits from today
        today = timezone.now().date()
        recent_profits = ProfitHistory.objects.filter(
            date_earned__date=today
        ).select_related('user', 'investment')
        
        # Group profits by user
        user_profits = {}
        for profit in recent_profits:
            user_id = profit.user.id
            if user_id not in user_profits:
                user_profits[user_id] = {
                    'user': profit.user,
                    'total_profit': Decimal('0'),
                    'profit_count': 0
                }
            user_profits[user_id]['total_profit'] += profit.amount
            user_profits[user_id]['profit_count'] += 1
        
        # Here you would integrate with your notification service
        # For now, we'll just log the notifications
        notification_count = 0
        for user_data in user_profits.values():
            logger.info(
                f"Profit notification for {user_data['user'].email}: "
                f"{user_data['total_profit']} from {user_data['profit_count']} trades"
            )
            notification_count += 1
        
        return {
            'status': 'completed',
            'notification_count': notification_count
        }
        
    except Exception as e:
        logger.error(f"Error in send_profit_notifications: {str(e)}")
        return {
            'status': 'failed',
            'error': str(e)
        }