# apps/trading/management/commands/toggle_weekend_trading.py
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from apps.core.models import SiteConfiguration


class Command(BaseCommand):
    help = 'Toggle weekend trading on/off or check current status'

    def add_arguments(self, parser):
        parser.add_argument(
            '--enable',
            action='store_true',
            help='Enable weekend trading',
        )
        
        parser.add_argument(
            '--disable',
            action='store_true',
            help='Disable weekend trading',
        )
        
        parser.add_argument(
            '--status',
            action='store_true',
            help='Show current weekend trading status',
        )
        
        parser.add_argument(
            '--trading-hours',
            nargs=2,
            metavar=('START', 'END'),
            help='Set trading hours (24-hour format, e.g., --trading-hours 8 20 for 8 AM to 8 PM)',
        )

    def handle(self, *args, **options):
        if options['status']:
            self.show_status()
            return
            
        if options['enable'] and options['disable']:
            raise CommandError('Cannot enable and disable at the same time')
            
        if not any([options['enable'], options['disable'], options['trading_hours']]):
            # No specific option provided, show current status
            self.show_status()
            return
            
        try:
            with transaction.atomic():
                # Get or create site configuration
                site_config, created = SiteConfiguration.objects.get_or_create(
                    pk=1,
                    defaults={
                        'site_name': 'TradeVision',
                        'site_description': 'Smart Trading Platform',
                        'weekend_trading_enabled': False,
                    }
                )
                
                if created:
                    self.stdout.write(
                        self.style.SUCCESS('Created new site configuration')
                    )
                
                # Handle weekend trading toggle
                if options['enable']:
                    site_config.weekend_trading_enabled = True
                    site_config.save()
                    self.stdout.write(
                        self.style.SUCCESS('✓ Weekend trading ENABLED')
                    )
                    self.stdout.write(
                        self.style.WARNING(
                            'Trading will now occur 7 days a week during trading hours'
                        )
                    )
                
                elif options['disable']:
                    site_config.weekend_trading_enabled = False
                    site_config.save()
                    self.stdout.write(
                        self.style.SUCCESS('✓ Weekend trading DISABLED')
                    )
                    self.stdout.write(
                        self.style.WARNING(
                            'Trading will only occur Monday-Friday during trading hours'
                        )
                    )
                
                # Handle trading hours
                if options['trading_hours']:
                    start_hour, end_hour = options['trading_hours']
                    try:
                        start_hour = int(start_hour)
                        end_hour = int(end_hour)
                        
                        if not (0 <= start_hour <= 23) or not (0 <= end_hour <= 23):
                            raise ValueError("Hours must be between 0-23")
                            
                        if start_hour >= end_hour:
                            raise ValueError("Start hour must be less than end hour")
                        
                        # Convert to time objects
                        from datetime import time
                        site_config.trading_start_time = time(start_hour, 0)
                        site_config.trading_end_time = time(end_hour, 0)
                        site_config.save()
                        
                        self.stdout.write(
                            self.style.SUCCESS(
                                f'✓ Trading hours updated: {start_hour:02d}:00 - {end_hour:02d}:00'
                            )
                        )
                        
                    except ValueError as e:
                        raise CommandError(f'Invalid trading hours: {e}')
                
                # Show final status
                self.stdout.write('')
                self.show_status()
                
        except Exception as e:
            raise CommandError(f'Error updating configuration: {e}')

    def show_status(self):
        """Display current trading configuration status"""
        try:
            site_config = SiteConfiguration.objects.first()
            
            if not site_config:
                self.stdout.write(
                    self.style.WARNING('No site configuration found. Run with --enable or --disable to create one.')
                )
                return
            
            self.stdout.write(
                self.style.SUCCESS('Current Trading Configuration:')
            )
            self.stdout.write('-' * 40)
            
            # Weekend trading status
            weekend_status = "ENABLED" if site_config.weekend_trading_enabled else "DISABLED"
            weekend_style = self.style.SUCCESS if site_config.weekend_trading_enabled else self.style.WARNING
            
            self.stdout.write(f'Weekend Trading: {weekend_style(weekend_status)}')
            
            # Trading hours
            start_time = site_config.trading_start_time or "08:00:00"
            end_time = site_config.trading_end_time or "18:00:00"
            self.stdout.write(f'Trading Hours: {start_time} - {end_time}')
            
            # Trading days
            if site_config.weekend_trading_enabled:
                trading_days = "Monday - Sunday (7 days)"
                days_style = self.style.SUCCESS
            else:
                trading_days = "Monday - Friday (5 days)"
                days_style = self.style.WARNING
                
            self.stdout.write(f'Trading Days: {days_style(trading_days)}')
            
            # Usage examples
            self.stdout.write('')
            self.stdout.write(self.style.HTTP_INFO('Usage Examples:'))
            self.stdout.write('• Enable weekend trading: python manage.py toggle_weekend_trading --enable')
            self.stdout.write('• Disable weekend trading: python manage.py toggle_weekend_trading --disable')
            self.stdout.write('• Set trading hours (8 AM - 8 PM): python manage.py toggle_weekend_trading --trading-hours 8 20')
            self.stdout.write('• Check status: python manage.py toggle_weekend_trading --status')
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error reading configuration: {e}')
            )