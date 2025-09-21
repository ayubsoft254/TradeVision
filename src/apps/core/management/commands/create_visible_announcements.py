from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from apps.core.models import Announcement
import uuid

User = get_user_model()


class Command(BaseCommand):
    help = 'Create highly visible test announcements with different styles'

    def add_arguments(self, parser):
        parser.add_argument(
            '--type',
            type=str,
            choices=['urgent', 'success', 'warning', 'info', 'all'],
            default='all',
            help='Type of visible announcement to create',
        )
        parser.add_argument(
            '--clear-first',
            action='store_true',
            help='Clear existing announcements first',
        )

    def handle(self, *args, **options):
        # Get or create admin user for announcements
        try:
            admin_user = User.objects.filter(is_superuser=True).first()
            if not admin_user:
                admin_user = User.objects.filter(is_staff=True).first()
        except Exception:
            admin_user = None

        # Clear existing announcements if requested
        if options['clear_first']:
            count = Announcement.objects.count()
            Announcement.objects.all().delete()
            self.stdout.write(
                self.style.SUCCESS(f'Cleared {count} existing announcements.')
            )

        announcement_type = options['type']
        
        if announcement_type == 'all' or announcement_type == 'urgent':
            self.create_urgent_announcement(admin_user)
        
        if announcement_type == 'all' or announcement_type == 'success':
            self.create_success_announcement(admin_user)
        
        if announcement_type == 'all' or announcement_type == 'warning':
            self.create_warning_announcement(admin_user)
        
        if announcement_type == 'all' or announcement_type == 'info':
            self.create_info_announcement(admin_user)

        # Show summary
        total = Announcement.objects.count()
        homepage = Announcement.objects.filter(show_on_homepage=True).count()
        
        self.stdout.write(
            self.style.SUCCESS(f'\n✅ Created visible announcements!')
        )
        self.stdout.write(f'Total announcements: {total}')
        self.stdout.write(f'Homepage announcements: {homepage}')
        self.stdout.write(f'\n🚀 Start your server and visit the homepage to see them!')

    def create_urgent_announcement(self, admin_user):
        """Create an urgent announcement"""
        announcement = Announcement.objects.create(
            title="🔥 URGENT: Limited Time Bonus Available!",
            message="Act now! Get a 50% welcome bonus on your first investment. This exclusive offer expires in 24 hours. Don't miss out on this incredible opportunity to maximize your profits!",
            announcement_type='danger',
            priority='urgent',
            show_on_homepage=True,
            show_on_dashboard=True,
            is_active=True,
            show_to_all_users=True,
            start_date=timezone.now(),
            created_by=admin_user
        )
        
        self.stdout.write(
            self.style.WARNING(f'Created URGENT announcement: "{announcement.title}"')
        )

    def create_success_announcement(self, admin_user):
        """Create a success announcement"""
        announcement = Announcement.objects.create(
            title="🎉 NEW: Instant Withdrawal Feature Now Live!",
            message="Great news! You can now withdraw your profits instantly, 24/7. Our new lightning-fast withdrawal system processes your requests in under 60 seconds. Start earning and withdrawing today!",
            announcement_type='success',
            priority='high',
            show_on_homepage=True,
            show_on_dashboard=True,
            is_active=True,
            show_to_all_users=True,
            start_date=timezone.now(),
            created_by=admin_user
        )
        
        self.stdout.write(
            self.style.SUCCESS(f'Created SUCCESS announcement: "{announcement.title}"')
        )

    def create_warning_announcement(self, admin_user):
        """Create a warning announcement"""
        announcement = Announcement.objects.create(
            title="⚠️ IMPORTANT: Platform Maintenance Tonight",
            message="Scheduled maintenance will occur tonight from 2:00 AM to 4:00 AM GMT. Trading will continue normally, but some features may be temporarily unavailable. Plan your activities accordingly.",
            announcement_type='warning',
            priority='high',
            show_on_homepage=True,
            show_on_dashboard=True,
            is_active=True,
            show_to_all_users=True,
            start_date=timezone.now(),
            created_by=admin_user
        )
        
        self.stdout.write(
            self.style.WARNING(f'Created WARNING announcement: "{announcement.title}"')
        )

    def create_info_announcement(self, admin_user):
        """Create an info announcement"""
        announcement = Announcement.objects.create(
            title="📈 Market Update: New Trading Opportunities",
            message="The markets are showing exceptional volatility patterns this week. Our AI algorithms have identified multiple high-profit opportunities. Increase your investment to maximize your earning potential during this favorable market period.",
            announcement_type='info',
            priority='medium',
            show_on_homepage=True,
            show_on_dashboard=True,
            is_active=True,
            show_to_all_users=True,
            start_date=timezone.now(),
            created_by=admin_user
        )
        
        self.stdout.write(
            self.style.SUCCESS(f'Created INFO announcement: "{announcement.title}"')
        )