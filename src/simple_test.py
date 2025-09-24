from apps.accounts.models import User, Referral
from django.test import RequestFactory
from django.contrib.sessions.middleware import SessionMiddleware
from apps.accounts.forms import CustomSignupForm

print("Testing Referral Functionality...")

# Clean up
User.objects.filter(email__in=['test_referrer@example.com', 'test_referred@example.com']).delete()

# Create referrer
referrer = User.objects.create_user(
    email='test_referrer@example.com',
    full_name='Test Referrer',
    password='testpass123'
)

# Generate referral code
referral_code = Referral.generate_referral_code(referrer)
Referral.objects.create(
    referrer=referrer,
    referred=referrer,
    referral_code=referral_code
)

print(f"Referrer created with code: {referral_code}")

# Test referral signup
factory = RequestFactory()
request = factory.post('/accounts/signup/', {
    'email': 'test_referred@example.com',
    'full_name': 'Test Referred',
    'password1': 'testpass123',
    'password2': 'testpass123',
    'phone_number': '+254700000000',
    'country': 'KE',
    'referral_code': referral_code
})

middleware = SessionMiddleware(lambda req: None)
middleware.process_request(request)
request.session.save()

form = CustomSignupForm(request.POST, request=request)
if form.is_valid():
    user = form.save(request)
    print(f"User created: {user.email}")
    
    # Check referral
    referral_exists = Referral.objects.filter(
        referrer=referrer,
        referred=user
    ).exists()
    
    print(f"Referral created: {referral_exists}")
else:
    print("Form errors:", form.errors)

print("Test completed")