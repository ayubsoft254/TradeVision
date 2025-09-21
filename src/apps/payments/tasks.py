# apps/payments/tasks.py
from celery import shared_task
from django.utils import timezone
from django.db import transaction as db_transaction
from django.db.models import Sum, F, Count, Q
from decimal import Decimal
import logging
from datetime import timedelta

from .models import (
    Transaction, DepositRequest, WithdrawalRequest, Agent, P2PMerchant, PaymentMethod
)
from apps.core.models import SystemLog
from apps.trading.models import ProfitHistory

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3)
def process_pending_deposits(self):
    """
    DISABLED: All deposits require manual admin approval.
    This task no longer automatically processes deposits.
    """
    logger.info("Automatic deposit processing is DISABLED. All deposits require manual admin approval.")
    
    # Count pending deposits for reporting only
    pending_count = DepositRequest.objects.filter(
        transaction__status='pending'
    ).count()
    
    processing_count = DepositRequest.objects.filter(
        transaction__status='processing'
    ).count()
    
    return {
        'status': 'disabled',
        'message': 'Automatic processing disabled - manual admin approval required',
        'pending_deposits': pending_count,
        'processing_deposits': processing_count,
        'timestamp': timezone.now().isoformat()
    }

def process_single_deposit(deposit_request):
    """
    Process a single manually approved deposit request.
    This function is now only called by admin actions, not automatically.
    """
    try:
        transaction = deposit_request.transaction
        user = transaction.user
        wallet = user.wallet
        
        # Update transaction status
        transaction.status = 'completed'
        transaction.completed_at = timezone.now()
        transaction.save()
        
        # Update deposit request
        deposit_request.processed_at = timezone.now()
        deposit_request.admin_approved = True
        deposit_request.save()
        
        # Credit user wallet
        wallet.balance = F('balance') + transaction.net_amount
        wallet.save()
        
        # Refresh wallet to get updated balance
        wallet.refresh_from_db()
        
        # Log the deposit
        SystemLog.objects.create(
            user=user,
            action_type='deposit',
            level='INFO',
            message=f'Deposit manually approved and processed: {transaction.net_amount} {wallet.currency} credited to wallet',
            metadata={
                'transaction_id': str(transaction.id),
                'amount': str(transaction.amount),
                'net_amount': str(transaction.net_amount),
                'payment_method': transaction.payment_method.name if transaction.payment_method else 'unknown',
                'approved_by': 'admin'
            }
        )
        
        # Send deposit confirmation notification
        send_deposit_confirmation.delay(str(transaction.id))
        
        return {
            'success': True,
            'amount': transaction.net_amount,
            'transaction_id': str(transaction.id)
        }
        
    except Exception as e:
        logger.error(f"Error processing manually approved deposit {deposit_request.id}: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }

@shared_task(bind=True, max_retries=3)
def process_withdrawal_requests(self):
    """
    DISABLED: All withdrawals require manual admin approval.
    This task no longer automatically processes withdrawals.
    """
    logger.info("Automatic withdrawal processing is DISABLED. All withdrawals require manual admin approval.")
    
    # Count pending withdrawals for reporting only
    pending_count = WithdrawalRequest.objects.filter(
        transaction__status='pending'
    ).count()
    
    processing_count = WithdrawalRequest.objects.filter(
        transaction__status='processing',
        otp_verified=True
    ).count()
    
    return {
        'status': 'disabled',
        'message': 'Automatic processing disabled - manual admin approval required',
        'pending_withdrawals': pending_count,
        'processing_withdrawals': processing_count,
        'timestamp': timezone.now().isoformat()
    }

def process_single_withdrawal(withdrawal_request):
    """
    Process a single manually approved withdrawal request.
    This function is now only called by admin actions, not automatically.
    """
    try:
        transaction = withdrawal_request.transaction
        user = transaction.user
        
        # Update transaction status
        transaction.status = 'completed'
        transaction.completed_at = timezone.now()
        transaction.save()
        
        # Update withdrawal request
        withdrawal_request.processed_at = timezone.now()
        withdrawal_request.admin_approved = True
        withdrawal_request.save()
        
        # Note: Wallet balance was already debited when withdrawal was created
        # We just need to confirm the withdrawal is complete
        
        # Log the withdrawal
        SystemLog.objects.create(
            user=user,
            action_type='withdrawal',
            level='INFO',
            message=f'Withdrawal manually approved and processed: {transaction.net_amount} {transaction.currency} sent to user',
            metadata={
                'transaction_id': str(transaction.id),
                'amount': str(transaction.amount),
                'net_amount': str(transaction.net_amount),
                'payment_method': transaction.payment_method.name if transaction.payment_method else 'unknown',
                'withdrawal_address': withdrawal_request.withdrawal_address,
                'approved_by': 'admin'
            }
        )
        
        # Send withdrawal confirmation notification
        send_withdrawal_confirmation.delay(str(transaction.id))
        
        return {
            'success': True,
            'amount': transaction.net_amount,
            'transaction_id': str(transaction.id)
        }
        
    except Exception as e:
        logger.error(f"Error processing manually approved withdrawal {withdrawal_request.id}: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }

@shared_task(bind=True, max_retries=3)
def auto_approve_small_deposits(self):
    """
    DISABLED: All deposits require manual admin approval.
    No automatic approval regardless of amount.
    """
    logger.info("Auto-approval is PERMANENTLY DISABLED. All deposits require manual admin review.")
    
    # Count small deposits that would have been auto-approved before
    small_deposits_count = DepositRequest.objects.filter(
        transaction__status='pending',
        transaction__amount__lt=100  # Small deposit threshold
    ).count()
    
    return {
        'status': 'disabled',
        'small_deposits_pending': small_deposits_count,
        'message': 'Auto-approval permanently disabled - manual review required for ALL deposits'
    }

@shared_task
def check_failed_transactions():
    """
    Check for transactions that have been pending too long and mark as failed.
    Extended timeout to allow for manual admin review.
    """
    try:
        now = timezone.now()
        
        # Find transactions pending for more than 7 DAYS (extended for manual review)
        stale_transactions = Transaction.objects.filter(
            status='pending',
            created_at__lt=now - timedelta(days=7)  # Changed from 24 hours to 7 days
        )
        
        failed_count = 0
        
        for transaction in stale_transactions:
            try:
                with db_transaction.atomic():
                    # Mark as failed
                    transaction.status = 'failed'
                    transaction.save()
                    
                    # If it's a withdrawal, refund the balance
                    if transaction.transaction_type == 'withdrawal':
                        wallet = transaction.user.wallet
                        wallet.profit_balance = F('profit_balance') + transaction.amount
                        wallet.save()
                        
                        # Unmark withdrawn profits
                        ProfitHistory.objects.filter(
                            user=transaction.user,
                            is_withdrawn=True
                        ).order_by('-date_earned')[:1].update(is_withdrawn=False)
                    
                    # Log the failure
                    SystemLog.objects.create(
                        user=transaction.user,
                        action_type='system_error',
                        level='WARNING',
                        message=f'Transaction marked as failed due to timeout: {transaction.transaction_type}',
                        metadata={
                            'transaction_id': str(transaction.id),
                            'amount': str(transaction.amount),
                            'reason': 'timeout_7_days',
                            'note': 'Extended timeout for manual admin review'
                        }
                    )
                    
                    failed_count += 1
                    logger.warning(f"Marked stale transaction {transaction.id} as failed (7-day timeout)")
                    
            except Exception as e:
                logger.error(f"Error marking transaction {transaction.id} as failed: {str(e)}")
        
        if failed_count > 0:
            logger.info(f"Marked {failed_count} stale transactions as failed (7-day timeout)")
        
        return {
            'status': 'completed',
            'failed_count': failed_count
        }
        
    except Exception as e:
        logger.error(f"Error in check_failed_transactions: {str(e)}")
        return {
            'status': 'failed',
            'error': str(e)
        }

@shared_task
def update_payment_provider_ratings():
    """
    Update ratings and statistics for agents and P2P merchants.
    Runs daily to maintain provider quality metrics.
    """
    try:
        updated_agents = 0
        updated_merchants = 0
        
        # Update agent ratings based on recent transactions
        agents = Agent.objects.filter(is_active=True)
        
        for agent in agents:
            try:
                # Get recent transactions for this agent (last 30 days)
                recent_transactions = Transaction.objects.filter(
                    metadata__agent_id=str(agent.id),
                    created_at__gte=timezone.now() - timedelta(days=30),
                    status='completed'
                )
                
                transaction_count = recent_transactions.count()
                
                if transaction_count > 0:
                    # Calculate success rate and update rating
                    # This is a simplified rating system
                    base_rating = 4.0
                    if transaction_count >= 10:
                        base_rating = 4.5
                    if transaction_count >= 50:
                        base_rating = 5.0
                    
                    agent.rating = base_rating
                    agent.total_transactions = F('total_transactions') + transaction_count
                    agent.save()
                    updated_agents += 1
                    
            except Exception as e:
                logger.error(f"Error updating agent {agent.id} rating: {str(e)}")
        
        # Update P2P merchant ratings
        merchants = P2PMerchant.objects.filter(is_active=True)
        
        for merchant in merchants:
            try:
                # Get recent transactions for this merchant
                recent_transactions = Transaction.objects.filter(
                    metadata__merchant_id=str(merchant.id),
                    created_at__gte=timezone.now() - timedelta(days=30),
                    status='completed'
                )
                
                transaction_count = recent_transactions.count()
                
                if transaction_count > 0:
                    # Calculate completion rate and rating
                    base_rating = 4.0
                    if transaction_count >= 20:
                        base_rating = 4.5
                    if transaction_count >= 100:
                        base_rating = 5.0
                    
                    merchant.rating = base_rating
                    merchant.total_orders = F('total_orders') + transaction_count
                    merchant.completion_rate = min(95.0 + (transaction_count * 0.1), 100.0)
                    merchant.save()
                    updated_merchants += 1
                    
            except Exception as e:
                logger.error(f"Error updating merchant {merchant.id} rating: {str(e)}")
        
        logger.info(f"Updated ratings: {updated_agents} agents, {updated_merchants} merchants")
        
        return {
            'status': 'completed',
            'updated_agents': updated_agents,
            'updated_merchants': updated_merchants
        }
        
    except Exception as e:
        logger.error(f"Error in update_payment_provider_ratings: {str(e)}")
        return {
            'status': 'failed',
            'error': str(e)
        }

@shared_task
def generate_payment_reports():
    """
    Generate daily payment reports for admin monitoring.
    Enhanced to include pending transactions requiring manual approval.
    """
    try:
        yesterday = timezone.now().date() - timedelta(days=1)
        
        # Get payment statistics for yesterday
        daily_stats = {
            'date': yesterday.isoformat(),
            'deposits': {
                'count': 0,
                'total_amount': Decimal('0'),
                'completed': 0,
                'pending': 0,
                'processing': 0,
                'failed': 0
            },
            'withdrawals': {
                'count': 0,
                'total_amount': Decimal('0'),
                'completed': 0,
                'pending': 0,
                'processing': 0,
                'failed': 0
            },
            'admin_action_required': {
                'pending_deposits': 0,
                'pending_withdrawals': 0
            }
        }
        
        # Get deposit statistics
        deposits = Transaction.objects.filter(
            transaction_type='deposit',
            created_at__date=yesterday
        )
        
        daily_stats['deposits']['count'] = deposits.count()
        daily_stats['deposits']['total_amount'] = deposits.aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0')
        daily_stats['deposits']['completed'] = deposits.filter(status='completed').count()
        daily_stats['deposits']['pending'] = deposits.filter(status='pending').count()
        daily_stats['deposits']['processing'] = deposits.filter(status='processing').count()
        daily_stats['deposits']['failed'] = deposits.filter(status='failed').count()
        
        # Get withdrawal statistics
        withdrawals = Transaction.objects.filter(
            transaction_type='withdrawal',
            created_at__date=yesterday
        )
        
        daily_stats['withdrawals']['count'] = withdrawals.count()
        daily_stats['withdrawals']['total_amount'] = withdrawals.aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0')
        daily_stats['withdrawals']['completed'] = withdrawals.filter(status='completed').count()
        daily_stats['withdrawals']['pending'] = withdrawals.filter(status='pending').count()
        daily_stats['withdrawals']['processing'] = withdrawals.filter(status='processing').count()
        daily_stats['withdrawals']['failed'] = withdrawals.filter(status='failed').count()
        
        # Get current pending transactions requiring admin action
        daily_stats['admin_action_required']['pending_deposits'] = Transaction.objects.filter(
            transaction_type='deposit',
            status='pending'
        ).count()
        
        daily_stats['admin_action_required']['pending_withdrawals'] = Transaction.objects.filter(
            transaction_type='withdrawal',
            status='pending'
        ).count()
        
        # Log the daily report with admin action alerts
        logger.info(f"Daily payment report: {daily_stats}")
        
        if daily_stats['admin_action_required']['pending_deposits'] > 0:
            logger.warning(f"ADMIN ACTION REQUIRED: {daily_stats['admin_action_required']['pending_deposits']} deposits awaiting approval")
        
        if daily_stats['admin_action_required']['pending_withdrawals'] > 0:
            logger.warning(f"ADMIN ACTION REQUIRED: {daily_stats['admin_action_required']['pending_withdrawals']} withdrawals awaiting approval")
        
        return {
            'status': 'completed',
            'daily_stats': daily_stats
        }
        
    except Exception as e:
        logger.error(f"Error in generate_payment_reports: {str(e)}")
        return {
            'status': 'failed',
            'error': str(e)
        }

@shared_task
def detect_suspicious_activity():
    """
    Detect suspicious payment patterns and flag for review.
    Enhanced monitoring since all payments require manual approval.
    """
    try:
        now = timezone.now()
        suspicious_count = 0
        
        # Check for multiple deposits from same user in short time
        recent_deposits = Transaction.objects.filter(
            created_at__gte=now - timedelta(hours=1),
            transaction_type='deposit'
        ).values('user').annotate(count=Count('id')).filter(count__gte=3)
        
        for user_deposits in recent_deposits:
            SystemLog.objects.create(
                user_id=user_deposits['user'],
                action_type='security',
                level='WARNING',
                message=f'Multiple deposits detected from same user: {user_deposits["count"]} deposits in 1 hour',
                metadata={
                    'deposit_count': user_deposits['count'],
                    'flagged_reason': 'multiple_deposits_short_time'
                }
            )
            suspicious_count += 1
        
        # Check for large withdrawal requests
        large_withdrawals = Transaction.objects.filter(
            transaction_type='withdrawal',
            amount__gte=10000,  # Large withdrawal threshold
            created_at__gte=now - timedelta(hours=24),
            status='pending'
        )
        
        for withdrawal in large_withdrawals:
            # Flag for manual review
            SystemLog.objects.create(
                user=withdrawal.user,
                action_type='security',
                level='WARNING',
                message=f'Large withdrawal flagged for review: {withdrawal.amount}',
                metadata={
                    'transaction_id': str(withdrawal.id),
                    'amount': str(withdrawal.amount),
                    'flagged_reason': 'large_amount'
                }
            )
            suspicious_count += 1
        
        # Check for rapid deposit-withdrawal patterns
        rapid_patterns = Transaction.objects.filter(
            created_at__gte=now - timedelta(hours=2)
        ).values('user').annotate(
            deposit_count=Count('id', filter=Q(transaction_type='deposit')),
            withdrawal_count=Count('id', filter=Q(transaction_type='withdrawal'))
        ).filter(deposit_count__gte=1, withdrawal_count__gte=1)
        
        for pattern in rapid_patterns:
            SystemLog.objects.create(
                user_id=pattern['user'],
                action_type='security',
                level='WARNING',
                message='Rapid deposit-withdrawal pattern detected',
                metadata={
                    'deposits': pattern['deposit_count'],
                    'withdrawals': pattern['withdrawal_count'],
                    'flagged_reason': 'rapid_deposit_withdrawal'
                }
            )
            suspicious_count += 1
        
        if suspicious_count > 0:
            logger.warning(f"Flagged {suspicious_count} suspicious activities for admin review")
        
        return {
            'status': 'completed',
            'suspicious_count': suspicious_count
        }
        
    except Exception as e:
        logger.error(f"Error in detect_suspicious_activity: {str(e)}")
        return {
            'status': 'failed',
            'error': str(e)
        }

# Notification tasks
@shared_task
def send_deposit_confirmation(transaction_id):
    """
    Send deposit confirmation notification to user.
    """
    try:
        transaction = Transaction.objects.get(id=transaction_id)
        user = transaction.user
        
        # Here you would integrate with your notification service
        # For now, we'll just log the notification
        logger.info(
            f"Deposit confirmation for {user.email}: "
            f"{transaction.net_amount} {transaction.currency} credited (Admin Approved)"
        )
        
        return {'status': 'sent', 'user_email': user.email}
        
    except Transaction.DoesNotExist:
        logger.error(f"Transaction {transaction_id} not found for deposit confirmation")
        return {'status': 'failed', 'error': 'Transaction not found'}
    except Exception as e:
        logger.error(f"Error sending deposit confirmation for {transaction_id}: {str(e)}")
        return {'status': 'failed', 'error': str(e)}

@shared_task
def send_withdrawal_confirmation(transaction_id):
    """
    Send withdrawal confirmation notification to user.
    """
    try:
        transaction = Transaction.objects.get(id=transaction_id)
        user = transaction.user
        
        # Log the notification
        logger.info(
            f"Withdrawal confirmation for {user.email}: "
            f"{transaction.net_amount} {transaction.currency} sent (Admin Approved)"
        )
        
        return {'status': 'sent', 'user_email': user.email}
        
    except Transaction.DoesNotExist:
        logger.error(f"Transaction {transaction_id} not found for withdrawal confirmation")
        return {'status': 'failed', 'error': 'Transaction not found'}
    except Exception as e:
        logger.error(f"Error sending withdrawal confirmation for {transaction_id}: {str(e)}")
        return {'status': 'failed', 'error': str(e)}

# Admin notification tasks
@shared_task
def notify_admin_pending_payments():
    """
    Notify admins about payments requiring approval.
    Runs every hour to alert admins of pending payments.
    """
    try:
        pending_deposits = Transaction.objects.filter(
            transaction_type='deposit',
            status='pending'
        ).count()
        
        pending_withdrawals = Transaction.objects.filter(
            transaction_type='withdrawal',
            status='pending'
        ).count()
        
        if pending_deposits > 0 or pending_withdrawals > 0:
            logger.warning(
                f"ADMIN ALERT: {pending_deposits} deposits and {pending_withdrawals} withdrawals "
                f"require manual approval"
            )
            
            # Here you would send actual notifications to admins
            # Email, Slack, SMS, etc.
        
        return {
            'status': 'completed',
            'pending_deposits': pending_deposits,
            'pending_withdrawals': pending_withdrawals
        }
        
    except Exception as e:
        logger.error(f"Error in notify_admin_pending_payments: {str(e)}")
        return {'status': 'failed', 'error': str(e)}