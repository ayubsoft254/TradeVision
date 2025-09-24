from allauth.account.adapter import DefaultAccountAdapter
from allauth.account.forms import SignupForm
from django.urls import reverse

class CustomAccountAdapter(DefaultAccountAdapter):
    """Custom allauth adapter to handle referral codes and other custom logic"""
    
    def get_signup_form_class(self, request):
        """Return custom signup form with request object"""
        from .forms import CustomSignupForm
        
        # Create a wrapper class that passes request to the form
        class CustomSignupFormWithRequest(CustomSignupForm):
            def __init__(self, *args, **kwargs):
                kwargs['request'] = request
                super().__init__(*args, **kwargs)
        
        return CustomSignupFormWithRequest
    
    def get_login_redirect_url(self, request):
        """Redirect to dashboard after login"""
        return reverse('trading:dashboard')
    
    def get_logout_redirect_url(self, request):
        """Redirect to home after logout"""
        return reverse('core:home')
    
    def save_user(self, request, user, form, commit=True):
        """Custom user saving logic"""
        user = super().save_user(request, user, form, commit=False)
        
        # The CustomSignupForm already handles referral logic in its save method
        # so we don't need to duplicate it here
        
        if commit:
            user.save()
        return user
    
    def is_open_for_signup(self, request):
        """Control whether new signups are allowed"""
        # You can add custom logic here to control signups
        # For example, during maintenance or based on certain conditions
        return True
    
    def send_confirmation_mail(self, request, emailconfirmation, signup):
        """Customize email confirmation sending"""
        # You can customize the email confirmation process here if needed
        super().send_confirmation_mail(request, emailconfirmation, signup)