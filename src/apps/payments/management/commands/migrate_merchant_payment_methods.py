# apps/payments/management/commands/migrate_merchant_payment_methods.py
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from apps.payments.models import P2PMerchant, PaymentMethod


class Command(BaseCommand):
    help = 'Migrate existing P2P merchant payment methods from old JSON format to new ManyToMany relationship'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            dest='dry_run',
            help='Run migration in dry-run mode (no changes made)',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            dest='force',
            help='Force migration even if merchants already have payment methods assigned',
        )

    def handle(self, *args, **options):
        self.stdout.write("=== P2P Merchant Payment Methods Migration ===")
        
        # Get all merchants that have supported_methods but no payment_methods
        if options['force']:
            merchants = P2PMerchant.objects.filter(supported_methods__isnull=False)
            self.stdout.write(
                self.style.WARNING(
                    f"Force mode: Processing {merchants.count()} merchants with supported_methods"
                )
            )
        else:
            merchants = P2PMerchant.objects.filter(
                supported_methods__isnull=False
            ).exclude(payment_methods__isnull=False)
            self.stdout.write(
                f"Found {merchants.count()} merchants with old payment method format"
            )

        if merchants.count() == 0:
            self.stdout.write(
                self.style.SUCCESS("No merchants need migration. All merchants are up to date!")
            )
            return

        # Method mapping from old string values to new PaymentMethod names
        method_mapping = {
            'mobile_money': 'mobile_money',
            'bank_transfer': 'bank_transfer', 
            'cash': 'agent',  # Cash transactions are typically done through agents
            'crypto': 'crypto',
            'binance_pay': 'binance_pay',
            'p2p': 'p2p',
            'cryptocurrency': 'crypto',  # Alternative name
            'agent': 'agent'
        }

        migrated_count = 0
        skipped_count = 0
        error_count = 0

        with transaction.atomic():
            for merchant in merchants:
                self.stdout.write(f"\nProcessing merchant: {merchant.name} (@{merchant.username})")
                self.stdout.write(f"  Country: {merchant.get_country_display()}")
                self.stdout.write(f"  Old methods: {merchant.supported_methods}")
                
                if not merchant.supported_methods:
                    self.stdout.write(
                        self.style.WARNING(f"  Skipped: No supported_methods data")
                    )
                    skipped_count += 1
                    continue

                # Check if merchant already has payment methods (unless force mode)
                if not options['force'] and merchant.payment_methods.exists():
                    self.stdout.write(
                        self.style.WARNING(f"  Skipped: Already has payment methods assigned")
                    )
                    skipped_count += 1
                    continue

                methods_added = []
                methods_not_found = []

                for old_method in merchant.supported_methods:
                    # Map old method name to new method name
                    new_method_name = method_mapping.get(old_method, old_method)
                    
                    # Find matching PaymentMethod
                    try:
                        payment_method = PaymentMethod.objects.filter(
                            name=new_method_name,
                            is_active=True,
                            countries__contains=merchant.country
                        ).first()
                        
                        if payment_method:
                            if options['dry_run']:
                                self.stdout.write(f"    Would add: {payment_method.display_name}")
                            else:
                                merchant.payment_methods.add(payment_method)
                                self.stdout.write(
                                    self.style.SUCCESS(f"    Added: {payment_method.display_name}")
                                )
                            methods_added.append(payment_method.display_name)
                        else:
                            # Try to find the method without country restriction
                            fallback_method = PaymentMethod.objects.filter(
                                name=new_method_name,
                                is_active=True
                            ).first()
                            
                            if fallback_method:
                                self.stdout.write(
                                    self.style.WARNING(
                                        f"    Warning: {fallback_method.display_name} not available in {merchant.get_country_display()}"
                                    )
                                )
                                if options['dry_run']:
                                    self.stdout.write(f"    Would add anyway: {fallback_method.display_name}")
                                else:
                                    merchant.payment_methods.add(fallback_method)
                                    self.stdout.write(f"    Added anyway: {fallback_method.display_name}")
                                methods_added.append(fallback_method.display_name)
                            else:
                                methods_not_found.append(f"{old_method} -> {new_method_name}")
                                
                    except Exception as e:
                        self.stdout.write(
                            self.style.ERROR(f"    Error processing {old_method}: {e}")
                        )
                        methods_not_found.append(f"{old_method} (error: {e})")

                if methods_added:
                    migrated_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(f"  ✓ Successfully processed {len(methods_added)} methods")
                    )
                elif methods_not_found:
                    error_count += 1
                    self.stdout.write(
                        self.style.ERROR(f"  ✗ Could not find methods: {', '.join(methods_not_found)}")
                    )
                else:
                    skipped_count += 1

            if options['dry_run']:
                self.stdout.write("\n" + "="*50)
                self.stdout.write(self.style.WARNING("DRY RUN - NO CHANGES MADE"))
                self.stdout.write("="*50)
                # Rollback transaction in dry run
                transaction.set_rollback(True)

        # Summary
        self.stdout.write(f"\n=== Migration Summary ===")
        self.stdout.write(f"Merchants processed: {migrated_count}")
        self.stdout.write(f"Merchants skipped: {skipped_count}")
        self.stdout.write(f"Merchants with errors: {error_count}")
        
        if options['dry_run']:
            self.stdout.write(
                self.style.WARNING("\nThis was a dry run. Run without --dry-run to apply changes.")
            )
        else:
            if migrated_count > 0:
                self.stdout.write(
                    self.style.SUCCESS(f"\n✓ Successfully migrated {migrated_count} merchants!")
                )
            if error_count > 0:
                self.stdout.write(
                    self.style.ERROR(f"\n⚠ {error_count} merchants had errors and may need manual review.")
                )

        # Show available payment methods by country
        self.stdout.write(f"\n=== Available Payment Methods by Country ===")
        countries = ['ZM', 'CD', 'TZ', 'KE', 'UG']
        country_names = dict(P2PMerchant.COUNTRY_CHOICES)
        
        for country_code in countries:
            methods = PaymentMethod.objects.filter(
                is_active=True,
                countries__contains=country_code
            ).order_by('display_name')
            
            self.stdout.write(f"\n{country_names[country_code]} ({country_code}):")
            if methods:
                for method in methods:
                    self.stdout.write(f"  • {method.display_name} ({method.name})")
            else:
                self.stdout.write("  No payment methods available")