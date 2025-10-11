from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.core.validators import RegexValidator
from django_countries.fields import CountryField
from phonenumber_field.modelfields import PhoneNumberField
import uuid

class UserManager(BaseUserManager):
    """Custom user manager"""
    
    def create_user(self, email, full_name, password=None, **extra_fields):
        """Create and return a regular user"""
        if not email:
            raise ValueError('The Email field must be set')
        
        email = self.normalize_email(email)
        
        # Generate username from email if not provided
        if 'username' not in extra_fields:
            base_username = email.split('@')[0]
            username = base_username
            counter = 0
            
            # Ensure username uniqueness
            while self.model.objects.filter(username=username).exists():
                counter += 1
                username = f"{base_username}{counter}"
            
            extra_fields['username'] = username
        
        user = self.model(email=email, full_name=full_name, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_superuser(self, email, full_name, password=None, **extra_fields):
        """Create and return a superuser"""
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_verified', True)
        
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        
        return self.create_user(email, full_name, password, **extra_fields)

class User(AbstractUser):
    """Custom User model"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=255)
    phone_number = PhoneNumberField(blank=True, null=True)
    country = CountryField(blank=True, null=True)
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Remove these fields
    first_name = None
    last_name = None
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['full_name']
    
    objects = UserManager()
    
    def save(self, *args, **kwargs):
        if not self.username:
            # Auto-generate username from email
            base_username = self.email.split('@')[0]
            username = base_username
            counter = 0
            
            # Ensure username uniqueness
            while User.objects.filter(username=username).exclude(pk=self.pk).exists():
                counter += 1
                username = f"{base_username}{counter}"
            
            self.username = username
        super().save(*args, **kwargs)
    
    def __str__(self):
        return self.email
    
    @property
    def display_name(self):
        return self.full_name or self.email.split('@')[0]

class UserProfile(models.Model):
    """Extended user profile information"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    date_of_birth = models.DateField(blank=True, null=True)
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    
    # KYC fields
    id_number = models.CharField(max_length=50, blank=True)
    id_document = models.ImageField(upload_to='documents/', blank=True, null=True)
    kyc_status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('approved', 'Approved'),
            ('rejected', 'Rejected'),
        ],
        default='pending'
    )
    
    # Security settings
    two_factor_enabled = models.BooleanField(default=False)
    withdrawal_otp_enabled = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.user.email} - Profile"

class UserReferralCode(models.Model):
    """Store each user's unique referral code"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='referral_code_obj')
    referral_code = models.CharField(max_length=20, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.user.email} - Code: {self.referral_code}"
    
    @classmethod
    def generate_unique_code(cls):
        """Generate a unique referral code"""
        import random
        import string
        
        while True:
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
            if not cls.objects.filter(referral_code=code).exists():
                return code
    
    @classmethod
    def get_or_create_for_user(cls, user):
        """Get or create a referral code for a user"""
        obj, created = cls.objects.get_or_create(
            user=user,
            defaults={'referral_code': cls.generate_unique_code()}
        )
        return obj.referral_code

class Referral(models.Model):
    """Referral relationships - tracks who referred whom"""
    referrer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='referrals_made')
    referred = models.OneToOneField(User, on_delete=models.CASCADE, related_name='referral')
    referral_code = models.CharField(max_length=20, db_index=True)  # The code used for this referral
    commission_earned = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.referrer.email} referred {self.referred.email}"
    
    class Meta:
        indexes = [
            models.Index(fields=['referrer', 'is_active']),
            models.Index(fields=['referred']),
        ]

# Signal to create user profile and referral code
from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=User)
def create_user_profile_and_referral_code(sender, instance, created, **kwargs):
    if created:
        # Create user profile
        UserProfile.objects.get_or_create(user=instance)
        # Create unique referral code for the user
        UserReferralCode.objects.get_or_create(
            user=instance,
            defaults={'referral_code': UserReferralCode.generate_unique_code()}
        )