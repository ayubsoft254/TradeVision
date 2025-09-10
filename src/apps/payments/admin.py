# apps/payments/admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import (
    PaymentMethod, Wallet, Transaction, DepositRequest, 
    WithdrawalRequest, Agent, P2PMerchant
)

@admin.register(PaymentMethod)
class PaymentMethodAdmin(admin.ModelAdmin):
    list_display = ['display_name', 'name', 'processing_fee', 'processing_time', 'is_active', 'countries_count']
    list_filter = ['name', 'is_active']
    search_fields = ['display_name', 'name']
    readonly_fields = ['countries_display']
    
    fieldsets = (
        (None, {
            'fields': ('name', 'display_name', 'is_active')
        }),
        ('Transaction Limits', {
            'fields': ('min_amount', 'max_amount', 'processing_fee', 'processing_time')
        }),
        ('Geographic Availability', {
            'fields': ('countries', 'countries_display')
        }),
    )
    
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
    list_display = ['user', 'balance', 'profit_balance', 'locked_balance', 'total_balance', 'currency', 'updated_at']
    list_filter = ['currency', 'created_at']
    search_fields = ['user__email', 'user__first_name', 'user__last_name']
    readonly_fields = ['created_at', 'updated_at', 'total_balance']
    
    fieldsets = (
        ('User', {
            'fields': ('user',)
        }),
        ('Balances', {
            'fields': ('balance', 'profit_balance', 'locked_balance', 'total_balance')
        }),
        ('Settings', {
            'fields': ('currency',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_readonly_fields(self, request, obj=None):
        if obj:  # editing an existing object
            return self.readonly_fields + ['user']
        return self.readonly_fields

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'transaction_type', 'amount', 'currency', 'status', 'payment_method', 'created_at']
    list_filter = ['transaction_type', 'status', 'currency', 'payment_method', 'created_at']
    search_fields = ['user__email', 'external_reference', 'description']
    readonly_fields = ['id', 'created_at', 'updated_at', 'completed_at']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Transaction Details', {
            'fields': ('id', 'user', 'transaction_type', 'amount', 'currency', 'status')
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
    
    def mark_as_completed(self, request, queryset):
        from django.utils import timezone
        updated = queryset.update(status='completed', completed_at=timezone.now())
        self.message_user(request, f'{updated} transactions marked as completed.')
    mark_as_completed.short_description = 'Mark selected transactions as completed'
    
    def mark_as_failed(self, request, queryset):
        updated = queryset.update(status='failed')
        self.message_user(request, f'{updated} transactions marked as failed.')
    mark_as_failed.short_description = 'Mark selected transactions as failed'

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
        return f"{obj.transaction.amount} {obj.transaction.currency}"
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
        return f"{obj.transaction.amount} {obj.transaction.currency}"
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