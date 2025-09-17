from django.core.management.base import BaseCommand
from apps.payments.models import P2PMerchant

class Command(BaseCommand):
    help = 'Update existing P2P merchants with payment details'
    
    def handle(self, *args, **options):
        self.stdout.write("Updating P2P merchants with payment details...")
        
        # Sample payment details for different merchants
        merchant_details = {
            'John Kamau': {
                'mobile_money_provider': 'M-Pesa',
                'mobile_money_number': '+254712345678',
                'mobile_money_name': 'John Kamau',
                'bank_name': 'Kenya Commercial Bank',
                'bank_account_number': '1234567890',
                'bank_account_name': 'John Kamau',
                'bank_branch': 'Nairobi CBD'
            },
            'Peter Mwangi': {
                'mobile_money_provider': 'Airtel Money',
                'mobile_money_number': '+254723456789',
                'mobile_money_name': 'Peter Mwangi',
                'bank_name': 'Equity Bank',
                'bank_account_number': '0987654321',
                'bank_account_name': 'Peter Mwangi',
                'bank_branch': 'Westlands'
            },
            'Sarah Nakato': {
                'mobile_money_provider': 'MTN Mobile Money',
                'mobile_money_number': '+256712345678',
                'mobile_money_name': 'Sarah Nakato',
                'bank_name': 'Stanbic Bank Uganda',
                'bank_account_number': '1122334455',
                'bank_account_name': 'Sarah Nakato',
                'bank_branch': 'Kampala Main'
            },
            'Grace Mwanza': {
                'mobile_money_provider': 'MTN Mobile Money',
                'mobile_money_number': '+260977123456',
                'mobile_money_name': 'Grace Mwanza',
                'bank_name': 'Standard Chartered Zambia',
                'bank_account_number': '5566778899',
                'bank_account_name': 'Grace Mwanza',
                'bank_branch': 'Lusaka'
            },
            'Emmanuel Kinyua': {
                'mobile_money_provider': 'Tigo Pesa',
                'mobile_money_number': '+255712345678',
                'mobile_money_name': 'Emmanuel Kinyua',
                'bank_name': 'CRDB Bank',
                'bank_account_number': '3344556677',
                'bank_account_name': 'Emmanuel Kinyua',
                'bank_branch': 'Dar es Salaam'
            },
            'Marie Kasongo': {
                'mobile_money_provider': 'Orange Money',
                'mobile_money_number': '+243912345678',
                'mobile_money_name': 'Marie Kasongo',
                'bank_name': 'TMB Bank',
                'bank_account_number': '7788990011',
                'bank_account_name': 'Marie Kasongo',
                'bank_branch': 'Kinshasa',
                'bank_swift_code': 'TMBKCDKI'
            }
        }
        
        updated_count = 0
        
        for merchant in P2PMerchant.objects.all():
            if merchant.name in merchant_details:
                details = merchant_details[merchant.name]
                
                # Update payment details
                for field, value in details.items():
                    setattr(merchant, field, value)
                
                merchant.save()
                updated_count += 1
                
                self.stdout.write(f"✅ Updated {merchant.name} with payment details")
                
                # Display the payment details for verification
                mm_details = merchant.get_mobile_money_details()
                if mm_details:
                    self.stdout.write(f"   Mobile Money: {mm_details['provider']} - {mm_details['number']}")
                
                bank_details = merchant.get_bank_transfer_details()
                if bank_details:
                    self.stdout.write(f"   Bank: {bank_details['bank_name']} - {bank_details['account_number']}")
                
                self.stdout.write("")
        
        self.stdout.write(self.style.SUCCESS(f"\n🎉 Successfully updated {updated_count} merchants with payment details!"))
        
        # Display summary of all merchants with payment details
        self.stdout.write("\n📋 Merchant Payment Details Summary:")
        for merchant in P2PMerchant.objects.all():
            self.stdout.write(f"\n{merchant.name} ({merchant.country}):")
            
            # Check mobile money
            mm_details = merchant.get_mobile_money_details()
            if mm_details:
                self.stdout.write(f"  📱 Mobile Money: {mm_details['provider']} ({mm_details['number']})")
            else:
                self.stdout.write("  📱 Mobile Money: Not configured")
            
            # Check bank transfer
            bank_details = merchant.get_bank_transfer_details()
            if bank_details:
                self.stdout.write(f"  🏦 Bank Transfer: {bank_details['bank_name']} ({bank_details['account_number']})")
            else:
                self.stdout.write("  🏦 Bank Transfer: Not configured")
            
            # Check payment methods
            methods = merchant.payment_methods.all()
            if methods.exists():
                method_names = [m.display_name for m in methods]
                self.stdout.write(f"  💳 Payment Methods: {', '.join(method_names)}")
            else:
                self.stdout.write("  💳 Payment Methods: None selected")
        
        self.stdout.write("")