from django.core.management.base import BaseCommand
from apps.payments.models import PaymentMethod
from apps.payments.admin import PaymentMethodAdminForm

class Command(BaseCommand):
    help = 'Test PaymentMethod admin form functionality'

    def handle(self, *args, **options):
        self.stdout.write('Testing PaymentMethod admin form...')
        
        try:
            # Get an existing payment method with old format
            old_method = PaymentMethod.objects.filter(
                countries__isnull=False
            ).exclude(countries__exact=[]).first()
            
            if old_method:
                self.stdout.write(f'📋 Testing with existing method: {old_method.display_name}')
                self.stdout.write(f'   Current countries data: {old_method.countries} (type: {type(old_method.countries)})')
                
                # Create a form instance for editing
                form = PaymentMethodAdminForm(instance=old_method)
                
                self.stdout.write(f'   Form initial data: {form.initial.get("available_countries", "NOT SET")}')
                
                # Test form rendering (this will trigger __init__)
                countries_field = form.fields['available_countries']
                self.stdout.write(f'   Available choices: {[choice[0] for choice in countries_field.choices]}')
                
            else:
                self.stdout.write('⚠️  No existing payment methods found to test')
                
            # Test creating a new form
            self.stdout.write('\n🆕 Testing new form creation...')
            new_form = PaymentMethodAdminForm()
            self.stdout.write(f'   New form initial countries: {new_form.initial.get("available_countries", "EMPTY")}')
            
            # Test form data processing
            self.stdout.write('\n🧪 Testing form validation...')
            test_data = {
                'name': 'mobile_money',
                'display_name': 'Test Mobile Money',
                'available_countries': ['ZM', 'UG'],
                'is_active': True,
                'min_amount': 10,
                'max_amount': 1000,
                'processing_fee': 2.5,
                'processing_time': '5 minutes'
            }
            
            test_form = PaymentMethodAdminForm(data=test_data)
            if test_form.is_valid():
                self.stdout.write('✅ Form validation passed')
                self.stdout.write(f'   Clean data countries: {test_form.cleaned_data.get("countries")}')
            else:
                self.stdout.write('❌ Form validation failed:')
                for field, errors in test_form.errors.items():
                    self.stdout.write(f'   {field}: {errors}')
                    
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Error: {str(e)}'))
            import traceback
            self.stdout.write(traceback.format_exc())