# apps/payments/forms.py
from django import forms
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from decimal import Decimal
import re

from .models import Transaction, DepositRequest, WithdrawalRequest, Agent, P2PMerchant

User = get_user_model()

class BasePaymentForm(forms.Form):
    """Base form for payment operations"""
    
    amount = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500',
            'placeholder': 'Enter amount',
            'min': '0',
            'step': '0.01'
        }),
        label='Amount'
    )
    
    def clean_amount(self):
        amount = self.cleaned_data['amount']
        
        if amount <= 0:
            raise ValidationError('Amount must be greater than zero.')
        
        # Check minimum transaction amount
        min_amount = Decimal('10')  # Business rule
        if amount < min_amount:
            raise ValidationError(f'Minimum transaction amount is {min_amount}.')
        
        # Check maximum transaction amount
        max_amount = Decimal('100000')  # Business rule
        if amount > max_amount:
            raise ValidationError(f'Maximum transaction amount is {max_amount}.')
        
        return amount

class DepositForm(BasePaymentForm):
    """Generic deposit form"""
    
    payment_proof = forms.ImageField(
        required=False,
        widget=forms.FileInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500',
            'accept': 'image/*'
        }),
        label='Payment Proof (Optional)',
        help_text='Upload a screenshot or photo of your payment confirmation'
    )
    
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500',
            'rows': 3,
            'placeholder': 'Additional notes or transaction reference (optional)'
        }),
        label='Notes',
        max_length=500
    )
    
    def clean_payment_proof(self):
        payment_proof = self.cleaned_data.get('payment_proof')
        
        if payment_proof:
            # Check file size (max 5MB)
            if payment_proof.size > 5 * 1024 * 1024:
                raise ValidationError('File size must be less than 5MB.')
            
            # Check file type
            allowed_types = ['image/jpeg', 'image/png', 'image/jpg', 'image/gif']
            if payment_proof.content_type not in allowed_types:
                raise ValidationError('Only JPEG, PNG, and GIF images are allowed.')
        
        return payment_proof

class WithdrawalForm(BasePaymentForm):
    """Generic withdrawal form"""
    
    withdrawal_address = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500',
            'placeholder': 'Enter your withdrawal address/account'
        }),
        label='Withdrawal Address/Account',
        help_text='Enter the account number, wallet address, or phone number where you want to receive funds'
    )
    
    confirm_withdrawal = forms.BooleanField(
        required=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'h-4 w-4 text-primary-600 focus:ring-primary-500 border-gray-300 rounded'
        }),
        label='I confirm this withdrawal request and understand that processing fees may apply'
    )
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        if self.user and hasattr(self.user, 'wallet'):
            max_amount = self.user.wallet.profit_balance
            self.fields['amount'].help_text = f'Available for withdrawal: {max_amount} {self.user.wallet.currency}'
            self.fields['amount'].widget.attrs['max'] = str(max_amount)
    
    def clean_amount(self):
        amount = super().clean_amount()
        
        # Check available balance for withdrawal
        if self.user and hasattr(self.user, 'wallet'):
            if amount > self.user.wallet.profit_balance:
                raise ValidationError(
                    f'Insufficient profit balance. Available: {self.user.wallet.profit_balance} {self.user.wallet.currency}'
                )
        
        return amount

class BinancePayForm(BasePaymentForm):
    """Binance Pay specific form"""
    
    binance_id = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500',
            'placeholder': 'Enter your Binance ID or email'
        }),
        label='Binance ID/Email',
        help_text='Your Binance account ID or registered email address'
    )
    
    transaction_reference = forms.CharField(
        required=False,
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500',
            'placeholder': 'Transaction reference (optional)'
        }),
        label='Transaction Reference',
        help_text='Binance transaction ID or reference number if available'
    )
    
    def __init__(self, *args, **kwargs):
        self.transaction_type = kwargs.pop('transaction_type', 'deposit')
        super().__init__(*args, **kwargs)
        
        if self.transaction_type == 'withdrawal':
            self.fields['binance_id'].label = 'Recipient Binance ID/Email'
            self.fields['binance_id'].help_text = 'Binance account where you want to receive funds'
    
    def clean_binance_id(self):
        binance_id = self.cleaned_data['binance_id']
        
        # Basic email validation if it looks like an email
        if '@' in binance_id:
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_pattern, binance_id):
                raise ValidationError('Please enter a valid email address.')
        else:
            # Validate Binance ID format (alphanumeric, 8-50 characters)
            if not re.match(r'^[a-zA-Z0-9]{8,50}$', binance_id):
                raise ValidationError('Binance ID should be 8-50 alphanumeric characters.')
        
        return binance_id

class P2PForm(BasePaymentForm):
    """P2P trading form"""
    
    merchant = forms.ModelChoiceField(
        queryset=P2PMerchant.objects.none(),
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500'
        }),
        label='Select Merchant',
        help_text='Choose a verified P2P merchant'
    )
    
    payment_method = forms.ChoiceField(
        choices=[
            ('mobile_money', 'Mobile Money'),
            ('bank_transfer', 'Bank Transfer'),
            ('cash', 'Cash'),
        ],
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500'
        }),
        label='Payment Method'
    )
    
    account_details = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500',
            'placeholder': 'Your account number/phone number'
        }),
        label='Account Details',
        help_text='Your mobile money number, bank account, or contact details'
    )
    
    def __init__(self, *args, **kwargs):
        self.transaction_type = kwargs.pop('transaction_type', 'deposit')
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        if self.user:
            # Filter merchants by user's country
            self.fields['merchant'].queryset = P2PMerchant.objects.filter(
                is_active=True,
                is_verified=True,
                country=self.user.country.code
            ).order_by('-rating')
        
        if self.transaction_type == 'withdrawal':
            self.fields['account_details'].label = 'Recipient Account Details'
            self.fields['account_details'].help_text = 'Account where you want to receive funds'
    
    def clean_account_details(self):
        account_details = self.cleaned_data['account_details']
        payment_method = self.cleaned_data.get('payment_method')
        
        if payment_method == 'mobile_money':
            # Validate mobile money format (basic validation)
            if not re.match(r'^\+?[0-9]{10,15}$', account_details.replace(' ', '')):
                raise ValidationError('Please enter a valid mobile money number with country code.')
        
        elif payment_method == 'bank_transfer':
            # Basic bank account validation
            if len(account_details.replace(' ', '')) < 8:
                raise ValidationError('Bank account number should be at least 8 digits.')
        
        return account_details

class AgentTransactionForm(BasePaymentForm):
    """Agent transaction form"""
    
    agent = forms.ModelChoiceField(
        queryset=Agent.objects.none(),
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500'
        }),
        label='Select Agent',
        help_text='Choose a verified local agent'
    )
    
    contact_method = forms.ChoiceField(
        choices=[
            ('phone', 'Phone Call'),
            ('sms', 'SMS'),
            ('whatsapp', 'WhatsApp'),
            ('telegram', 'Telegram'),
        ],
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500'
        }),
        label='Preferred Contact Method'
    )
    
    location_details = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500',
            'placeholder': 'Meeting location or additional details'
        }),
        label='Location/Contact Details',
        help_text='Specify meeting location or additional contact information'
    )
    
    def __init__(self, *args, **kwargs):
        self.transaction_type = kwargs.pop('transaction_type', 'deposit')
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        if self.user:
            # Filter agents by user's country
            self.fields['agent'].queryset = Agent.objects.filter(
                is_active=True,
                is_verified=True,
                country=self.user.country.code
            ).order_by('-rating')

class TransactionFilterForm(forms.Form):
    """Form for filtering transactions"""
    
    TRANSACTION_TYPES = [
        ('', 'All Types'),
        ('deposit', 'Deposits'),
        ('withdrawal', 'Withdrawals'),
        ('investment', 'Investments'),
        ('profit', 'Profits'),
        ('bonus', 'Bonuses'),
        ('fee', 'Fees'),
    ]
    
    STATUS_CHOICES = [
        ('', 'All Statuses'),
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]
    
    transaction_type = forms.ChoiceField(
        choices=TRANSACTION_TYPES,
        required=False,
        widget=forms.Select(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-primary-500 focus:border-primary-500'
        })
    )
    
    status = forms.ChoiceField(
        choices=STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-primary-500 focus:border-primary-500'
        })
    )
    
    start_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-primary-500 focus:border-primary-500',
            'type': 'date'
        }),
        label='From Date'
    )
    
    end_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-primary-500 focus:border-primary-500',
            'type': 'date'
        }),
        label='To Date'
    )
    
    min_amount = forms.DecimalField(
        required=False,
        max_digits=12,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-primary-500 focus:border-primary-500',
            'placeholder': 'Minimum amount',
            'step': '0.01'
        }),
        label='Min Amount'
    )
    
    max_amount = forms.DecimalField(
        required=False,
        max_digits=12,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-primary-500 focus:border-primary-500',
            'placeholder': 'Maximum amount',
            'step': '0.01'
        }),
        label='Max Amount'
    )
    
    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        min_amount = cleaned_data.get('min_amount')
        max_amount = cleaned_data.get('max_amount')
        
        if start_date and end_date and start_date > end_date:
            raise ValidationError('Start date cannot be after end date.')
        
        if min_amount and max_amount and min_amount > max_amount:
            raise ValidationError('Minimum amount cannot be greater than maximum amount.')
        
        return cleaned_data

class BankTransferForm(BasePaymentForm):
    """Bank transfer specific form"""
    
    bank_name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500',
            'placeholder': 'Enter bank name'
        }),
        label='Bank Name'
    )
    
    account_number = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500',
            'placeholder': 'Enter account number'
        }),
        label='Account Number'
    )
    
    account_name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500',
            'placeholder': 'Enter account holder name'
        }),
        label='Account Holder Name'
    )
    
    swift_code = forms.CharField(
        required=False,
        max_length=20,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500',
            'placeholder': 'SWIFT/BIC code (if international)'
        }),
        label='SWIFT/BIC Code',
        help_text='Required for international transfers'
    )
    
    def clean_account_number(self):
        account_number = self.cleaned_data['account_number']
        
        # Remove spaces and validate
        account_number = account_number.replace(' ', '')
        
        if not account_number.isdigit():
            raise ValidationError('Account number should contain only digits.')
        
        if len(account_number) < 8:
            raise ValidationError('Account number should be at least 8 digits.')
        
        return account_number
    
    def clean_swift_code(self):
        swift_code = self.cleaned_data.get('swift_code')
        
        if swift_code:
            # Basic SWIFT code validation
            if not re.match(r'^[A-Z]{6}[A-Z0-9]{2}([A-Z0-9]{3})?$', swift_code.upper()):
                raise ValidationError('Please enter a valid SWIFT/BIC code.')
            
            return swift_code.upper()
        
        return swift_code

class MobileMoneyForm(BasePaymentForm):
    """Mobile money specific form"""
    
    PROVIDERS = [
        ('mpesa', 'M-Pesa'),
        ('airtel', 'Airtel Money'),
        ('mtn', 'MTN Mobile Money'),
        ('orange', 'Orange Money'),
        ('vodacom', 'Vodacom M-Pesa'),
    ]
    
    provider = forms.ChoiceField(
        choices=PROVIDERS,
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500'
        }),
        label='Mobile Money Provider'
    )
    
    phone_number = forms.CharField(
        max_length=20,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500',
            'placeholder': '+254700000000'
        }),
        label='Mobile Money Number',
        help_text='Include country code'
    )
    
    account_name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500',
            'placeholder': 'Account holder name'
        }),
        label='Account Holder Name'
    )
    
    def clean_phone_number(self):
        phone_number = self.cleaned_data['phone_number']
        
        # Remove spaces and validate format
        phone_number = phone_number.replace(' ', '').replace('-', '')
        
        if not re.match(r'^\+?[0-9]{10,15}$', phone_number):
            raise ValidationError('Please enter a valid phone number with country code.')
        
        if not phone_number.startswith('+'):
            phone_number = '+' + phone_number
        
        return phone_number

class CryptoForm(BasePaymentForm):
    """Cryptocurrency specific form"""
    
    CURRENCIES = [
        ('BTC', 'Bitcoin (BTC)'),
        ('ETH', 'Ethereum (ETH)'),
        ('USDT', 'Tether (USDT)'),
        ('BNB', 'Binance Coin (BNB)'),
        ('USDC', 'USD Coin (USDC)'),
    ]
    
    currency = forms.ChoiceField(
        choices=CURRENCIES,
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500'
        }),
        label='Cryptocurrency'
    )
    
    wallet_address = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500',
            'placeholder': 'Enter wallet address'
        }),
        label='Wallet Address'
    )
    
    network = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500',
            'placeholder': 'e.g., ERC20, BEP20, TRC20'
        }),
        label='Network',
        help_text='Specify the blockchain network'
    )
    
    def clean_wallet_address(self):
        wallet_address = self.cleaned_data['wallet_address']
        currency = self.cleaned_data.get('currency')
        
        # Basic wallet address validation
        if len(wallet_address) < 26:
            raise ValidationError('Wallet address is too short.')
        
        if len(wallet_address) > 200:
            raise ValidationError('Wallet address is too long.')
        
        # Currency-specific validation could be added here
        if currency == 'BTC' and not re.match(r'^[13][a-km-zA-HJ-NP-Z1-9]{25,34}$', wallet_address):
            raise ValidationError('Invalid Bitcoin wallet address.')
        elif currency == 'ETH' and not re.match(r'^0x[a-fA-F0-9]{40}$', wallet_address):
            raise ValidationError('Invalid Ethereum wallet address.')
        return wallet_address