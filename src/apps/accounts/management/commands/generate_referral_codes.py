# apps/accounts/management/commands/generate_referral_codes.py
from django.core.management.base import BaseCommand
from apps.accounts.models import User, UserReferralCode


class Command(BaseCommand):
    help = 'Generate referral codes for all existing users who don\'t have one'

    def handle(self, *args, **options):
        self.stdout.write('Generating referral codes for existing users...')
        
        users_without_codes = User.objects.filter(referral_code_obj__isnull=True)
        count = users_without_codes.count()
        
        if count == 0:
            self.stdout.write(self.style.SUCCESS('All users already have referral codes!'))
            return
        
        self.stdout.write(f'Found {count} users without referral codes')
        
        created_count = 0
        for user in users_without_codes:
            try:
                code = UserReferralCode.generate_unique_code()
                UserReferralCode.objects.create(
                    user=user,
                    referral_code=code
                )
                created_count += 1
                self.stdout.write(f'  Created code {code} for {user.email}')
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'  Error creating code for {user.email}: {e}')
                )
        
        self.stdout.write(
            self.style.SUCCESS(f'Successfully created {created_count} referral codes!')
        )
        
        # Display summary
        total_codes = UserReferralCode.objects.count()
        total_users = User.objects.count()
        self.stdout.write(f'\nSummary:')
        self.stdout.write(f'  Total users: {total_users}')
        self.stdout.write(f'  Total referral codes: {total_codes}')
