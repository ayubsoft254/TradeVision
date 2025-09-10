# apps/core/models.py
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
import uuid

User = get_user_model()

class SiteConfiguration(models.Model):
    """Global site configuration settings"""
    site_name = models.CharField(max_length=100, default='TradeVision')
    site_description = models.TextField(default='Smart Trading Platform')
    site_logo = models.ImageField(upload_to='site/', blank=True, null=True)
    site_favicon = models.ImageField(upload_to='site/', blank=True, null=True)
    
    # Contact information
    contact_email = models.EmailField(default='support@tradevision.com')
    contact_phone = models.CharField(max_length=20, default='+254 700 000 000')
    contact_address = models.TextField(blank=True)
    
    # Social media links
    facebook_url = models.URLField(blank=True)
    twitter_url = models.URLField(blank=True)
    telegram_url = models.URLField(blank=True)
    whatsapp_url = models.URLField(blank=True)
    
    # Trading settings
    trading_start_time = models.TimeField(default='08:00')
    trading_end_time = models.TimeField(default='18:00')
    weekend_trading_enabled = models.BooleanField(default=False)
    
    # Platform statistics
    total_users = models.IntegerField(default=0)
    total_invested = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_profits_paid = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    platform_uptime = models.DecimalField(max_digits=5, decimal_places=2, default=99.9)
    
    # Maintenance mode
    maintenance_mode = models.BooleanField(default=False)
    maintenance_message = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Site Configuration'
        verbose_name_plural = 'Site Configuration'
    
    def __str__(self):
        return self.site_name
    
    def save(self, *args, **kwargs):
        # Ensure only one configuration exists
        if not self.pk and SiteConfiguration.objects.exists():
            raise ValueError('Only one site configuration is allowed')
        super().save(*args, **kwargs)

class Announcement(models.Model):
    """Site-wide announcements"""
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]
    
    TYPE_CHOICES = [
        ('info', 'Information'),
        ('warning', 'Warning'),
        ('success', 'Success'),
        ('danger', 'Danger'),
        ('maintenance', 'Maintenance'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200)
    message = models.TextField()
    announcement_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='info')
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium')
    
    # Display settings
    is_active = models.BooleanField(default=True)
    show_to_all_users = models.BooleanField(default=True)
    show_to_authenticated_only = models.BooleanField(default=False)
    show_on_dashboard = models.BooleanField(default=True)
    show_on_homepage = models.BooleanField(default=False)
    
    # Scheduling
    start_date = models.DateTimeField(default=timezone.now)
    end_date = models.DateTimeField(blank=True, null=True)
    
    # Targeting
    target_countries = models.JSONField(default=list, blank=True)
    target_packages = models.JSONField(default=list, blank=True)
    
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='announcements_created')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-priority', '-created_at']
    
    def __str__(self):
        return self.title
    
    def is_visible(self):
        """Check if announcement should be visible now"""
        now = timezone.now()
        if not self.is_active:
            return False
        if now < self.start_date:
            return False
        if self.end_date and now > self.end_date:
            return False
        return True

class FAQ(models.Model):
    """Frequently Asked Questions"""
    CATEGORY_CHOICES = [
        ('general', 'General'),
        ('trading', 'Trading & Packages'),
        ('payments', 'Payments & Withdrawals'),
        ('security', 'Security & Account'),
        ('technical', 'Technical Support'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    question = models.CharField(max_length=500)
    answer = models.TextField()
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='general')
    
    # Display settings
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    order = models.IntegerField(default=0)
    
    # Statistics
    view_count = models.IntegerField(default=0)
    helpful_votes = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['category', 'order', '-is_featured']
        verbose_name = 'FAQ'
        verbose_name_plural = 'FAQs'
    
    def __str__(self):
        return self.question

class SupportTicket(models.Model):
    """Customer support tickets"""
    STATUS_CHOICES = [
        ('open', 'Open'),
        ('in_progress', 'In Progress'),
        ('waiting_customer', 'Waiting for Customer'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed'),
    ]
    
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]
    
    CATEGORY_CHOICES = [
        ('account', 'Account Issues'),
        ('trading', 'Trading Problems'),
        ('payments', 'Payment Issues'),
        ('technical', 'Technical Support'),
        ('general', 'General Inquiry'),
        ('complaint', 'Complaint'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ticket_number = models.CharField(max_length=20, unique=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='support_tickets')
    
    # Ticket details
    subject = models.CharField(max_length=200)
    description = models.TextField()
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='general')
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    
    # Assignment
    assigned_to = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='assigned_tickets'
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Ticket #{self.ticket_number} - {self.subject}"
    
    def save(self, *args, **kwargs):
        if not self.ticket_number:
            self.ticket_number = self.generate_ticket_number()
        super().save(*args, **kwargs)
    
    @classmethod
    def generate_ticket_number(cls):
        """Generate unique ticket number"""
        import random
        import string
        
        while True:
            number = ''.join(random.choices(string.digits, k=8))
            ticket_number = f"TV{number}"
            if not cls.objects.filter(ticket_number=ticket_number).exists():
                return ticket_number

class SupportMessage(models.Model):
    """Messages within support tickets"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ticket = models.ForeignKey(SupportTicket, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(User, on_delete=models.CASCADE)
    message = models.TextField()
    is_internal = models.BooleanField(default=False)  # Internal staff notes
    
    # Attachments
    attachment = models.FileField(upload_to='support_attachments/', blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['created_at']
    
    def __str__(self):
        return f"Message in {self.ticket.ticket_number} by {self.sender.email}"

class NewsUpdate(models.Model):
    """Platform news and updates"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200)
    content = models.TextField()
    excerpt = models.TextField(max_length=300, blank=True)
    featured_image = models.ImageField(upload_to='news/', blank=True, null=True)
    
    # Publishing
    is_published = models.BooleanField(default=False)
    publish_date = models.DateTimeField(default=timezone.now)
    
    # SEO
    slug = models.SlugField(unique=True, blank=True)
    meta_description = models.CharField(max_length=160, blank=True)
    
    # Author
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='news_posts')
    
    # Statistics
    view_count = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-publish_date']
        verbose_name = 'News Update'
        verbose_name_plural = 'News Updates'
    
    def __str__(self):
        return self.title
    
    def save(self, *args, **kwargs):
        if not self.slug:
            from django.utils.text import slugify
            self.slug = slugify(self.title)
        
        if not self.excerpt and self.content:
            # Auto-generate excerpt from content
            self.excerpt = self.content[:297] + '...' if len(self.content) > 300 else self.content
        
        super().save(*args, **kwargs)

class SystemLog(models.Model):
    """System activity logs"""
    LOG_LEVELS = [
        ('DEBUG', 'Debug'),
        ('INFO', 'Info'),
        ('WARNING', 'Warning'),
        ('ERROR', 'Error'),
        ('CRITICAL', 'Critical'),
    ]
    
    ACTION_TYPES = [
        ('login', 'User Login'),
        ('logout', 'User Logout'),
        ('registration', 'User Registration'),
        ('investment', 'Investment Created'),
        ('trade', 'Trade Executed'),
        ('withdrawal', 'Withdrawal Request'),
        ('deposit', 'Deposit Made'),
        ('admin_action', 'Admin Action'),
        ('system_error', 'System Error'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    action_type = models.CharField(max_length=20, choices=ACTION_TYPES)
    level = models.CharField(max_length=10, choices=LOG_LEVELS, default='INFO')
    message = models.TextField()
    
    # Technical details
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    request_path = models.CharField(max_length=500, blank=True)
    
    # Additional data
    metadata = models.JSONField(default=dict, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['action_type', '-created_at']),
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['level', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.action_type} - {self.level} - {self.created_at}"