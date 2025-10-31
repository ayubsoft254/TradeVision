from allauth.account.adapter import DefaultAccountAdapter
from allauth.account.forms import SignupForm
from django.urls import reverse

class CustomAccountAdapter(DefaultAccountAdapter):
    """Custom allauth adapter to handle referral codes and other custom logic"""
    
    def get_signup_form_class(self, request):
        """Return custom signup form with request object"""
        from .forms import CustomSignupForm
        return CustomSignupForm
    
    def pre_save_user(self, request, form, user):
        """Called before the user is saved during signup"""
        return super().pre_save_user(request, form, user)
    
    def save_user(self, request, sociallogin, form):
        """Called to save a user instance"""
        return super().save_user(request, sociallogin, form)
    
    def get_login_redirect_url(self, request):
        """Redirect to dashboard after login"""
        return reverse('trading:dashboard')
    
    def get_logout_redirect_url(self, request):
        """Redirect to home after logout"""
        return reverse('core:home')
    
    def is_open_for_signup(self, request):
        """Control whether new signups are allowed"""
        # You can add custom logic here to control signups
        # For example, during maintenance or based on certain conditions
        return True
    
    def send_confirmation_mail(self, request, emailconfirmation, signup):
        """Customize email confirmation sending"""
        # You can customize the email confirmation process here if needed
        super().send_confirmation_mail(request, emailconfirmation, signup)