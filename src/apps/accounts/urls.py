from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    # Profile Management
    path('profile/', views.ProfileView.as_view(), name='profile'),
    path('profile/edit/', views.EditProfileView.as_view(), name='edit_profile'),
    
    # Security & Authentication
    path('security/', views.SecurityView.as_view(), name='security'),
    path('2fa/setup/', views.TwoFactorSetupView.as_view(), name='2fa_setup'),
    path('delete-account/', views.delete_account, name='delete_account'),
    
    # KYC Verification
    path('kyc/', views.KYCVerificationView.as_view(), name='kyc_verification'),
    
    # Referral System
    path('referrals/', views.ReferralView.as_view(), name='referrals'),
    path('api/generate-referral-code/', views.generate_new_referral_code, name='generate_referral_code'),
    
    # Account Activity & Notifications
    path('activity/', views.AccountActivityView.as_view(), name='activity'),
    path('notifications/', views.NotificationsView.as_view(), name='notifications'),
    
    # Custom Allauth views (if needed)
    path('password/reset/custom/', views.CustomPasswordResetView.as_view(), name='custom_password_reset'),
    path('email/verification/custom/', views.CustomEmailVerificationView.as_view(), name='custom_email_verification'),
    ]