# apps/trading/views.py
from django.shortcuts import redirect
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.contrib import messages
from django.views.generic import TemplateView, DetailView, ListView
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse
from django.db.models import Sum, Count, Avg
from django.utils import timezone
from django.conf import settings
from decimal import Decimal
import json
from datetime import timedelta
from .models import TradingPackage, Investment, Trade, ProfitHistory
from .forms import InvestmentForm, TradeInitiationForm
from apps.payments.models import Wallet, Transaction
from apps.core.models import SystemLog
from django.db import transaction as db_transaction
import logging

logger = logging.getLogger(__name__)

class DashboardView(LoginRequiredMixin, TemplateView):
    """Main trading dashboard"""
    template_name = 'trading/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = get_user_model().objects.get(pk=self.request.user.pk)
        
        # Get or create user wallet
        wallet, created = Wallet.objects.get_or_create(
            user=user,
            defaults={'currency': settings.SUPPORTED_CURRENCIES.get(user.country.code, settings.DEFAULT_CURRENCY)}
        )
        
        # User investments statistics
        investments = Investment.objects.filter(user=user)
        active_investments = investments.filter(status='active')
        
        # Trading statistics
        total_invested = investments.aggregate(
            total=Sum('principal_amount')
        )['total'] or Decimal('0')
        
        total_profits = ProfitHistory.objects.filter(user=user).aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0')
        
        # Active trades
        active_trades = Trade.objects.filter(
            investment__user=user,
            status__in=['pending', 'running']
        ).select_related('investment', 'investment__package').order_by('-created_at')[:5]
        
        # Recent profits
        recent_profits = ProfitHistory.objects.filter(user=user).select_related(
            'investment', 'investment__package'
        ).order_by('-date_earned')[:5]
        
        # Daily profit chart data (last 7 days)
        profit_chart_data = self.get_profit_chart_data(user)
        
        # Investment distribution
        investment_distribution = self.get_investment_distribution(user)
        
        # Performance metrics
        performance_metrics = self.get_performance_metrics(user)
        
        context.update({
            'wallet': wallet,
            'active_investments': active_investments,
            'total_invested': total_invested,
            'total_profits': total_profits,
            'active_trades': active_trades,
            'recent_profits': recent_profits,
            'profit_chart_data': json.dumps(profit_chart_data),
            'investment_distribution': json.dumps(investment_distribution),
            'performance_metrics': performance_metrics,
            'trading_allowed': self.is_trading_allowed(),
            'user': user,
        })
        
        return context
    
    def get_profit_chart_data(self, user):
        """Get profit data for chart visualization"""
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=6)
        
        profits_by_date = {}
        current_date = start_date
        
        while current_date <= end_date:
            profits_by_date[current_date.strftime('%Y-%m-%d')] = 0
            current_date += timedelta(days=1)
        
        # Get actual profit data
        profits = ProfitHistory.objects.filter(
            user=user,
            date_earned__date__gte=start_date,
            date_earned__date__lte=end_date
        ).values('date_earned__date').annotate(
            total_profit=Sum('amount')
        )
        
        for profit in profits:
            date_str = profit['date_earned__date'].strftime('%Y-%m-%d')
            profits_by_date[date_str] = float(profit['total_profit'])
        
        return {
            'labels': list(profits_by_date.keys()),
            'data': list(profits_by_date.values())
        }
    
    def get_investment_distribution(self, user):
        """Get investment distribution by package"""
        investments = Investment.objects.filter(
            user=user,
            status='active'
        ).values('package__display_name').annotate(
            total_amount=Sum('principal_amount'),
            count=Count('id')
        )
        
        # Handle empty data case
        if not investments.exists():
            return {
                'labels': ['No Investments'],
                'data': [0]
            }
        
        return {
            'labels': [inv['package__display_name'] for inv in investments],
            'data': [float(inv['total_amount']) for inv in investments]
        }
    
    def get_performance_metrics(self, user):
        """Calculate performance metrics"""
        total_invested = Investment.objects.filter(user=user).aggregate(
            total=Sum('principal_amount')
        )['total'] or Decimal('0')
        
        total_profits = ProfitHistory.objects.filter(user=user).aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0')
        
        avg_daily_profit = ProfitHistory.objects.filter(user=user).aggregate(
            avg=Avg('amount')
        )['avg'] or Decimal('0')
        
        # ROI calculation
        roi = (total_profits / total_invested * 100) if total_invested > 0 else 0
        
        # Trading streak (consecutive profitable days)
        trading_streak = self.calculate_trading_streak(user)
        
        return {
            'total_invested': total_invested,
            'total_profits': total_profits,
            'roi_percentage': float(roi),
            'avg_daily_profit': avg_daily_profit,
            'trading_streak': trading_streak,
        }
    
    def calculate_trading_streak(self, user):
        """Calculate consecutive profitable trading days"""
        recent_trades = Trade.objects.filter(
            investment__user=user,
            status='completed',
            profit_amount__gt=0
        ).order_by('-completed_at')[:30]
        
        if not recent_trades:
            return 0
        
        streak = 0
        current_date = None
        
        for trade in recent_trades:
            trade_date = trade.completed_at.date()
            
            if current_date is None:
                current_date = trade_date
                streak = 1
            elif trade_date == current_date - timedelta(days=1):
                streak += 1
                current_date = trade_date
            else:
                break
        
        return streak
    
    def is_trading_allowed(self):
        """Check if trading is currently allowed based on time constraints"""
        # Get current time in the configured timezone (Africa/Nairobi)
        from django.conf import settings
        from django.utils import timezone as tz
        
        # Get timezone-aware current time
        utc_now = timezone.now()
        
        # Convert to local timezone
        if hasattr(tz, 'get_current_timezone'):
            local_tz = tz.get_current_timezone()
        else:
            import zoneinfo
            local_tz = zoneinfo.ZoneInfo(settings.TIME_ZONE)
        
        local_now = utc_now.astimezone(local_tz)
        
        current_weekday = local_now.weekday()
        current_time = local_now.time()
        
        # Check if it's a weekday (Monday=0 to Friday=4)
        if current_weekday >= 5:
            return False
        
        # Check trading hours (8 AM to 6 PM) in the local timezone
        from datetime import time
        trading_start = time(8, 0)  # 8:00 AM
        trading_end = time(18, 0)   # 6:00 PM
        
        return trading_start <= current_time <= trading_end

class PackagesView(LoginRequiredMixin, TemplateView):
    """Trading packages overview"""
    template_name = 'trading/packages.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get all active trading packages
        packages = TradingPackage.objects.filter(is_active=True).order_by('min_stake')
        
        # Get user wallet
        wallet, created = Wallet.objects.get_or_create(
            user=self.request.user,
            defaults={'currency': settings.SUPPORTED_CURRENCIES.get(self.request.user.country.code, settings.DEFAULT_CURRENCY)}
        )
        
        # Get user's existing investments
        user_investments = Investment.objects.filter(
            user=self.request.user,
            status='active'
        ).values('package').annotate(
            total_invested=Sum('principal_amount'),
            count=Count('id')
        )
        
        investment_by_package = {inv['package']: inv for inv in user_investments}
        
        # Calculate potential returns for each package
        package_data = []
        for package in packages:
            user_investment = investment_by_package.get(package.pk, {})
            
            # Calculate minimum investment returns
            min_investment = package.min_stake
            welcome_bonus = min_investment * (package.welcome_bonus / 100)
            total_trading_amount = min_investment + welcome_bonus
            
            # Calculate daily profit range
            min_daily_profit = total_trading_amount * (package.profit_min / 100)
            max_daily_profit = total_trading_amount * (package.profit_max / 100)
            avg_daily_profit = (min_daily_profit + max_daily_profit) / 2
            
            # Calculate monthly and yearly projections
            monthly_profit = avg_daily_profit * 22  # 22 trading days per month
            yearly_profit = avg_daily_profit * 260   # 260 trading days per year
            
            package_data.append({
                'package': package,
                'min_investment': min_investment,
                'welcome_bonus': welcome_bonus,
                'total_trading_amount': total_trading_amount,
                'min_daily_profit': min_daily_profit,
                'max_daily_profit': max_daily_profit,
                'avg_daily_profit': avg_daily_profit,
                'monthly_profit': monthly_profit,
                'yearly_profit': yearly_profit,
                'user_investment': user_investment,
                'can_afford': wallet.balance >= min_investment,
            })
        
        context.update({
            'packages': package_data,
            'wallet': wallet,
        })
        
        return context

class InvestView(LoginRequiredMixin, TemplateView):
    """Investment creation view"""
    template_name = 'trading/invest.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        package_name = self.kwargs.get('package_type')
        
        try:
            package = TradingPackage.objects.get(name=package_name, is_active=True)
        except TradingPackage.DoesNotExist:
            messages.error(self.request, 'Invalid trading package selected.')
            return context
        
        # Get user wallet
        wallet, created = Wallet.objects.get_or_create(
            user=self.request.user,
            defaults={'currency': settings.SUPPORTED_CURRENCIES.get(self.request.user.country.code, settings.DEFAULT_CURRENCY)}
        )
        
        # Get investment form
        form = InvestmentForm(package=package, user=self.request.user)
        
        context.update({
            'package': package,
            'wallet': wallet,
            'form': form,
        })
        
        return context
    
    def post(self, request, *args, **kwargs):
        package_name = self.kwargs.get('package_type')
        
        try:
            package = TradingPackage.objects.get(name=package_name, is_active=True)
        except TradingPackage.DoesNotExist:
            messages.error(request, 'Invalid trading package selected.')
            return redirect('trading:packages')
        
        form = InvestmentForm(request.POST, package=package, user=request.user)
        
        if form.is_valid():
            investment_amount = form.cleaned_data['principal_amount']
            
            # Get user wallet
            wallet = request.user.wallet
            
            # Verify sufficient balance
            if investment_amount > wallet.balance:
                messages.error(request, 'Insufficient wallet balance.')
                return self.render_to_response(self.get_context_data(form=form))
            
            # Create investment with maturity date calculation
            maturity_date = timezone.now() + timedelta(days=package.duration_days)
            investment = Investment.objects.create(
                user=request.user,
                package=package,
                principal_amount=investment_amount,
                maturity_date=maturity_date,
                welcome_bonus_amount=investment_amount * (package.welcome_bonus / 100)
            )
            
            # Update wallet balances
            wallet.balance -= investment_amount
            wallet.locked_balance += investment.total_investment
            wallet.save()
            
            # Create investment transaction
            Transaction.objects.create(
                user=request.user,
                transaction_type='investment',
                amount=investment_amount,
                currency=wallet.currency,
                status='completed',
                net_amount=investment_amount,
                description=f'Investment in {package.display_name}'
            )
            
            # Create welcome bonus transaction
            if investment.welcome_bonus_amount > 0:
                Transaction.objects.create(
                    user=request.user,
                    transaction_type='bonus',
                    amount=investment.welcome_bonus_amount,
                    currency=wallet.currency,
                    status='completed',
                    net_amount=investment.welcome_bonus_amount,
                    description=f'Welcome bonus for {package.display_name}'
                )
            
            # Log the investment
            SystemLog.objects.create(
                user=request.user,
                action_type='investment',
                level='INFO',
                message=f'User invested {investment_amount} {wallet.currency} in {package.display_name}',
                ip_address=request.META.get('REMOTE_ADDR'),
                metadata={'investment_id': str(investment.id), 'package': package.name}
            )
            
            messages.success(
                request,
                f'Successfully invested {investment_amount} {wallet.currency} in {package.display_name}! '
                f'Welcome bonus of {investment.welcome_bonus_amount} {wallet.currency} has been added.'
            )
            
            return redirect('trading:dashboard')
        
        return self.render_to_response(self.get_context_data(form=form))

class TradesView(LoginRequiredMixin, ListView):
    """All user trades view"""
    model = Trade
    template_name = 'trading/trades.html'
    context_object_name = 'trades'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = Trade.objects.filter(
            investment__user=self.request.user
        ).select_related('investment', 'investment__package').order_by('-created_at')
        
        # Filter by status
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        # Filter by package
        package = self.request.GET.get('package')
        if package:
            queryset = queryset.filter(investment__package__name=package)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get filter options
        packages = TradingPackage.objects.filter(is_active=True)
        status_choices = Trade.STATUS_CHOICES
        
        # Get trade statistics
        all_trades = Trade.objects.filter(investment__user=self.request.user)
        stats = {
            'total_trades': all_trades.count(),
            'completed_trades': all_trades.filter(status='completed').count(),
            'running_trades': all_trades.filter(status='running').count(),
            'total_profit': all_trades.filter(status='completed').aggregate(
                total=Sum('profit_amount')
            )['total'] or Decimal('0'),
        }
        
        context.update({
            'packages': packages,
            'status_choices': status_choices,
            'selected_status': self.request.GET.get('status'),
            'selected_package': self.request.GET.get('package'),
            'stats': stats,
        })
        
        return context

class TradeDetailView(LoginRequiredMixin, DetailView):
    """Individual trade details"""
    model = Trade
    template_name = 'trading/trade_detail.html'
    context_object_name = 'trade'
    pk_url_kwarg = 'trade_id'
    
    def get_queryset(self):
        return Trade.objects.filter(
            investment__user=self.request.user
        ).select_related('investment', 'investment__package')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get related trades from same investment
        related_trades = Trade.objects.filter(
            investment=self.object.investment
        ).exclude(pk=self.object.pk).order_by('-created_at')[:5]
        
        # Get profit history for this trade
        profit_history = ProfitHistory.objects.filter(trade=self.object).first()
        
        context.update({
            'related_trades': related_trades,
            'profit_history': profit_history,
        })
        
        return context

class InitiateTradeView(LoginRequiredMixin, TemplateView):
    """Initiate new trade"""
    template_name = 'trading/initiate_trade.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get active investments without running trades
        available_investments = Investment.objects.filter(
            user=self.request.user,
            status='active'
        ).exclude(
            trades__status__in=['pending', 'running']
        ).select_related('package')
        
        # Get form
        form = TradeInitiationForm(user=self.request.user)
        
        context.update({
            'available_investments': available_investments,
            'form': form,
            'trading_allowed': self.is_trading_allowed(),
        })
        
        return context
    
    def post(self, request, *args, **kwargs):
        logger.info(f"Trade initiation POST request received for user {request.user.id}")
        logger.info(f"POST data: {request.POST}")
        
        if not self.is_trading_allowed():
            logger.warning(f"Trade initiation blocked - outside trading hours for user {request.user.id}")
            messages.error(request, 'Trading is only allowed Monday to Friday, 8 AM to 6 PM.')
            return redirect('trading:initiate_trade')

        # Get investment ID from form data
        investment_id = request.POST.get('investment')
        confirm_trade = request.POST.get('confirm_trade')
        
        logger.info(f"Form data - investment_id: {investment_id}, confirm_trade: {confirm_trade}")

        # Validate inputs
        if not investment_id:
            logger.error(f"No investment selected by user {request.user.id}")
            messages.error(request, 'Please select an investment.')
            return self.render_to_response(self.get_context_data())

        if not confirm_trade:
            logger.error(f"Trade confirmation not provided by user {request.user.id}")
            messages.error(request, 'Please confirm the trade initiation.')
            return self.render_to_response(self.get_context_data())

        try:
            # Get the investment and validate ownership
            investment = Investment.objects.get(
                id=investment_id,
                user=request.user,
                status='active'
            )
            logger.info(f"Found valid investment {investment.id} for user {request.user.id}")
        except Investment.DoesNotExist:
            logger.error(f"Invalid investment {investment_id} selected by user {request.user.id}")
            messages.error(request, 'Invalid investment selected.')
            return self.render_to_response(self.get_context_data())

        # Check if there's already a pending/running trade
        existing_trade = Trade.objects.filter(
            investment=investment,
            status__in=['pending', 'running']
        ).first()

        if existing_trade:
            logger.warning(f"Trade already exists for investment {investment.id}")
            messages.warning(request, 'There is already an active trade for this investment.')
            return redirect('trading:trades')

        try:
            # Import the Celery task
            from .tasks import initiate_manual_trade
            
            logger.info(f"Starting manual trade task for investment {investment.id}")
            
            # Initiate trade asynchronously with explicit queue routing
            task_result = initiate_manual_trade.apply_async(
                args=[str(investment.id), str(request.user.id), request.META.get('REMOTE_ADDR')],
                queue='critical'
            )
            
            logger.info(f"Trade initiation task started with ID: {task_result.id}")
            
            # Store task ID in session for status checking
            request.session['trade_initiation_task_id'] = task_result.id
            request.session['trade_initiation_investment'] = str(investment.id)
            
            messages.success(
                request,
                f'Trade initiation started for {investment.package.display_name}. Please wait...'
            )
            
            # Redirect to status page where we'll check the task result
            return redirect('trading:trade_initiation_status')
            
        except Exception as e:
            logger.error(f"Error starting trade initiation task: {str(e)}", exc_info=True)
            messages.error(request, 'An error occurred while initiating the trade. Please try again.')
            return self.render_to_response(self.get_context_data())
    
    def is_trading_allowed(self):
        """Check if trading is currently allowed based on time constraints"""
        # Get current time in the configured timezone (Africa/Nairobi)
        from django.conf import settings
        from django.utils import timezone as tz
        
        # Get timezone-aware current time
        utc_now = timezone.now()
        
        # Convert to local timezone
        if hasattr(tz, 'get_current_timezone'):
            local_tz = tz.get_current_timezone()
        else:
            import zoneinfo
            local_tz = zoneinfo.ZoneInfo(settings.TIME_ZONE)
        
        local_now = utc_now.astimezone(local_tz)
        
        current_weekday = local_now.weekday()
        current_time = local_now.time()
        
        # Check if it's a weekday (Monday=0 to Friday=4)
        if current_weekday >= 5:
            return False
        
        # Check trading hours (8 AM to 6 PM) in the local timezone
        from datetime import time
        trading_start = time(8, 0)  # 8:00 AM
        trading_end = time(18, 0)   # 6:00 PM
        
        return trading_start <= current_time <= trading_end

class TradeInitiationStatusView(LoginRequiredMixin, TemplateView):
    """Check trade initiation status"""
    template_name = 'trading/trade_initiation_status.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get task ID from session
        task_id = self.request.session.get('trade_initiation_task_id')
        investment_id = self.request.session.get('trade_initiation_investment')
        
        context.update({
            'task_id': task_id,
            'investment_id': investment_id,
            'has_task': bool(task_id),
        })
        
        return context

@require_http_methods(["GET"])
def check_trade_initiation_status(request):
    """AJAX endpoint to check trade initiation task status"""
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Authentication required'}, status=401)
    
    task_id = request.GET.get('task_id')
    if not task_id:
        return JsonResponse({'error': 'Task ID required'}, status=400)
    
    try:
        from celery.result import AsyncResult
        from .tasks import initiate_manual_trade
        
        # Get task result
        task_result = AsyncResult(task_id)
        
        response_data = {
            'task_id': task_id,
            'status': task_result.status,
            'ready': task_result.ready(),
        }
        
        if task_result.ready():
            if task_result.successful():
                result = task_result.result
                response_data.update({
                    'success': True,
                    'result': result,
                })
                
                # Clear session data if successful
                if 'trade_initiation_task_id' in request.session:
                    del request.session['trade_initiation_task_id']
                if 'trade_initiation_investment' in request.session:
                    del request.session['trade_initiation_investment']
                    
            else:
                response_data.update({
                    'success': False,
                    'error': str(task_result.result) if task_result.result else 'Unknown error',
                })
        else:
            response_data.update({
                'success': None,
                'message': 'Trade initiation in progress...'
            })
        
        return JsonResponse(response_data)
        
    except Exception as e:
        logger.error(f"Error checking trade initiation status: {str(e)}")
        return JsonResponse({
            'error': 'Failed to check task status',
            'success': False
        }, status=500)

class InvestmentListView(LoginRequiredMixin, ListView):
    """User investments list"""
    model = Investment
    template_name = 'trading/investments.html'
    context_object_name = 'investments'
    paginate_by = 10
    
    def get_queryset(self):
        return Investment.objects.filter(
            user=self.request.user
        ).select_related('package').order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get investment statistics
        user_investments = self.get_queryset()
        
        stats = {
            'total_investments': user_investments.count(),
            'active_investments': user_investments.filter(status='active').count(),
            'total_invested': user_investments.aggregate(
                total=Sum('principal_amount')
            )['total'] or Decimal('0'),
            'total_profits': ProfitHistory.objects.filter(
                user=self.request.user
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0'),
        }
        
        context['stats'] = stats
        return context

class ProfitHistoryView(LoginRequiredMixin, ListView):
    """User profit history"""
    model = ProfitHistory
    template_name = 'trading/profit_history.html'
    context_object_name = 'profits'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = ProfitHistory.objects.filter(
            user=self.request.user
        ).select_related('investment', 'investment__package', 'trade').order_by('-date_earned')
        
        # Filter by date range
        start_date = self.request.GET.get('start_date')
        end_date = self.request.GET.get('end_date')
        
        if start_date:
            queryset = queryset.filter(date_earned__date__gte=start_date)
        if end_date:
            queryset = queryset.filter(date_earned__date__lte=end_date)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get profit statistics
        all_profits = ProfitHistory.objects.filter(user=self.request.user)
        
        stats = {
            'total_profits': all_profits.aggregate(total=Sum('amount'))['total'] or Decimal('0'),
            'withdrawn_profits': all_profits.filter(is_withdrawn=True).aggregate(
                total=Sum('amount')
            )['total'] or Decimal('0'),
            'available_profits': self.request.user.wallet.profit_balance,
            'avg_daily_profit': all_profits.aggregate(avg=Avg('amount'))['avg'] or Decimal('0'),
        }
        
        context.update({
            'stats': stats,
            'start_date': self.request.GET.get('start_date'),
            'end_date': self.request.GET.get('end_date'),
        })
        
        return context

# AJAX Views
@login_required
def get_package_calculator(request):
    """AJAX view for package calculator"""
    if request.method == 'GET':
        package_id = request.GET.get('package_id')
        investment_amount = request.GET.get('amount')
        
        try:
            package = TradingPackage.objects.get(id=package_id, is_active=True)
            amount = Decimal(investment_amount)
            
            if amount < package.min_stake:
                return JsonResponse({
                    'success': False,
                    'error': f'Minimum investment is {package.min_stake}'
                })
            
            # Calculate returns
            welcome_bonus = amount * (package.welcome_bonus / 100)
            total_trading_amount = amount + welcome_bonus
            
            min_daily_profit = total_trading_amount * (package.profit_min / 100)
            max_daily_profit = total_trading_amount * (package.profit_max / 100)
            avg_daily_profit = (min_daily_profit + max_daily_profit) / 2
            
            monthly_profit = avg_daily_profit * 22
            yearly_profit = avg_daily_profit * 260
            
            return JsonResponse({
                'success': True,
                'data': {
                    'investment_amount': float(amount),
                    'welcome_bonus': float(welcome_bonus),
                    'total_trading_amount': float(total_trading_amount),
                    'min_daily_profit': float(min_daily_profit),
                    'max_daily_profit': float(max_daily_profit),
                    'avg_daily_profit': float(avg_daily_profit),
                    'monthly_profit': float(monthly_profit),
                    'yearly_profit': float(yearly_profit),
                }
            })
            
        except (TradingPackage.DoesNotExist, ValueError, TypeError):
            return JsonResponse({
                'success': False,
                'error': 'Invalid package or amount'
            })
    
    return JsonResponse({'success': False, 'error': 'Invalid request'})

@login_required
def get_trade_countdown(request, trade_id):
    """AJAX view for trade countdown"""
    try:
        trade = Trade.objects.get(
            id=trade_id,
            investment__user=request.user
        )
        
        if trade.status == 'completed':
            return JsonResponse({
                'success': True,
                'status': 'completed',
                'message': 'Trade completed'
            })
        
        time_remaining = trade.time_remaining
        total_seconds = int(time_remaining.total_seconds())
        
        if total_seconds <= 0:
            return JsonResponse({
                'success': True,
                'status': 'ready',
                'message': 'Trade ready for completion'
            })
        
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        
        return JsonResponse({
            'success': True,
            'status': 'running',
            'time_remaining': {
                'hours': hours,
                'minutes': minutes,
                'seconds': seconds,
                'total_seconds': total_seconds
            }
        })
        
    except Trade.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Trade not found'
        })

@login_required
def trading_statistics(request):
    """AJAX view for trading statistics"""
    user = request.user
    
    # Get date range
    days = int(request.GET.get('days', 30))
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=days)
    
    # Profit data
    profits = ProfitHistory.objects.filter(
        user=user,
        date_earned__date__gte=start_date,
        date_earned__date__lte=end_date
    ).values('date_earned__date').annotate(
        daily_profit=Sum('amount')
    ).order_by('date_earned__date')
    
    # Trade data
    trades = Trade.objects.filter(
        investment__user=user,
        created_at__date__gte=start_date,
        created_at__date__lte=end_date
    ).values('created_at__date', 'status').annotate(
        count=Count('id')
    )
    
    # Format data for charts
    profit_data = {p['date_earned__date'].strftime('%Y-%m-%d'): float(p['daily_profit']) for p in profits}
    trade_data = {}
    
    for trade in trades:
        date_str = trade['created_at__date'].strftime('%Y-%m-%d')
        if date_str not in trade_data:
            trade_data[date_str] = {'completed': 0, 'running': 0, 'failed': 0}
        trade_data[date_str][trade['status']] = trade['count']
    
    return JsonResponse({
        'success': True,
        'profit_data': profit_data,
        'trade_data': trade_data
    })

@login_required
@require_http_methods(["POST"])
def stop_trade(request, trade_id):
    """
    Stop a running trade and calculate pro-rata profits.
    AJAX endpoint to handle user-initiated trade stopping.
    """
    try:
        trade = Trade.objects.get(id=trade_id, investment__user=request.user)
        
        # Check if trade is running
        if trade.status != 'running':
            return JsonResponse({
                'success': False,
                'error': f'Cannot stop {trade.status} trade. Only running trades can be stopped.'
            }, status=400)
        
        # Call the trade's stop_trade method
        result = trade.stop_trade()
        
        if result['success']:
            # Log the activity
            SystemLog.objects.create(
                user=request.user,
                action_type='trade_stopped',
                level='INFO',
                message=f'User stopped trade {trade.id}',
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                request_path=request.path,
                metadata={
                    'trade_id': str(trade.id),
                    'profit_amount': str(result.get('profit_amount', 0)),
                    'currency': result.get('currency', 'N/A')
                }
            )
            
            return JsonResponse({
                'success': True,
                'message': result['message'],
                'profit_amount': result['profit_amount'],
                'currency': result['currency']
            })
        else:
            return JsonResponse({
                'success': False,
                'error': result['message']
            }, status=400)
    
    except Trade.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Trade not found or unauthorized'
        }, status=404)
    except Exception as e:
        logger.error(f"Error stopping trade {trade_id}: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': f'Error stopping trade: {str(e)}'
        }, status=500)