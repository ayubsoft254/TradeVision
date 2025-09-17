from django.core.management.base import BaseCommand
from apps.payments.models import P2PMerchant

class Command(BaseCommand):
    help = 'Display all merchant payment details in a formatted way'
    
    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("🏪 P2P MERCHANT PAYMENT DETAILS"))
        self.stdout.write("=" * 60)
        
        merchants = P2PMerchant.objects.all().order_by('country', 'name')
        
        for merchant in merchants:
            self.stdout.write(f"\n📍 {merchant.name} (@{merchant.username}) - {merchant.country}")
            self.stdout.write("-" * 50)
            
            # Basic info
            self.stdout.write(f"   📧 Email: {merchant.email}")
            self.stdout.write(f"   📱 Phone: {merchant.phone_number}")
            self.stdout.write(f"   ⭐ Rating: {merchant.rating}/5.0")
            self.stdout.write(f"   ✅ Verified: {'Yes' if merchant.is_verified else 'No'}")
            self.stdout.write(f"   🟢 Active: {'Yes' if merchant.is_active else 'No'}")
            
            # Payment Methods
            self.stdout.write(f"   💳 Payment Methods:")
            payment_methods = merchant.payment_methods.all()
            if payment_methods.exists():
                for method in payment_methods:
                    self.stdout.write(f"      • {method.display_name} ({method.processing_fee}% fee)")
            else:
                self.stdout.write("      • No payment methods configured")
            
            # Mobile Money Details
            mobile_details = merchant.get_mobile_money_details()
            if mobile_details:
                self.stdout.write(f"   📱 Mobile Money Details:")
                self.stdout.write(f"      Provider: {mobile_details['provider']}")
                self.stdout.write(f"      Number: {mobile_details['number']}")
                self.stdout.write(f"      Name: {mobile_details['name']}")
            else:
                self.stdout.write("   📱 Mobile Money: Not configured")
            
            # Bank Transfer Details
            bank_details = merchant.get_bank_transfer_details()
            if bank_details:
                self.stdout.write(f"   🏦 Bank Transfer Details:")
                self.stdout.write(f"      Bank: {bank_details['bank_name']}")
                self.stdout.write(f"      Account Number: {bank_details['account_number']}")
                self.stdout.write(f"      Account Name: {bank_details['account_name']}")
                if bank_details['branch']:
                    self.stdout.write(f"      Branch: {bank_details['branch']}")
                if bank_details['swift_code']:
                    self.stdout.write(f"      SWIFT Code: {bank_details['swift_code']}")
            else:
                self.stdout.write("   🏦 Bank Transfer: Not configured")
            
            # Business details
            self.stdout.write(f"   💼 Business Info:")
            self.stdout.write(f"      Commission: {merchant.commission_rate}%")
            self.stdout.write(f"      Min Order: {merchant.min_order_amount}")
            self.stdout.write(f"      Max Order: {merchant.max_order_amount}")
            self.stdout.write(f"      Completion Rate: {merchant.completion_rate}%")
            self.stdout.write(f"      Total Orders: {merchant.total_orders}")
        
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(self.style.SUCCESS(f"📊 Total merchants: {merchants.count()}"))
        
        # Summary by country
        countries = merchants.values_list('country', flat=True).distinct()
        for country in countries:
            count = merchants.filter(country=country).count()
            active_count = merchants.filter(country=country, is_active=True).count()
            verified_count = merchants.filter(country=country, is_verified=True).count()
            self.stdout.write(f"   {country}: {count} total ({active_count} active, {verified_count} verified)")
        
        # Payment method coverage
        self.stdout.write(f"\n💳 Payment Method Coverage:")
        mm_merchants = merchants.filter(mobile_money_provider__isnull=False).exclude(mobile_money_provider='').count()
        bank_merchants = merchants.filter(bank_name__isnull=False).exclude(bank_name='').count()
        self.stdout.write(f"   📱 Mobile Money: {mm_merchants}/{merchants.count()} merchants")
        self.stdout.write(f"   🏦 Bank Transfer: {bank_merchants}/{merchants.count()} merchants")