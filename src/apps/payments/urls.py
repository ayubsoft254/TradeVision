# apps/payments/urls.py
from django.urls import path
from . import views
# from . import views_binance

app_name = 'payments'

urlpatterns = [
    # Deposit System
    path('deposit/', views.DepositView.as_view(), name='deposit'),
    path('deposit/<str:method>/', views.DepositMethodView.as_view(), name='deposit_method'),
    
    # Withdrawal System
    path('withdraw/', views.WithdrawView.as_view(), name='withdraw'),
    path('withdraw/<str:method>/', views.WithdrawMethodView.as_view(), name='withdraw_method'),
    path('withdraw-profit/', views.withdraw_profit, name='withdraw_profit'),
    
    # Transaction Management
    path('transactions/', views.TransactionHistoryView.as_view(), name='transactions'),
    path('transaction/<uuid:transaction_id>/', views.TransactionDetailView.as_view(), name='transaction_detail'),
    path('transaction/<uuid:transaction_id>/upload-proof/', views.upload_payment_proof, name='upload_payment_proof'),
    
    # Payment Networks
    path('agents/', views.AgentsView.as_view(), name='agents'),
    path('p2p/', views.P2PView.as_view(), name='p2p'),
    
    # AJAX Endpoints
    path('api/payment-methods/', views.get_payment_methods, name='payment_methods'),
    path('api/calculate-fees/', views.calculate_fees, name='calculate_fees'),
    path('api/wallet-balance/', views.wallet_balance, name='wallet_balance'),
    path('api/transaction-status/<uuid:transaction_id>/', views.transaction_status, name='transaction_status'),

    # # Binance Pay URLs
    # path('binance/initiate/', views_binance.initiate_binance_payment, name='binance_initiate'),
    # path('binance/return/', views_binance.binance_payment_return, name='binance_return'),
    # path('binance/cancel/', views_binance.binance_payment_cancel, name='binance_cancel'),
    # path('binance/webhook/', views_binance.binance_webhook, name='binance_webhook'),
    
    # # AJAX endpoints
    # path('api/binance/status/', views_binance.check_binance_payment_status, name='binance_status'),
]