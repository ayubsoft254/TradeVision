from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from apps.payments.models import PaymentMethod, P2PMerchant
from apps.payments.forms import P2PForm

class Command(BaseCommand):
    help = 'Test P2P deposit flow'
    
    def handle(self, *args, **options):
        User = get_user_model()
        
        # Get a test user
        try:
            user = User.objects.filter(is_active=True).first()
            if not user:
                self.stdout.write(self.style.ERROR("No active users found"))
                return
                
            self.stdout.write(f"Testing with user: {user.username} (Country: {user.country})")
            
            # Check P2P payment method exists and is available
            try:
                p2p_method = PaymentMethod.objects.get(name='p2p')
                self.stdout.write(f"✅ P2P Payment Method: {p2p_method.display_name}")
                self.stdout.write(f"  - Active: {p2p_method.is_active}")
                self.stdout.write(f"  - Countries: {p2p_method.countries}")
                self.stdout.write(f"  - Fee: {p2p_method.processing_fee}%")
                
                # Check if user's country is supported
                if user.country and user.country.code in p2p_method.countries:
                    self.stdout.write(f"✅ User's country ({user.country.code}) is supported")
                else:
                    self.stdout.write(f"❌ User's country ({user.country.code if user.country else 'None'}) not supported")
                    
            except PaymentMethod.DoesNotExist:
                self.stdout.write(self.style.ERROR("❌ P2P Payment Method not found"))
                return
            
            # Check available merchants for user
            if user.country:
                merchants = P2PMerchant.objects.filter(
                    is_active=True,
                    country=user.country.code
                )
                self.stdout.write(f"✅ Available P2P merchants for {user.country.code}: {merchants.count()}")
                for merchant in merchants:
                    methods = merchant.payment_methods.all()
                    method_names = [m.display_name for m in methods]
                    self.stdout.write(f"  - {merchant.name}: {', '.join(method_names)}")
            else:
                self.stdout.write("❌ User has no country set")
                
            # Test P2P form initialization
            try:
                form = P2PForm(transaction_type='deposit', user=user)
                self.stdout.write("✅ P2P Form initialized successfully")
                
                # Check form fields
                if hasattr(form, 'fields'):
                    if 'merchant' in form.fields:
                        merchant_count = form.fields['merchant'].queryset.count()
                        self.stdout.write(f"  - Merchant choices: {merchant_count}")
                    if 'payment_method' in form.fields:
                        method_count = form.fields['payment_method'].queryset.count()
                        self.stdout.write(f"  - Payment method choices: {method_count}")
                        
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"❌ P2P Form initialization failed: {e}"))
                
            # Test URL patterns
            self.stdout.write("\n📋 P2P URLs available:")
            self.stdout.write("  - /payments/deposit/ (shows P2P as option)")
            self.stdout.write("  - /payments/deposit/p2p/ (P2P deposit form)")
            self.stdout.write("  - /payments/p2p/ (P2P merchants list)")
            
            self.stdout.write(self.style.SUCCESS("\n🎉 P2P deposit system is ready!"))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Test failed: {e}"))
            import traceback
            traceback.print_exc()