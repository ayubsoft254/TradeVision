from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django_countries.fields import Country

class Command(BaseCommand):
    help = 'Set country for test user'
    
    def handle(self, *args, **options):
        User = get_user_model()
        
        # Check current users and their countries
        self.stdout.write("Current users:")
        for user in User.objects.all()[:5]:
            country_info = f"{user.country} ({user.country.code})" if user.country else "None"
            self.stdout.write(f"- {user.username}: Country = {country_info}")

        # Set country for test user
        test_user = User.objects.filter(is_active=True).first()
        if test_user:
            test_user.country = Country('KE')  # Set to Kenya
            test_user.save()
            self.stdout.write(self.style.SUCCESS(f"✅ Updated {test_user.username} country to: {test_user.country} ({test_user.country.code})"))
        else:
            self.stdout.write(self.style.ERROR("No test user found"))