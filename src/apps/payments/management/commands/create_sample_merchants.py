# apps/payments/management/commands/create_sample_merchants.py
from django.core.management.base import BaseCommand
from apps.payments.models import P2PMerchant, PaymentMethod


class Command(BaseCommand):
    help = 'Create sample P2P merchants and ensure payment methods exist'

    def handle(self, *args, **options):
        # Create or get payment methods first
        payment_methods = {}
        
        # Mobile Money
        mobile_money, created = PaymentMethod.objects.get_or_create(
            name='mobile_money',
            defaults={
                'display_name': 'Mobile Money',
                'countries': ['KE', 'UG', 'TZ', 'ZM'],
                'is_active': True,
                'min_amount': 10,
                'processing_fee': 2.0,
                'processing_time': 'Instant'
            }
        )
        payment_methods['mobile_money'] = mobile_money
        
        # Bank Transfer
        bank_transfer, created = PaymentMethod.objects.get_or_create(
            name='bank_transfer',
            defaults={
                'display_name': 'Bank Transfer',
                'countries': ['KE', 'UG', 'TZ', 'ZM', 'CD'],
                'is_active': True,
                'min_amount': 50,
                'processing_fee': 1.5,
                'processing_time': '1-3 hours'
            }
        )
        payment_methods['bank_transfer'] = bank_transfer
        
        # Crypto
        crypto, created = PaymentMethod.objects.get_or_create(
            name='crypto',
            defaults={
                'display_name': 'Cryptocurrency',
                'countries': ['KE', 'UG', 'TZ', 'ZM', 'CD'],
                'is_active': True,
                'min_amount': 20,
                'processing_fee': 1.0,
                'processing_time': '10-30 minutes'
            }
        )
        payment_methods['crypto'] = crypto
        
        # Sample merchants data
        merchants_data = [
            {
                'name': 'John Kamau',
                'username': 'johnkamau_ke',
                'phone_number': '+254700123456',
                'email': 'johnkamau@example.com',
                'country': 'KE',
                'methods': ['mobile_money', 'bank_transfer'],
                'min_order': 500,
                'max_order': 50000,
                'commission': 1.5,
                'rating': 4.8,
            },
            {
                'name': 'Sarah Nakato',
                'username': 'sarah_uganda',
                'phone_number': '+256701234567',
                'email': 'sarah.nakato@example.com',
                'country': 'UG',
                'methods': ['mobile_money', 'bank_transfer'],
                'min_order': 300,
                'max_order': 30000,
                'commission': 1.8,
                'rating': 4.6,
            },
            {
                'name': 'Peter Mwangi',
                'username': 'peter_crypto',
                'phone_number': '+254712345678',
                'email': 'peter.mwangi@example.com',
                'country': 'KE',
                'methods': ['crypto', 'mobile_money'],
                'min_order': 1000,
                'max_order': 100000,
                'commission': 1.2,
                'rating': 4.9,
            },
            {
                'name': 'Grace Mwanza',
                'username': 'grace_zambia',
                'phone_number': '+260971234567',
                'email': 'grace.mwanza@example.com',
                'country': 'ZM',
                'methods': ['mobile_money', 'bank_transfer'],
                'min_order': 400,
                'max_order': 25000,
                'commission': 2.0,
                'rating': 4.5,
            },
            {
                'name': 'Emmanuel Kinyua',
                'username': 'emma_tanzania',
                'phone_number': '+255701234567',
                'email': 'emmanuel.kinyua@example.com',
                'country': 'TZ',
                'methods': ['mobile_money', 'bank_transfer'],
                'min_order': 600,
                'max_order': 35000,
                'commission': 1.7,
                'rating': 4.7,
            },
            {
                'name': 'Marie Kasongo',
                'username': 'marie_drc',
                'phone_number': '+243901234567',
                'email': 'marie.kasongo@example.com',
                'country': 'CD',
                'methods': ['bank_transfer', 'crypto'],
                'min_order': 800,
                'max_order': 40000,
                'commission': 2.2,
                'rating': 4.4,
            },
        ]
        
        created_count = 0
        for merchant_data in merchants_data:
            merchant, created = P2PMerchant.objects.get_or_create(
                username=merchant_data['username'],
                defaults={
                    'name': merchant_data['name'],
                    'phone_number': merchant_data['phone_number'],
                    'email': merchant_data['email'],
                    'country': merchant_data['country'],
                    'is_verified': True,
                    'is_active': True,
                    'commission_rate': merchant_data['commission'],
                    'min_order_amount': merchant_data['min_order'],
                    'max_order_amount': merchant_data['max_order'],
                    'rating': merchant_data['rating'],
                    'completion_rate': 95.0,
                    'total_orders': 150,
                }
            )
            
            if created:
                # Add payment methods
                for method_name in merchant_data['methods']:
                    if method_name in payment_methods:
                        merchant.payment_methods.add(payment_methods[method_name])
                
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Created merchant: {merchant.name} (@{merchant.username}) in {merchant.country}'
                    )
                )
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f'Merchant already exists: {merchant.name} (@{merchant.username})'
                    )
                )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\nCreated {created_count} new P2P merchants. '
                f'Total merchants in database: {P2PMerchant.objects.count()}'
            )
        )
        
        # Show payment methods count
        self.stdout.write(
            self.style.SUCCESS(
                f'Total payment methods: {PaymentMethod.objects.count()}'
            )
        )