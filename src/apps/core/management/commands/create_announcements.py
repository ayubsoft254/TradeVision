from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from apps.core.models import Announcement
import uuid

User = get_user_model()


class Command(BaseCommand):
    help = 'Create test announcements for the platform'

    def add_arguments(self, parser):
        parser.add_argument(
            '--title',
            type=str,
            help='Title of the announcement',
        )
        parser.add_argument(
            '--message',
            type=str,
            help='Message content of the announcement',
        )
        parser.add_argument(
            '--type',
            type=str,
            choices=['info', 'warning', 'success', 'danger', 'maintenance'],
            default='info',
            help='Type of announcement',
        )
        parser.add_argument(
            '--priority',
            type=str,
            choices=['low', 'medium', 'high', 'urgent'],
            default='medium',
            help='Priority of announcement',
        )
        parser.add_argument(
            '--homepage',
            action='store_true',
            help='Show on homepage',
        )
        parser.add_argument(
            '--dashboard',
            action='store_true',
            help='Show on dashboard',
        )
        parser.add_argument(
            '--create-sample',
            action='store_true',
            help='Create sample announcements for testing',
        )
        parser.add_argument(
            '--clear-all',
            action='store_true',
            help='Clear all existing announcements',
        )

    def handle(self, *args, **options):
        # Get or create admin user for announcements
        try:
            admin_user = User.objects.filter(is_superuser=True).first()
            if not admin_user:
                admin_user = User.objects.filter(is_staff=True).first()
            if not admin_user:
                self.stdout.write(
                    self.style.WARNING('No admin user found. Creating announcements without user reference.')
                )
                admin_user = None
        except Exception as e:
            self.stdout.write(
                self.style.WARNING(f'Error finding admin user: {e}. Creating announcements without user reference.')
            )
            admin_user = None

        # Clear all announcements if requested
        if options['clear_all']:
            count = Announcement.objects.count()
            Announcement.objects.all().delete()
            self.stdout.write(
                self.style.SUCCESS(f'Cleared {count} existing announcements.')
            )
            return

        # Create sample announcements if requested
        if options['create_sample']:
            self.create_sample_announcements(admin_user)
            return

        # Create single announcement from arguments
        if options['title'] and options['message']:
            self.create_announcement(
                title=options['title'],
                message=options['message'],
                announcement_type=options['type'],
                priority=options['priority'],
                show_on_homepage=options['homepage'],
                show_on_dashboard=options['dashboard'],
                created_by=admin_user
            )
        else:
            self.stdout.write(
                self.style.ERROR('Please provide both --title and --message, or use --create-sample')
            )

    def create_announcement(self, title, message, announcement_type='info', priority='medium',
                          show_on_homepage=False, show_on_dashboard=True, created_by=None):
        """Create a single announcement"""
        try:
            announcement = Announcement.objects.create(
                title=title,
                message=message,
                announcement_type=announcement_type,
                priority=priority,
                show_on_homepage=show_on_homepage,
                show_on_dashboard=show_on_dashboard,
                is_active=True,
                show_to_all_users=True,
                start_date=timezone.now(),
                created_by=created_by
            )
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'Created announcement: "{title}" (ID: {announcement.id})'
                )
            )
            return announcement
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error creating announcement: {e}')
            )
            return None

    def create_sample_announcements(self, admin_user):
        """Create a set of sample announcements for testing"""
        sample_announcements = [
            {
                'title': 'Welcome to TradeVision Platform!',
                'message': 'Experience institutional-grade trading with our advanced AI algorithms. Start your trading journey today with as little as $100.',
                'announcement_type': 'success',
                'priority': 'high',
                'show_on_homepage': True,
                'show_on_dashboard': True,
            },
            {
                'title': 'New Trading Packages Available',
                'message': 'We have launched new premium trading packages with enhanced profit margins. Check out our latest investment opportunities.',
                'announcement_type': 'info',
                'priority': 'medium',
                'show_on_homepage': True,
                'show_on_dashboard': True,
            },
            {
                'title': 'Platform Maintenance Scheduled',
                'message': 'Scheduled maintenance will occur on Sunday from 2:00 AM to 4:00 AM GMT. Trading will continue normally during this period.',
                'announcement_type': 'warning',
                'priority': 'medium',
                'show_on_homepage': False,
                'show_on_dashboard': True,
            },
            {
                'title': 'Instant Withdrawal Feature Live',
                'message': 'You can now withdraw your profits instantly 24/7! Our new instant withdrawal system is now active for all verified users.',
                'announcement_type': 'success',
                'priority': 'high',
                'show_on_homepage': True,
                'show_on_dashboard': True,
            },
            {
                'title': 'Security Update Completed',
                'message': 'We have successfully implemented enhanced security measures to protect your account. Your funds are safer than ever.',
                'announcement_type': 'info',
                'priority': 'low',
                'show_on_homepage': False,
                'show_on_dashboard': True,
            },
            {
                'title': 'Holiday Trading Hours',
                'message': 'Please note that trading hours may be adjusted during the holiday season. Check our schedule for detailed information.',
                'announcement_type': 'info',
                'priority': 'medium',
                'show_on_homepage': True,
                'show_on_dashboard': True,
            }
        ]

        created_count = 0
        for announcement_data in sample_announcements:
            announcement = self.create_announcement(
                created_by=admin_user,
                **announcement_data
            )
            if announcement:
                created_count += 1

        self.stdout.write(
            self.style.SUCCESS(f'Created {created_count} sample announcements successfully!')
        )
        
        # Show summary
        total_announcements = Announcement.objects.count()
        homepage_announcements = Announcement.objects.filter(
            is_active=True,
            show_on_homepage=True
        ).count()
        
        self.stdout.write(f'\nSummary:')
        self.stdout.write(f'Total announcements: {total_announcements}')
        self.stdout.write(f'Homepage announcements: {homepage_announcements}')
        self.stdout.write(f'\nYou can now visit your homepage to see the announcements!')