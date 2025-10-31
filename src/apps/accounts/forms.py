from django import forms
from django.contrib.auth.forms import UserCreationForm, PasswordChangeForm
from django.core.exceptions import ValidationError
from allauth.account.forms import SignupForm, LoginForm
from django_countries.fields import CountryField
from phonenumber_field.formfields import PhoneNumberField
from .models import User, UserProfile
import re
import logging

logger = logging.getLogger(__name__)

class CustomSignupForm(SignupForm):
    """Custom registration form with additional fields"""
    
    full_name = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500',
            'placeholder': 'Enter your full name',
            'autocomplete': 'name'
        }),
        help_text='Your legal full name as it appears on your ID'
    )
    
    phone_number = PhoneNumberField(
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500',
            'placeholder': '+254700000000',
            'autocomplete': 'tel'
        }),
        help_text='Include country code (e.g., +254700000000)'
    )
    
    country = CountryField().formfield(
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500'
        }),
        empty_label="Choose Country"
    )
    
    referral_code = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500',
            'placeholder': 'Enter referral code (optional)'
        }),
        help_text='If you have a referral code, enter it here'
    )
    
    def __init__(self, *args, **kwargs):
        # Get request from kwargs if available
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        
        # Customize existing fields
        self.fields['email'].widget.attrs.update({
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500',
            'placeholder': 'Enter your email address',
            'autocomplete': 'email'
        })
        
        self.fields['password1'].widget.attrs.update({
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500',
            'placeholder': 'Create a strong password',
            'autocomplete': 'new-password'
        })
        
        self.fields['password2'].widget.attrs.update({
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500',
            'placeholder': 'Confirm your password',
            'autocomplete': 'new-password'
        })
        
        # Limit country choices to supported countries
        supported_countries = ['KE', 'UG', 'TZ', 'CD', 'ZM']
        try:
            # Only filter choices if they are available
            if hasattr(self.fields['country'], 'choices') and self.fields['country'].choices:
                country_choices = [(code, name) for code, name in self.fields['country'].choices if code in supported_countries or code == '']
                self.fields['country'].choices = country_choices
        except (AttributeError, TypeError):
            # Skip country filtering if there's an issue
            pass
        
        # Pre-populate referral code from session if available
        if not self.request:
            # Try to get request from the form's parent if available
            pass
        else:
            if hasattr(self.request, 'session'):
                session_referral_code = self.request.session.get('referral_code')
                if session_referral_code and not self.data.get('referral_code'):
                    self.fields['referral_code'].initial = session_referral_code
    
    def clean_full_name(self):
        full_name = self.cleaned_data.get('full_name')
        if not full_name:
            raise ValidationError('Full name is required.')
        
        # Check for minimum length
        if len(full_name.strip()) < 2:
            raise ValidationError('Full name must be at least 2 characters long.')
        
        # Check for valid characters (letters, spaces, hyphens, apostrophes)
        if not re.match(r"^[a-zA-Z\s\-']+$", full_name):
            raise ValidationError('Full name can only contain letters, spaces, hyphens, and apostrophes.')
        
        return full_name.strip()
    
    def clean_phone_number(self):
        phone_number = self.cleaned_data.get('phone_number')
        if phone_number:
            # Check if phone number already exists
            existing = User.objects.filter(phone_number=phone_number).exists()
            if existing:
                raise ValidationError('A user with this phone number already exists.')
        return phone_number
    
    def clean_referral_code(self):
        referral_code = self.cleaned_data.get('referral_code')
        if referral_code:
            from .models import UserReferralCode
            if not UserReferralCode.objects.filter(referral_code=referral_code).exists():
                raise ValidationError('Invalid referral code.')
        return referral_code
    
    def save(self, request):
        """Save the user and handle referral code"""
        # Store referral code for later processing
        referral_code = self.cleaned_data.get('referral_code')
        if not referral_code and hasattr(request, 'session'):
            referral_code = request.session.get('referral_code')
        
        # Store in session for post-email confirmation processing
        if referral_code and hasattr(request, 'session'):
            request.session['pending_referral_code'] = referral_code
        
        # Call parent save - this handles the actual user creation and email verification flow
        user = super().save(request)
        
        # Set custom user fields if user object is valid
        # The adapter's pre_save_user method should have already set these,
        # but we ensure they're set here as a fallback
        if user and isinstance(user, User):
            try:
                if not user.full_name:
                    user.full_name = self.cleaned_data.get('full_name', '')
                if not user.phone_number:
                    user.phone_number = self.cleaned_data.get('phone_number')
                if not user.country:
                    user.country = self.cleaned_data.get('country')
                user.save()
            except Exception as e:
                logger.error(f"Error saving user fields after signup: {e}")
        
        return user

class CustomLoginForm(LoginForm):
    """Custom login form with styling"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Customize login field
        self.fields['login'].widget.attrs.update({
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500',
            'placeholder': 'Enter your email address',
            'autocomplete': 'email'
        })
        
        self.fields['password'].widget.attrs.update({
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500',
            'placeholder': 'Enter your password',
            'autocomplete': 'current-password'
        })
        
        # Update labels
        self.fields['login'].label = 'Email Address'

class UserProfileForm(forms.ModelForm):
    """Form for updating basic user information"""
    
    class Meta:
        model = User
        fields = ['full_name', 'phone_number', 'country']
        widgets = {
            'full_name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500',
                'placeholder': 'Enter your full name'
            }),
            'phone_number': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500',
                'placeholder': '+254700000000'
            }),
            'country': forms.Select(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500'
            })
        }
    
    def clean_full_name(self):
        full_name = self.cleaned_data.get('full_name')
        if len(full_name.strip()) < 2:
            raise ValidationError('Full name must be at least 2 characters long.')
        return full_name.strip()

class ProfileUpdateForm(forms.ModelForm):
    """Form for updating extended profile information"""
    
    class Meta:
        model = UserProfile
        fields = [
            'avatar', 'date_of_birth', 'address', 'city', 'postal_code'
        ]
        widgets = {
            'avatar': forms.FileInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500',
                'accept': 'image/*'
            }),
            'date_of_birth': forms.DateInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500',
                'type': 'date'
            }),
            'address': forms.Textarea(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500',
                'rows': 3,
                'placeholder': 'Enter your address'
            }),
            'city': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500',
                'placeholder': 'Enter your city'
            }),
            'postal_code': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500',
                'placeholder': 'Enter postal code'
            })
        }

class SecuritySettingsForm(forms.ModelForm):
    """Form for updating security settings"""
    
    class Meta:
        model = UserProfile
        fields = ['two_factor_enabled', 'withdrawal_otp_enabled']
        widgets = {
            'two_factor_enabled': forms.CheckboxInput(attrs={
                'class': 'h-4 w-4 text-primary-600 focus:ring-primary-500 border-gray-300 rounded'
            }),
            'withdrawal_otp_enabled': forms.CheckboxInput(attrs={
                'class': 'h-4 w-4 text-primary-600 focus:ring-primary-500 border-gray-300 rounded'
            })
        }

class KYCVerificationForm(forms.ModelForm):
    """Form for KYC document submission"""
    
    class Meta:
        model = UserProfile
        fields = [
            'id_number', 'id_document', 'date_of_birth', 
            'address', 'city', 'postal_code'
        ]
        widgets = {
            'id_number': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500',
                'placeholder': 'Enter your ID number'
            }),
            'id_document': forms.FileInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500',
                'accept': 'image/*,.pdf',
                'required': True
            }),
            'date_of_birth': forms.DateInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500',
                'type': 'date',
                'required': True
            }),
            'address': forms.Textarea(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500',
                'rows': 3,
                'placeholder': 'Enter your full address',
                'required': True
            }),
            'city': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500',
                'placeholder': 'Enter your city',
                'required': True
            }),
            'postal_code': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500',
                'placeholder': 'Enter postal code'
            })
        }
    
    def clean_id_number(self):
        id_number = self.cleaned_data.get('id_number')
        if id_number:
            # Remove spaces and check length
            id_number = id_number.replace(' ', '')
            if len(id_number) < 6:
                raise ValidationError('ID number must be at least 6 characters long.')
        return id_number
    
    def clean_id_document(self):
        id_document = self.cleaned_data.get('id_document')
        if id_document:
            # Check file size (max 5MB)
            if id_document.size > 5 * 1024 * 1024:
                raise ValidationError('File size must be less than 5MB.')
            
            # Check file type
            allowed_types = ['image/jpeg', 'image/png', 'image/jpg', 'application/pdf']
            if id_document.content_type not in allowed_types:
                raise ValidationError('Only JPEG, PNG, and PDF files are allowed.')
        
        return id_document

class CustomPasswordChangeForm(PasswordChangeForm):
    """Custom password change form with styling"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        for field_name, field in self.fields.items():
            field.widget.attrs.update({
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500'
            })
        
        self.fields['old_password'].widget.attrs['placeholder'] = 'Enter current password'
        self.fields['new_password1'].widget.attrs['placeholder'] = 'Enter new password'
        self.fields['new_password2'].widget.attrs['placeholder'] = 'Confirm new password'

class ContactForm(forms.Form):
    """Contact form for support inquiries"""
    
    SUBJECT_CHOICES = [
        ('general', 'General Inquiry'),
        ('account', 'Account Issues'),
        ('trading', 'Trading Problems'),
        ('payments', 'Payment Issues'),
        ('technical', 'Technical Support'),
        ('complaint', 'Complaint'),
    ]
    
    name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500',
            'placeholder': 'Your full name'
        })
    )
    
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500',
            'placeholder': 'Your email address'
        })
    )
    
    subject = forms.ChoiceField(
        choices=SUBJECT_CHOICES,
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500'
        })
    )
    
    message = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500',
            'rows': 6,
            'placeholder': 'Describe your inquiry or issue in detail...'
        })
    )
    
    def clean_message(self):
        message = self.cleaned_data.get('message')
        if len(message.strip()) < 10:
            raise ValidationError('Message must be at least 10 characters long.')
        return message.strip()

class ReferralCodeForm(forms.Form):
    """Form for entering referral code"""
    
    referral_code = forms.CharField(
        max_length=20,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500',
            'placeholder': 'Enter referral code',
            'autocomplete': 'off'
        })
    )
    
    def clean_referral_code(self):
        referral_code = self.cleaned_data.get('referral_code')
        if referral_code:
            from .models import UserReferralCode
            if not UserReferralCode.objects.filter(referral_code=referral_code).exists():
                raise ValidationError('Invalid referral code.')
        return referral_code