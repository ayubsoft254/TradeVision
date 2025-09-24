# apps/payments/views.py
from django.shortcuts import redirect, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.generic import TemplateView, ListView, DetailView, CreateView
from django.http import JsonResponse
from django.db.models import Sum, Avg
from django.utils import timezone
from django.conf import settings
from django.contrib.auth import get_user_model
from decimal import Decimal
import json
from django.views.decorators.http import require_POST

user = get_user_model()

from .models import (
    PaymentMethod, Wallet, Transaction, DepositRequest,
    WithdrawalRequest, Agent, P2PMerchant
)
from .forms import (
    DepositForm, WithdrawalForm, BinancePayForm, P2PForm,
    AgentTransactionForm, TransactionFilterForm, BankTransferForm,
    MobileMoneyForm, CryptoForm
)
from apps.core.models import SystemLog
from apps.trading.models import ProfitHistory

User = get_user_model()

class DepositView(LoginRequiredMixin, TemplateView):
    """Main deposit page with method selection"""
    template_name = 'payments/deposit.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Get user wallet
        wallet, created = Wallet.objects.get_or_create(
            user=user,
            defaults={'currency': settings.SUPPORTED_CURRENCIES.get(user.country.code, settings.DEFAULT_CURRENCY)}
        )
        
        # Get available payment methods for user's country
        # Fix: SQLite does not support contains lookup for JSONField
        if user.country and user.country.code:
            payment_methods = [m for m in PaymentMethod.objects.filter(is_active=True).order_by('name') if user.country.code in m.countries]
        else:
            # If user has no country set, show all payment methods
            payment_methods = list(PaymentMethod.objects.filter(is_active=True).order_by('name'))
        
        # Get recent deposits
        recent_deposits = Transaction.objects.filter(
            user=user,
            transaction_type='deposit'
        ).order_by('-created_at')[:5]
        
        # Deposit statistics
        deposit_stats = {
            'total_deposits': Transaction.objects.filter(
                user=user,
                transaction_type='deposit',
                status='completed'
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0'),
            'pending_deposits': Transaction.objects.filter(
                user=user,
                transaction_type='deposit',
                status__in=['pending', 'processing']
            ).count(),
            'this_month_deposits': Transaction.objects.filter(
                user=user,
                transaction_type='deposit',
                status='completed',
                created_at__month=timezone.now().month
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0'),
        }
        
        context.update({
            'wallet': wallet,
            'payment_methods': payment_methods,
            'recent_deposits': recent_deposits,
            'deposit_stats': deposit_stats,
        })
        
        return context

class DepositMethodView(LoginRequiredMixin, TemplateView):
    """Specific deposit method page"""
    template_name = 'payments/deposit_method.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        method_name = self.kwargs.get('method')
        user = self.request.user
        
        # Get payment method
        # Fix: SQLite does not support contains lookup for JSONField
        try:
            payment_method = next(
                m for m in PaymentMethod.objects.filter(name=method_name, is_active=True)
                if user.country.code in m.countries
            )
        except StopIteration:
            messages.error(self.request, 'Invalid payment method selected.')
            return context
        
        # Get user wallet
        wallet = user.wallet
        
        # Get appropriate form based on method
        form = self.get_deposit_form(method_name)
        
        # Get method-specific data
        method_data = self.get_method_data(method_name)
        
        context.update({
            'payment_method': payment_method,
            'wallet': wallet,
            'form': form,
            'method_data': method_data,
        })
        
        return context
    
    def get_deposit_form(self, method_name):
        """Get the appropriate form for the payment method"""
        if method_name == 'binance_pay':
            return BinancePayForm()
        elif method_name == 'p2p':
            return P2PForm(transaction_type='deposit', user=self.request.user)
        elif method_name == 'agent':
            return AgentTransactionForm(transaction_type='deposit', user=self.request.user)
        elif method_name == 'mobile_money':
            from .forms import MobileMoneyForm
            return MobileMoneyForm()
        elif method_name == 'bank_transfer':
            from .forms import BankTransferForm
            return BankTransferForm()
        elif method_name == 'crypto':
            from .forms import CryptoForm
            return CryptoForm()
        else:
            return DepositForm()
    
    def get_method_data(self, method_name):
        """Get method-specific data"""
        if method_name == 'p2p':
            merchants = P2PMerchant.objects.filter(
                is_active=True,
                country=self.request.user.country.code
            ).order_by('-rating')[:10]
            return {
                'merchants': [
                    {
                        'id': m.id,
                        'name': m.name,
                        'rating': m.rating,
                        'total_orders': m.total_orders,
                        'payment_methods': [pm.display_name for pm in m.payment_methods.all()]
                    }
                    for m in merchants
                ]
            }
        elif method_name == 'agent':
            try:
                agents = Agent.objects.filter(
                    is_active=True,
                    country=self.request.user.country.code
                ).order_by('-rating')[:10]
                return {
                    'agents': [
                        {
                            'id': a.id,
                            'name': a.name,
                            'rating': getattr(a, 'rating', 0),
                            'location': getattr(a, 'location', '')
                        }
                        for a in agents
                    ]
                }
            except:
                # Agent model might not exist yet
                return {'agents': []}
        return {}
    
    def post(self, request, *args, **kwargs):
        method_name = self.kwargs.get('method')
        
        # Fix: SQLite does not support contains lookup for JSONField
        try:
            if request.user.country and request.user.country.code:
                payment_method = next(
                    m for m in PaymentMethod.objects.filter(name=method_name, is_active=True)
                    if request.user.country.code in m.countries
                )
            else:
                # If user has no country, allow any active payment method
                payment_method = PaymentMethod.objects.get(name=method_name, is_active=True)
        except (StopIteration, PaymentMethod.DoesNotExist):
            messages.error(request, 'Invalid payment method selected.')
            return redirect('payments:deposit')
        
        # Get appropriate form
        if method_name == 'binance_pay':
            form = BinancePayForm(request.POST, request.FILES)
        elif method_name == 'p2p':
            form = P2PForm(request.POST, request.FILES, transaction_type='deposit', user=request.user)
        elif method_name == 'agent':
            form = AgentTransactionForm(request.POST, request.FILES, transaction_type='deposit', user=request.user)
        elif method_name == 'mobile_money':
            from .forms import MobileMoneyForm
            form = MobileMoneyForm(request.POST, request.FILES)
        elif method_name == 'bank_transfer':
            from .forms import BankTransferForm
            form = BankTransferForm(request.POST, request.FILES)
        elif method_name == 'crypto':
            from .forms import CryptoForm
            form = CryptoForm(request.POST, request.FILES)
        else:
            form = DepositForm(request.POST, request.FILES)
        
        if form.is_valid():
            return self.process_deposit(request, form, payment_method)
        
        context = self.get_context_data()
        context['form'] = form
        return self.render_to_response(context)
    
    def process_deposit(self, request, form, payment_method):
        """Process the deposit request"""
        amount = form.cleaned_data['amount']
        
        # Calculate fees
        processing_fee = amount * (payment_method.processing_fee / 100)
        net_amount = amount - processing_fee
        
        # Create transaction
        transaction = Transaction.objects.create(
            user=request.user,
            transaction_type='deposit',
            amount=amount,
            currency=request.user.wallet.currency,
            status='pending',
            payment_method=payment_method,
            processing_fee=processing_fee,
            net_amount=net_amount,
            description=f'Deposit via {payment_method.display_name}'
        )
        
        # Create deposit request
        # Convert Decimal values to strings and exclude file fields for JSON serialization
        payment_details = {}
        for key, value in form.cleaned_data.items():
            # Skip file fields as they're handled separately
            if key == 'payment_proof':
                continue
            elif isinstance(value, Decimal):
                payment_details[key] = str(value)
            elif hasattr(value, 'pk'):  # Django model instance
                payment_details[key] = str(value.pk)
                payment_details[f'{key}_name'] = str(value)  # Also store the string representation
            else:
                payment_details[key] = value
        
        deposit_request = DepositRequest.objects.create(
            transaction=transaction,
            payment_details=payment_details
        )
        
        # Handle file upload if present in form
        if 'payment_proof' in form.cleaned_data and form.cleaned_data['payment_proof']:
            deposit_request.payment_proof = form.cleaned_data['payment_proof']
            deposit_request.save()
        
        # Log the deposit request
        SystemLog.objects.create(
            user=request.user,
            action_type='deposit',
            level='INFO',
            message=f'User requested deposit of {amount} {request.user.wallet.currency} via {payment_method.display_name}',
            ip_address=request.META.get('REMOTE_ADDR'),
            metadata={
                'transaction_id': str(transaction.id),
                'payment_method': payment_method.name,
                'amount': str(amount)
            }
        )
        
        messages.success(
            request,
            f'Deposit request submitted successfully! Amount: {amount} {request.user.wallet.currency}. '
            f'You will receive {net_amount} {request.user.wallet.currency} after processing.'
        )
        
        return redirect('payments:transaction_detail', transaction_id=transaction.id)

class WithdrawView(LoginRequiredMixin, TemplateView):
    """Main withdrawal page"""
    template_name = 'payments/withdraw.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Get user wallet
        wallet = user.wallet
        
        # Get available payment methods for withdrawals
        # Fix: SQLite does not support contains lookup for JSONField
        payment_methods = [m for m in PaymentMethod.objects.filter(is_active=True).order_by('name') if user.country.code in m.countries]
        
        # Get recent withdrawals
        recent_withdrawals = Transaction.objects.filter(
            user=user,
            transaction_type='withdrawal'
        ).order_by('-created_at')[:5]
        
        # Withdrawal statistics
        withdrawal_stats = {
            'total_withdrawals': Transaction.objects.filter(
                user=user,
                transaction_type='withdrawal',
                status='completed'
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0'),
            'pending_withdrawals': Transaction.objects.filter(
                user=user,
                transaction_type='withdrawal',
                status__in=['pending', 'processing']
            ).count(),
            'available_balance': wallet.profit_balance,
        }
        
        context.update({
            'wallet': wallet,
            'payment_methods': payment_methods,
            'recent_withdrawals': recent_withdrawals,
            'withdrawal_stats': withdrawal_stats,
        })
        
        return context

class WithdrawMethodView(LoginRequiredMixin, TemplateView):
    """Specific withdrawal method page"""
    template_name = 'payments/withdraw_method.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        method_name = self.kwargs.get('method')
        user = self.request.user
        
        # Get payment method
        # Fix: SQLite does not support contains lookup for JSONField
        try:
            payment_method = next(
                m for m in PaymentMethod.objects.filter(name=method_name, is_active=True)
                if user.country.code in m.countries
            )
        except StopIteration:
            messages.error(self.request, 'Invalid payment method selected.')
            return context
        
        # Get user wallet
        wallet = user.wallet
        
        # Check if user has withdrawable balance
        if wallet.profit_balance <= 0:
            messages.warning(self.request, 'You have no profits available for withdrawal.')
            return context
        
        # Get appropriate form
        form = self.get_withdrawal_form(method_name)
        
        # Get method-specific data
        method_data = self.get_method_data(method_name)
        
        context.update({
            'payment_method': payment_method,
            'wallet': wallet,
            'form': form,
            'method_data': method_data,
        })
        
        return context
    
    def get_withdrawal_form(self, method_name):
        """Get the appropriate form for the payment method"""
        user = self.request.user
        
        if method_name == 'binance_pay':
            return BinancePayForm(transaction_type='withdrawal')
        elif method_name == 'mobile_money':
            return MobileMoneyForm(transaction_type='withdrawal', user=user)
        elif method_name == 'bank_transfer':
            return BankTransferForm()
        elif method_name == 'crypto':
            return CryptoForm()
        elif method_name == 'p2p':
            return P2PForm(transaction_type='withdrawal', user=user)
        elif method_name == 'agent':
            return AgentTransactionForm(transaction_type='withdrawal', user=user)
        else:
            return WithdrawalForm(user=user)
    
    def get_method_data(self, method_name):
        """Get method-specific data"""
        if method_name == 'p2p':
            merchants = P2PMerchant.objects.filter(
                is_active=True,
                country=self.request.user.country.code
            ).order_by('-rating')[:10]
            return {
                'merchants': [
                    {
                        'id': m.id,
                        'name': m.name,
                        'rating': m.rating,
                        'total_orders': m.total_orders,
                        'payment_methods': [pm.display_name for pm in m.payment_methods.all()]
                    }
                    for m in merchants
                ]
            }
        elif method_name == 'agent':
            try:
                agents = Agent.objects.filter(
                    is_active=True,
                    country=self.request.user.country.code
                ).order_by('-rating')[:10]
                return {
                    'agents': [
                        {
                            'id': a.id,
                            'name': a.name,
                            'rating': getattr(a, 'rating', 0),
                            'location': getattr(a, 'location', '')
                        }
                        for a in agents
                    ]
                }
            except:
                # Agent model might not exist yet
                return {'agents': []}
        return {}
    
    def post(self, request, *args, **kwargs):
        method_name = self.kwargs.get('method')
        user = request.user
        
        # Fix: SQLite does not support contains lookup for JSONField
        try:
            payment_method = next(
                m for m in PaymentMethod.objects.filter(name=method_name, is_active=True)
                if user.country.code in m.countries
            )
        except StopIteration:
            messages.error(request, 'Invalid payment method selected.')
            return redirect('payments:withdraw')
        
        # Get appropriate form with POST data
        if method_name == 'binance_pay':
            form = BinancePayForm(request.POST, request.FILES, transaction_type='withdrawal')
        elif method_name == 'mobile_money':
            form = MobileMoneyForm(request.POST, request.FILES, transaction_type='withdrawal', user=user)
        elif method_name == 'bank_transfer':
            form = BankTransferForm(request.POST, request.FILES)
        elif method_name == 'crypto':
            form = CryptoForm(request.POST, request.FILES)
        elif method_name == 'p2p':
            form = P2PForm(request.POST, request.FILES, transaction_type='withdrawal', user=user)
        elif method_name == 'agent':
            form = AgentTransactionForm(request.POST, request.FILES, transaction_type='withdrawal', user=user)
        else:
            form = WithdrawalForm(request.POST, request.FILES, user=user)
        
        if form.is_valid():
            return self.process_withdrawal(request, form, payment_method)
        
        context = self.get_context_data()
        context['form'] = form
        return self.render_to_response(context)
    
    def process_withdrawal(self, request, form, payment_method):
        """Process the withdrawal request"""
        amount = form.cleaned_data['amount']
        wallet = request.user.wallet
        
        # Check available balance
        if amount > wallet.profit_balance:
            messages.error(request, 'Insufficient profit balance for withdrawal.')
            return redirect('payments:withdraw')
        
        # Calculate fees
        processing_fee = amount * (payment_method.processing_fee / 100)
        net_amount = amount - processing_fee
        
        # Create transaction
        transaction = Transaction.objects.create(
            user=request.user,
            transaction_type='withdrawal',
            amount=amount,
            currency=wallet.currency,
            status='pending',
            payment_method=payment_method,
            processing_fee=processing_fee,
            net_amount=net_amount,
            description=f'Withdrawal via {payment_method.display_name}'
        )
        
        # Create withdrawal request
        # Convert Decimal values to strings and exclude file fields for JSON serialization
        withdrawal_address = {}
        for key, value in form.cleaned_data.items():
            # Skip file fields as they're handled separately
            if key in ['payment_proof', 'confirm_withdrawal']:
                continue
            elif isinstance(value, Decimal):
                withdrawal_address[key] = str(value)
            elif hasattr(value, 'pk'):  # Django model instance
                withdrawal_address[key] = str(value.pk)
                withdrawal_address[f'{key}_name'] = str(value)  # Also store the string representation
            else:
                withdrawal_address[key] = value
        
        withdrawal_request = WithdrawalRequest.objects.create(
            transaction=transaction,
            withdrawal_address=withdrawal_address
        )
        
        # Update wallet balance (reserve the amount)
        wallet.profit_balance -= amount
        wallet.save()
        
        # Mark related profits as withdrawn
        profits_to_mark = ProfitHistory.objects.filter(
            user=request.user,
            is_withdrawn=False
        ).order_by('date_earned')
        
        remaining_amount = amount
        for profit in profits_to_mark:
            if remaining_amount <= 0:
                break
            if profit.amount <= remaining_amount:
                profit.is_withdrawn = True
                profit.save()
                remaining_amount -= profit.amount
        
        # Log the withdrawal request
        SystemLog.objects.create(
            user=request.user,
            action_type='withdrawal',
            level='INFO',
            message=f'User requested withdrawal of {amount} {wallet.currency} via {payment_method.display_name}',
            ip_address=request.META.get('REMOTE_ADDR'),
            metadata={
                'transaction_id': str(transaction.id),
                'payment_method': payment_method.name,
                'amount': str(amount)
            }
        )
        
        messages.success(
            request,
            f'Withdrawal request submitted successfully! Amount: {amount} {wallet.currency}. '
            f'You will receive {net_amount} {wallet.currency} after processing and fees.'
        )
        
        return redirect('payments:transaction_detail', transaction_id=transaction.id)

class TransactionHistoryView(LoginRequiredMixin, ListView):
    """Transaction history with filtering"""
    model = Transaction
    template_name = 'payments/transaction_history.html'
    context_object_name = 'transactions'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = Transaction.objects.filter(
            user=self.request.user
        ).select_related('payment_method').order_by('-created_at')
        
        # Apply filters
        transaction_type = self.request.GET.get('type')
        if transaction_type:
            queryset = queryset.filter(transaction_type=transaction_type)
        
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        start_date = self.request.GET.get('start_date')
        if start_date:
            queryset = queryset.filter(created_at__date__gte=start_date)
        
        end_date = self.request.GET.get('end_date')
        if end_date:
            queryset = queryset.filter(created_at__date__lte=end_date)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get filter form
        filter_form = TransactionFilterForm(self.request.GET)
        
        # Get transaction statistics
        user_transactions = Transaction.objects.filter(user=self.request.user)
        
        stats = {
            'total_transactions': user_transactions.count(),
            'total_deposits': user_transactions.filter(
                transaction_type='deposit',
                status='completed'
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0'),
            'total_withdrawals': user_transactions.filter(
                transaction_type='withdrawal',
                status='completed'
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0'),
            'pending_transactions': user_transactions.filter(
                status__in=['pending', 'processing']
            ).count(),
        }
        
        context.update({
            'filter_form': filter_form,
            'stats': stats,
        })
        
        return context

class TransactionDetailView(LoginRequiredMixin, DetailView):
    """Individual transaction details"""
    model = Transaction
    template_name = 'payments/transaction_detail.html'
    context_object_name = 'transaction'
    pk_url_kwarg = 'transaction_id'
    
    def get_queryset(self):
        return Transaction.objects.filter(user=self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get related request details
        deposit_request = None
        withdrawal_request = None
        merchant = None
        merchant_payment_details = {}
        all_merchant_payment_methods = []
        
        if self.object.transaction_type == 'deposit':
            try:
                deposit_request = DepositRequest.objects.get(transaction=self.object)
                # Try to get merchant if available (P2P or agent)
                if self.object.payment_method:
                    # Check for P2P merchant
                    from .models import P2PMerchant, Agent
                    merchant = None
                    # Try to find a P2PMerchant or Agent related to this transaction
                    # (Assume metadata or payment_details may have merchant_id or agent_id)
                    merchant_id = None
                    agent_id = None
                    if deposit_request.payment_details:
                        merchant_id = deposit_request.payment_details.get('merchant_id')
                        agent_id = deposit_request.payment_details.get('agent_id')
                    if merchant_id:
                        try:
                            merchant = P2PMerchant.objects.get(id=merchant_id)
                        except P2PMerchant.DoesNotExist:
                            merchant = None
                    elif agent_id:
                        try:
                            merchant = Agent.objects.get(id=agent_id)
                        except Agent.DoesNotExist:
                            merchant = None
                    # If not found by id, optionally try to find by email/phone if present
                    if not merchant and deposit_request.payment_details:
                        email = deposit_request.payment_details.get('merchant_email')
                        if email:
                            try:
                                merchant = P2PMerchant.objects.filter(email=email).first() or Agent.objects.filter(email=email).first()
                            except Exception:
                                merchant = None
                    
                    # Get all payment details for the merchant
                    if merchant and hasattr(merchant, 'get_mobile_money_details'):
                        # This is a P2PMerchant
                        mobile_money = merchant.get_mobile_money_details()
                        bank_transfer = merchant.get_bank_transfer_details()
                        
                        if mobile_money:
                            all_merchant_payment_methods.append({
                                'method': 'Mobile Money',
                                'details': mobile_money
                            })
                        if bank_transfer:
                            all_merchant_payment_methods.append({
                                'method': 'Bank Transfer',
                                'details': bank_transfer
                            })
                        
                        # Get payment details for the specific method used
                        if self.object.payment_method:
                            merchant_payment_details = merchant.get_payment_details_for_method(self.object.payment_method.name) or {}
                    elif merchant:
                        # This is an Agent - show basic contact info
                        merchant_payment_details = {
                            'name': merchant.name,
                            'phone': merchant.phone_number,
                            'email': merchant.email,
                            'address': merchant.address
                        }
                        all_merchant_payment_methods.append({
                            'method': 'Cash/Local Agent',
                            'details': merchant_payment_details
                        })
            except DepositRequest.DoesNotExist:
                pass
        elif self.object.transaction_type == 'withdrawal':
            try:
                withdrawal_request = WithdrawalRequest.objects.get(transaction=self.object)
            except WithdrawalRequest.DoesNotExist:
                pass
        
        context.update({
            'deposit_request': deposit_request,
            'withdrawal_request': withdrawal_request,
            'merchant': merchant,
            'merchant_payment_details': merchant_payment_details,
            'all_merchant_payment_methods': all_merchant_payment_methods,
        })
        
        return context

class AgentsView(LoginRequiredMixin, ListView):
    """List of available agents"""
    model = Agent
    template_name = 'payments/agents.html'
    context_object_name = 'agents'
    paginate_by = 20
    
    def get_queryset(self):
        return Agent.objects.filter(
            is_active=True,
            country=self.request.user.country.code
        ).order_by('-rating', '-total_transactions')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get agent statistics
        stats = {
            'total_agents': self.get_queryset().count(),
            'verified_agents': self.get_queryset().filter(is_verified=True).count(),
            'avg_rating': self.get_queryset().aggregate(
                avg_rating=Avg('rating')
            )['avg_rating'] or 0,
        }
        
        context['stats'] = stats
        return context

class P2PView(LoginRequiredMixin, ListView):
    """List of P2P merchants"""
    model = P2PMerchant
    template_name = 'payments/p2p.html'
    context_object_name = 'merchants'
    paginate_by = 20
    
    def get_queryset(self):
        return P2PMerchant.objects.filter(
            is_active=True,
            country=self.request.user.country.code
        ).order_by('-rating', '-total_orders')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get merchant statistics
        stats = {
            'total_merchants': self.get_queryset().count(),
            'verified_merchants': self.get_queryset().filter(is_verified=True).count(),
            'avg_rating': self.get_queryset().aggregate(
                avg_rating=Avg('rating')
            )['avg_rating'] or 0,
        }
        
        context['stats'] = stats
        return context

# AJAX Views
@login_required
def get_payment_methods(request):
    """AJAX view to get available payment methods"""
    country_code = request.user.country.code
    
    # Fix: SQLite does not support contains lookup for JSONField
    methods = [
        {
            'name': m.name,
            'display_name': m.display_name,
            'processing_fee': m.processing_fee,
            'processing_time': m.processing_time
        }
        for m in PaymentMethod.objects.filter(is_active=True)
        if country_code in m.countries
    ]
    return JsonResponse({
        'success': True,
        'methods': methods
    })

@login_required
def calculate_fees(request):
    """AJAX view to calculate transaction fees"""
    amount = request.GET.get('amount')
    method_name = request.GET.get('method')
    
    try:
        amount = Decimal(amount)
        # Fix: SQLite does not support contains lookup for JSONField
        payment_method = next(
            m for m in PaymentMethod.objects.filter(name=method_name, is_active=True)
            if request.user.country.code in m.countries
        )
        
        processing_fee = amount * (payment_method.processing_fee / 100)
        net_amount = amount - processing_fee
        
        return JsonResponse({
            'success': True,
            'data': {
                'amount': float(amount),
                'processing_fee': float(processing_fee),
                'net_amount': float(net_amount),
                'fee_percentage': float(payment_method.processing_fee)
            }
        })
        
    except (ValueError, PaymentMethod.DoesNotExist):
        return JsonResponse({
            'success': False,
            'error': 'Invalid amount or payment method'
        })

@login_required
def wallet_balance(request):
    """AJAX view to get current wallet balance"""
    wallet = request.user.wallet
    
    return JsonResponse({
        'success': True,
        'data': {
            'total_balance': float(wallet.total_balance),
            'available_balance': float(wallet.balance),
            'profit_balance': float(wallet.profit_balance),
            'locked_balance': float(wallet.locked_balance),
            'currency': wallet.currency
        }
    })

@login_required
def transaction_status(request, transaction_id):
    """AJAX view to get transaction status"""
    try:
        transaction = Transaction.objects.get(
            id=transaction_id,
            user=request.user
        )
        
        return JsonResponse({
            'success': True,
            'data': {
                'status': transaction.status,
                'amount': float(transaction.amount),
                'net_amount': float(transaction.net_amount),
                'created_at': transaction.created_at.isoformat(),
                'completed_at': transaction.completed_at.isoformat() if transaction.completed_at else None
            }
        })
        
    except Transaction.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Transaction not found'
        })

@require_POST
@login_required
def withdraw_profit(request):
    try:
        data = json.loads(request.body)
        profit_id = data.get('profit_id')
        profit = get_object_or_404(ProfitHistory, id=profit_id, user=request.user, is_withdrawn=False)

        wallet = request.user.wallet

        # Transfer profit to wallet
        wallet.profit_balance -= Decimal(profit.amount)
        wallet.balance += Decimal(profit.amount)
        wallet.save()

        # Mark profit as withdrawn
        profit.is_withdrawn = True
        profit.save()

        # Log transaction
        Transaction.objects.create(
            user=request.user,
            transaction_type='profit_withdrawal',
            amount=profit.amount,
            currency=wallet.currency,
            status='completed',
            net_amount=profit.amount,
            description=f'Profit withdrawal (ID: {profit.id})'
        )

        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

"""
@login_required
@require_POST
def upload_payment_proof(request, transaction_id):
    # Upload payment proof for a deposit transaction
    try:
        # Get the transaction
        transaction = get_object_or_404(Transaction, id=transaction_id, user=request.user)
        
        # Check if it's a deposit transaction
        if transaction.transaction_type != 'deposit':
            messages.error(request, 'Payment proof can only be uploaded for deposit transactions.')
            return redirect('payments:transaction_detail', transaction_id=transaction_id)
        
        # Check if transaction is still pending
        if transaction.status not in ['pending', 'processing']:
            messages.error(request, 'Payment proof can only be uploaded for pending transactions.')
            return redirect('payments:transaction_detail', transaction_id=transaction_id)
        
        # Get or create deposit request
        deposit_request, created = DepositRequest.objects.get_or_create(
            transaction=transaction,
            defaults={'payment_details': {}}
        )
        
        # Check if proof file was uploaded
        if 'payment_proof' not in request.FILES:
            messages.error(request, 'Please select a payment proof file to upload.')
            return redirect('payments:transaction_detail', transaction_id=transaction_id)
        
        # Update the deposit request with the new proof
        deposit_request.payment_proof = request.FILES['payment_proof']
        deposit_request.save()
        
        # Log the upload
        SystemLog.objects.create(
            user=request.user,
            action='payment_proof_uploaded',
            description=f'Payment proof uploaded for transaction {transaction.id}',
            metadata={
                'transaction_id': str(transaction.id),
                'amount': float(transaction.amount),
                'payment_method': transaction.payment_method.display_name if transaction.payment_method else 'Unknown'
            }
        )
        
        messages.success(request, 'Payment proof uploaded successfully! Your deposit will be processed shortly.')
        return redirect('payments:transaction_detail', transaction_id=transaction_id)
        
    except Exception as e:
        messages.error(request, f'Error uploading payment proof: {str(e)}')
        return redirect('payments:transaction_detail', transaction_id=transaction_id)
"""