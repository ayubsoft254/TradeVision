# apps/payments/admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.conf import settings
from django import forms
from .models import (
    PaymentMethod, Wallet, Transaction, DepositRequest, 
    WithdrawalRequest, Agent, P2PMerchant
)

# Custom admin forms for enhanced currency selection
class WalletAdminForm(forms.ModelForm):
    """Custom form for Wallet admin with enhanced currency selection"""
    
    class Meta:
        model = Wallet
        fields = '__all__'
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add help text for currency field
        self.fields['currency'].help_text = (
            "💰 USDT is the primary platform currency. "
            "Legacy currencies are for existing users only."
        )
        # Add CSS classes for better styling
        self.fields['currency'].widget.attrs.update({
            'class': 'currency-selector',
            'style': 'font-weight: bold; font-size: 14px;'
        })

class TransactionAdminForm(forms.ModelForm):
    """Custom form for Transaction admin with enhanced currency selection"""
    
    class Meta:
        model = Transaction
        fields = '__all__'
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add help text for currency field
        self.fields['currency'].help_text = (
            "💎 Select transaction currency. USDT is recommended for all new transactions."
        )
        # Add CSS classes for better styling
        self.fields['currency'].widget.attrs.update({
            'class': 'currency-selector',
            'style': 'font-weight: bold; font-size: 14px;'
        })

@admin.register(PaymentMethod)
class PaymentMethodAdmin(admin.ModelAdmin):
    list_display = ['display_name', 'name', 'usdt_friendly_display', 'processing_fee', 'processing_time', 'is_active', 'countries_count']
    list_filter = ['name', 'is_active']
    search_fields = ['display_name', 'name']
    readonly_fields = ['countries_display', 'usdt_compatibility']
    
    fieldsets = (
        ('Payment Method Details', {
            'fields': ('name', 'display_name', 'is_active', 'usdt_compatibility')
        }),
        ('USDT & Cryptocurrency Settings', {
            'fields': ('crypto_support_info',),
            'classes': ('highlight-crypto',),
            'description': 'USDT and cryptocurrency compatibility information'
        }),
        ('Transaction Limits (USDT)', {
            'fields': ('min_amount', 'max_amount', 'processing_fee', 'processing_time'),
            'description': 'All amounts are in USDT'
        }),
        ('Geographic Availability', {
            'fields': ('countries', 'countries_display')
        }),
    )
    
    def usdt_friendly_display(self, obj):
        crypto_keywords = ['crypto', 'bitcoin', 'usdt', 'tether', 'binance', 'blockchain']
        if any(keyword in obj.name.lower() for keyword in crypto_keywords):
            return format_html('<span style="color: green; font-weight: bold;">✓ USDT Ready</span>')
        return format_html('<span style="color: orange;">⚠ Traditional</span>')
    usdt_friendly_display.short_description = 'USDT Support'
    
    def usdt_compatibility(self, obj):
        crypto_keywords = ['crypto', 'bitcoin', 'usdt', 'tether', 'binance', 'blockchain']
        if any(keyword in obj.name.lower() for keyword in crypto_keywords):
            return format_html(
                '<div style="background: #e8f5e8; padding: 10px; border-radius: 5px; color: green;">'
                '<strong>✓ USDT Compatible</strong><br>'
                'This payment method supports USDT transactions<br>'
                'Optimized for cryptocurrency payments'
                '</div>'
            )
        return format_html(
            '<div style="background: #fff3cd; padding: 10px; border-radius: 5px; color: #856404;">'
            '<strong>Traditional Payment Method</strong><br>'
            'May require conversion from USDT<br>'
            'Consider adding crypto-friendly alternatives'
            '</div>'
        )
    usdt_compatibility.short_description = 'USDT Compatibility Analysis'
    
    def crypto_support_info(self, obj):
        return format_html(
            '<div style="background: #d1ecf1; padding: 10px; border-radius: 5px;">'
            'Platform primary currency: <strong>USDT</strong><br>'
            'Crypto-friendly methods provide better user experience<br>'
            'Traditional methods may require additional conversion steps'
            '</div>'
        )
    crypto_support_info.short_description = 'Platform Currency Info'
    
    def countries_count(self, obj):
        return len(obj.countries) if obj.countries else 0
    countries_count.short_description = 'Countries'
    
    def countries_display(self, obj):
        if obj.countries:
            return ', '.join(obj.countries)
        return 'None'
    countries_display.short_description = 'Available Countries'

@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    form = WalletAdminForm
    list_display = ['user', 'currency_display', 'balance', 'profit_balance', 'locked_balance', 'total_balance', 'updated_at']
    list_filter = ['currency', 'created_at', 'updated_at']
    search_fields = ['user__email', 'user__first_name', 'user__last_name']
    readonly_fields = ['created_at', 'updated_at', 'total_balance', 'currency_info']
    
    fieldsets = (
        ('User', {
            'fields': ('user',)
        }),
        ('Currency Settings', {
            'fields': ('currency', 'currency_info'),
            'description': 'Select the wallet currency. USDT is the primary platform currency.'
        }),
        ('Balances (USDT)', {
            'fields': ('balance', 'profit_balance', 'locked_balance', 'total_balance')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def currency_display(self, obj):
        currency_info = {
            'USDT': {'color': 'green', 'icon': '💰', 'label': 'Primary'},
            'BUSD': {'color': '#f0b90b', 'icon': '🟡', 'label': 'Binance'},
            'BTC': {'color': '#f7931a', 'icon': '₿', 'label': 'Bitcoin'},
            'ETH': {'color': '#627eea', 'icon': '⟠', 'label': 'Ethereum'},
            'BNB': {'color': '#f0b90b', 'icon': '🔶', 'label': 'BNB'},
            'USDC': {'color': '#2775ca', 'icon': '🔵', 'label': 'USD Coin'},
            'DAI': {'color': '#f4b731', 'icon': '◈', 'label': 'Dai'},
        }
        
        info = currency_info.get(obj.currency, {'color': '#666', 'icon': '💱', 'label': 'Legacy'})
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{} {} ({})</span>',
            info['color'], info['icon'], obj.currency, info['label']
        )
    currency_display.short_description = 'Currency'
    currency_display.admin_order_field = 'currency'
    
    def currency_info(self, obj):
        currency_details = {
            'USDT': {
                'bg': '#e8f5e8',
                'color': '#2e7d32',
                'title': 'USDT (Tether)',
                'description': 'Primary platform currency<br>Stable value pegged to USD<br>Fast and low-cost transactions'
            },
            'BUSD': {
                'bg': '#fff8e1',
                'color': '#f57f17',
                'title': 'BUSD (Binance USD)',
                'description': 'Binance stablecoin<br>USD-pegged stable value<br>Binance ecosystem integration'
            },
            'BTC': {
                'bg': '#fff3e0',
                'color': '#e65100',
                'title': 'Bitcoin',
                'description': 'Digital gold standard<br>Decentralized cryptocurrency<br>High value store'
            },
            'ETH': {
                'bg': '#e8eaf6',
                'color': '#3949ab',
                'title': 'Ethereum',
                'description': 'Smart contract platform<br>DeFi ecosystem base<br>Programmable money'
            },
            'BNB': {
                'bg': '#fff8e1',
                'color': '#f57f17',
                'title': 'Binance Coin',
                'description': 'Binance exchange token<br>Reduced trading fees<br>Ecosystem utility token'
            },
            'USDC': {
                'bg': '#e3f2fd',
                'color': '#1976d2',
                'title': 'USD Coin',
                'description': 'Centre-issued stablecoin<br>USD-backed reserve<br>Regulated compliance'
            },
            'DAI': {
                'bg': '#fffde7',
                'color': '#f57f17',
                'title': 'Dai Stablecoin',
                'description': 'Decentralized stablecoin<br>MakerDAO protocol<br>Collateral-backed stability'
            }
        }
        
        details = currency_details.get(obj.currency)
        if details:
            return format_html(
                '<div style="background: {}; padding: 10px; border-radius: 5px; color: {};">'
                '<strong>{}</strong><br>'
                '{}'
                '</div>',
                details['bg'], details['color'], details['title'], details['description']
            )
        
        return format_html(
            '<div style="background: #fff3cd; padding: 10px; border-radius: 5px; color: #856404;">'
            '<strong>Legacy Currency: {}</strong><br>'
            'Consider migrating to USDT<br>'
            'Limited platform support'
            '</div>',
            obj.currency
        )
    currency_info.short_description = 'Currency Information'
    
    def get_readonly_fields(self, request, obj=None):
        if obj:  # editing an existing object
            return self.readonly_fields + ['user']
        return self.readonly_fields
    
    class Media:
        css = {
            'all': ('admin/css/custom_admin.css',)
        }

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    form = TransactionAdminForm
    list_display = ['id', 'user', 'transaction_type', 'amount_display', 'status', 'payment_method', 'created_at']
    list_filter = ['transaction_type', 'status', 'currency', 'payment_method', 'created_at']
    search_fields = ['user__email', 'external_reference', 'description']
    readonly_fields = ['id', 'created_at', 'updated_at', 'completed_at']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Transaction Details', {
            'fields': ('id', 'user', 'transaction_type', 'amount', 'currency', 'status'),
            'description': 'Basic transaction information with currency selection'
        }),
        ('Payment Information', {
            'fields': ('payment_method', 'external_reference', 'description')
        }),
        ('Financial Details', {
            'fields': ('processing_fee', 'net_amount')
        }),
        ('Metadata', {
            'fields': ('metadata',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'completed_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['mark_as_completed', 'mark_as_failed']
    
    def amount_display(self, obj):
        currency_formats = {
            'USDT': {'color': '#2563eb', 'currency_color': 'green', 'icon': '💰'},
            'BUSD': {'color': '#f57f17', 'currency_color': '#f57f17', 'icon': '🟡'},
            'BTC': {'color': '#f7931a', 'currency_color': '#f7931a', 'icon': '₿'},
            'ETH': {'color': '#627eea', 'currency_color': '#627eea', 'icon': '⟠'},
            'BNB': {'color': '#f0b90b', 'currency_color': '#f0b90b', 'icon': '🔶'},
            'USDC': {'color': '#2775ca', 'currency_color': '#2775ca', 'icon': '🔵'},
            'DAI': {'color': '#f4b731', 'currency_color': '#f4b731', 'icon': '◈'},
        }
        
        format_info = currency_formats.get(obj.currency, {'color': '#666', 'currency_color': '#666', 'icon': '💱'})
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{} <span style="color: {};">{} {}</span></span>',
            format_info['color'], obj.amount, format_info['currency_color'], format_info['icon'], obj.currency
        )
    amount_display.short_description = 'Amount'
    amount_display.admin_order_field = 'amount'
    
    def mark_as_completed(self, request, queryset):
        from django.utils import timezone
        updated = queryset.update(status='completed', completed_at=timezone.now())
        self.message_user(request, f'{updated} transactions marked as completed.')
    mark_as_completed.short_description = 'Mark selected transactions as completed'
    
    def mark_as_failed(self, request, queryset):
        updated = queryset.update(status='failed')
        self.message_user(request, f'{updated} transactions marked as failed.')
    mark_as_failed.short_description = 'Mark selected transactions as failed'
    
    class Media:
        css = {
            'all': ('admin/css/custom_admin.css',)
        }

@admin.register(DepositRequest)
class DepositRequestAdmin(admin.ModelAdmin):
    list_display = ['id', 'get_user', 'get_amount', 'get_status', 'payment_proof_link', 'processed_by', 'created_at']
    list_filter = ['transaction__status', 'processed_by', 'transaction__created_at']
    search_fields = ['transaction__user__email', 'transaction__external_reference']
    readonly_fields = ['id', 'get_transaction_link', 'payment_proof_preview']
    date_hierarchy = 'transaction__created_at'
    
    fieldsets = (
        ('Request Details', {
            'fields': ('id', 'get_transaction_link', 'payment_details')
        }),
        ('Payment Proof', {
            'fields': ('payment_proof', 'payment_proof_preview')
        }),
        ('Processing', {
            'fields': ('admin_notes', 'processed_by', 'processed_at')
        }),
    )
    
    def get_user(self, obj):
        return obj.transaction.user
    get_user.short_description = 'User'
    get_user.admin_order_field = 'transaction__user'
    
    def get_amount(self, obj):
        currency_formats = {
            'USDT': {'color': '#2563eb', 'currency_color': 'green', 'icon': '💰'},
            'BUSD': {'color': '#f57f17', 'currency_color': '#f57f17', 'icon': '🟡'},
            'BTC': {'color': '#f7931a', 'currency_color': '#f7931a', 'icon': '₿'},
            'ETH': {'color': '#627eea', 'currency_color': '#627eea', 'icon': '⟠'},
            'BNB': {'color': '#f0b90b', 'currency_color': '#f0b90b', 'icon': '🔶'},
            'USDC': {'color': '#2775ca', 'currency_color': '#2775ca', 'icon': '🔵'},
            'DAI': {'color': '#f4b731', 'currency_color': '#f4b731', 'icon': '◈'},
        }
        
        format_info = currency_formats.get(obj.transaction.currency, {'color': '#666', 'currency_color': '#666', 'icon': '💱'})
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{} <span style="color: {};">{} {}</span></span>',
            format_info['color'], obj.transaction.amount, format_info['currency_color'], format_info['icon'], obj.transaction.currency
        )
    get_amount.short_description = 'Amount'
    get_amount.admin_order_field = 'transaction__amount'
    
    def get_status(self, obj):
        status = obj.transaction.status
        colors = {
            'pending': 'orange',
            'processing': 'blue',
            'completed': 'green',
            'failed': 'red',
            'cancelled': 'gray'
        }
        return format_html(
            '<span style="color: {};">{}</span>',
            colors.get(status, 'black'),
            status.title()
        )
    get_status.short_description = 'Status'
    get_status.admin_order_field = 'transaction__status'
    
    def payment_proof_link(self, obj):
        if obj.payment_proof:
            return format_html('<a href="{}" target="_blank">View</a>', obj.payment_proof.url)
        return 'No proof'
    payment_proof_link.short_description = 'Proof'
    
    def payment_proof_preview(self, obj):
        if obj.payment_proof:
            return format_html('<img src="{}" style="max-width: 200px; max-height: 200px;" />', obj.payment_proof.url)
        return 'No image'
    payment_proof_preview.short_description = 'Preview'
    
    def get_transaction_link(self, obj):
        url = reverse('admin:payments_transaction_change', args=[obj.transaction.pk])
        return format_html('<a href="{}">{}</a>', url, obj.transaction.id)
    get_transaction_link.short_description = 'Transaction'
    
    def created_at(self, obj):
        return obj.transaction.created_at
    created_at.short_description = 'Created'
    created_at.admin_order_field = 'transaction__created_at'

@admin.register(WithdrawalRequest)
class WithdrawalRequestAdmin(admin.ModelAdmin):
    list_display = ['id', 'get_user', 'get_amount', 'get_status', 'otp_verified', 'processed_by', 'created_at']
    list_filter = ['transaction__status', 'otp_verified', 'processed_by', 'transaction__created_at']
    search_fields = ['transaction__user__email', 'transaction__external_reference']
    readonly_fields = ['id', 'get_transaction_link', 'withdrawal_address_display']
    date_hierarchy = 'transaction__created_at'
    
    fieldsets = (
        ('Request Details', {
            'fields': ('id', 'get_transaction_link', 'withdrawal_address', 'withdrawal_address_display')
        }),
        ('Verification', {
            'fields': ('otp_verified',)
        }),
        ('Processing', {
            'fields': ('admin_notes', 'processed_by', 'processed_at')
        }),
    )
    
    actions = ['mark_otp_verified']
    
    def get_user(self, obj):
        return obj.transaction.user
    get_user.short_description = 'User'
    get_user.admin_order_field = 'transaction__user'
    
    def get_amount(self, obj):
        currency_formats = {
            'USDT': {'color': '#2563eb', 'currency_color': 'green', 'icon': '💰'},
            'BUSD': {'color': '#f57f17', 'currency_color': '#f57f17', 'icon': '🟡'},
            'BTC': {'color': '#f7931a', 'currency_color': '#f7931a', 'icon': '₿'},
            'ETH': {'color': '#627eea', 'currency_color': '#627eea', 'icon': '⟠'},
            'BNB': {'color': '#f0b90b', 'currency_color': '#f0b90b', 'icon': '🔶'},
            'USDC': {'color': '#2775ca', 'currency_color': '#2775ca', 'icon': '🔵'},
            'DAI': {'color': '#f4b731', 'currency_color': '#f4b731', 'icon': '◈'},
        }
        
        format_info = currency_formats.get(obj.transaction.currency, {'color': '#666', 'currency_color': '#666', 'icon': '💱'})
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{} <span style="color: {};">{} {}</span></span>',
            format_info['color'], obj.transaction.amount, format_info['currency_color'], format_info['icon'], obj.transaction.currency
        )
    get_amount.short_description = 'Amount (Withdrawal)'
    get_amount.admin_order_field = 'transaction__amount'
    
    def get_status(self, obj):
        status = obj.transaction.status
        colors = {
            'pending': 'orange',
            'processing': 'blue',
            'completed': 'green',
            'failed': 'red',
            'cancelled': 'gray'
        }
        return format_html(
            '<span style="color: {};">{}</span>',
            colors.get(status, 'black'),
            status.title()
        )
    get_status.short_description = 'Status'
    get_status.admin_order_field = 'transaction__status'
    
    def withdrawal_address_display(self, obj):
        if obj.withdrawal_address:
            return format_html('<pre>{}</pre>', 
                             '\n'.join([f'{k}: {v}' for k, v in obj.withdrawal_address.items()]))
        return 'No address data'
    withdrawal_address_display.short_description = 'Withdrawal Details'
    
    def get_transaction_link(self, obj):
        url = reverse('admin:payments_transaction_change', args=[obj.transaction.pk])
        return format_html('<a href="{}">{}</a>', url, obj.transaction.id)
    get_transaction_link.short_description = 'Transaction'
    
    def created_at(self, obj):
        return obj.transaction.created_at
    created_at.short_description = 'Created'
    created_at.admin_order_field = 'transaction__created_at'
    
    def mark_otp_verified(self, request, queryset):
        updated = queryset.update(otp_verified=True)
        self.message_user(request, f'{updated} withdrawal requests marked as OTP verified.')
    mark_otp_verified.short_description = 'Mark as OTP verified'

@admin.register(Agent)
class AgentAdmin(admin.ModelAdmin):
    list_display = ['name', 'city', 'country', 'phone_number', 'is_verified', 'is_active', 'rating', 'total_transactions']
    list_filter = ['country', 'is_verified', 'is_active', 'created_at']
    search_fields = ['name', 'phone_number', 'email', 'city']
    readonly_fields = ['id', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'name', 'phone_number', 'email')
        }),
        ('Location', {
            'fields': ('country', 'city', 'address')
        }),
        ('Business Settings', {
            'fields': ('commission_rate', 'max_transaction_amount')
        }),
        ('Status & Performance', {
            'fields': ('is_verified', 'is_active', 'rating', 'total_transactions')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['mark_as_verified', 'mark_as_unverified', 'activate_agents', 'deactivate_agents']
    
    def mark_as_verified(self, request, queryset):
        updated = queryset.update(is_verified=True)
        self.message_user(request, f'{updated} agents marked as verified.')
    mark_as_verified.short_description = 'Mark selected agents as verified'
    
    def mark_as_unverified(self, request, queryset):
        updated = queryset.update(is_verified=False)
        self.message_user(request, f'{updated} agents marked as unverified.')
    mark_as_unverified.short_description = 'Mark selected agents as unverified'
    
    def activate_agents(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} agents activated.')
    activate_agents.short_description = 'Activate selected agents'
    
    def deactivate_agents(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} agents deactivated.')
    deactivate_agents.short_description = 'Deactivate selected agents'

@admin.register(P2PMerchant)
class P2PMerchantAdmin(admin.ModelAdmin):
    list_display = ['name', 'username', 'country', 'is_verified', 'is_active', 'rating', 'completion_rate', 'total_orders']
    list_filter = ['country', 'is_verified', 'is_active', 'supported_methods', 'created_at']
    search_fields = ['name', 'username', 'phone_number', 'email']
    readonly_fields = ['id', 'created_at', 'updated_at', 'supported_methods_display']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'name', 'username', 'phone_number', 'email')
        }),
        ('Location & Methods', {
            'fields': ('country', 'supported_methods', 'supported_methods_display')
        }),
        ('Business Settings', {
            'fields': ('commission_rate', 'min_order_amount', 'max_order_amount')
        }),
        ('Status & Performance', {
            'fields': ('is_verified', 'is_active', 'rating', 'completion_rate', 'total_orders')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['mark_as_verified', 'mark_as_unverified', 'activate_merchants', 'deactivate_merchants']
    
    def supported_methods_display(self, obj):
        if obj.supported_methods:
            return ', '.join(obj.supported_methods)
        return 'None'
    supported_methods_display.short_description = 'Payment Methods'
    
    def mark_as_verified(self, request, queryset):
        updated = queryset.update(is_verified=True)
        self.message_user(request, f'{updated} merchants marked as verified.')
    mark_as_verified.short_description = 'Mark selected merchants as verified'
    
    def mark_as_unverified(self, request, queryset):
        updated = queryset.update(is_verified=False)
        self.message_user(request, f'{updated} merchants marked as unverified.')
    mark_as_unverified.short_description = 'Mark selected merchants as unverified'
    
    def activate_merchants(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} merchants activated.')
    activate_merchants.short_description = 'Activate selected merchants'
    
    def deactivate_merchants(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} merchants deactivated.')
    deactivate_merchants.short_description = 'Deactivate selected merchants'