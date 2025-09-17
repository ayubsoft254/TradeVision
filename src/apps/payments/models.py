# apps/payments/models.py
from django.db import models
from django.conf import settings
from django.utils import timezone
import uuid

class PaymentMethod(models.Model):
    """Available payment methods by country"""
    METHOD_TYPES = [
        ('binance_pay', 'Binance Pay'),
        ('p2p', 'P2P Trading'),
        ('agent', 'Local Agent'),
        ('mobile_money', 'Mobile Money'),
        ('bank_transfer', 'Bank Transfer'),
        ('crypto', 'Cryptocurrency'),
    ]
    
    COUNTRY_CHOICES = [
        ('ZM', 'Zambia'),
        ('CD', 'Democratic Republic of Congo (DRC)'),
        ('TZ', 'Tanzania'),
        ('KE', 'Kenya'),
        ('UG', 'Uganda'),
        # Additional countries can be added here
    ]
    
    name = models.CharField(max_length=50, choices=METHOD_TYPES)
    display_name = models.CharField(max_length=100)
    countries = models.JSONField(default=list, help_text="List of country codes (e.g., ['ZM', 'KE', 'UG'])")  # List of country codes
    is_active = models.BooleanField(default=True)
    min_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    max_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    processing_fee = models.DecimalField(max_digits=5, decimal_places=2, default=0)  # Percentage
    processing_time = models.CharField(max_length=50, default="Instant")  # e.g., "Instant", "1-3 hours"
    
    def __str__(self):
        return self.display_name
    
    def is_available_for_country(self, country_code):
        return country_code in self.countries

class Wallet(models.Model):
    """User wallet for managing funds"""
    
    CURRENCY_CHOICES = [
        ('USDT', 'USDT (Tether) - Primary'),
        ('BUSD', 'BUSD (Binance USD)'),
        ('BTC', 'Bitcoin'),
        ('ETH', 'Ethereum'),
        ('BNB', 'Binance Coin'),
        ('USDC', 'USD Coin'),
        ('DAI', 'Dai Stablecoin'),
        ('KSH', 'Kenyan Shilling (Legacy)'),
        ('UGX', 'Ugandan Shilling (Legacy)'),
        ('TZS', 'Tanzanian Shilling (Legacy)'),
    ]
    
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='wallet')
    balance = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    profit_balance = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    locked_balance = models.DecimalField(max_digits=15, decimal_places=2, default=0)  # Invested amounts
    currency = models.CharField(max_length=10, choices=CURRENCY_CHOICES, default='USDT')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.user.email} - Wallet ({self.currency})"
    
    @property
    def total_balance(self):
        return self.balance + self.profit_balance
    
    @property
    def withdrawable_balance(self):
        return self.profit_balance  # Only profits are withdrawable before maturity

class Transaction(models.Model):
    """All financial transactions"""
    TRANSACTION_TYPES = [
        ('deposit', 'Deposit'),
        ('withdrawal', 'Withdrawal'),
        ('investment', 'Investment'),
        ('profit', 'Profit'),
        ('bonus', 'Welcome Bonus'),
        ('referral', 'Referral Commission'),
        ('fee', 'Processing Fee'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]
    
    CURRENCY_CHOICES = [
        ('USDT', 'USDT (Tether) - Primary'),
        ('BUSD', 'BUSD (Binance USD)'),
        ('BTC', 'Bitcoin'),
        ('ETH', 'Ethereum'),
        ('BNB', 'Binance Coin'),
        ('USDC', 'USD Coin'),
        ('DAI', 'Dai Stablecoin'),
        ('KSH', 'Kenyan Shilling (Legacy)'),
        ('UGX', 'Ugandan Shilling (Legacy)'),
        ('TZS', 'Tanzanian Shilling (Legacy)'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='transactions')
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    currency = models.CharField(max_length=10, choices=CURRENCY_CHOICES, default='USDT')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Payment method details
    payment_method = models.ForeignKey(PaymentMethod, on_delete=models.SET_NULL, null=True, blank=True)
    external_reference = models.CharField(max_length=100, blank=True)  # External transaction ID
    
    # Additional details
    description = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    
    # Fee information
    processing_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    net_amount = models.DecimalField(max_digits=15, decimal_places=2)  # Amount after fees
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    def save(self, *args, **kwargs):
        if not self.net_amount:
            self.net_amount = self.amount - self.processing_fee
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.transaction_type.title()}: {self.amount} {self.currency} - {self.user.email}"
    
    class Meta:
        ordering = ['-created_at']

class DepositRequest(models.Model):
    """Deposit requests with proof of payment"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    transaction = models.OneToOneField(Transaction, on_delete=models.CASCADE, related_name='deposit_request')
    payment_proof = models.ImageField(upload_to='payment_proofs/', blank=True, null=True)
    payment_details = models.JSONField(default=dict)  # Store payment method specific details
    admin_notes = models.TextField(blank=True)
    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='processed_deposits'
    )
    processed_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"Deposit Request: {self.transaction.amount} - {self.transaction.user.email}"

class WithdrawalRequest(models.Model):
    """Withdrawal requests"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    transaction = models.OneToOneField(Transaction, on_delete=models.CASCADE, related_name='withdrawal_request')
    withdrawal_address = models.JSONField(default=dict)  # Store withdrawal destination details
    otp_verified = models.BooleanField(default=False)
    admin_notes = models.TextField(blank=True)
    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='processed_withdrawals'
    )
    processed_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"Withdrawal Request: {self.transaction.amount} - {self.transaction.user.email}"

class Agent(models.Model):
    """Local agents for cash transactions"""
    
    COUNTRY_CHOICES = [
        ('ZM', 'Zambia'),
        ('CD', 'Democratic Republic of Congo (DRC)'),
        ('TZ', 'Tanzania'),
        ('KE', 'Kenya'),
        ('UG', 'Uganda'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    phone_number = models.CharField(max_length=20)
    email = models.EmailField()
    country = models.CharField(max_length=2, choices=COUNTRY_CHOICES)
    city = models.CharField(max_length=100)
    address = models.TextField()
    is_verified = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2, default=2.0)  # Percentage
    max_transaction_amount = models.DecimalField(max_digits=12, decimal_places=2)
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    total_transactions = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.name} - {self.city}, {self.country}"

class P2PMerchant(models.Model):
    """P2P trading merchants"""
    
    COUNTRY_CHOICES = [
        ('ZM', 'Zambia'),
        ('CD', 'Democratic Republic of Congo (DRC)'),
        ('TZ', 'Tanzania'),
        ('KE', 'Kenya'),
        ('UG', 'Uganda'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    username = models.CharField(max_length=50, unique=True)
    phone_number = models.CharField(max_length=20)
    email = models.EmailField()
    country = models.CharField(max_length=2, choices=COUNTRY_CHOICES)
    supported_methods = models.JSONField(default=list)  # e.g., ['mobile_money', 'bank_transfer']
    is_verified = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2, default=1.5)
    min_order_amount = models.DecimalField(max_digits=12, decimal_places=2)
    max_order_amount = models.DecimalField(max_digits=12, decimal_places=2)
    completion_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    total_orders = models.IntegerField(default=0)
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.name} (@{self.username})"