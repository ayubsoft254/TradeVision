# apps/payments/management/commands/test_merchant_payments.py
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from apps.payments.models import P2PMerchant, PaymentMethod
from apps.payments.forms import P2PForm

User = get_user_model()


class Command(BaseCommand):
    help = 'Test merchant payment method functionality'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('=== Testing Merchant Payment Methods ===\n'))
        
        # Check merchants and their payment methods
        merchants = P2PMerchant.objects.all()
        self.stdout.write(f"Total merchants: {merchants.count()}")
        
        for merchant in merchants:
            methods = merchant.payment_methods.all()
            self.stdout.write(
                self.style.SUCCESS(f"✅ {merchant.name} ({merchant.country}): {methods.count()} methods")
            )
            for method in methods:
                self.stdout.write(f"   - {method.display_name}")
            self.stdout.write('')
        
        # Test form with a Kenyan user
        self.stdout.write(self.style.SUCCESS('=== Testing P2P Form ===\n'))
        user = User.objects.filter(country='KE').first()
        if user:
            self.stdout.write(f"Testing with user: {user.email} (Country: {user.country})")
            
            form = P2PForm(user=user, transaction_type='deposit')
            
            merchants_queryset = form.fields['merchant'].queryset
            methods_queryset = form.fields['payment_method'].queryset
            
            self.stdout.write(f"Available merchants: {merchants_queryset.count()}")
            for merchant in merchants_queryset:
                self.stdout.write(f"  - {merchant.name}")
            
            self.stdout.write(f"Available payment methods: {methods_queryset.count()}")
            for method in methods_queryset:
                self.stdout.write(f"  - {method.display_name}")
            
            # Test merchant-method compatibility
            self.stdout.write(self.style.SUCCESS('\n=== Testing Merchant-Method Compatibility ==='))
            for merchant in merchants_queryset:
                merchant_methods = merchant.payment_methods.all()
                self.stdout.write(f"{merchant.name} supports:")
                for method in merchant_methods:
                    available_in_form = method in methods_queryset
                    status = "✅" if available_in_form else "❌"
                    self.stdout.write(f"  {status} {method.display_name}")
                    
            # Test that form validation works
            self.stdout.write(self.style.SUCCESS('\n=== Testing Form Validation ==='))
            if merchants_queryset.exists() and methods_queryset.exists():
                merchant = merchants_queryset.first()
                compatible_methods = merchant.payment_methods.filter(
                    id__in=methods_queryset.values_list('id', flat=True)
                )
                
                if compatible_methods.exists():
                    method = compatible_methods.first()
                    form_data = {
                        'amount': '100.00',
                        'merchant': merchant.id,
                        'payment_method': method.id,
                        'account_details': '+254700000000'
                    }
                    
                    test_form = P2PForm(form_data, user=user, transaction_type='deposit')
                    if test_form.is_valid():
                        self.stdout.write(
                            self.style.SUCCESS(f"✅ Form validation passed: {merchant.name} + {method.display_name}")
                        )
                    else:
                        self.stdout.write(
                            self.style.ERROR(f"❌ Form validation failed: {test_form.errors}")
                        )
                else:
                    self.stdout.write(
                        self.style.WARNING("⚠️ No compatible payment methods found for selected merchant")
                    )
            else:
                self.stdout.write(
                    self.style.WARNING("⚠️ No merchants or payment methods available for testing")
                )
                
        else:
            self.stdout.write(self.style.WARNING("No Kenyan user found for testing"))
            
        self.stdout.write(self.style.SUCCESS('\n=== Test Complete ==='))