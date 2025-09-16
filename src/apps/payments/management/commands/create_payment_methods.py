from django.core.management.base import BaseCommand
from apps.payments.models import PaymentMethod

class Command(BaseCommand):
    help = 'Creates default payment methods'

    def handle(self, *args, **options):
        payment_methods = [
            {
                'name': 'binance_pay',
                'display_name': 'Binance Pay',
                'countries': ['KE', 'UG', 'TZ', 'NG', 'GH', 'US', 'UK', 'CA'],  # Add your supported countries
                'is_active': True,
                'min_amount': 10.00,
                'max_amount': 10000.00,
                'processing_fee': 0.5,
                'processing_time': 'Instant'
            },
            {
                'name': 'mobile_money',
                'display_name': 'Mobile Money',
                'countries': ['KE', 'UG', 'TZ', 'NG', 'GH'],
                'is_active': True,
                'min_amount': 1.00,
                'max_amount': 50000.00,
                'processing_fee': 1.0,
                'processing_time': '1-24 hours'
            },
            {
                'name': 'bank_transfer',
                'display_name': 'Bank Transfer',
                'countries': ['KE', 'UG', 'TZ', 'NG', 'GH', 'US', 'UK', 'CA'],
                'is_active': True,
                'min_amount': 10.00,
                'max_amount': 100000.00,
                'processing_fee': 0.0,
                'processing_time': '1-3 business days'
            },
            {
                'name': 'p2p',
                'display_name': 'P2P Trading',
                'countries': ['KE', 'UG', 'TZ', 'NG', 'GH'],
                'is_active': True,
                'min_amount': 5.00,
                'max_amount': 20000.00,
                'processing_fee': 1.5,
                'processing_time': '5-30 minutes'
            },
            {
                'name': 'agent',
                'display_name': 'Local Agent',
                'countries': ['KE', 'UG', 'TZ', 'NG', 'GH'],
                'is_active': True,
                'min_amount': 20.00,
                'max_amount': 10000.00,
                'processing_fee': 2.0,
                'processing_time': '10-60 minutes'
            },
            {
                'name': 'crypto',
                'display_name': 'Cryptocurrency',
                'countries': ['KE', 'UG', 'TZ', 'NG', 'GH', 'US', 'UK', 'CA'],
                'is_active': True,
                'min_amount': 10.00,
                'max_amount': 50000.00,
                'processing_fee': 0.5,
                'processing_time': '10-60 minutes'
            },
        ]

        for method_data in payment_methods:
            method, created = PaymentMethod.objects.get_or_create(
                name=method_data['name'],
                defaults=method_data
            )
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f'Created payment method: {method.display_name}')
                )
            else:
                # Update existing method
                for key, value in method_data.items():
                    setattr(method, key, value)
                method.save()
                self.stdout.write(
                    self.style.WARNING(f'Updated payment method: {method.display_name}')
                )

        self.stdout.write(
            self.style.SUCCESS('Successfully processed all payment methods')
        )