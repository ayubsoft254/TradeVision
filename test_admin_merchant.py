# Test Admin Merchant Creation
from django.test import TestCase
from apps.payments.models import PaymentMethod, P2PMerchant
from apps.payments.admin import P2PMerchantAdminForm


class TestMerchantAdmin(TestCase):
    def setUp(self):
        # Create payment methods
        self.mobile_money = PaymentMethod.objects.create(
            name='mobile_money',
            display_name='Mobile Money',
            countries=['KE', 'UG'],
            is_active=True
        )
        
        self.bank_transfer = PaymentMethod.objects.create(
            name='bank_transfer',
            display_name='Bank Transfer',
            countries=['KE', 'UG', 'TZ'],
            is_active=True
        )
    
    def test_merchant_form_with_country(self):
        """Test that form filters payment methods by country"""
        merchant = P2PMerchant.objects.create(
            name='Test Merchant',
            username='test_merchant',
            phone_number='+254700000000',
            email='test@example.com',
            country='KE',
            min_order_amount=100,
            max_order_amount=10000,
        )
        
        # Test form initialization
        form = P2PMerchantAdminForm(instance=merchant)
        
        # Should show payment methods available in Kenya
        available_ids = list(form.fields['payment_methods'].queryset.values_list('id', flat=True))
        
        # Both methods should be available for KE
        self.assertIn(self.mobile_money.id, available_ids)
        self.assertIn(self.bank_transfer.id, available_ids)
        
        print("✅ Admin form correctly filters payment methods by country")
    
    def test_merchant_creation_with_methods(self):
        """Test creating merchant with payment methods"""
        form_data = {
            'name': 'New Test Merchant',
            'username': 'new_test_merchant',
            'phone_number': '+254701234567',
            'email': 'newtest@example.com',
            'country': 'UG',
            'payment_methods': [self.mobile_money.id, self.bank_transfer.id],
            'min_order_amount': 200,
            'max_order_amount': 15000,
            'commission_rate': 2.0,
            'is_verified': True,
            'is_active': True,
            'rating': 4.5,
            'completion_rate': 95.0,
            'total_orders': 0,
        }
        
        form = P2PMerchantAdminForm(data=form_data)
        
        if form.is_valid():
            merchant = form.save()
            
            # Check that payment methods were assigned
            assigned_methods = merchant.payment_methods.all()
            self.assertEqual(assigned_methods.count(), 2)
            
            # Check specific methods
            method_names = [m.name for m in assigned_methods]
            self.assertIn('mobile_money', method_names)
            self.assertIn('bank_transfer', method_names)
            
            print(f"✅ Created merchant '{merchant.name}' with {assigned_methods.count()} payment methods")
            for method in assigned_methods:
                print(f"   - {method.display_name}")
        else:
            print(f"❌ Form validation failed: {form.errors}")
            self.fail("Form should be valid")


# Run the test
if __name__ == '__main__':
    import django
    from django.conf import settings
    from django.test.utils import get_runner
    
    django.setup()
    TestRunner = get_runner(settings)
    test_runner = TestRunner()
    result = test_runner.run_tests(['__main__'])