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
class PaymentMethodAdminForm(forms.ModelForm):
    """Custom form for PaymentMethod admin with enhanced country selection"""
    
    # Available countries for payment methods
    COUNTRY_CHOICES = [
        ('ZM', 'Zambia'),
        ('CD', 'Democratic Republic of Congo (DRC)'),
        ('TZ', 'Tanzania'),
        ('KE', 'Kenya'),
        ('UG', 'Uganda'),
    ]
    
    # Create a multiple choice field for countries
    available_countries = forms.MultipleChoiceField(
        choices=COUNTRY_CHOICES,
        widget=forms.CheckboxSelectMultiple(attrs={
            'class': 'country-selector',
            'style': 'display: flex; flex-wrap: wrap; gap: 10px;'
        }),
        required=False,
        help_text="Select all countries where this payment method is available"
    )
    
    class Meta:
        model = PaymentMethod
        fields = '__all__'
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Pre-populate available_countries from the countries JSON field
        if self.instance and self.instance.pk:
            # Handle different formats of country data
            countries_data = self.instance.countries or []
            selected_countries = []
            
            if isinstance(countries_data, list):
                # New format: ['ZM', 'UG', 'TZ']
                selected_countries = [code for code in countries_data if len(code) == 2]
            elif isinstance(countries_data, dict):
                # Old format: {'Kenya': ['Kenya', 'Uganda', 'Tanzania']}
                # Try to map country names to codes
                country_name_to_code = {
                    'Kenya': 'KE',
                    'Uganda': 'UG', 
                    'Tanzania': 'TZ',
                    'Zambia': 'ZM',
                    'Democratic Republic of Congo': 'CD',
                    'DRC': 'CD'
                }
                
                for key, values in countries_data.items():
                    if isinstance(values, list):
                        for country in values:
                            if country in country_name_to_code:
                                code = country_name_to_code[country]
                                if code not in selected_countries:
                                    selected_countries.append(code)
                    elif key in country_name_to_code:
                        code = country_name_to_code[key]
                        if code not in selected_countries:
                            selected_countries.append(code)
            elif isinstance(countries_data, str):
                # Handle string format - try to parse as JSON
                try:
                    import json
                    parsed_data = json.loads(countries_data)
                    if isinstance(parsed_data, list):
                        selected_countries = [code for code in parsed_data if len(code) == 2]
                except (json.JSONDecodeError, TypeError):
                    selected_countries = []
            
            self.initial['available_countries'] = selected_countries
            
        # Style the form fields
        self.fields['name'].widget.attrs.update({
            'class': 'payment-method-selector',
            'style': 'font-weight: bold;'
        })
        
        self.fields['display_name'].help_text = (
            "User-friendly name shown to customers (e.g., 'MTN Mobile Money', 'Airtel Money')"
        )
        
        # Add help text for countries field
        self.fields['available_countries'].help_text = (
            "Select all countries where this payment method is available. "
            "This will replace any existing country data."
        )
        
        # Hide the raw countries JSON field and make it not required
        self.fields['countries'].widget = forms.HiddenInput()
        self.fields['countries'].required = False
    
    def clean(self):
        cleaned_data = super().clean()
        # Convert the available_countries selection to the countries JSON field
        selected_countries = cleaned_data.get('available_countries', [])
        
        # Ensure we have a proper list of valid country codes
        if selected_countries:
            # Filter to ensure we only have valid 2-letter country codes
            valid_countries = []
            for country in selected_countries:
                if isinstance(country, str) and len(country) == 2:
                    valid_countries.append(country)
            cleaned_data['countries'] = valid_countries
        else:
            cleaned_data['countries'] = []
            
        return cleaned_data
    
    def save(self, commit=True):
        # Make sure the countries field is properly set from available_countries
        selected_countries = self.cleaned_data.get('available_countries', [])
        
        # Ensure it's stored as a proper list in the JSON field
        if selected_countries:
            valid_countries = [country for country in selected_countries if isinstance(country, str) and len(country) == 2]
            self.instance.countries = valid_countries
        else:
            self.instance.countries = []
            
        return super().save(commit=commit)

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
    form = PaymentMethodAdminForm
    list_display = ['display_name', 'name', 'usdt_friendly_display', 'processing_fee', 'processing_time', 'is_active', 'countries_count', 'countries_list']
    list_filter = ['name', 'is_active']
    search_fields = ['display_name', 'name']
    readonly_fields = ['countries_display', 'usdt_compatibility', 'crypto_support_info']
    
    fieldsets = (
        ('Payment Method Details', {
            'fields': ('name', 'display_name', 'is_active', 'usdt_compatibility')
        }),
        ('Country Availability', {
            'fields': ('available_countries', 'countries_display'),
            'description': 'Select the countries where this payment method is available'
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
        ('Advanced Settings', {
            'fields': ('countries',),
            'classes': ('collapse',),
            'description': 'Raw JSON data (automatically managed)'
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
        countries_data = obj.countries or []
        
        if isinstance(countries_data, list):
            return len([code for code in countries_data if isinstance(code, str) and len(code) == 2])
        elif isinstance(countries_data, dict):
            # Count unique countries from old format
            country_name_to_code = {
                'Kenya': 'KE', 'Uganda': 'UG', 'Tanzania': 'TZ',
                'Zambia': 'ZM', 'Democratic Republic of Congo': 'CD', 'DRC': 'CD'
            }
            unique_codes = set()
            
            for key, values in countries_data.items():
                if isinstance(values, list):
                    for country in values:
                        if country in country_name_to_code:
                            unique_codes.add(country_name_to_code[country])
                elif key in country_name_to_code:
                    unique_codes.add(country_name_to_code[key])
            
            return len(unique_codes)
        
        return 0
    countries_count.short_description = 'Countries'
    
    def countries_list(self, obj):
        """Show country names instead of codes in the list view"""
        countries_data = obj.countries or []
        
        # Country mapping
        country_mapping = {
            'ZM': '🇿🇲 Zambia',
            'CD': '🇨🇩 DRC',
            'TZ': '🇹🇿 Tanzania', 
            'KE': '🇰🇪 Kenya',
            'UG': '🇺🇬 Uganda'
        }
        
        # Handle different data formats
        country_codes = []
        
        if isinstance(countries_data, list):
            # New format: ['ZM', 'UG', 'TZ']
            country_codes = [code for code in countries_data if isinstance(code, str) and len(code) == 2]
        elif isinstance(countries_data, dict):
            # Old format: {'Kenya': ['Kenya', 'Uganda', 'Tanzania']}
            country_name_to_code = {
                'Kenya': 'KE', 'Uganda': 'UG', 'Tanzania': 'TZ',
                'Zambia': 'ZM', 'Democratic Republic of Congo': 'CD', 'DRC': 'CD'
            }
            
            for key, values in countries_data.items():
                if isinstance(values, list):
                    for country in values:
                        if country in country_name_to_code:
                            code = country_name_to_code[country]
                            if code not in country_codes:
                                country_codes.append(code)
                elif key in country_name_to_code:
                    code = country_name_to_code[key]
                    if code not in country_codes:
                        country_codes.append(code)
        
        if country_codes:
            country_names = [country_mapping.get(code, code) for code in country_codes]
            result = ', '.join(country_names)
            # Add indicator for old format
            if isinstance(countries_data, dict):
                result += ' <small style="color: orange;">⚠️</small>'
            return format_html('<span style="font-size: 12px;">{}</span>', result)
        return format_html('<span style="color: #999;">No countries</span>')
    countries_list.short_description = 'Available In'
    
    def countries_display(self, obj):
        """Enhanced display of countries in the detail view"""
        countries_data = obj.countries or []
        
        # Country mapping for display
        country_mapping = {
            'ZM': {'name': 'Zambia', 'flag': '🇿🇲', 'color': '#1e7e34'},
            'CD': {'name': 'Democratic Republic of Congo', 'flag': '🇨🇩', 'color': '#155724'},
            'TZ': {'name': 'Tanzania', 'flag': '🇹🇿', 'color': '#0c5460'},
            'KE': {'name': 'Kenya', 'flag': '🇰🇪', 'color': '#721c24'},
            'UG': {'name': 'Uganda', 'flag': '🇺🇬', 'color': '#856404'}
        }
        
        # Handle different data formats
        country_codes = []
        
        if isinstance(countries_data, list):
            # New format: ['ZM', 'UG', 'TZ']
            country_codes = [code for code in countries_data if isinstance(code, str) and len(code) == 2]
        elif isinstance(countries_data, dict):
            # Old format: {'Kenya': ['Kenya', 'Uganda', 'Tanzania']}
            country_name_to_code = {
                'Kenya': 'KE', 'Uganda': 'UG', 'Tanzania': 'TZ',
                'Zambia': 'ZM', 'Democratic Republic of Congo': 'CD', 'DRC': 'CD'
            }
            
            for key, values in countries_data.items():
                if isinstance(values, list):
                    for country in values:
                        if country in country_name_to_code:
                            code = country_name_to_code[country]
                            if code not in country_codes:
                                country_codes.append(code)
                elif key in country_name_to_code:
                    code = country_name_to_code[key]
                    if code not in country_codes:
                        country_codes.append(code)
        
        if country_codes:
            country_html = []
            for code in country_codes:
                country_info = country_mapping.get(code, {'name': code, 'flag': '🌍', 'color': '#6c757d'})
                country_html.append(
                    f'<span style="display: inline-block; margin: 4px; padding: 6px 12px; '
                    f'background-color: {country_info["color"]}20; color: {country_info["color"]}; '
                    f'border: 1px solid {country_info["color"]}40; border-radius: 16px; font-size: 13px;">'
                    f'{country_info["flag"]} {country_info["name"]}</span>'
                )
            
            # Add a note if data format needs updating
            if isinstance(countries_data, dict):
                country_html.append(
                    '<br><small style="color: #856404; font-style: italic;">⚠️ Old data format detected. '
                    'Save this record to update to new format.</small>'
                )
            
            return format_html('<div style="line-height: 2;">{}</div>', ''.join(country_html))
        else:
            return format_html('<span style="color: #dc3545; font-style: italic;">No countries selected</span>')
    countries_display.short_description = 'Available Countries'
    
    class Media:
        css = {
            'all': ('admin/css/custom_admin.css',)
        }

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

class P2PMerchantAdminForm(forms.ModelForm):
    """Custom form for P2PMerchant admin with enhanced payment method selection"""
    
    class Meta:
        model = P2PMerchant
        fields = '__all__'
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Filter payment methods based on merchant's country
        if self.instance and self.instance.pk and self.instance.country:
            # Show only payment methods available in the merchant's country
            available_methods = PaymentMethod.objects.filter(
                is_active=True,
                countries__contains=self.instance.country
            ).order_by('display_name')
            
            self.fields['payment_methods'].queryset = available_methods
            self.fields['payment_methods'].help_text = (
                f"Select payment methods available in {dict(P2PMerchant.COUNTRY_CHOICES)[self.instance.country]}. "
                "Only active payment methods supported in this country are shown."
            )
        else:
            # For new merchants, show all active payment methods
            self.fields['payment_methods'].queryset = PaymentMethod.objects.filter(
                is_active=True
            ).order_by('display_name')
            self.fields['payment_methods'].help_text = (
                "Select payment methods this merchant supports. "
                "Save the merchant first to see country-specific options."
            )
        
        # Use CheckboxSelectMultiple widget for better UX
        self.fields['payment_methods'].widget = forms.CheckboxSelectMultiple(
            attrs={
                'class': 'payment-methods-selector',
                'style': 'display: flex; flex-wrap: wrap; gap: 10px;'
            }
        )
        
        # Hide the old supported_methods field - it's kept for backward compatibility
        self.fields['supported_methods'].widget = forms.HiddenInput()
        self.fields['supported_methods'].required = False
        self.fields['supported_methods'].help_text = "Legacy field - data automatically migrated to payment_methods"
        
        # Enhance other fields
        self.fields['country'].widget.attrs.update({
            'class': 'country-selector',
            'style': 'font-weight: bold;'
        })
        
        self.fields['username'].help_text = "Unique username for the merchant - will be shown to users"
        self.fields['commission_rate'].help_text = "Commission rate as percentage (e.g., 1.5 for 1.5%)"
        
    def clean(self):
        cleaned_data = super().clean()
        country = cleaned_data.get('country')
        payment_methods = cleaned_data.get('payment_methods')
        
        # Validate that selected payment methods are available in the merchant's country
        if country and payment_methods:
            invalid_methods = []
            for method in payment_methods:
                if not method.is_available_for_country(country):
                    invalid_methods.append(method.display_name)
            
            if invalid_methods:
                raise forms.ValidationError(
                    f"The following payment methods are not available in "
                    f"{dict(P2PMerchant.COUNTRY_CHOICES)[country]}: {', '.join(invalid_methods)}"
                )
        
        return cleaned_data
    
    def save(self, commit=True):
        merchant = super().save(commit=commit)
        
        if commit:
            # Migrate old supported_methods data if payment_methods is empty
            merchant.migrate_supported_methods()
        
        return merchant

@admin.register(P2PMerchant)
class P2PMerchantAdmin(admin.ModelAdmin):
    form = P2PMerchantAdminForm
    list_display = ['name', 'username', 'country', 'payment_methods_display', 'is_verified', 'is_active', 'rating', 'completion_rate', 'total_orders']
    list_filter = ['country', 'is_verified', 'is_active', 'payment_methods', 'created_at']
    search_fields = ['name', 'username', 'phone_number', 'email']
    readonly_fields = ['id', 'created_at', 'updated_at', 'payment_methods_info', 'country_methods_available']
    filter_horizontal = ['payment_methods']  # Use the nice filter widget
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'name', 'username', 'phone_number', 'email')
        }),
        ('Location & Methods', {
            'fields': ('country', 'country_methods_available', 'payment_methods', 'payment_methods_info'),
            'description': 'Select the country and payment methods this merchant supports'
        }),
        ('Business Settings', {
            'fields': ('commission_rate', 'min_order_amount', 'max_order_amount')
        }),
        ('Status & Performance', {
            'fields': ('is_verified', 'is_active', 'rating', 'completion_rate', 'total_orders')
        }),
        ('Advanced Settings', {
            'fields': ('supported_methods',),
            'classes': ('collapse',),
            'description': 'Legacy data (automatically managed)'
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['mark_as_verified', 'mark_as_unverified', 'activate_merchants', 'deactivate_merchants', 'migrate_payment_methods']
    
    def payment_methods_display(self, obj):
        """Display selected payment methods in list view"""
        methods = obj.payment_methods.filter(is_active=True)
        if methods.exists():
            method_list = []
            for method in methods[:3]:  # Show max 3 methods in list view
                # Add emoji/icon based on method type
                icons = {
                    'binance_pay': '🟡',
                    'mobile_money': '📱',
                    'bank_transfer': '🏦', 
                    'crypto': '₿',
                    'agent': '👤',
                    'p2p': '🤝'
                }
                icon = icons.get(method.name, '💳')
                method_list.append(f'{icon} {method.display_name}')
            
            result = ', '.join(method_list)
            if methods.count() > 3:
                result += f' (+{methods.count() - 3} more)'
            
            return format_html('<span style="font-size: 12px;">{}</span>', result)
        else:
            # Fall back to old supported_methods if no payment_methods selected
            if obj.supported_methods:
                return format_html(
                    '<span style="color: orange; font-size: 12px;">⚠️ Legacy: {}</span>',
                    ', '.join(obj.supported_methods)
                )
            return format_html('<span style="color: #999;">No methods</span>')
    payment_methods_display.short_description = 'Payment Methods'
    
    def payment_methods_info(self, obj):
        """Enhanced display of payment methods in detail view"""
        methods = obj.payment_methods.filter(is_active=True)
        
        if methods.exists():
            method_html = []
            for method in methods:
                # Add styling based on method type
                colors = {
                    'binance_pay': '#f0b90b',
                    'mobile_money': '#2563eb',
                    'bank_transfer': '#059669',
                    'crypto': '#f59e0b',
                    'agent': '#7c3aed',
                    'p2p': '#dc2626'
                }
                
                icons = {
                    'binance_pay': '🟡',
                    'mobile_money': '📱',
                    'bank_transfer': '🏦', 
                    'crypto': '₿',
                    'agent': '👤',
                    'p2p': '🤝'
                }
                
                color = colors.get(method.name, '#6b7280')
                icon = icons.get(method.name, '💳')
                
                available = method.is_available_for_country(obj.country)
                status_style = 'color: green;' if available else 'color: red;'
                status_text = '✓ Available' if available else '✗ Not Available'
                
                method_html.append(
                    f'<div style="display: inline-block; margin: 4px; padding: 8px 12px; '
                    f'background-color: {color}20; color: {color}; '
                    f'border: 1px solid {color}40; border-radius: 16px; font-size: 13px;">'
                    f'{icon} {method.display_name}<br>'
                    f'<small style="{status_style}">{status_text}</small>'
                    f'</div>'
                )
            
            return format_html('<div style="line-height: 2;">{}</div>', ''.join(method_html))
        else:
            # Show migration info if using old system
            if obj.supported_methods:
                return format_html(
                    '<div style="background: #fff3cd; padding: 10px; border-radius: 5px; color: #856404;">'
                    '<strong>⚠️ Legacy Payment Methods</strong><br>'
                    'Old format: {}<br>'
                    '<small>Use "Migrate payment methods" action to convert to new format</small>'
                    '</div>',
                    ', '.join(obj.supported_methods)
                )
            return format_html('<span style="color: #dc3545; font-style: italic;">No payment methods selected</span>')
    payment_methods_info.short_description = 'Payment Methods Details'
    
    def country_methods_available(self, obj):
        """Show available payment methods for the merchant's country"""
        if obj.country:
            available_methods = PaymentMethod.objects.filter(
                is_active=True,
                countries__contains=obj.country
            ).order_by('display_name')
            
            if available_methods.exists():
                method_names = [f'• {method.display_name}' for method in available_methods]
                return format_html(
                    '<div style="background: #dbeafe; padding: 10px; border-radius: 5px; color: #1e40af;">'
                    '<strong>Available in {}</strong><br>{}</div>',
                    dict(P2PMerchant.COUNTRY_CHOICES)[obj.country],
                    '<br>'.join(method_names)
                )
            else:
                return format_html(
                    '<div style="background: #fef2f2; padding: 10px; border-radius: 5px; color: #dc2626;">'
                    'No payment methods available in {}</div>',
                    dict(P2PMerchant.COUNTRY_CHOICES)[obj.country]
                )
        return format_html('<span style="color: #9ca3af;">Select a country first</span>')
    country_methods_available.short_description = 'Available Methods'
    
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
    
    def migrate_payment_methods(self, request, queryset):
        """Migrate old supported_methods to new payment_methods relationship"""
        migrated_count = 0
        for merchant in queryset:
            if merchant.supported_methods and not merchant.payment_methods.exists():
                merchant.migrate_supported_methods()
                migrated_count += 1
        
        self.message_user(request, f'{migrated_count} merchants migrated to new payment method system.')
    migrate_payment_methods.short_description = 'Migrate to new payment method system'
    
    class Media:
        css = {
            'all': ('admin/css/custom_admin.css',)
        }