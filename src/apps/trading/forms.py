# apps/trading/forms.py
from django import forms
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from decimal import Decimal
from .models import Investment, Trade, TradingPackage

User = get_user_model()

class InvestmentForm(forms.ModelForm):
    """Form for creating new investments"""
    
    class Meta:
        model = Investment
        fields = ['principal_amount']
        widgets = {
            'principal_amount': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500',
                'placeholder': 'Enter investment amount',
                'min': '0',
                'step': '0.01',
                'id': 'investment-amount'
            })
        }
        labels = {
            'principal_amount': 'Investment Amount'
        }
    
    def __init__(self, *args, **kwargs):
        self.package = kwargs.pop('package', None)
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        if self.package:
            self.fields['principal_amount'].widget.attrs.update({
                'min': str(self.package.min_stake),
                'data-package-id': str(self.package.id),
                'data-min-stake': str(self.package.min_stake),
                'data-welcome-bonus': str(self.package.welcome_bonus),
                'data-profit-min': str(self.package.profit_min),
                'data-profit-max': str(self.package.profit_max),
            })
            
            self.fields['principal_amount'].help_text = (
                f'Minimum investment: {self.package.min_stake} '
                f'{self.user.wallet.currency if self.user and hasattr(self.user, "wallet") else "KSH"}'
            )
    
    def clean_principal_amount(self):
        amount = self.cleaned_data['principal_amount']
        
        if amount <= 0:
            raise ValidationError('Investment amount must be greater than zero.')
        
        # Check minimum stake for package
        if self.package and amount < self.package.min_stake:
            raise ValidationError(
                f'Minimum investment for {self.package.display_name} is {self.package.min_stake}.'
            )
        
        # Check maximum reasonable investment (optional business rule)
        max_investment = Decimal('1000000')  # 1 million
        if amount > max_investment:
            raise ValidationError(f'Maximum investment amount is {max_investment}.')
        
        # Check user wallet balance
        if self.user and hasattr(self.user, 'wallet'):
            if amount > self.user.wallet.balance:
                raise ValidationError(
                    f'Insufficient wallet balance. Available: {self.user.wallet.balance} '
                    f'{self.user.wallet.currency}'
                )
        
        return amount

class TradeInitiationForm(forms.Form):
    """Form for initiating trades"""
    
    investment = forms.ModelChoiceField(
        queryset=Investment.objects.none(),
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500'
        }),
        label='Select Investment',
        help_text='Choose an investment to start trading with'
    )
    
    confirm_trade = forms.BooleanField(
        required=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'h-4 w-4 text-primary-600 focus:ring-primary-500 border-gray-300 rounded'
        }),
        label='I confirm I want to initiate this trade',
        help_text='By checking this box, you confirm that you want to start a 24-hour trading cycle'
    )
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        if self.user:
            # Get investments that don't have active trades
            available_investments = Investment.objects.filter(
                user=self.user,
                status='active'
            ).exclude(
                trades__status__in=['pending', 'running']
            ).select_related('package')
            
            self.fields['investment'].queryset = available_investments
            
            # Custom display for investment choices
            choices = []
            for investment in available_investments:
                choice_text = (
                    f'{investment.package.display_name} - '
                    f'{investment.total_investment} {self.user.wallet.currency} '
                    f'(Profit: {investment.package.profit_min}-{investment.package.profit_max}%)'
                )
                choices.append((investment.id, choice_text))
            
            self.fields['investment'].choices = [('', 'Select an investment')] + choices
    
    def clean_investment(self):
        investment = self.cleaned_data.get('investment')
        
        if not investment:
            raise ValidationError('Please select an investment.')
        
        # Check if investment belongs to user
        if investment.user != self.user:
            raise ValidationError('Invalid investment selected.')
        
        # Check if investment is active
        if investment.status != 'active':
            raise ValidationError('Selected investment is not active.')
        
        # Check if there's already an active trade
        active_trade = Trade.objects.filter(
            investment=investment,
            status__in=['pending', 'running']
        ).exists()
        
        if active_trade:
            raise ValidationError('This investment already has an active trade.')
        
        return investment

class PackageCalculatorForm(forms.Form):
    """Form for package profit calculations"""
    
    package = forms.ModelChoiceField(
        queryset=TradingPackage.objects.filter(is_active=True),
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500'
        }),
        label='Trading Package'
    )
    
    investment_amount = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500',
            'placeholder': 'Enter amount to calculate',
            'min': '0',
            'step': '0.01'
        }),
        label='Investment Amount'
    )
    
    def clean(self):
        cleaned_data = super().clean()
        package = cleaned_data.get('package')
        amount = cleaned_data.get('investment_amount')
        
        if package and amount:
            if amount < package.min_stake:
                raise ValidationError(
                    f'Minimum investment for {package.display_name} is {package.min_stake}'
                )
        
        return cleaned_data

class InvestmentFilterForm(forms.Form):
    """Form for filtering investments"""
    
    STATUS_CHOICES = [
        ('', 'All Statuses'),
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    PACKAGE_CHOICES = [
        ('', 'All Packages'),
        ('basic', 'Basic Package'),
        ('standard', 'Standard Package'),
        ('premium', 'Premium Package'),
    ]
    
    status = forms.ChoiceField(
        choices=STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-primary-500 focus:border-primary-500'
        })
    )
    
    package = forms.ChoiceField(
        choices=PACKAGE_CHOICES,
        required=False,
        widget=forms.Select(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-primary-500 focus:border-primary-500'
        })
    )
    
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-primary-500 focus:border-primary-500',
            'type': 'date'
        })
    )
    
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-primary-500 focus:border-primary-500',
            'type': 'date'
        })
    )

class TradeFilterForm(forms.Form):
    """Form for filtering trades"""
    
    STATUS_CHOICES = [
        ('', 'All Statuses'),
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    status = forms.ChoiceField(
        choices=STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-primary-500 focus:border-primary-500'
        })
    )
    
    package = forms.ModelChoiceField(
        queryset=TradingPackage.objects.filter(is_active=True),
        required=False,
        empty_label='All Packages',
        widget=forms.Select(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-primary-500 focus:border-primary-500'
        })
    )
    
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-primary-500 focus:border-primary-500',
            'type': 'date'
        }),
        label='From Date'
    )
    
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-primary-500 focus:border-primary-500',
            'type': 'date'
        }),
        label='To Date'
    )
    
    def clean(self):
        cleaned_data = super().clean()
        date_from = cleaned_data.get('date_from')
        date_to = cleaned_data.get('date_to')
        
        if date_from and date_to and date_from > date_to:
            raise ValidationError('Start date cannot be after end date.')
        
        return cleaned_data

class ProfitHistoryFilterForm(forms.Form):
    """Form for filtering profit history"""
    
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-primary-500 focus:border-primary-500',
            'type': 'date'
        }),
        label='From Date'
    )
    
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-primary-500 focus:border-primary-500',
            'type': 'date'
        }),
        label='To Date'
    )
    
    package = forms.ModelChoiceField(
        queryset=TradingPackage.objects.filter(is_active=True),
        required=False,
        empty_label='All Packages',
        widget=forms.Select(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-primary-500 focus:border-primary-500'
        })
    )
    
    min_amount = forms.DecimalField(
        required=False,
        max_digits=10,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-primary-500 focus:border-primary-500',
            'placeholder': 'Minimum profit amount',
            'step': '0.01'
        }),
        label='Minimum Profit'
    )
    
    def clean(self):
        cleaned_data = super().clean()
        date_from = cleaned_data.get('date_from')
        date_to = cleaned_data.get('date_to')
        min_amount = cleaned_data.get('min_amount')
        
        if date_from and date_to and date_from > date_to:
            raise ValidationError('Start date cannot be after end date.')
        
        if min_amount and min_amount < 0:
            raise ValidationError('Minimum amount cannot be negative.')
        
        return cleaned_data

class QuickInvestForm(forms.Form):
    """Quick investment form for dashboard"""
    
    package = forms.ModelChoiceField(
        queryset=TradingPackage.objects.filter(is_active=True),
        widget=forms.Select(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-primary-500 focus:border-primary-500'
        }),
        empty_label='Select Package'
    )
    
    amount = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-primary-500 focus:border-primary-500',
            'placeholder': 'Investment amount',
            'min': '0',
            'step': '0.01'
        })
    )
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
    
    def clean(self):
        cleaned_data = super().clean()
        package = cleaned_data.get('package')
        amount = cleaned_data.get('amount')
        
        if package and amount:
            # Check minimum stake
            if amount < package.min_stake:
                raise ValidationError(
                    f'Minimum investment for {package.display_name} is {package.min_stake}'
                )
            
            # Check wallet balance
            if self.user and hasattr(self.user, 'wallet'):
                if amount > self.user.wallet.balance:
                    raise ValidationError('Insufficient wallet balance.')
        
        return cleaned_data

class WithdrawProfitForm(forms.Form):
    """Form for withdrawing profits"""
    
    amount = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500',
            'placeholder': 'Enter withdrawal amount',
            'min': '0',
            'step': '0.01'
        }),
        label='Withdrawal Amount'
    )
    
    withdrawal_method = forms.ChoiceField(
        choices=[
            ('', 'Select withdrawal method'),
            ('binance_pay', 'Binance Pay'),
            ('p2p', 'P2P Trading'),
            ('agent', 'Local Agent'),
            ('bank_transfer', 'Bank Transfer'),
        ],
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500'
        }),
        label='Withdrawal Method'
    )
    
    confirm_withdrawal = forms.BooleanField(
        required=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'h-4 w-4 text-primary-600 focus:ring-primary-500 border-gray-300 rounded'
        }),
        label='I confirm this withdrawal request'
    )
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        if self.user and hasattr(self.user, 'wallet'):
            self.fields['amount'].help_text = (
                f'Available for withdrawal: {self.user.wallet.profit_balance} '
                f'{self.user.wallet.currency}'
            )
    
    def clean_amount(self):
        amount = self.cleaned_data['amount']
        
        if amount <= 0:
            raise ValidationError('Withdrawal amount must be greater than zero.')
        
        # Check minimum withdrawal amount
        min_withdrawal = Decimal('100')  # Business rule
        if amount < min_withdrawal:
            raise ValidationError(f'Minimum withdrawal amount is {min_withdrawal}.')
        
        # Check available profit balance
        if self.user and hasattr(self.user, 'wallet'):
            if amount > self.user.wallet.profit_balance:
                raise ValidationError(
                    f'Insufficient profit balance. Available: {self.user.wallet.profit_balance} '
                    f'{self.user.wallet.currency}'
                )
        
        return amount

class ReinvestProfitForm(forms.Form):
    """Form for reinvesting profits"""
    
    package = forms.ModelChoiceField(
        queryset=TradingPackage.objects.filter(is_active=True),
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500'
        }),
        label='Select Package for Reinvestment'
    )
    
    amount = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500',
            'placeholder': 'Enter reinvestment amount',
            'min': '0',
            'step': '0.01'
        }),
        label='Reinvestment Amount'
    )
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        if self.user and hasattr(self.user, 'wallet'):
            max_amount = self.user.wallet.profit_balance
            self.fields['amount'].help_text = (
                f'Available profits: {max_amount} {self.user.wallet.currency}'
            )
            self.fields['amount'].widget.attrs['max'] = str(max_amount)
    
    def clean(self):
        cleaned_data = super().clean()
        package = cleaned_data.get('package')
        amount = cleaned_data.get('amount')
        
        if package and amount:
            # Check minimum stake
            if amount < package.min_stake:
                raise ValidationError(
                    f'Minimum investment for {package.display_name} is {package.min_stake}'
                )
            
            # Check available profit balance
            if self.user and hasattr(self.user, 'wallet'):
                if amount > self.user.wallet.profit_balance:
                    raise ValidationError('Insufficient profit balance for reinvestment.')
        
        return cleaned_data