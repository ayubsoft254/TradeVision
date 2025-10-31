# apps/accounts/signals.py
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.conf import settings
from decimal import Decimal
import logging

from apps.payments.models import Transaction, Wallet
from apps.trading.models import Investment
from .models import Referral, User

logger = logging.getLogger(__name__)

# Referral commission configuration
REFERRAL_COMMISSION_RATE = Decimal('5.0')  # 5% commission on deposits
REFERRAL_MIN_DEPOSIT = Decimal('10.0')  # Minimum deposit to earn commission


@receiver(post_save, sender=User)
def process_pending_referral_on_email_confirmation(sender, instance, created, **kwargs):
    """
    Process pending referral code after user confirms their email.
    This is called whenever a user is saved (including email confirmation).
    """
    # Only process on email confirmation (when user becomes verified and has email_verified_at)
    if created:
        return  # Skip on user creation
    
    # Check if user already has a referral (only process once)
    if hasattr(instance, '_referral_processed'):
        return
    
    # Check if user already has a referral relationship
    if Referral.objects.filter(referred=instance).exists():
        return
    
    try:
        # Try to get pending referral code from any session data
        # Since we can't access session here, we look for it via allauth's email confirmation
        from allauth.account.models import EmailAddress
        
        # Check if email is now confirmed
        email_obj = EmailAddress.objects.filter(user=instance, verified=True).first()
        if not email_obj:
            return
        
        # Check for pending referral in user attributes (if set during signup)
        pending_code = getattr(instance, '_pending_referral_code', None)
        if pending_code:
            from .models import UserReferralCode
            try:
                referrer_code_obj = UserReferralCode.objects.get(referral_code=pending_code)
                referrer = referrer_code_obj.user
                
                if referrer != instance:
                    Referral.objects.create(
                        referrer=referrer,
                        referred=instance,
                        referral_code=pending_code
                    )
                    logger.info(f"Processed referral code {pending_code} for user {instance.email}")
            except UserReferralCode.DoesNotExist:
                logger.warning(f"Invalid referral code {pending_code} for user {instance.email}")
    except Exception as e:
        logger.error(f"Error processing pending referral for user {instance.email}: {e}", exc_info=True)


# Try to connect to allauth's email_confirmed signal if available
try:
    from allauth.account.signals import email_confirmed
    
    @receiver(email_confirmed)
    def handle_referral_on_email_confirmed(sender, request, email_address, **kwargs):
        """
        Process pending referral code after email confirmation.
        This is called when user confirms their email address.
        """
        user = email_address.user
        
        try:
            # Get pending referral code from session
            pending_code = request.session.get('pending_referral_code')
            
            if not pending_code:
                return
            
            # Check if user already has a referral
            if Referral.objects.filter(referred=user).exists():
                return
            
            from .models import UserReferralCode
            try:
                referrer_code_obj = UserReferralCode.objects.get(referral_code=pending_code)
                referrer = referrer_code_obj.user
                
                # Don't allow self-referral
                if referrer != user:
                    Referral.objects.create(
                        referrer=referrer,
                        referred=user,
                        referral_code=pending_code
                    )
                    logger.info(f"Successfully processed referral code {pending_code} for user {user.email}")
                
                # Clear from session
                if 'pending_referral_code' in request.session:
                    del request.session['pending_referral_code']
                    
            except UserReferralCode.DoesNotExist:
                logger.warning(f"Invalid referral code {pending_code} provided during email confirmation")
        
        except Exception as e:
            logger.error(f"Error processing referral on email confirmation: {e}", exc_info=True)

except ImportError:
    logger.debug("allauth email_confirmed signal not available, using fallback method")

@receiver(post_save, sender=Transaction)
def award_referral_commission(sender, instance, created, **kwargs):
    """
    Award referral commission when a referred user makes a successful deposit.
    Commission is calculated as a percentage of the deposit amount.
    """
    # Only process completed deposit transactions
    if not (instance.transaction_type == 'deposit' and instance.status == 'completed'):
        return
    
    # Only process on status change to completed (not on creation as completed)
    if created and instance.status == 'completed':
        # This is a new transaction already completed, proceed
        pass
    elif not created:
        # This is an update, check if it just became completed
        old_instance = Transaction.objects.filter(pk=instance.pk).first()
        if old_instance and old_instance.status == 'completed':
            # Already was completed, don't process again
            return
    else:
        # Created but not completed, skip
        return
    
    try:
        # Check if the depositor was referred by someone
        referral = Referral.objects.filter(
            referred=instance.user,
            is_active=True
        ).exclude(
            referrer=instance.user  # Exclude self-referrals
        ).first()
        
        if not referral:
            logger.info(f"No active referral found for user {instance.user.email}")
            return
        
        # Check minimum deposit amount
        if instance.amount < REFERRAL_MIN_DEPOSIT:
            logger.info(f"Deposit amount {instance.amount} is below minimum {REFERRAL_MIN_DEPOSIT}")
            return
        
        # Calculate commission (percentage of deposit)
        commission_amount = (instance.amount * REFERRAL_COMMISSION_RATE) / Decimal('100')
        commission_amount = commission_amount.quantize(Decimal('0.01'))  # Round to 2 decimal places
        
        # Update referral commission earned
        referral.commission_earned += commission_amount
        referral.save(update_fields=['commission_earned'])
        
        # Get or create wallet for referrer
        referrer_wallet, created = Wallet.objects.get_or_create(
            user=referral.referrer,
            defaults={'currency': instance.currency}
        )
        
        # Add commission to referrer's profit balance
        referrer_wallet.profit_balance += commission_amount
        referrer_wallet.save(update_fields=['profit_balance', 'updated_at'])
        
        # Create a transaction record for the commission
        Transaction.objects.create(
            user=referral.referrer,
            transaction_type='referral',
            amount=commission_amount,
            currency=instance.currency,
            status='completed',
            description=f'Referral commission from {instance.user.email}\'s deposit of {instance.amount} {instance.currency}',
            net_amount=commission_amount,
            metadata={
                'referral_id': str(referral.id),
                'referred_user': instance.user.email,
                'original_transaction_id': str(instance.id),
                'original_amount': str(instance.amount),
                'commission_rate': str(REFERRAL_COMMISSION_RATE)
            }
        )
        
        logger.info(
            f"Awarded referral commission of {commission_amount} {instance.currency} "
            f"to {referral.referrer.email} for referral of {instance.user.email}"
        )
        
    except Exception as e:
        logger.error(f"Error awarding referral commission: {e}", exc_info=True)


@receiver(post_save, sender=Investment)
def award_investment_referral_bonus(sender, instance, created, **kwargs):
    """
    Optional: Award additional bonus when referred user makes their first investment.
    This is separate from deposit commissions and can be used as an extra incentive.
    """
    if not created:
        return
    
    try:
        # Check if this is the user's first investment
        investment_count = Investment.objects.filter(user=instance.user).count()
        if investment_count > 1:
            return  # Not first investment
        
        # Check if the investor was referred by someone
        referral = Referral.objects.filter(
            referred=instance.user,
            is_active=True
        ).exclude(
            referrer=instance.user  # Exclude self-referrals
        ).first()
        
        if not referral:
            return
        
        # Award a small bonus for first investment (e.g., 2% of investment)
        FIRST_INVESTMENT_BONUS_RATE = Decimal('2.0')  # 2% bonus
        bonus_amount = (instance.principal_amount * FIRST_INVESTMENT_BONUS_RATE) / Decimal('100')
        bonus_amount = bonus_amount.quantize(Decimal('0.01'))
        
        # Update referral commission earned
        referral.commission_earned += bonus_amount
        referral.save(update_fields=['commission_earned'])
        
        # Get or create wallet for referrer
        referrer_wallet, created = Wallet.objects.get_or_create(
            user=referral.referrer,
            defaults={'currency': 'USDT'}
        )
        
        # Add bonus to referrer's profit balance
        referrer_wallet.profit_balance += bonus_amount
        referrer_wallet.save(update_fields=['profit_balance', 'updated_at'])
        
        # Create a transaction record for the bonus
        Transaction.objects.create(
            user=referral.referrer,
            transaction_type='referral',
            amount=bonus_amount,
            currency='USDT',
            status='completed',
            description=f'First investment bonus from {instance.user.email}\'s investment of {instance.principal_amount} USDT',
            net_amount=bonus_amount,
            metadata={
                'referral_id': str(referral.id),
                'referred_user': instance.user.email,
                'investment_id': str(instance.id),
                'investment_amount': str(instance.principal_amount),
                'bonus_rate': str(FIRST_INVESTMENT_BONUS_RATE),
                'bonus_type': 'first_investment'
            }
        )
        
        logger.info(
            f"Awarded first investment bonus of {bonus_amount} USDT "
            f"to {referral.referrer.email} for referral of {instance.user.email}"
        )
        
    except Exception as e:
        logger.error(f"Error awarding investment referral bonus: {e}", exc_info=True)


@receiver(pre_save, sender=Transaction)
def track_transaction_status_change(sender, instance, **kwargs):
    """
    Track transaction status changes before save.
    This captures the old status so we can compare it in post_save.
    """
    if instance.pk:
        try:
            old_instance = Transaction.objects.get(pk=instance.pk)
            instance._old_status = old_instance.status
        except Transaction.DoesNotExist:
            instance._old_status = None
    else:
        instance._old_status = None


@receiver(post_save, sender=Transaction)
def handle_cancelled_transaction_refund(sender, instance, created, **kwargs):
    """
    Refund money to user's wallet when a transaction is cancelled or failed.
    
    For withdrawals:
    - If cancelled/failed, refund the amount back to profit_balance
    - The money was deducted when the withdrawal was requested
    
    For deposits:
    - No refund needed as money was never added
    """
    # Skip if this is a new transaction
    if created:
        return
    
    # Check if status changed to cancelled or failed
    old_status = getattr(instance, '_old_status', None)
    new_status = instance.status
    
    # Only process if status changed to cancelled or failed
    if old_status == new_status:
        return
    
    if new_status not in ['cancelled', 'failed']:
        return
    
    # Only refund for withdrawals (deposits never took money)
    if instance.transaction_type != 'withdrawal':
        return
    
    # Check if already refunded (prevent double refunds)
    refund_metadata = instance.metadata or {}
    if refund_metadata.get('refunded'):
        logger.info(f"Transaction {instance.id} already refunded, skipping")
        return
    
    try:
        # Get user wallet
        wallet = Wallet.objects.get(user=instance.user)
        
        # Refund the amount back to profit balance
        refund_amount = instance.amount
        wallet.profit_balance += refund_amount
        wallet.save(update_fields=['profit_balance', 'updated_at'])
        
        # Mark profits as not withdrawn
        from apps.trading.models import ProfitHistory
        withdrawn_profits = ProfitHistory.objects.filter(
            user=instance.user,
            is_withdrawn=True
        ).order_by('-date_earned')
        
        remaining_amount = refund_amount
        for profit in withdrawn_profits:
            if remaining_amount <= 0:
                break
            if profit.amount <= remaining_amount:
                profit.is_withdrawn = False
                profit.save(update_fields=['is_withdrawn'])
                remaining_amount -= profit.amount
        
        # Update metadata to mark as refunded
        if not instance.metadata:
            instance.metadata = {}
        instance.metadata['refunded'] = True
        instance.metadata['refund_amount'] = str(refund_amount)
        instance.metadata['refund_reason'] = f'Transaction {new_status}'
        instance.metadata['original_status'] = old_status
        
        # Save without triggering signals again
        Transaction.objects.filter(pk=instance.pk).update(metadata=instance.metadata)
        
        logger.info(
            f"Refunded {refund_amount} {instance.currency} to {instance.user.email} "
            f"for {new_status} withdrawal transaction {instance.id}"
        )
        
        # Create a transaction record for the refund
        Transaction.objects.create(
            user=instance.user,
            transaction_type='bonus',  # Using 'bonus' type for refunds
            amount=refund_amount,
            currency=instance.currency,
            status='completed',
            description=f'Refund for {new_status} withdrawal (Transaction #{instance.id})',
            net_amount=refund_amount,
            metadata={
                'refund_for_transaction': str(instance.id),
                'refund_reason': f'Withdrawal {new_status}',
                'original_amount': str(instance.amount),
                'is_refund': True
            }
        )
        
    except Wallet.DoesNotExist:
        logger.error(f"Wallet not found for user {instance.user.email}, cannot refund transaction {instance.id}")
    except Exception as e:
        logger.error(f"Error refunding cancelled/failed transaction {instance.id}: {e}", exc_info=True)
