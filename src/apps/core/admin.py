# apps/core/admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.db.models import Count
from django.utils import timezone
from .models import (
    SiteConfiguration, Announcement, FAQ, SupportTicket, 
    SupportMessage, NewsUpdate, SystemLog
)

@admin.register(SiteConfiguration)
class SiteConfigurationAdmin(admin.ModelAdmin):
    """Site Configuration Admin"""
    list_display = (
        'site_name', 'contact_email', 'total_users', 
        'maintenance_mode', 'updated_at'
    )
    readonly_fields = ('created_at', 'updated_at', 'get_logo_preview', 'get_favicon_preview')
    
    fieldsets = (
        ('Basic Information', {
            'fields': (
                'site_name', 'site_description', 'get_logo_preview', 'site_logo', 
                'get_favicon_preview', 'site_favicon'
            )
        }),
        ('Contact Information', {
            'fields': (
                'contact_email', 'contact_phone', 'contact_address'
            )
        }),
        ('Social Media', {
            'fields': (
                'facebook_url', 'twitter_url', 'telegram_url', 'whatsapp_url'
            ),
            'classes': ('collapse',)
        }),
        ('Trading Settings', {
            'fields': (
                'trading_start_time', 'trading_end_time', 'weekend_trading_enabled'
            )
        }),
        ('Platform Statistics', {
            'fields': (
                'total_users', 'total_invested', 'total_profits_paid', 'platform_uptime'
            )
        }),
        ('Maintenance', {
            'fields': (
                'maintenance_mode', 'maintenance_message'
            )
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_logo_preview(self, obj):
        """Display logo preview"""
        if obj.site_logo:
            return format_html(
                '<img src="{}" width="100" height="100" style="object-fit: contain;" />',
                obj.site_logo.url
            )
        return 'No logo'
    get_logo_preview.short_description = 'Logo Preview'
    
    def get_favicon_preview(self, obj):
        """Display favicon preview"""
        if obj.site_favicon:
            return format_html(
                '<img src="{}" width="32" height="32" style="object-fit: contain;" />',
                obj.site_favicon.url
            )
        return 'No favicon'
    get_favicon_preview.short_description = 'Favicon Preview'
    
    def has_add_permission(self, request):
        # Only allow one site configuration
        return not SiteConfiguration.objects.exists()
    
    def has_delete_permission(self, request, obj=None):
        # Don't allow deletion of site configuration
        return False

@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    """Announcement Admin"""
    list_display = (
        'title', 'announcement_type', 'priority', 'is_active', 
        'show_on_homepage', 'start_date', 'end_date', 'created_by'
    )
    list_filter = (
        'announcement_type', 'priority', 'is_active', 'show_on_homepage', 
        'show_on_dashboard', 'start_date', 'created_at'
    )
    search_fields = ('title', 'message', 'created_by__email')
    readonly_fields = ('id', 'created_at', 'updated_at')
    date_hierarchy = 'start_date'
    
    fieldsets = (
        ('Announcement Details', {
            'fields': (
                'title', 'message', 'announcement_type', 'priority'
            )
        }),
        ('Display Settings', {
            'fields': (
                'is_active', 'show_to_all_users', 'show_to_authenticated_only',
                'show_on_dashboard', 'show_on_homepage'
            )
        }),
        ('Scheduling', {
            'fields': ('start_date', 'end_date')
        }),
        ('Targeting', {
            'fields': ('target_countries', 'target_packages'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['activate_announcements', 'deactivate_announcements', 'extend_announcements']
    
    def save_model(self, request, obj, form, change):
        if not change:  # Only set created_by on creation
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
    
    def activate_announcements(self, request, queryset):
        """Bulk activate announcements"""
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} announcements have been activated.')
    activate_announcements.short_description = 'Activate selected announcements'
    
    def deactivate_announcements(self, request, queryset):
        """Bulk deactivate announcements"""
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} announcements have been deactivated.')
    deactivate_announcements.short_description = 'Deactivate selected announcements'
    
    def extend_announcements(self, request, queryset):
        """Extend announcement end date by 7 days"""
        from datetime import timedelta
        
        for announcement in queryset:
            if announcement.end_date:
                announcement.end_date += timedelta(days=7)
            else:
                announcement.end_date = timezone.now() + timedelta(days=7)
            announcement.save()
        
        self.message_user(request, f'Extended {queryset.count()} announcements by 7 days.')
    extend_announcements.short_description = 'Extend selected announcements by 7 days'

@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    """FAQ Admin"""
    list_display = (
        'question', 'category', 'is_active', 'is_featured', 
        'order', 'view_count', 'helpful_votes'
    )
    list_filter = ('category', 'is_active', 'is_featured', 'created_at')
    search_fields = ('question', 'answer')
    list_editable = ('is_active', 'is_featured', 'order')
    readonly_fields = ('id', 'view_count', 'helpful_votes', 'created_at', 'updated_at')
    
    fieldsets = (
        ('FAQ Content', {
            'fields': ('question', 'answer', 'category')
        }),
        ('Display Settings', {
            'fields': ('is_active', 'is_featured', 'order')
        }),
        ('Statistics', {
            'fields': ('view_count', 'helpful_votes'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['feature_faqs', 'unfeature_faqs', 'reset_statistics']
    
    def feature_faqs(self, request, queryset):
        """Bulk feature FAQs"""
        updated = queryset.update(is_featured=True)
        self.message_user(request, f'{updated} FAQs have been featured.')
    feature_faqs.short_description = 'Feature selected FAQs'
    
    def unfeature_faqs(self, request, queryset):
        """Bulk unfeature FAQs"""
        updated = queryset.update(is_featured=False)
        self.message_user(request, f'{updated} FAQs have been unfeatured.')
    unfeature_faqs.short_description = 'Unfeature selected FAQs'
    
    def reset_statistics(self, request, queryset):
        """Reset FAQ statistics"""
        updated = queryset.update(view_count=0, helpful_votes=0)
        self.message_user(request, f'Reset statistics for {updated} FAQs.')
    reset_statistics.short_description = 'Reset statistics for selected FAQs'

class SupportMessageInline(admin.TabularInline):
    """Inline for Support Messages"""
    model = SupportMessage
    extra = 0
    readonly_fields = ('sender', 'created_at')
    fields = ('sender', 'message', 'is_internal', 'created_at')
    
    def has_delete_permission(self, request, obj=None):
        return False

@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    """Support Ticket Admin"""
    list_display = (
        'ticket_number', 'get_user_email', 'subject', 'category', 
        'priority', 'status', 'assigned_to', 'created_at'
    )
    list_filter = (
        'category', 'priority', 'status', 'created_at', 
        'assigned_to', 'resolved_at'
    )
    search_fields = (
        'ticket_number', 'subject', 'description', 
        'user__email', 'user__full_name'
    )
    readonly_fields = (
        'id', 'ticket_number', 'user', 'created_at', 
        'updated_at', 'get_user_info'
    )
    list_editable = ('status', 'assigned_to')
    date_hierarchy = 'created_at'
    inlines = [SupportMessageInline]
    
    fieldsets = (
        ('Ticket Information', {
            'fields': (
                'ticket_number', 'get_user_info', 'subject', 'description'
            )
        }),
        ('Classification', {
            'fields': ('category', 'priority', 'status')
        }),
        ('Assignment', {
            'fields': ('assigned_to',)
        }),
        ('Timestamps', {
            'fields': (
                'created_at', 'updated_at', 'resolved_at', 'closed_at'
            ),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['assign_to_me', 'mark_resolved', 'mark_closed', 'escalate_priority']
    
    def get_user_email(self, obj):
        """Get user email with link"""
        url = reverse('admin:accounts_user_change', args=[obj.user.pk])
        return format_html('<a href="{}">{}</a>', url, obj.user.email)
    get_user_email.short_description = 'User'
    get_user_email.admin_order_field = 'user__email'
    
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
    
    def assign_to_me(self, request, queryset):
        """Assign tickets to current admin user"""
        updated = queryset.update(assigned_to=request.user, status='in_progress')
        self.message_user(request, f'{updated} tickets have been assigned to you.')
    assign_to_me.short_description = 'Assign selected tickets to me'
    
    def mark_resolved(self, request, queryset):
        """Mark tickets as resolved"""
        updated = queryset.update(status='resolved', resolved_at=timezone.now())
        self.message_user(request, f'{updated} tickets have been marked as resolved.')
    mark_resolved.short_description = 'Mark selected tickets as resolved'
    
    def mark_closed(self, request, queryset):
        """Mark tickets as closed"""
        updated = queryset.update(status='closed', closed_at=timezone.now())
        self.message_user(request, f'{updated} tickets have been marked as closed.')
    mark_closed.short_description = 'Mark selected tickets as closed'
    
    def escalate_priority(self, request, queryset):
        """Escalate ticket priority"""
        priority_map = {'low': 'medium', 'medium': 'high', 'high': 'urgent'}
        
        for ticket in queryset:
            if ticket.priority in priority_map:
                ticket.priority = priority_map[ticket.priority]
                ticket.save()
        
        self.message_user(request, f'Escalated priority for {queryset.count()} tickets.')
    escalate_priority.short_description = 'Escalate priority for selected tickets'

@admin.register(SupportMessage)
class SupportMessageAdmin(admin.ModelAdmin):
    """Support Message Admin"""
    list_display = (
        'get_ticket_number', 'get_sender_email', 'get_message_preview', 
        'is_internal', 'created_at'
    )
    list_filter = ('is_internal', 'created_at', 'ticket__status')
    search_fields = (
        'message', 'ticket__ticket_number', 'sender__email', 
        'ticket__subject'
    )
    readonly_fields = ('id', 'ticket', 'sender', 'created_at')
    
    def get_ticket_number(self, obj):
        """Get ticket number with link"""
        url = reverse('admin:core_supportticket_change', args=[obj.ticket.pk])
        return format_html('<a href="{}">{}</a>', url, obj.ticket.ticket_number)
    get_ticket_number.short_description = 'Ticket'
    get_ticket_number.admin_order_field = 'ticket__ticket_number'
    
    def get_sender_email(self, obj):
        """Get sender email"""
        return obj.sender.email
    get_sender_email.short_description = 'Sender'
    get_sender_email.admin_order_field = 'sender__email'
    
    def get_message_preview(self, obj):
        """Get message preview"""
        return obj.message[:100] + '...' if len(obj.message) > 100 else obj.message
    get_message_preview.short_description = 'Message Preview'
    
    def has_add_permission(self, request):
        return False  # Messages should be created through tickets

@admin.register(NewsUpdate)
class NewsUpdateAdmin(admin.ModelAdmin):
    """News Update Admin"""
    list_display = (
        'title', 'author', 'is_published', 'publish_date', 
        'view_count', 'created_at'
    )
    list_filter = ('is_published', 'publish_date', 'author', 'created_at')
    search_fields = ('title', 'content', 'excerpt', 'author__email')
    readonly_fields = ('id', 'slug', 'view_count', 'created_at', 'updated_at', 'get_image_preview')
    prepopulated_fields = {'slug': ('title',)}
    date_hierarchy = 'publish_date'
    
    fieldsets = (
        ('Article Content', {
            'fields': (
                'title', 'slug', 'excerpt', 'content', 
                'get_image_preview', 'featured_image'
            )
        }),
        ('Publishing', {
            'fields': ('is_published', 'publish_date', 'author')
        }),
        ('SEO', {
            'fields': ('meta_description',),
            'classes': ('collapse',)
        }),
        ('Statistics', {
            'fields': ('view_count',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['publish_articles', 'unpublish_articles', 'reset_view_counts']
    
    def get_image_preview(self, obj):
        """Display featured image preview"""
        if obj.featured_image:
            return format_html(
                '<img src="{}" width="200" height="150" style="object-fit: cover;" />',
                obj.featured_image.url
            )
        return 'No image'
    get_image_preview.short_description = 'Featured Image Preview'
    
    def save_model(self, request, obj, form, change):
        if not change:  # Only set author on creation
            obj.author = request.user
        super().save_model(request, obj, form, change)
    
    def publish_articles(self, request, queryset):
        """Bulk publish articles"""
        updated = queryset.update(is_published=True)
        self.message_user(request, f'{updated} articles have been published.')
    publish_articles.short_description = 'Publish selected articles'
    
    def unpublish_articles(self, request, queryset):
        """Bulk unpublish articles"""
        updated = queryset.update(is_published=False)
        self.message_user(request, f'{updated} articles have been unpublished.')
    unpublish_articles.short_description = 'Unpublish selected articles'
    
    def reset_view_counts(self, request, queryset):
        """Reset view counts"""
        updated = queryset.update(view_count=0)
        self.message_user(request, f'Reset view counts for {updated} articles.')
    reset_view_counts.short_description = 'Reset view counts for selected articles'

@admin.register(SystemLog)
class SystemLogAdmin(admin.ModelAdmin):
    """System Log Admin"""
    list_display = (
        'action_type', 'level', 'get_user_email', 'get_message_preview', 
        'ip_address', 'created_at'
    )
    list_filter = ('action_type', 'level', 'created_at')
    search_fields = ('message', 'user__email', 'ip_address', 'request_path')
    readonly_fields = (
        'id', 'user', 'action_type', 'level', 'message', 
        'ip_address', 'user_agent', 'request_path', 'metadata', 'created_at'
    )
    date_hierarchy = 'created_at'
    
    def get_user_email(self, obj):
        """Get user email or 'Anonymous'"""
        if obj.user:
            url = reverse('admin:accounts_user_change', args=[obj.user.pk])
            return format_html('<a href="{}">{}</a>', url, obj.user.email)
        return 'Anonymous'
    get_user_email.short_description = 'User'
    get_user_email.admin_order_field = 'user__email'
    
    def get_message_preview(self, obj):
        """Get message preview"""
        return obj.message[:100] + '...' if len(obj.message) > 100 else obj.message
    get_message_preview.short_description = 'Message Preview'
    
    def has_add_permission(self, request):
        return False  # Logs should be created automatically
    
    def has_change_permission(self, request, obj=None):
        return False  # Logs should not be modified
    
    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser  # Only superusers can delete logs
