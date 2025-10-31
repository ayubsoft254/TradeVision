from django.test import TestCase, Client, RequestFactory
from django.contrib.auth import get_user_model
from django.urls import reverse
from allauth.account.models import EmailAddress
from .models import UserReferralCode, Referral

User = get_user_model()


class SignupFlowTests(TestCase):
    """Test cases for the signup flow with referral code handling"""
    
    def setUp(self):
        """Set up test client and URLs"""
        self.client = Client()
        self.factory = RequestFactory()
        self.signup_url = reverse('account_signup')
        self.referral_url = reverse('core:referral_redirect')
    
    def test_user_signup_without_referral_code(self):
        """Test basic signup without referral code"""
        response = self.client.post(self.signup_url, {
            'email': 'testuser@example.com',
            'full_name': 'Test User',
            'phone_number': '+254700000000',
            'country': 'KE',
            'password1': 'SecurePass123!',
            'password2': 'SecurePass123!',
        })
        
        # User should be created
        self.assertTrue(User.objects.filter(email='testuser@example.com').exists())
        
        # User should have no pending referral code
        user = User.objects.get(email='testuser@example.com')
        self.assertIsNone(user.pending_referral_code)
        self.assertFalse(user.referral_code_processed)
        
        # No referral should exist
        self.assertFalse(Referral.objects.filter(referred=user).exists())
    
    def test_user_signup_with_valid_referral_code(self):
        """Test signup with valid referral code"""
        # Create referrer
        referrer = User.objects.create_user(
            email='referrer@example.com',
            full_name='Referrer User',
            password='Pass123'
        )
        ref_code = UserReferralCode.objects.get(user=referrer).referral_code
        
        # Sign up referred user with referral code
        response = self.client.post(self.signup_url, {
            'email': 'referred@example.com',
            'full_name': 'Referred User',
            'phone_number': '+254700000001',
            'country': 'KE',
            'password1': 'SecurePass123!',
            'password2': 'SecurePass123!',
            'referral_code': ref_code,
        })
        
        # User should be created
        referred_user = User.objects.get(email='referred@example.com')
        self.assertIsNotNone(referred_user)
        
        # Referral code should be stored in user model
        self.assertEqual(referred_user.pending_referral_code, ref_code)
        self.assertFalse(referred_user.referral_code_processed)
        
        # Simulate email confirmation
        email_obj = EmailAddress.objects.get(user=referred_user)
        email_obj.verified = True
        email_obj.save()
        
        # Trigger email_confirmed signal manually
        from allauth.account.signals import email_confirmed
        request = self.factory.get('/')
        request.session = self.client.session
        
        email_confirmed.send(
            sender=type(email_obj),
            request=request,
            email_address=email_obj
        )
        
        # Referral should be created
        referral = Referral.objects.get(referred=referred_user)
        self.assertEqual(referral.referrer, referrer)
        self.assertEqual(referral.referral_code, ref_code)
        self.assertTrue(referral.is_active)
        
        # User should be marked as processed
        referred_user.refresh_from_db()
        self.assertTrue(referred_user.referral_code_processed)
        self.assertIsNone(referred_user.pending_referral_code)
    
    def test_signup_with_invalid_referral_code(self):
        """Test signup with invalid referral code shows error"""
        response = self.client.post(self.signup_url, {
            'email': 'user@example.com',
            'full_name': 'User',
            'phone_number': '+254700000002',
            'country': 'KE',
            'password1': 'SecurePass123!',
            'password2': 'SecurePass123!',
            'referral_code': 'INVALID123',
        })
        
        # Form should have error
        self.assertFormError(response, 'form', 'referral_code', 'Invalid referral code.')
        
        # User should NOT be created
        self.assertFalse(User.objects.filter(email='user@example.com').exists())
    
    def test_referral_redirect_with_valid_code(self):
        """Test referral redirect stores code in session and redirects to signup"""
        # Create referrer and get code
        referrer = User.objects.create_user(
            email='referrer@example.com',
            full_name='Referrer',
            password='Pass123'
        )
        ref_code = UserReferralCode.objects.get(user=referrer).referral_code
        
        # Visit referral link
        response = self.client.get(f'{self.referral_url}?ref={ref_code}')
        
        # Should redirect to signup
        self.assertRedirects(response, self.signup_url)
        
        # Session should have referral code
        self.assertEqual(self.client.session['referral_code'], ref_code)
    
    def test_referral_redirect_with_invalid_code(self):
        """Test referral redirect with invalid code redirects to home"""
        response = self.client.get(f'{self.referral_url}?ref=INVALID123')
        
        # Should redirect to home
        self.assertRedirects(response, reverse('core:home'))
    
    def test_referral_redirect_without_code(self):
        """Test referral redirect without code redirects to signup"""
        response = self.client.get(self.referral_url)
        
        # Should redirect to signup
        self.assertRedirects(response, self.signup_url)
    
    def test_prevent_self_referral(self):
        """Test that a user cannot refer themselves"""
        # Create user
        user = User.objects.create_user(
            email='user@example.com',
            full_name='User',
            password='Pass123'
        )
        
        # Try to create self-referral
        from allauth.account.signals import email_confirmed
        request = self.factory.get('/')
        request.session = {}
        
        # Manually set session with self-referral code
        user_ref_code = UserReferralCode.objects.get(user=user).referral_code
        request.session['pending_referral_code'] = user_ref_code
        
        # Trigger signal
        email_obj = EmailAddress.objects.create(
            user=user,
            email=user.email,
            verified=True,
            primary=True
        )
        
        email_confirmed.send(
            sender=type(email_obj),
            request=request,
            email_address=email_obj
        )
        
        # No referral should be created
        self.assertFalse(Referral.objects.filter(referred=user).exists())
        
        # User should be marked as processed
        user.refresh_from_db()
        self.assertTrue(user.referral_code_processed)
    
    def test_prevent_duplicate_referrals(self):
        """Test that a user can only be referred once"""
        # Create two referrers
        referrer1 = User.objects.create_user(
            email='referrer1@example.com',
            full_name='Referrer 1',
            password='Pass123'
        )
        referrer2 = User.objects.create_user(
            email='referrer2@example.com',
            full_name='Referrer 2',
            password='Pass123'
        )
        
        # Create referred user
        referred = User.objects.create_user(
            email='referred@example.com',
            full_name='Referred',
            password='Pass123'
        )
        
        # Create first referral
        ref1_code = UserReferralCode.objects.get(user=referrer1).referral_code
        referral1 = Referral.objects.create(
            referrer=referrer1,
            referred=referred,
            referral_code=ref1_code
        )
        
        # Try to create second referral
        ref2_code = UserReferralCode.objects.get(user=referrer2).referral_code
        
        # Should not create (duplicate prevention)
        from allauth.account.signals import email_confirmed
        request = self.factory.get('/')
        request.session = {'pending_referral_code': ref2_code}
        
        email_obj = EmailAddress.objects.get(user=referred)
        
        email_confirmed.send(
            sender=type(email_obj),
            request=request,
            email_address=email_obj
        )
        
        # Only first referral should exist
        referrals = Referral.objects.filter(referred=referred)
        self.assertEqual(referrals.count(), 1)
        self.assertEqual(referrals.first().referrer, referrer1)
    
    def test_user_profile_creation_on_signup(self):
        """Test that UserProfile is created when User is created"""
        user = User.objects.create_user(
            email='user@example.com',
            full_name='User',
            password='Pass123'
        )
        
        # UserProfile should exist
        self.assertTrue(hasattr(user, 'profile'))
        self.assertIsNotNone(user.profile)
    
    def test_referral_code_generation(self):
        """Test that unique referral code is generated for each user"""
        user1 = User.objects.create_user(
            email='user1@example.com',
            full_name='User 1',
            password='Pass123'
        )
        user2 = User.objects.create_user(
            email='user2@example.com',
            full_name='User 2',
            password='Pass123'
        )
        
        code1 = UserReferralCode.objects.get(user=user1).referral_code
        code2 = UserReferralCode.objects.get(user=user2).referral_code
        
        # Codes should be different
        self.assertNotEqual(code1, code2)
        
        # Both should be valid format (8 characters)
        self.assertEqual(len(code1), 8)
        self.assertEqual(len(code2), 8)
