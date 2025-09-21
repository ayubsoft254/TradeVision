# apps/payments/tasks.py
from celery import shared_task
from django.utils import timezone
from django.db import transaction as db_transaction
from django.db.models import Sum, F
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
    Process approved deposit requests and update user wallets.
    Runs every 5 minutes to handle approved deposits.
    """
    try:
        # Get approved deposits that haven't been processed
        pending_deposits = DepositRequest.objects.filter(
            transaction__status='processing'
        ).select_related(
            'transaction',
            'transaction__user',
            'transaction__user__wallet',
            'transaction__payment_method'
        )
        
        processed_count = 0
        failed_count = 0
        total_amount = Decimal('0')
        
        for deposit_request in pending_deposits:
            try:
                with db_transaction.atomic():
                    transaction = deposit_request.transaction
                    
                    # Skip if already processed
                    if transaction.status != 'processing':
                        continue
                    
                    # Process the deposit
                    result = process_single_deposit(deposit_request)
                    
                    if result['success']:
                        processed_count += 1
                        total_amount += result['amount']
                        logger.info(f"Successfully processed deposit {transaction.id} - Amount: {result['amount']}")
                    else:
                        failed_count += 1
                        logger.error(f"Failed to process deposit {transaction.id}: {result['error']}")
                        
            except Exception as e:
                failed_count += 1
                logger.error(f"Error processing deposit request {deposit_request.id}: {str(e)}")
        
        logger.info(f"Deposit processing completed: {processed_count} successful, {failed_count} failed")
        
        return {
            'status': 'completed',
            'processed_count': processed_count,
            'failed_count': failed_count,
            'total_amount': float(total_amount),
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Critical error in process_pending_deposits: {str(e)}")
        
        if self.request.retries < self.max_retries:
            logger.info(f"Retrying process_pending_deposits, attempt {self.request.retries + 1}")
            raise self.retry(countdown=300, exc=e)
        
        return {
            'status': 'failed',
            'error': str(e),
            'processed_count': 0
        }

def process_single_deposit(deposit_request):
    """
    Process a single approved deposit request.
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
            message=f'Deposit processed: {transaction.net_amount} {wallet.currency} credited to wallet',
            metadata={
                'transaction_id': str(transaction.id),
                'amount': str(transaction.amount),
                'net_amount': str(transaction.net_amount),
                'payment_method': transaction.payment_method.name if transaction.payment_method else 'unknown'
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
        logger.error(f"Error processing single deposit {deposit_request.id}: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }

@shared_task(bind=True, max_retries=3)
def process_withdrawal_requests(self):
    """
    Process approved withdrawal requests.
    Runs every 10 minutes to handle approved withdrawals.
    """
    try:
        # Get approved withdrawals that haven't been processed
        pending_withdrawals = WithdrawalRequest.objects.filter(
            transaction__status='processing',
            otp_verified=True
        ).select_related(
            'transaction',
            'transaction__user',
            'transaction__user__wallet',
            'transaction__payment_method'
        )
        
        processed_count = 0
        failed_count = 0
        total_amount = Decimal('0')
        
        for withdrawal_request in pending_withdrawals:
            try:
                with db_transaction.atomic():
                    transaction = withdrawal_request.transaction
                    
                    # Skip if already processed
                    if transaction.status != 'processing':
                        continue
                    
                    # Process the withdrawal
                    result = process_single_withdrawal(withdrawal_request)
                    
                    if result['success']:
                        processed_count += 1
                        total_amount += result['amount']
                        logger.info(f"Successfully processed withdrawal {transaction.id} - Amount: {result['amount']}")
                    else:
                        failed_count += 1
                        logger.error(f"Failed to process withdrawal {transaction.id}: {result['error']}")
                        
            except Exception as e:
                failed_count += 1
                logger.error(f"Error processing withdrawal request {withdrawal_request.id}: {str(e)}")
        
        logger.info(f"Withdrawal processing completed: {processed_count} successful, {failed_count} failed")
        
        return {
            'status': 'completed',
            'processed_count': processed_count,
            'failed_count': failed_count,
            'total_amount': float(total_amount),
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Critical error in process_withdrawal_requests: {str(e)}")
        
        if self.request.retries < self.max_retries:
            logger.info(f"Retrying process_withdrawal_requests, attempt {self.request.retries + 1}")
            raise self.retry(countdown=600, exc=e)
        
        return {
            'status': 'failed',
            'error': str(e),
            'processed_count': 0
        }

def process_single_withdrawal(withdrawal_request):
    """
    Process a single approved withdrawal request.
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
        withdrawal_request.save()
        
        # Note: Wallet balance was already debited when withdrawal was created
        # We just need to confirm the withdrawal is complete
        
        # Log the withdrawal
        SystemLog.objects.create(
            user=user,
            action_type='withdrawal',
            level='INFO',
            message=f'Withdrawal processed: {transaction.net_amount} {transaction.currency} sent to user',
            metadata={
                'transaction_id': str(transaction.id),
                'amount': str(transaction.amount),
                'net_amount': str(transaction.net_amount),
                'payment_method': transaction.payment_method.name if transaction.payment_method else 'unknown',
                'withdrawal_address': withdrawal_request.withdrawal_address
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
        logger.error(f"Error processing single withdrawal {withdrawal_request.id}: {str(e)}")
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
    logger.info("Auto-approval is disabled. All deposits require manual admin review.")
    return {
        'status': 'disabled',
        'approved_count': 0,
        'message': 'Auto-approval disabled - manual review required for all deposits'
    }

@shared_task
def check_failed_transactions():
    """
    Check for transactions that have been pending too long and mark as failed.
    Runs daily for cleanup.
    """
    try:
        now = timezone.now()
        
        # Find transactions pending for more than 24 hours
        stale_transactions = Transaction.objects.filter(
            status='pending',
            created_at__lt=now - timedelta(hours=24)
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
                            'reason': 'timeout_24h'
                        }
                    )
                    
                    failed_count += 1
                    logger.warning(f"Marked stale transaction {transaction.id} as failed")
                    
            except Exception as e:
                logger.error(f"Error marking transaction {transaction.id} as failed: {str(e)}")
        
        if failed_count > 0:
            logger.info(f"Marked {failed_count} stale transactions as failed")
        
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
    Runs daily to provide payment system insights.
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
                'failed': 0
            },
            'withdrawals': {
                'count': 0,
                'total_amount': Decimal('0'),
                'completed': 0,
                'pending': 0,
                'failed': 0
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
        daily_stats['deposits']['pending'] = deposits.filter(status__in=['pending', 'processing']).count()
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
        daily_stats['withdrawals']['pending'] = withdrawals.filter(status__in=['pending', 'processing']).count()
        daily_stats['withdrawals']['failed'] = withdrawals.filter(status='failed').count()
        
        # Log the daily report
        logger.info(f"Daily payment report: {daily_stats}")
        
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
    Runs hourly for fraud detection.
    """
    try:
        now = timezone.now()
        suspicious_count = 0
        
        # Check for multiple deposits from same IP in short time
        recent_transactions = Transaction.objects.filter(
            created_at__gte=now - timedelta(hours=1),
            transaction_type='deposit'
        )
        
        # Check for unusual withdrawal patterns
        large_withdrawals = Transaction.objects.filter(
            transaction_type='withdrawal',
            amount__gte=10000,  # Large withdrawal threshold
            created_at__gte=now - timedelta(hours=24),
            status='pending'
        )
        
        for withdrawal in large_withwithdrawals:
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
        
        if suspicious_count > 0:
            logger.warning(f"Flagged {suspicious_count} suspicious transactions for review")
        
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
            f"{transaction.net_amount} {transaction.currency} credited"
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
            f"{transaction.net_amount} {transaction.currency} sent"
        )
        
        return {'status': 'sent', 'user_email': user.email}
        
    except Transaction.DoesNotExist:
        logger.error(f"Transaction {transaction_id} not found for withdrawal confirmation")
        return {'status': 'failed', 'error': 'Transaction not found'}
    except Exception as e:
        logger.error(f"Error sending withdrawal confirmation for {transaction_id}: {str(e)}")
        return {'status': 'failed', 'error': str(e)}