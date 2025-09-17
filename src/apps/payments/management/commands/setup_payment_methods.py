# apps/payments/management/commands/setup_payment_methods.py
from django.core.management.base import BaseCommand
from apps.payments.models import PaymentMethod


class Command(BaseCommand):
    help = 'Set up default payment methods with country support'

    def handle(self, *args, **options):
        self.stdout.write("Setting up payment methods...")
        
        # Payment methods data
        payment_methods = [
            {
                'name': 'mobile_money',
                'display_name': 'Mobile Money',
                'countries': ['KE', 'UG', 'TZ', 'ZM'],
                'min_amount': 10.00,
                'max_amount': 50000.00,
                'processing_fee': 2.5,
                'processing_time': '5-10 minutes'
            },
            {
                'name': 'bank_transfer',
                'display_name': 'Bank Transfer',
                'countries': ['KE', 'UG', 'TZ', 'ZM', 'CD'],
                'min_amount': 50.00,
                'max_amount': 100000.00,
                'processing_fee': 1.5,
                'processing_time': '1-24 hours'
            },
            {
                'name': 'binance_pay',
                'display_name': 'Binance Pay',
                'countries': ['KE', 'UG', 'TZ', 'ZM', 'CD'],
                'min_amount': 5.00,
                'max_amount': 200000.00,
                'processing_fee': 0.5,
                'processing_time': 'Instant'
            },
            {
                'name': 'crypto',
                'display_name': 'Cryptocurrency',
                'countries': ['KE', 'UG', 'TZ', 'ZM', 'CD'],
                'min_amount': 20.00,
                'max_amount': 500000.00,
                'processing_fee': 1.0,
                'processing_time': '10-30 minutes'
            },
            {
                'name': 'agent',
                'display_name': 'Local Agent (Cash)',
                'countries': ['KE', 'UG', 'TZ', 'ZM', 'CD'],
                'min_amount': 20.00,
                'max_amount': 10000.00,
                'processing_fee': 3.0,
                'processing_time': '30 minutes - 2 hours'
            },
        ]
        
        created_count = 0
        updated_count = 0
        
        for method_data in payment_methods:
            payment_method, created = PaymentMethod.objects.get_or_create(
                name=method_data['name'],
                defaults={
                    'display_name': method_data['display_name'],
                    'countries': method_data['countries'],
                    'min_amount': method_data['min_amount'],
                    'max_amount': method_data['max_amount'],
                    'processing_fee': method_data['processing_fee'],
                    'processing_time': method_data['processing_time'],
                    'is_active': True
                }
            )
            
            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f"✓ Created: {payment_method.display_name}")
                )
            else:
                # Update existing payment method
                payment_method.display_name = method_data['display_name']
                payment_method.countries = method_data['countries']
                payment_method.min_amount = method_data['min_amount']
                payment_method.max_amount = method_data['max_amount']
                payment_method.processing_fee = method_data['processing_fee']
                payment_method.processing_time = method_data['processing_time']
                payment_method.is_active = True
                payment_method.save()
                
                updated_count += 1
                self.stdout.write(
                    self.style.WARNING(f"↻ Updated: {payment_method.display_name}")
                )
        
        self.stdout.write(f"\n=== Summary ===")
        self.stdout.write(f"Created: {created_count} payment methods")
        self.stdout.write(f"Updated: {updated_count} payment methods")
        
        # Show all active payment methods by country
        self.stdout.write(f"\n=== Payment Methods by Country ===")
        countries = {
            'KE': 'Kenya',
            'UG': 'Uganda',
            'TZ': 'Tanzania',
            'ZM': 'Zambia',
            'CD': 'Democratic Republic of Congo'
        }
        
        for code, name in countries.items():
            # Use icontains for SQLite compatibility instead of contains
            methods = PaymentMethod.objects.filter(
                is_active=True,
                countries__icontains=f'"{code}"'
            ).order_by('display_name')
            
            self.stdout.write(f"\n{name} ({code}):")
            for method in methods:
                self.stdout.write(f"  • {method.display_name} (${method.min_amount}-${method.max_amount}, {method.processing_fee}% fee)")
        
        self.stdout.write(
            self.style.SUCCESS(f"\n✓ Payment methods setup complete!")
        )