from django.core.management.base import BaseCommand
from apps.payments.models import PaymentMethod
from apps.payments.admin import PaymentMethodAdminForm

class Command(BaseCommand):
    help = 'Test complete PaymentMethod admin form save process'

    def handle(self, *args, **options):
        self.stdout.write('Testing complete PaymentMethod admin form save...')
        
        try:
            # Test 1: Create a new payment method via form
            self.stdout.write('\n🆕 Creating new PaymentMethod via admin form...')
            new_form_data = {
                'name': 'mobile_money',
                'display_name': 'Vodacom M-Pesa',
                'available_countries': ['TZ', 'CD'],
                'is_active': True,
                'min_amount': 5,
                'max_amount': 500,
                'processing_fee': 1.5,
                'processing_time': 'Instant'
            }
            
            new_form = PaymentMethodAdminForm(data=new_form_data)
            if new_form.is_valid():
                saved_method = new_form.save()
                self.stdout.write(f'✅ Created: {saved_method.display_name}')
                self.stdout.write(f'   Countries: {saved_method.countries}')
                self.stdout.write(f'   Type: {type(saved_method.countries)}')
            else:
                self.stdout.write('❌ Form validation failed:')
                for field, errors in new_form.errors.items():
                    self.stdout.write(f'   {field}: {errors}')
            
            # Test 2: Edit an existing payment method with old format
            old_method = PaymentMethod.objects.filter(
                countries__isnull=False
            ).exclude(countries__exact=[]).first()
            
            if old_method:
                self.stdout.write(f'\n🔧 Editing existing method: {old_method.display_name}')
                self.stdout.write(f'   Before: {old_method.countries}')
                
                # Create form with existing data and new selection
                edit_form_data = {
                    'name': old_method.name,
                    'display_name': old_method.display_name,
                    'available_countries': ['ZM', 'KE'],  # Change countries
                    'is_active': old_method.is_active,
                    'min_amount': old_method.min_amount,
                    'max_amount': old_method.max_amount,
                    'processing_fee': old_method.processing_fee,
                    'processing_time': old_method.processing_time
                }
                
                edit_form = PaymentMethodAdminForm(data=edit_form_data, instance=old_method)
                if edit_form.is_valid():
                    updated_method = edit_form.save()
                    self.stdout.write(f'✅ Updated: {updated_method.display_name}')
                    self.stdout.write(f'   After: {updated_method.countries}')
                    self.stdout.write(f'   Type: {type(updated_method.countries)}')
                else:
                    self.stdout.write('❌ Edit form validation failed:')
                    for field, errors in edit_form.errors.items():
                        self.stdout.write(f'   {field}: {errors}')
            
            # Test 3: Show final state
            self.stdout.write('\n📊 Final PaymentMethod states:')
            all_methods = PaymentMethod.objects.all()
            for method in all_methods:
                countries_format = "new" if isinstance(method.countries, list) else "old"
                self.stdout.write(f'   {method.display_name}: {method.countries} ({countries_format})')
                    
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Error: {str(e)}'))
            import traceback
            self.stdout.write(traceback.format_exc())