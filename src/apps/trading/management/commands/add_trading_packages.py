# apps/trading/management/commands/add_trading_packages.py
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from decimal import Decimal
from apps.trading.models import TradingPackage


class Command(BaseCommand):
    help = 'Add trading packages to the system'

    def add_arguments(self, parser):
        # Option to add default packages
        parser.add_argument(
            '--default',
            action='store_true',
            help='Add default trading packages (Basic, Standard, Premium)',
        )
        
        # Option to add custom package
        parser.add_argument(
            '--name',
            type=str,
            help='Package name (basic, standard, or premium)',
        )
        
        parser.add_argument(
            '--display-name',
            type=str,
            help='Display name for the package',
        )
        
        parser.add_argument(
            '--min-stake',
            type=float,
            help='Minimum stake amount',
        )
        
        parser.add_argument(
            '--profit-min',
            type=float,
            help='Minimum daily profit percentage',
        )
        
        parser.add_argument(
            '--profit-max',
            type=float,
            help='Maximum daily profit percentage',
        )
        
        parser.add_argument(
            '--welcome-bonus',
            type=float,
            help='Welcome bonus percentage',
        )
        
        parser.add_argument(
            '--duration-days',
            type=int,
            default=7,
            help='Package duration in days (default: 7 days - 1 week)',
        )
        
        parser.add_argument(
            '--update',
            action='store_true',
            help='Update package if it already exists',
        )
        
        parser.add_argument(
            '--list',
            action='store_true',
            help='List all existing trading packages',
        )

    def handle(self, *args, **options):
        if options['list']:
            self.list_packages()
            return
            
        if options['default']:
            self.add_default_packages()
            return
            
        if options['name']:
            self.add_custom_package(options)
            return
            
        # If no specific option provided, show help
        self.stdout.write(
            self.style.WARNING(
                'Please specify either --default for default packages, '
                '--name for custom package, or --list to view existing packages.\n'
                'Use --help for more information.'
            )
        )

    def list_packages(self):
        """List all existing trading packages"""
        packages = TradingPackage.objects.all()
        
        if not packages:
            self.stdout.write(self.style.WARNING('No trading packages found.'))
            return
            
        self.stdout.write(self.style.SUCCESS('Existing Trading Packages:'))
        self.stdout.write('-' * 80)
        
        for package in packages:
            status = "Active" if package.is_active else "Inactive"
            self.stdout.write(
                f"• {package.display_name} ({package.name})\n"
                f"  Min Stake: ${package.min_stake:,}\n"
                f"  Daily Profit: {package.profit_min}% - {package.profit_max}%\n"
                f"  Welcome Bonus: {package.welcome_bonus}%\n"
                f"  Duration: {package.duration_days} days\n"
                f"  Status: {status}\n"
            )

    def add_default_packages(self):
        """Add default trading packages"""
        default_packages = [
            {
                'name': 'basic',
                'display_name': 'Basic Trading Package',
                'min_stake': Decimal('100.00'),
                'profit_min': Decimal('2.50'),
                'profit_max': Decimal('5.00'),
                'welcome_bonus': Decimal('10.00'),
                'duration_days': 7,
            },
            {
                'name': 'standard',
                'display_name': 'Standard Trading Package',
                'min_stake': Decimal('500.00'),
                'profit_min': Decimal('3.50'),
                'profit_max': Decimal('7.50'),
                'welcome_bonus': Decimal('15.00'),
                'duration_days': 7,
            },
            {
                'name': 'premium',
                'display_name': 'Premium Trading Package',
                'min_stake': Decimal('1000.00'),
                'profit_min': Decimal('5.00'),
                'profit_max': Decimal('10.00'),
                'welcome_bonus': Decimal('20.00'),
                'duration_days': 7,
            },
        ]
        
        with transaction.atomic():
            created_count = 0
            updated_count = 0
            
            for package_data in default_packages:
                package, created = TradingPackage.objects.get_or_create(
                    name=package_data['name'],
                    defaults=package_data
                )
                
                if created:
                    created_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'✓ Created package: {package.display_name}'
                        )
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING(
                            f'Package "{package.display_name}" already exists'
                        )
                    )
            
            if created_count > 0:
                self.stdout.write(
                    self.style.SUCCESS(
                        f'\nSuccessfully created {created_count} trading package(s)!'
                    )
                )
            else:
                self.stdout.write(
                    self.style.WARNING(
                        'No new packages were created. All packages already exist.'
                    )
                )

    def add_custom_package(self, options):
        """Add a custom trading package"""
        required_fields = [
            'name', 'display_name', 'min_stake', 'profit_min', 
            'profit_max', 'welcome_bonus'
        ]
        
        # Validate required fields
        missing_fields = [
            field for field in required_fields 
            if not options.get(field.replace('_', '_'))
        ]
        
        if missing_fields:
            missing_formatted = [field.replace('_', '-') for field in missing_fields]
            raise CommandError(
                f'Missing required arguments: {", ".join(missing_formatted)}'
            )
        
        # Validate package name
        valid_names = ['basic', 'standard', 'premium']
        if options['name'] not in valid_names:
            raise CommandError(
                f'Invalid package name. Must be one of: {", ".join(valid_names)}'
            )
        
        # Validate profit percentages
        if options['profit_min'] >= options['profit_max']:
            raise CommandError(
                'Minimum profit percentage must be less than maximum profit percentage'
            )
        
        package_data = {
            'name': options['name'],
            'display_name': options['display_name'],
            'min_stake': Decimal(str(options['min_stake'])),
            'profit_min': Decimal(str(options['profit_min'])),
            'profit_max': Decimal(str(options['profit_max'])),
            'welcome_bonus': Decimal(str(options['welcome_bonus'])),
            'duration_days': options['duration_days'],
            'is_active': True,
        }
        
        try:
            with transaction.atomic():
                if options['update']:
                    package, created = TradingPackage.objects.update_or_create(
                        name=package_data['name'],
                        defaults=package_data
                    )
                    
                    if created:
                        self.stdout.write(
                            self.style.SUCCESS(
                                f'✓ Created package: {package.display_name}'
                            )
                        )
                    else:
                        self.stdout.write(
                            self.style.SUCCESS(
                                f'✓ Updated package: {package.display_name}'
                            )
                        )
                else:
                    package = TradingPackage.objects.create(**package_data)
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'✓ Created package: {package.display_name}'
                        )
                    )
                    
        except Exception as e:
            if 'UNIQUE constraint failed' in str(e):
                raise CommandError(
                    f'Package with name "{options["name"]}" already exists. '
                    'Use --update flag to update existing package.'
                )
            else:
                raise CommandError(f'Error creating package: {str(e)}')

    def validate_positive_number(self, value, field_name):
        """Validate that a number is positive"""
        if value <= 0:
            raise CommandError(f'{field_name} must be a positive number')