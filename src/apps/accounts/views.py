# apps/accounts/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.generic import TemplateView, UpdateView, CreateView
from django.urls import reverse_lazy
from django.db.models import Sum, Count, Q
from django.utils import timezone
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.http import JsonResponse
from django.core.paginator import Paginator
import secrets
import string

from .models import User, UserProfile, Referral
from .forms import UserProfileForm, ProfileUpdateForm, SecuritySettingsForm
from apps.trading.models import Investment, ProfitHistory
from apps.payments.models import Transaction, Wallet

class ProfileView(LoginRequiredMixin, TemplateView):
    """User profile dashboard"""
    template_name = 'account/profile.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Get or create user profile
        profile, created = UserProfile.objects.get_or_create(user=user)
        
        # Get user statistics
        total_investments = Investment.objects.filter(user=user).count()
        total_invested = Investment.objects.filter(user=user).aggregate(
            total=Sum('principal_amount')
        )['total'] or 0
        
        total_profits = ProfitHistory.objects.filter(user=user).aggregate(
            total=Sum('amount')
        )['total'] or 0
        
        # Get recent activity
        recent_transactions = Transaction.objects.filter(user=user).order_by('-created_at')[:5]
        recent_investments = Investment.objects.filter(user=user).order_by('-created_at')[:3]
        
        # Get referral information
        try:
            # Get the user's own referral code (from any referral record where they are the referrer or referred)
            referral = Referral.objects.filter(
                Q(referrer=user) | Q(referred=user)
            ).first()
            
            if referral:
                referral_code = referral.referral_code
            else:
                referral_code = self.generate_referral_code(user)
            
            # Get commission earned from referrals where user is the referrer
            referral_earnings = Referral.objects.filter(referrer=user).aggregate(
                total=Sum('commission_earned')
            )['total'] or 0
            
            # Count referred users (excluding self-referrals)
            referred_users = Referral.objects.filter(referrer=user).exclude(referred=user).count()
        except Exception:
            referral_code = self.generate_referral_code(user)
            referral_earnings = 0
            referred_users = 0
        
        context.update({
            'profile': profile,
            'total_investments': total_investments,
            'total_invested': total_invested,
            'total_profits': total_profits,
            'recent_transactions': recent_transactions,
            'recent_investments': recent_investments,
            'referral_code': referral_code,
            'referral_earnings': referral_earnings,
            'referred_users': referred_users,
        })
        
        return context
    
    def generate_referral_code(self, user):
        """Generate referral code for user if not exists"""
        try:
            # Try to find existing referral code for this user
            referral = Referral.objects.filter(
                Q(referrer=user) | Q(referred=user)
            ).first()
            
            if referral:
                return referral.referral_code
                
        except Referral.DoesNotExist:
            pass
        
        # Generate new code and create a placeholder referral record
        code = Referral.generate_referral_code(user)
        # Create a referral record for the user to store their referral code
        # We'll use the user as both referrer and referred initially
        # This will be updated when they actually refer someone
        Referral.objects.create(
            referrer=user,
            referred=user,  # Temporary self-referral for code storage
            referral_code=code
        )
        return code

class EditProfileView(LoginRequiredMixin, UpdateView):
    """Edit user profile information"""
    model = User
    form_class = UserProfileForm
    template_name = 'account/edit_profile.html'
    success_url = reverse_lazy('accounts:profile')
    
    def get_object(self):
        return self.request.user
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        if self.request.POST:
            context['profile_form'] = ProfileUpdateForm(
                self.request.POST, 
                self.request.FILES, 
                instance=self.request.user.profile
            )
        else:
            context['profile_form'] = ProfileUpdateForm(instance=self.request.user.profile)
        
        return context
    
    def form_valid(self, form):
        context = self.get_context_data()
        profile_form = context['profile_form']
        
        if profile_form.is_valid():
            # Save user form
            self.object = form.save()
            
            # Save profile form
            profile = profile_form.save(commit=False)
            profile.user = self.object
            profile.save()
            
            messages.success(self.request, 'Profile updated successfully!')
            return redirect(self.success_url)
        else:
            return self.render_to_response(self.get_context_data(form=form))

class SecurityView(LoginRequiredMixin, TemplateView):
    """Security settings and password change"""
    template_name = 'account/security.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['password_form'] = PasswordChangeForm(self.request.user)
        context['security_form'] = SecuritySettingsForm(instance=self.request.user.profile)
        return context
    
    def post(self, request, *args, **kwargs):
        if 'change_password' in request.POST:
            return self.change_password(request)
        elif 'update_security' in request.POST:
            return self.update_security_settings(request)
        
        return self.get(request, *args, **kwargs)
    
    def change_password(self, request):
        """Handle password change"""
        form = PasswordChangeForm(request.user, request.POST)
        
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)  # Keep user logged in
            messages.success(request, 'Password changed successfully!')
            return redirect('accounts:security')
        else:
            context = self.get_context_data()
            context['password_form'] = form
            return self.render_to_response(context)
    
    def update_security_settings(self, request):
        """Handle security settings update"""
        form = SecuritySettingsForm(request.POST, instance=request.user.profile)
        
        if form.is_valid():
            form.save()
            messages.success(request, 'Security settings updated successfully!')
            return redirect('accounts:security')
        else:
            context = self.get_context_data()
            context['security_form'] = form
            return self.render_to_response(context)

class ReferralView(LoginRequiredMixin, TemplateView):
    """Referral system dashboard"""
    template_name = 'account/referrals.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Get or create referral code
        try:
            user_referral = Referral.objects.filter(
                Q(referrer=user) | Q(referred=user)
            ).first()
            
            if user_referral:
                referral_code = user_referral.referral_code
            else:
                raise Referral.DoesNotExist
                
        except Referral.DoesNotExist:
            referral_code = Referral.generate_referral_code(user)
            Referral.objects.create(
                referrer=user,
                referred=user,  # Temporary self-referral
                referral_code=referral_code
            )
        
        # Get referred users
        referred_users = Referral.objects.filter(referrer=user).exclude(referred=user)
        
        # Get referral statistics
        total_referrals = referred_users.count()
        total_earnings = referred_users.aggregate(
            total=Sum('commission_earned')
        )['total'] or 0
        
        # Get recent referrals
        recent_referrals = referred_users.order_by('-created_at')[:10]
        
        # Pagination for referral list
        paginator = Paginator(referred_users.order_by('-created_at'), 10)
        page_number = self.request.GET.get('page')
        referrals_page = paginator.get_page(page_number)
        
        # Referral link
        referral_link = self.request.build_absolute_uri(
            f"/?ref={referral_code}"
        )
        
        context.update({
            'referral_code': referral_code,
            'referral_link': referral_link,
            'total_referrals': total_referrals,
            'total_earnings': total_earnings,
            'recent_referrals': recent_referrals,
            'referrals_page': referrals_page,
        })
        
        return context

class KYCVerificationView(LoginRequiredMixin, TemplateView):
    """KYC verification process"""
    template_name = 'account/kyc_verification.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['profile'] = self.request.user.profile
        return context
    
    def post(self, request, *args, **kwargs):
        profile = request.user.profile
        
        # Handle file uploads
        if 'id_document' in request.FILES:
            profile.id_document = request.FILES['id_document']
        
        # Update KYC information
        profile.id_number = request.POST.get('id_number', '')
        profile.date_of_birth = request.POST.get('date_of_birth')
        profile.address = request.POST.get('address', '')
        profile.city = request.POST.get('city', '')
        profile.postal_code = request.POST.get('postal_code', '')
        
        # Set KYC status to pending
        profile.kyc_status = 'pending'
        profile.save()
        
        messages.success(request, 'KYC documents submitted successfully! We will review your documents within 24-48 hours.')
        return redirect('accounts:profile')

class AccountActivityView(LoginRequiredMixin, TemplateView):
    """User account activity log"""
    template_name = 'account/activity.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Get all user transactions
        transactions = Transaction.objects.filter(user=user).order_by('-created_at')
        
        # Filter by type if specified
        transaction_type = self.request.GET.get('type')
        if transaction_type:
            transactions = transactions.filter(transaction_type=transaction_type)
        
        # Pagination
        paginator = Paginator(transactions, 20)
        page_number = self.request.GET.get('page')
        transactions_page = paginator.get_page(page_number)
        
        # Get transaction types for filter
        transaction_types = Transaction.objects.filter(user=user).values_list(
            'transaction_type', flat=True
        ).distinct()
        
        context.update({
            'transactions_page': transactions_page,
            'transaction_types': transaction_types,
            'selected_type': transaction_type,
        })
        
        return context

class NotificationsView(LoginRequiredMixin, TemplateView):
    """User notifications center"""
    template_name = 'account/notifications.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # For now, we'll use recent transactions and activities as notifications
        # In a full implementation, you'd have a separate Notification model
        
        notifications = []
        
        # Recent profits
        recent_profits = ProfitHistory.objects.filter(user=user).order_by('-date_earned')[:5]
        for profit in recent_profits:
            notifications.append({
                'type': 'profit',
                'title': 'Profit Earned',
                'message': f'You earned {profit.amount} from your {profit.investment.package.display_name}',
                'timestamp': profit.date_earned,
                'icon': 'fas fa-money-bill-wave',
                'color': 'green'
            })
        
        # Recent investments
        recent_investments = Investment.objects.filter(user=user).order_by('-created_at')[:3]
        for investment in recent_investments:
            notifications.append({
                'type': 'investment',
                'title': 'Investment Created',
                'message': f'Successfully invested {investment.principal_amount} in {investment.package.display_name}',
                'timestamp': investment.created_at,
                'icon': 'fas fa-chart-line',
                'color': 'blue'
            })
        
        # Sort notifications by timestamp
        notifications.sort(key=lambda x: x['timestamp'], reverse=True)
        
        context['notifications'] = notifications[:10]
        return context

@login_required
def generate_new_referral_code(request):
    """AJAX view to generate new referral code"""
    if request.method == 'POST':
        try:
            # Get existing referral or create new one
            referral, created = Referral.objects.get_or_create(
                referrer=request.user,
                defaults={'referred': request.user}
            )
            
            # Generate new code
            new_code = Referral.generate_referral_code(request.user)
            referral.referral_code = new_code
            referral.save()
            
            return JsonResponse({
                'success': True,
                'new_code': new_code,
                'message': 'New referral code generated successfully!'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': 'Error generating new code. Please try again.'
            })
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'})

@login_required
def delete_account(request):
    """Account deletion view"""
    if request.method == 'POST':
        password = request.POST.get('password')
        
        # Verify password
        if request.user.check_password(password):
            # Check for active investments
            active_investments = Investment.objects.filter(
                user=request.user,
                status='active'
            ).exists()
            
            if active_investments:
                messages.error(
                    request,
                    'Cannot delete account with active investments. Please wait for maturity or contact support.'
                )
                return redirect('accounts:security')
            
            # Check for pending withdrawals
            pending_withdrawals = Transaction.objects.filter(
                user=request.user,
                transaction_type='withdrawal',
                status__in=['pending', 'processing']
            ).exists()
            
            if pending_withdrawals:
                messages.error(
                    request,
                    'Cannot delete account with pending withdrawals. Please wait for completion or contact support.'
                )
                return redirect('accounts:security')
            
            # Mark user as inactive instead of deleting
            request.user.is_active = False
            request.user.save()
            
            messages.success(request, 'Account deactivated successfully.')
            return redirect('account_logout')
        else:
            messages.error(request, 'Incorrect password. Account deletion cancelled.')
            return redirect('accounts:security')
    
    return redirect('accounts:security')

class TwoFactorSetupView(LoginRequiredMixin, TemplateView):
    """Two-factor authentication setup"""
    template_name = 'account/2fa_setup.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        profile = self.request.user.profile
        context['two_factor_enabled'] = profile.two_factor_enabled
        return context
    
    def post(self, request, *args, **kwargs):
        action = request.POST.get('action')
        profile = request.user.profile
        
        if action == 'enable':
            # In a real implementation, you'd integrate with a 2FA library
            # For now, we'll just toggle the setting
            profile.two_factor_enabled = True
            profile.save()
            messages.success(request, 'Two-factor authentication enabled successfully!')
        
        elif action == 'disable':
            profile.two_factor_enabled = False
            profile.save()
            messages.success(request, 'Two-factor authentication disabled.')
        
        return redirect('accounts:security')

# Custom allauth views (if needed)
class CustomPasswordResetView(TemplateView):
    """Custom password reset view"""
    template_name = 'account/password_reset.html'

class CustomEmailVerificationView(TemplateView):
    """Custom email verification view"""
    template_name = 'account/email_verification_sent.html'