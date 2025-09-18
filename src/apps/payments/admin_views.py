# apps/payments/admin_views.py
from django.contrib import admin
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from django.db.models import Count, Sum, Q
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal

from .models import Transaction, DepositRequest, WithdrawalRequest, Wallet


@staff_member_required
def payments_dashboard(request):
    """
    Custom admin dashboard for payment processing overview
    """
    # Date ranges for statistics
    today = timezone.now().date()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)
    
    # Deposit statistics
    pending_deposits = DepositRequest.objects.filter(
        transaction__status='pending'
    ).select_related('transaction', 'transaction__user')
    
    processing_deposits = DepositRequest.objects.filter(
        transaction__status='processing'
    ).select_related('transaction', 'transaction__user')
    
    today_deposits = DepositRequest.objects.filter(
        transaction__created_at__date=today
    ).aggregate(
        count=Count('id'),
        total=Sum('transaction__amount')
    )
    
    week_deposits = DepositRequest.objects.filter(
        transaction__created_at__date__gte=week_ago
    ).aggregate(
        count=Count('id'),
        total=Sum('transaction__amount')
    )
    
    # Withdrawal statistics
    pending_withdrawals = WithdrawalRequest.objects.filter(
        transaction__status='pending'
    ).select_related('transaction', 'transaction__user')
    
    processing_withdrawals = WithdrawalRequest.objects.filter(
        transaction__status='processing'
    ).select_related('transaction', 'transaction__user')
    
    otp_pending_withdrawals = WithdrawalRequest.objects.filter(
        transaction__status='pending',
        otp_verified=False
    ).count()
    
    today_withdrawals = WithdrawalRequest.objects.filter(
        transaction__created_at__date=today
    ).aggregate(
        count=Count('id'),
        total=Sum('transaction__amount')
    )
    
    week_withdrawals = WithdrawalRequest.objects.filter(
        transaction__created_at__date__gte=week_ago
    ).aggregate(
        count=Count('id'),
        total=Sum('transaction__amount')
    )
    
    # Platform statistics
    total_wallets = Wallet.objects.count()
    total_balance = Wallet.objects.aggregate(
        balance=Sum('balance'),
        profit_balance=Sum('profit_balance'),
        locked_balance=Sum('locked_balance')
    )
    
    # Recent failed transactions
    failed_transactions = Transaction.objects.filter(
        status='failed',
        created_at__date__gte=week_ago
    ).select_related('user')[:10]
    
    # High value transactions requiring attention
    high_value_deposits = DepositRequest.objects.filter(
        transaction__status='pending',
        transaction__amount__gte=1000  # Adjust threshold as needed
    ).select_related('transaction', 'transaction__user')[:5]
    
    high_value_withdrawals = WithdrawalRequest.objects.filter(
        transaction__status='pending',
        transaction__amount__gte=1000  # Adjust threshold as needed
    ).select_related('transaction', 'transaction__user')[:5]
    
    context = {
        'title': 'Payments Dashboard',
        'site_title': admin.site.site_title,
        'site_header': admin.site.site_header,
        
        # Pending items requiring immediate attention
        'pending_deposits': pending_deposits[:10],  # Show first 10
        'pending_deposits_count': pending_deposits.count(),
        'processing_deposits': processing_deposits[:5],
        'pending_withdrawals': pending_withdrawals[:10],
        'pending_withdrawals_count': pending_withdrawals.count(),
        'processing_withdrawals': processing_withdrawals[:5],
        'otp_pending_count': otp_pending_withdrawals,
        
        # Statistics
        'today_deposits': today_deposits,
        'week_deposits': week_deposits,
        'today_withdrawals': today_withdrawals,
        'week_withdrawals': week_withdrawals,
        
        # Platform overview
        'total_wallets': total_wallets,
        'total_balance': total_balance,
        
        # Items needing attention
        'failed_transactions': failed_transactions,
        'high_value_deposits': high_value_deposits,
        'high_value_withdrawals': high_value_withdrawals,
        
        # Quick action URLs
        'deposit_admin_url': '/admin/payments/depositrequest/',
        'withdrawal_admin_url': '/admin/payments/withdrawalrequest/',
        'transaction_admin_url': '/admin/payments/transaction/',
    }
    
    return render(request, 'admin/payments/dashboard.html', context)


def get_admin_urls():
    """
    Get custom admin URLs for payments
    """
    from django.urls import path
    
    return [
        path('payments-dashboard/', payments_dashboard, name='payments_dashboard'),
    ]