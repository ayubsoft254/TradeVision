from django.core.management.base import BaseCommand
from apps.payments.models import PaymentMethod

class Command(BaseCommand):
    help = 'Test PaymentMethod creation with country selection'

    def handle(self, *args, **options):
        self.stdout.write('Testing PaymentMethod creation...')
        
        # Test creating a payment method with countries
        try:
            # Test 1: Create with list of countries
            method1 = PaymentMethod.objects.create(
                name='mobile_money',
                display_name='MTN Mobile Money',
                countries=['ZM', 'UG', 'TZ'],
                is_active=True,
                min_amount=10.00,
                max_amount=1000.00,
                processing_fee=2.5,
                processing_time='5-10 minutes'
            )
            self.stdout.write(self.style.SUCCESS(f'✅ Created method1: {method1.display_name}'))
            self.stdout.write(f'Countries stored as: {method1.countries} (type: {type(method1.countries)})')
            
            # Test 2: Create with empty countries
            method2 = PaymentMethod.objects.create(
                name='crypto',
                display_name='Cryptocurrency',
                countries=[],
                is_active=True,
                min_amount=50.00,
                processing_fee=1.0,
                processing_time='Instant'
            )
            self.stdout.write(self.style.SUCCESS(f'✅ Created method2: {method2.display_name}'))
            self.stdout.write(f'Countries stored as: {method2.countries} (type: {type(method2.countries)})')
            
            # Test 3: Query and display
            all_methods = PaymentMethod.objects.all()
            self.stdout.write('\n📋 All PaymentMethods:')
            for method in all_methods:
                self.stdout.write(f'- {method.display_name}: {method.countries}')
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Error: {str(e)}'))
            import traceback
            self.stdout.write(traceback.format_exc())