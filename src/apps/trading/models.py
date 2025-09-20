# apps/trading/models.py
from django.db import models
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
import uuid
import random
from decimal import Decimal

class TradingPackage(models.Model):
    """Trading package configuration"""
    PACKAGE_TYPES = [
        ('basic', 'Basic Package'),
        ('standard', 'Standard Package'),
        ('premium', 'Premium Package'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=50, choices=PACKAGE_TYPES, unique=True)
    display_name = models.CharField(max_length=100)
    min_stake = models.DecimalField(max_digits=12, decimal_places=2)
    profit_min = models.DecimalField(max_digits=5, decimal_places=2)  # Minimum daily profit %
    profit_max = models.DecimalField(max_digits=5, decimal_places=2)  # Maximum daily profit %
    welcome_bonus = models.DecimalField(max_digits=5, decimal_places=2)  # Welcome bonus %
    duration_days = models.IntegerField(default=365)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.display_name
    
    def get_random_profit_rate(self):
        """Generate a random profit rate between min and max"""
        min_rate = float(self.profit_min)
        max_rate = float(self.profit_max)
        return Decimal(str(round(random.uniform(min_rate, max_rate), 2)))
    
    @staticmethod
    def is_weekend_trading_enabled():
        """Check if weekend trading is enabled in site configuration"""
        from apps.core.models import SiteConfiguration
        try:
            site_config = SiteConfiguration.objects.first()
            return site_config.weekend_trading_enabled if site_config else False
        except:
            return False

class Investment(models.Model):
    """User investment in a trading package"""
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='investments')
    package = models.ForeignKey(TradingPackage, on_delete=models.CASCADE)
    principal_amount = models.DecimalField(max_digits=12, decimal_places=2)
    welcome_bonus_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_profits = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    start_date = models.DateTimeField(auto_now_add=True)
    maturity_date = models.DateTimeField()
    is_principal_withdrawable = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def save(self, *args, **kwargs):
        # Auto-calculate maturity_date if not set
        if not self.maturity_date and self.package:
            self.maturity_date = timezone.now() + timedelta(days=self.package.duration_days)
        
        # Auto-calculate welcome bonus if not set
        if not self.welcome_bonus_amount and self.package and self.principal_amount:
            self.welcome_bonus_amount = self.principal_amount * (self.package.welcome_bonus / 100)
        
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.user.email} - {self.package.display_name}"
    
    @property
    def total_investment(self):
        return self.principal_amount + self.welcome_bonus_amount
    
    @property
    def is_mature(self):
        return timezone.now() >= self.maturity_date
    
    @property
    def days_remaining(self):
        if self.is_mature:
            return 0
        return (self.maturity_date - timezone.now()).days

class Trade(models.Model):
    """Individual trading session"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    investment = models.ForeignKey(Investment, on_delete=models.CASCADE, related_name='trades')
    trade_amount = models.DecimalField(max_digits=12, decimal_places=2)
    profit_rate = models.DecimalField(max_digits=5, decimal_places=2)  # Daily profit rate used
    profit_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    completed_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def save(self, *args, **kwargs):
        if not self.end_time:
            self.end_time = self.start_time + timedelta(hours=24)
        
        if not self.profit_amount and self.profit_rate:
            # Ensure all operations use Decimal type
            from decimal import Decimal
            self.profit_amount = self.trade_amount * (self.profit_rate / Decimal('100'))
    
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"Trade {self.id} - {self.investment.user.email}"
    
    @property
    def is_ready_for_completion(self):
        """Check if 24 hours have passed and trading is allowed"""
        if timezone.now() < self.end_time:
            return False
        
        # Check site configuration for weekend trading
        from apps.core.models import SiteConfiguration
        try:
            site_config = SiteConfiguration.objects.first()
            weekend_trading_enabled = site_config.weekend_trading_enabled if site_config else False
        except:
            weekend_trading_enabled = False
        
        # If weekend trading is disabled, check if it's a weekday
        if not weekend_trading_enabled:
            current_weekday = timezone.now().weekday()
            if current_weekday >= 5:  # Saturday=5, Sunday=6
                return False
        
        return True
    
    @property
    def time_remaining(self):
        """Get remaining time for trade completion"""
        if self.status == 'completed':
            return timedelta(0)
        
        remaining = self.end_time - timezone.now()
        return remaining if remaining.total_seconds() > 0 else timedelta(0)

class ProfitHistory(models.Model):
    """Track all profit distributions"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profit_history')
    investment = models.ForeignKey(Investment, on_delete=models.CASCADE, related_name='profit_distributions')
    trade = models.OneToOneField(Trade, on_delete=models.CASCADE, related_name='profit_record')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    profit_rate = models.DecimalField(max_digits=5, decimal_places=2)
    date_earned = models.DateTimeField(auto_now_add=True)
    is_withdrawn = models.BooleanField(default=False)
    
    def __str__(self):
        return f"Profit: {self.amount} - {self.user.email}"
    
    class Meta:
        ordering = ['-date_earned']
        verbose_name_plural = "Profit histories"