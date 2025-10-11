# apps/accounts/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
from decimal import Decimal
import logging

from apps.payments.models import Transaction, Wallet
from apps.trading.models import Investment
from .models import Referral

logger = logging.getLogger(__name__)

# Referral commission configuration
REFERRAL_COMMISSION_RATE = Decimal('5.0')  # 5% commission on deposits
REFERRAL_MIN_DEPOSIT = Decimal('10.0')  # Minimum deposit to earn commission


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
