from django.core.management.base import BaseCommand
from apps.payments.models import P2PMerchant, PaymentMethod
from decimal import Decimal

class Command(BaseCommand):
    help = 'Add 4 P2P merchants for each country with mobile payment details'
    
    def handle(self, *args, **options):
        self.stdout.write("Creating P2P merchants for all countries...")
        
        # Country-specific merchant data
        merchants_data = {
            'KE': [  # Kenya
                {
                    'name': 'David Kiprotich',
                    'username': 'david_kiprotich_ke',
                    'email': 'david.kiprotich@example.com',
                    'phone': '+254722123456',
                    'mobile_provider': 'M-Pesa',
                    'mobile_number': '+254722123456',
                    'commission': Decimal('1.30'),
                    'min_order': Decimal('200'),
                    'max_order': Decimal('75000')
                },
                {
                    'name': 'Alice Wanjiku',
                    'username': 'alice_wanjiku_ke',
                    'email': 'alice.wanjiku@example.com',
                    'phone': '+254733234567',
                    'mobile_provider': 'Airtel Money',
                    'mobile_number': '+254733234567',
                    'commission': Decimal('1.40'),
                    'min_order': Decimal('300'),
                    'max_order': Decimal('60000')
                },
                {
                    'name': 'Michael Ochieng',
                    'username': 'michael_ochieng_ke',
                    'email': 'michael.ochieng@example.com',
                    'phone': '+254744345678',
                    'mobile_provider': 'M-Pesa',
                    'mobile_number': '+254744345678',
                    'commission': Decimal('1.25'),
                    'min_order': Decimal('500'),
                    'max_order': Decimal('80000')
                },
                {
                    'name': 'Grace Njeri',
                    'username': 'grace_njeri_ke',
                    'email': 'grace.njeri@example.com',
                    'phone': '+254755456789',
                    'mobile_provider': 'Safaricom M-Pesa',
                    'mobile_number': '+254755456789',
                    'commission': Decimal('1.35'),
                    'min_order': Decimal('250'),
                    'max_order': Decimal('70000')
                }
            ],
            'UG': [  # Uganda
                {
                    'name': 'Robert Ssemakula',
                    'username': 'robert_ssemakula_ug',
                    'email': 'robert.ssemakula@example.com',
                    'phone': '+256766123456',
                    'mobile_provider': 'MTN Mobile Money',
                    'mobile_number': '+256766123456',
                    'commission': Decimal('1.60'),
                    'min_order': Decimal('150'),
                    'max_order': Decimal('45000')
                },
                {
                    'name': 'Catherine Namusoke',
                    'username': 'catherine_namusoke_ug',
                    'email': 'catherine.namusoke@example.com',
                    'phone': '+256777234567',
                    'mobile_provider': 'Airtel Money',
                    'mobile_number': '+256777234567',
                    'commission': Decimal('1.70'),
                    'min_order': Decimal('100'),
                    'max_order': Decimal('35000')
                },
                {
                    'name': 'Joseph Kiwanuka',
                    'username': 'joseph_kiwanuka_ug',
                    'email': 'joseph.kiwanuka@example.com',
                    'phone': '+256788345678',
                    'mobile_provider': 'MTN Mobile Money',
                    'mobile_number': '+256788345678',
                    'commission': Decimal('1.55'),
                    'min_order': Decimal('200'),
                    'max_order': Decimal('50000')
                },
                {
                    'name': 'Diana Nalubega',
                    'username': 'diana_nalubega_ug',
                    'email': 'diana.nalubega@example.com',
                    'phone': '+256799456789',
                    'mobile_provider': 'M-Sente',
                    'mobile_number': '+256799456789',
                    'commission': Decimal('1.65'),
                    'min_order': Decimal('180'),
                    'max_order': Decimal('40000')
                }
            ],
            'TZ': [  # Tanzania
                {
                    'name': 'Hassan Mwalimu',
                    'username': 'hassan_mwalimu_tz',
                    'email': 'hassan.mwalimu@example.com',
                    'phone': '+255754123456',
                    'mobile_provider': 'M-Pesa Tanzania',
                    'mobile_number': '+255754123456',
                    'commission': Decimal('1.50'),
                    'min_order': Decimal('300'),
                    'max_order': Decimal('55000')
                },
                {
                    'name': 'Fatuma Juma',
                    'username': 'fatuma_juma_tz',
                    'email': 'fatuma.juma@example.com',
                    'phone': '+255765234567',
                    'mobile_provider': 'Tigo Pesa',
                    'mobile_number': '+255765234567',
                    'commission': Decimal('1.75'),
                    'min_order': Decimal('250'),
                    'max_order': Decimal('45000')
                },
                {
                    'name': 'John Mwamba',
                    'username': 'john_mwamba_tz',
                    'email': 'john.mwamba@example.com',
                    'phone': '+255776345678',
                    'mobile_provider': 'Airtel Money',
                    'mobile_number': '+255776345678',
                    'commission': Decimal('1.45'),
                    'min_order': Decimal('400'),
                    'max_order': Decimal('65000')
                },
                {
                    'name': 'Amina Rajabu',
                    'username': 'amina_rajabu_tz',
                    'email': 'amina.rajabu@example.com',
                    'phone': '+255787456789',
                    'mobile_provider': 'HaloPesa',
                    'mobile_number': '+255787456789',
                    'commission': Decimal('1.80'),
                    'min_order': Decimal('200'),
                    'max_order': Decimal('38000')
                }
            ],
            'ZM': [  # Zambia
                {
                    'name': 'Patrick Mwanza',
                    'username': 'patrick_mwanza_zm',
                    'email': 'patrick.mwanza@example.com',
                    'phone': '+260966123456',
                    'mobile_provider': 'MTN Mobile Money',
                    'mobile_number': '+260966123456',
                    'commission': Decimal('1.90'),
                    'min_order': Decimal('200'),
                    'max_order': Decimal('35000')
                },
                {
                    'name': 'Mercy Banda',
                    'username': 'mercy_banda_zm',
                    'email': 'mercy.banda@example.com',
                    'phone': '+260977234567',
                    'mobile_provider': 'Airtel Money',
                    'mobile_number': '+260977234567',
                    'commission': Decimal('2.10'),
                    'min_order': Decimal('150'),
                    'max_order': Decimal('28000')
                },
                {
                    'name': 'Charles Phiri',
                    'username': 'charles_phiri_zm',
                    'email': 'charles.phiri@example.com',
                    'phone': '+260988345678',
                    'mobile_provider': 'MTN Mobile Money',
                    'mobile_number': '+260988345678',
                    'commission': Decimal('1.85'),
                    'min_order': Decimal('250'),
                    'max_order': Decimal('42000')
                },
                {
                    'name': 'Janet Tembo',
                    'username': 'janet_tembo_zm',
                    'email': 'janet.tembo@example.com',
                    'phone': '+260999456789',
                    'mobile_provider': 'Zamtel Kwacha',
                    'mobile_number': '+260999456789',
                    'commission': Decimal('2.05'),
                    'min_order': Decimal('180'),
                    'max_order': Decimal('32000')
                }
            ],
            'CD': [  # Democratic Republic of Congo
                {
                    'name': 'Jean-Baptiste Mukendi',
                    'username': 'jean_mukendi_cd',
                    'email': 'jean.mukendi@example.com',
                    'phone': '+243810123456',
                    'mobile_provider': 'Orange Money',
                    'mobile_number': '+243810123456',
                    'commission': Decimal('2.50'),
                    'min_order': Decimal('500'),
                    'max_order': Decimal('25000')
                },
                {
                    'name': 'Claudine Tshimanga',
                    'username': 'claudine_tshimanga_cd',
                    'email': 'claudine.tshimanga@example.com',
                    'phone': '+243821234567',
                    'mobile_provider': 'Vodacom M-Pesa',
                    'mobile_number': '+243821234567',
                    'commission': Decimal('2.30'),
                    'min_order': Decimal('400'),
                    'max_order': Decimal('30000')
                },
                {
                    'name': 'Pierre Kabongo',
                    'username': 'pierre_kabongo_cd',
                    'email': 'pierre.kabongo@example.com',
                    'phone': '+243832345678',
                    'mobile_provider': 'Airtel Money',
                    'mobile_number': '+243832345678',
                    'commission': Decimal('2.40'),
                    'min_order': Decimal('600'),
                    'max_order': Decimal('28000')
                },
                {
                    'name': 'Esperance Mvita',
                    'username': 'esperance_mvita_cd',
                    'email': 'esperance.mvita@example.com',
                    'phone': '+243843456789',
                    'mobile_provider': 'Orange Money',
                    'mobile_number': '+243843456789',
                    'commission': Decimal('2.60'),
                    'min_order': Decimal('350'),
                    'max_order': Decimal('22000')
                }
            ]
        }
        
        # Get payment methods
        try:
            mobile_money = PaymentMethod.objects.get(name='mobile_money')
            p2p_method = PaymentMethod.objects.get(name='p2p')
        except PaymentMethod.DoesNotExist as e:
            self.stdout.write(self.style.ERROR(f"Required payment method not found: {e}"))
            return
        
        created_count = 0
        updated_count = 0
        
        for country_code, merchants in merchants_data.items():
            country_name = dict(P2PMerchant.COUNTRY_CHOICES)[country_code]
            self.stdout.write(f"\n🌍 Creating merchants for {country_name} ({country_code})")
            
            for merchant_data in merchants:
                # Check if merchant already exists
                merchant, created = P2PMerchant.objects.get_or_create(
                    username=merchant_data['username'],
                    defaults={
                        'name': merchant_data['name'],
                        'email': merchant_data['email'],
                        'phone_number': merchant_data['phone'],
                        'country': country_code,
                        'is_verified': True,
                        'is_active': True,
                        'commission_rate': merchant_data['commission'],
                        'min_order_amount': merchant_data['min_order'],
                        'max_order_amount': merchant_data['max_order'],
                        'completion_rate': Decimal('96.5'),
                        'total_orders': 85,
                        'rating': Decimal('4.6'),
                        # Mobile money details
                        'mobile_money_provider': merchant_data['mobile_provider'],
                        'mobile_money_number': merchant_data['mobile_number'],
                        'mobile_money_name': merchant_data['name'],
                    }
                )
                
                if created:
                    # Add payment methods
                    merchant.payment_methods.add(mobile_money, p2p_method)
                    created_count += 1
                    self.stdout.write(f"  ✅ Created: {merchant.name} (@{merchant.username})")
                    self.stdout.write(f"     📱 {merchant_data['mobile_provider']}: {merchant_data['mobile_number']}")
                    self.stdout.write(f"     💰 Commission: {merchant_data['commission']}%")
                    self.stdout.write(f"     📊 Range: {merchant_data['min_order']} - {merchant_data['max_order']}")
                else:
                    # Update existing merchant if needed
                    updated = False
                    if not merchant.mobile_money_provider:
                        merchant.mobile_money_provider = merchant_data['mobile_provider']
                        merchant.mobile_money_number = merchant_data['mobile_number']
                        merchant.mobile_money_name = merchant_data['name']
                        merchant.save()
                        updated = True
                        updated_count += 1
                    
                    # Ensure payment methods are added
                    if not merchant.payment_methods.filter(name='mobile_money').exists():
                        merchant.payment_methods.add(mobile_money)
                        updated = True
                    if not merchant.payment_methods.filter(name='p2p').exists():
                        merchant.payment_methods.add(p2p_method)
                        updated = True
                    
                    if updated:
                        self.stdout.write(f"  🔄 Updated: {merchant.name} (@{merchant.username})")
                    else:
                        self.stdout.write(f"  ⚠️  Exists: {merchant.name} (@{merchant.username})")
        
        self.stdout.write(f"\n" + "="*60)
        self.stdout.write(self.style.SUCCESS(f"🎉 Merchant creation completed!"))
        self.stdout.write(f"   ✅ Created: {created_count} new merchants")
        self.stdout.write(f"   🔄 Updated: {updated_count} existing merchants")
        
        # Summary by country
        self.stdout.write(f"\n📊 Summary by Country:")
        total_merchants = 0
        for country_code, country_name in P2PMerchant.COUNTRY_CHOICES:
            count = P2PMerchant.objects.filter(country=country_code).count()
            active_count = P2PMerchant.objects.filter(country=country_code, is_active=True).count()
            verified_count = P2PMerchant.objects.filter(country=country_code, is_verified=True).count()
            mobile_count = P2PMerchant.objects.filter(
                country=country_code, 
                mobile_money_provider__isnull=False
            ).exclude(mobile_money_provider='').count()
            
            self.stdout.write(f"   {country_code} ({country_name}):")
            self.stdout.write(f"      Total: {count} merchants")
            self.stdout.write(f"      Active: {active_count} merchants")
            self.stdout.write(f"      Verified: {verified_count} merchants")
            self.stdout.write(f"      With Mobile Money: {mobile_count} merchants")
            total_merchants += count
        
        self.stdout.write(f"\n🌍 Total merchants across all countries: {total_merchants}")
        
        # Payment method statistics
        p2p_merchants = P2PMerchant.objects.filter(payment_methods__name='p2p').distinct().count()
        mobile_merchants = P2PMerchant.objects.filter(payment_methods__name='mobile_money').distinct().count()
        mobile_configured = P2PMerchant.objects.filter(
            mobile_money_provider__isnull=False
        ).exclude(mobile_money_provider='').count()
        
        self.stdout.write(f"\n💳 Payment Method Coverage:")
        self.stdout.write(f"   P2P Trading: {p2p_merchants} merchants")
        self.stdout.write(f"   Mobile Money: {mobile_merchants} merchants")
        self.stdout.write(f"   Mobile Money Configured: {mobile_configured} merchants")
        
        # Sample merchant details for verification
        self.stdout.write(f"\n📋 Sample Merchant Details (First from each country):")
        for country_code, country_name in P2PMerchant.COUNTRY_CHOICES:
            sample_merchant = P2PMerchant.objects.filter(country=country_code).first()
            if sample_merchant:
                mobile_details = sample_merchant.get_mobile_money_details()
                self.stdout.write(f"   {country_code}: {sample_merchant.name}")
                self.stdout.write(f"      📱 {mobile_details['provider'] if mobile_details else 'Not configured'}")
                payment_methods = [m.display_name for m in sample_merchant.payment_methods.all()]
                self.stdout.write(f"      💳 Methods: {', '.join(payment_methods) if payment_methods else 'None'}")
        
        self.stdout.write("")