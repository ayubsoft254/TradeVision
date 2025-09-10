# apps/payments/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.generic import TemplateView, ListView, DetailView, CreateView
from django.urls import reverse_lazy
from django.http import JsonResponse, Http404
from django.db.models import Sum, Count, Q, Avg
from django.utils import timezone
from django.conf import settings
from django.core.paginator import Paginator
from decimal import Decimal
import json
from datetime import timedelta

from .models import (
    PaymentMethod, Wallet, Transaction, DepositRequest,
    WithdrawalRequest, Agent, P2PMerchant
)
from .forms import (
    DepositForm, WithdrawalForm, BinancePayForm, P2PForm,
    AgentTransactionForm, TransactionFilterForm
)
from apps.core.models import SystemLog
from apps.trading.models import ProfitHistory

class DepositView(LoginRequiredMixin, TemplateView):
    """Main deposit page with method selection"""
    template_name = 'payments/deposit.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Get user wallet
        wallet, created = Wallet.objects.get_or_create(
            user=user,
            defaults={'currency': settings.SUPPORTED_CURRENCIES.get(user.country.code, 'KSH')}
        )
        
        # Get available payment methods for user's country
        payment_methods = PaymentMethod.objects.filter(
            is_active=True,
            countries__contains=[user.country.code]
        ).order_by('name')
        
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
        try:
            payment_method = PaymentMethod.objects.get(
                name=method_name,
                is_active=True,
                countries__contains=[user.country.code]
            )
        except PaymentMethod.DoesNotExist:
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
            return P2PForm(transaction_type='deposit')
        elif method_name == 'agent':
            return AgentTransactionForm(transaction_type='deposit')
        else:
            return DepositForm()
    
    def get_method_data(self, method_name):
        """Get method-specific data"""
        if method_name == 'p2p':
            return {
                'merchants': P2PMerchant.objects.filter(
                    is_active=True,
                    country=self.request.user.country.code
                ).order_by('-rating')[:10]
            }
        elif method_name == 'agent':
            return {
                'agents': Agent.objects.filter(
                    is_active=True,
                    country=self.request.user.country.code
                ).order_by('-rating')[:10]
            }
        return {}
    
    def post(self, request, *args, **kwargs):
        method_name = self.kwargs.get('method')
        
        try:
            payment_method = PaymentMethod.objects.get(
                name=method_name,
                is_active=True,
                countries__contains=[request.user.country.code]
            )
        except PaymentMethod.DoesNotExist:
            messages.error(request, 'Invalid payment method selected.')
            return redirect('payments:deposit')
        
        # Get appropriate form
        if method_name == 'binance_pay':
            form = BinancePayForm(request.POST)
        elif method_name == 'p2p':
            form = P2PForm(request.POST, transaction_type='deposit')
        elif method_name == 'agent':
            form = AgentTransactionForm(request.POST, transaction_type='deposit')
        else:
            form = DepositForm(request.POST)
        
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
        deposit_request = DepositRequest.objects.create(
            transaction=transaction,
            payment_details=form.cleaned_data
        )
        
        # Handle file upload if present
        if 'payment_proof' in request.FILES:
            deposit_request.payment_proof = request.FILES['payment_proof']
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
        payment_methods = PaymentMethod.objects.filter(
            is_active=True,
            countries__contains=[user.country.code]
        ).order_by('name')
        
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
        try:
            payment_method = PaymentMethod.objects.get(
                name=method_name,
                is_active=True,
                countries__contains=[user.country.code]
            )
        except PaymentMethod.DoesNotExist:
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
        if method_name == 'binance_pay':
            return BinancePayForm(transaction_type='withdrawal')
        elif method_name == 'p2p':
            return P2PForm(transaction_type='withdrawal')
        elif method_name == 'agent':
            return AgentTransactionForm(transaction_type='withdrawal')
        else:
            return WithdrawalForm()
    
    def get_method_data(self, method_name):
        """Get method-specific data"""
        if method_name == 'p2p':
            return {
                'merchants': P2PMerchant.objects.filter(
                    is_active=True,
                    country=self.request.user.country.code
                ).order_by('-rating')[:10]
            }
        elif method_name == 'agent':
            return {
                'agents': Agent.objects.filter(
                    is_active=True,
                    country=self.request.user.country.code
                ).order_by('-rating')[:10]
            }
        return {}
    
    def post(self, request, *args, **kwargs):
        method_name = self.kwargs.get('method')
        
        try:
            payment_method = PaymentMethod.objects.get(
                name=method_name,
                is_active=True,
                countries__contains=[request.user.country.code]
            )
        except PaymentMethod.DoesNotExist:
            messages.error(request, 'Invalid payment method selected.')
            return redirect('payments:withdraw')
        
        # Get appropriate form
        if method_name == 'binance_pay':
            form = BinancePayForm(request.POST, transaction_type='withdrawal')
        elif method_name == 'p2p':
            form = P2PForm(request.POST, transaction_type='withdrawal')
        elif method_name == 'agent':
            form = AgentTransactionForm(request.POST, transaction_type='withdrawal')
        else:
            form = WithdrawalForm(request.POST)
        
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
        withdrawal_request = WithdrawalRequest.objects.create(
            transaction=transaction,
            withdrawal_address=form.cleaned_data
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
        
        if self.object.transaction_type == 'deposit':
            try:
                deposit_request = DepositRequest.objects.get(transaction=self.object)
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
    
    methods = PaymentMethod.objects.filter(
        is_active=True,
        countries__contains=[country_code]
    ).values('name', 'display_name', 'processing_fee', 'processing_time')
    
    return JsonResponse({
        'success': True,
        'methods': list(methods)
    })

@login_required
def calculate_fees(request):
    """AJAX view to calculate transaction fees"""
    amount = request.GET.get('amount')
    method_name = request.GET.get('method')
    
    try:
        amount = Decimal(amount)
        payment_method = PaymentMethod.objects.get(
            name=method_name,
            is_active=True,
            countries__contains=[request.user.country.code]
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