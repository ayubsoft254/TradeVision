from django.core.management.base import BaseCommand
from apps.payments.models import PaymentMethod

class Command(BaseCommand):
    help = 'Create P2P payment method'
    
    def handle(self, *args, **options):
        # Create P2P payment method
        p2p_method, created = PaymentMethod.objects.get_or_create(
            name='p2p',
            defaults={
                'display_name': 'P2P Trading',
                'is_active': True,
                'processing_fee': 1.0,  # 1% fee
                'processing_time': '5-15 minutes',
                'min_amount': 10,
                'max_amount': 10000,
                'countries': ['KE', 'UG', 'TZ', 'ZM', 'CD']  # All supported countries
            }
        )

        if created:
            self.stdout.write(self.style.SUCCESS("✅ Created P2P payment method successfully!"))
        else:
            self.stdout.write("P2P payment method already exists")

        self.stdout.write(f"P2P Method: {p2p_method.name} - {p2p_method.display_name}")
        self.stdout.write(f"Active: {p2p_method.is_active}")
        self.stdout.write(f"Countries: {p2p_method.countries}")
        self.stdout.write(f"Fee: {p2p_method.processing_fee}%")
        self.stdout.write(f"Processing Time: {p2p_method.processing_time}")

        # Verify it's now in the list
        self.stdout.write("\nAll payment methods now:")
        for method in PaymentMethod.objects.all().order_by('name'):
            self.stdout.write(f"- {method.name}: {method.display_name}")