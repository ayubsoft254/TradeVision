from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import User, UserProfile, Referral

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Custom User Admin"""
    list_display = (
        'username', 'email', 'full_name', 'country', 'phone_number', 
        'is_verified', 'is_active', 'date_joined'
    )
    list_filter = (
        'country', 'is_verified', 'is_active', 'is_staff', 
        'is_superuser', 'date_joined'
    )
    search_fields = ('email', 'full_name', 'phone_number')
    ordering = ('-date_joined',)
    readonly_fields = ('id', 'date_joined', 'last_login', 'updated_at')
    
    fieldsets = (
        (None, {
            'fields': ('id', 'email', 'password')
        }),
        ('Personal Information', {
            'fields': ('full_name', 'phone_number', 'country')
        }),
        ('Permissions', {
            'fields': (
                'is_active', 'is_staff', 'is_superuser', 'is_verified',
                'groups', 'user_permissions'
            ),
            'classes': ('collapse',)
        }),
        ('Important Dates', {
            'fields': ('last_login', 'date_joined', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': (
                'email', 'full_name', 'phone_number', 'country', 
                'password1', 'password2', 'is_active', 'is_verified'
            ),
        }),
    )
    
    actions = ['verify_users', 'unverify_users', 'activate_users', 'deactivate_users']
    
    def verify_users(self, request, queryset):
        """Bulk verify users"""
        updated = queryset.update(is_verified=True)
        self.message_user(request, f'{updated} users have been verified.')
    verify_users.short_description = 'Mark selected users as verified'
    
    def unverify_users(self, request, queryset):
        """Bulk unverify users"""
        updated = queryset.update(is_verified=False)
        self.message_user(request, f'{updated} users have been unverified.')
    unverify_users.short_description = 'Mark selected users as unverified'
    
    def activate_users(self, request, queryset):
        """Bulk activate users"""
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} users have been activated.')
    activate_users.short_description = 'Activate selected users'
    
    def deactivate_users(self, request, queryset):
        """Bulk deactivate users"""
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} users have been deactivated.')
    deactivate_users.short_description = 'Deactivate selected users'

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    """User Profile Admin"""
    list_display = (
        'get_user_email', 'get_user_name', 'kyc_status', 
        'two_factor_enabled', 'withdrawal_otp_enabled', 'created_at'
    )
    list_filter = (
        'kyc_status', 'two_factor_enabled', 'withdrawal_otp_enabled', 
        'created_at', 'user__country'
    )
    search_fields = ('user__email', 'user__full_name', 'id_number', 'city')
    readonly_fields = ('created_at', 'updated_at', 'get_user_info', 'get_avatar_preview')
    
    fieldsets = (
        ('User Information', {
            'fields': ('get_user_info', 'get_avatar_preview', 'avatar')
        }),
        ('Personal Details', {
            'fields': (
                'date_of_birth', 'address', 'city', 'postal_code'
            )
        }),
        ('KYC Information', {
            'fields': (
                'id_number', 'id_document', 'kyc_status'
            )
        }),
        ('Security Settings', {
            'fields': (
                'two_factor_enabled', 'withdrawal_otp_enabled'
            )
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['approve_kyc', 'reject_kyc', 'enable_2fa', 'disable_2fa']
    
    def get_user_email(self, obj):
        """Get user email with link to user admin"""
        url = reverse('admin:accounts_user_change', args=[obj.user.pk])
        return format_html('<a href="{}">{}</a>', url, obj.user.email)
    get_user_email.short_description = 'Email'
    get_user_email.admin_order_field = 'user__email'
    
    def get_user_name(self, obj):
        """Get user full name"""
        return obj.user.full_name or 'No name'
    get_user_name.short_description = 'Full Name'
    get_user_name.admin_order_field = 'user__full_name'
    
    def get_user_info(self, obj):
        """Display user information"""
        return format_html(
            '<strong>Email:</strong> {}<br>'
            '<strong>Name:</strong> {}<br>'
            '<strong>Phone:</strong> {}<br>'
            '<strong>Country:</strong> {}',
            obj.user.email,
            obj.user.full_name or 'Not provided',
            obj.user.phone_number or 'Not provided',
            obj.user.country.name if obj.user.country else 'Not provided'
        )
    get_user_info.short_description = 'User Information'
    
    def get_avatar_preview(self, obj):
        """Display avatar preview"""
        if obj.avatar:
            return format_html(
                '<img src="{}" width="100" height="100" style="border-radius: 50%;" />',
                obj.avatar.url
            )
        return 'No avatar'
    get_avatar_preview.short_description = 'Avatar Preview'
    
    def approve_kyc(self, request, queryset):
        """Bulk approve KYC"""
        updated = queryset.update(kyc_status='approved')
        self.message_user(request, f'{updated} KYC applications have been approved.')
    approve_kyc.short_description = 'Approve selected KYC applications'
    
    def reject_kyc(self, request, queryset):
        """Bulk reject KYC"""
        updated = queryset.update(kyc_status='rejected')
        self.message_user(request, f'{updated} KYC applications have been rejected.')
    reject_kyc.short_description = 'Reject selected KYC applications'
    
    def enable_2fa(self, request, queryset):
        """Bulk enable 2FA"""
        updated = queryset.update(two_factor_enabled=True)
        self.message_user(request, f'2FA enabled for {updated} users.')
    enable_2fa.short_description = 'Enable 2FA for selected users'
    
    def disable_2fa(self, request, queryset):
        """Bulk disable 2FA"""
        updated = queryset.update(two_factor_enabled=False)
        self.message_user(request, f'2FA disabled for {updated} users.')
    disable_2fa.short_description = 'Disable 2FA for selected users'

@admin.register(Referral)
class ReferralAdmin(admin.ModelAdmin):
    """Referral Admin"""
    list_display = (
        'get_referrer_email', 'get_referred_email', 'referral_code', 
        'commission_earned', 'is_active', 'created_at'
    )
    list_filter = ('is_active', 'created_at')
    search_fields = (
        'referrer__email', 'referred__email', 'referral_code',
        'referrer__full_name', 'referred__full_name'
    )
    readonly_fields = ('created_at', 'get_referrer_info', 'get_referred_info')
    ordering = ('-created_at',)
    
    fieldsets = (
        ('Referral Information', {
            'fields': (
                'get_referrer_info', 'get_referred_info', 'referral_code'
            )
        }),
        ('Financial Details', {
            'fields': ('commission_earned', 'is_active')
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['activate_referrals', 'deactivate_referrals', 'calculate_commissions']
    
    def get_referrer_email(self, obj):
        """Get referrer email with link"""
        url = reverse('admin:accounts_user_change', args=[obj.referrer.pk])
        return format_html('<a href="{}">{}</a>', url, obj.referrer.email)
    get_referrer_email.short_description = 'Referrer'
    get_referrer_email.admin_order_field = 'referrer__email'
    
    def get_referred_email(self, obj):
        """Get referred email with link"""
        url = reverse('admin:accounts_user_change', args=[obj.referred.pk])
        return format_html('<a href="{}">{}</a>', url, obj.referred.email)
    get_referred_email.short_description = 'Referred User'
    get_referred_email.admin_order_field = 'referred__email'
    
    def get_referrer_info(self, obj):
        """Display referrer information"""
        return format_html(
            '<strong>Email:</strong> {}<br>'
            '<strong>Name:</strong> {}<br>'
            '<strong>Country:</strong> {}',
            obj.referrer.email,
            obj.referrer.full_name or 'Not provided',
            obj.referrer.country.name if obj.referrer.country else 'Not provided'
        )
    get_referrer_info.short_description = 'Referrer Information'
    
    def get_referred_info(self, obj):
        """Display referred user information"""
        return format_html(
            '<strong>Email:</strong> {}<br>'
            '<strong>Name:</strong> {}<br>'
            '<strong>Country:</strong> {}',
            obj.referred.email,
            obj.referred.full_name or 'Not provided',
            obj.referred.country.name if obj.referred.country else 'Not provided'
        )
    get_referred_info.short_description = 'Referred User Information'
    
    def activate_referrals(self, request, queryset):
        """Bulk activate referrals"""
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} referrals have been activated.')
    activate_referrals.short_description = 'Activate selected referrals'
    
    def deactivate_referrals(self, request, queryset):
        """Bulk deactivate referrals"""
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} referrals have been deactivated.')
    deactivate_referrals.short_description = 'Deactivate selected referrals'
    
    def calculate_commissions(self, request, queryset):
        """Calculate commissions for referrals (placeholder)"""
        # This would implement actual commission calculation logic
        self.message_user(request, 'Commission calculation completed.')
    calculate_commissions.short_description = 'Calculate commissions for selected referrals'

# Inline admin for UserProfile in User admin
class UserProfileInline(admin.StackedInline):
    """Inline UserProfile in User admin"""
    model = UserProfile
    extra = 0
    fields = (
        'kyc_status', 'two_factor_enabled', 'withdrawal_otp_enabled',
        'date_of_birth', 'city'
    )
    readonly_fields = ('kyc_status',)

# Update UserAdmin to include UserProfile inline
UserAdmin.inlines = [UserProfileInline]

# Custom admin site header and title
admin.site.site_header = "TradeVision Administration"
admin.site.site_title = "TradeVision Admin"
admin.site.index_title = "Welcome to TradeVision Administration"

# # Add custom CSS for better admin appearance
# class TradeVisionAdminConfig:
#     """Custom admin configuration"""
    
#     class Media:
#         css = {
#             'all': ('admin/css/custom_admin.css',)
#         }
#         js = ('admin/js/custom_admin.js',)