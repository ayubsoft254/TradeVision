"""
Management command to fix referral system data
- Generate referral codes for all users
- Remove self-referrals
- Clean up duplicate referral relationships
"""
from django.core.management.base import BaseCommand
from django.db.models import Count
from apps.accounts.models import User, UserReferralCode, Referral


class Command(BaseCommand):
    help = 'Fix referral system data and generate codes for all users'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without making changes',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made'))
        
        self.stdout.write(self.style.SUCCESS('Starting referral system cleanup...'))
        
        # Step 1: Generate referral codes for all users
        self.stdout.write('\n1. Generating referral codes for all users...')
        users_without_codes = User.objects.exclude(
            id__in=UserReferralCode.objects.values_list('user_id', flat=True)
        )
        
        created_count = 0
        for user in users_without_codes:
            if not dry_run:
                UserReferralCode.get_or_create_for_user(user)
            created_count += 1
        
        self.stdout.write(
            self.style.SUCCESS(
                f'   ✓ Created referral codes for {created_count} users'
            )
        )
        
        # Step 2: Remove self-referrals (where referrer == referred)
        self.stdout.write('\n2. Removing self-referrals...')
        self_referrals = Referral.objects.filter(referrer=models.F('referred'))
        self_referral_count = self_referrals.count()
        
        if self_referral_count > 0:
            if not dry_run:
                self_referrals.delete()
            self.stdout.write(
                self.style.WARNING(
                    f'   ✓ Removed {self_referral_count} self-referral records'
                )
            )
        else:
            self.stdout.write(self.style.SUCCESS('   ✓ No self-referrals found'))
        
        # Step 3: Check for duplicate referrals (same referred user multiple times)
        self.stdout.write('\n3. Checking for duplicate referrals...')
        duplicates = Referral.objects.values('referred').annotate(
            count=Count('id')
        ).filter(count__gt=1)
        
        if duplicates.exists():
            self.stdout.write(
                self.style.WARNING(
                    f'   ! Found {duplicates.count()} users with duplicate referral records'
                )
            )
            
            for dup in duplicates:
                referred_user = User.objects.get(id=dup['referred'])
                referrals = Referral.objects.filter(referred=referred_user).order_by('created_at')
                
                # Keep the oldest referral, delete the rest
                keep = referrals.first()
                delete_refs = referrals.exclude(id=keep.id)
                
                self.stdout.write(
                    f'   - User {referred_user.email}: keeping referral by {keep.referrer.email}, '
                    f'deleting {delete_refs.count()} duplicate(s)'
                )
                
                if not dry_run:
                    delete_refs.delete()
        else:
            self.stdout.write(self.style.SUCCESS('   ✓ No duplicate referrals found'))
        
        # Step 4: Display statistics
        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.SUCCESS('REFERRAL SYSTEM STATISTICS'))
        self.stdout.write('='*60)
        
        total_users = User.objects.count()
        users_with_codes = UserReferralCode.objects.count()
        total_referrals = Referral.objects.count()
        active_referrals = Referral.objects.filter(is_active=True).count()
        
        # Users who have referred others
        referrers = Referral.objects.values('referrer').distinct().count()
        
        # Users who were referred
        referred = Referral.objects.values('referred').distinct().count()
        
        self.stdout.write(f'\nTotal users: {total_users}')
        self.stdout.write(f'Users with referral codes: {users_with_codes}')
        self.stdout.write(f'Total referral relationships: {total_referrals}')
        self.stdout.write(f'Active referral relationships: {active_referrals}')
        self.stdout.write(f'Users who referred others: {referrers}')
        self.stdout.write(f'Users who were referred: {referred}')
        
        # Top referrers
        self.stdout.write('\n' + '-'*60)
        self.stdout.write('TOP 5 REFERRERS:')
        self.stdout.write('-'*60)
        
        from django.db.models import Count, Sum
        top_referrers = User.objects.annotate(
            referral_count=Count('referrals_made', filter=models.Q(referrals_made__is_active=True)),
            total_earned=Sum('referrals_made__commission_earned', filter=models.Q(referrals_made__is_active=True))
        ).filter(referral_count__gt=0).order_by('-referral_count')[:5]
        
        for user in top_referrers:
            self.stdout.write(
                f'  {user.email}: {user.referral_count} referrals, '
                f'${user.total_earned or 0:.2f} earned'
            )
        
        if not dry_run:
            self.stdout.write('\n' + self.style.SUCCESS('✓ Referral system cleanup completed!'))
        else:
            self.stdout.write(
                '\n' + self.style.WARNING(
                    '✓ Dry run completed. Run without --dry-run to apply changes.'
                )
            )


# Import models at module level for F expression
from django.db import models
