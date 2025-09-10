from django.urls import path
from . import views

app_name = 'payments'

urlpatterns = [
    path('deposit/', views.DepositView.as_view(), name='deposit'),
    path('deposit/<str:method>/', views.DepositMethodView.as_view(), name='deposit_method'),
    path('withdraw/', views.WithdrawView.as_view(), name='withdraw'),
    path('withdraw/<str:method>/', views.WithdrawMethodView.as_view(), name='withdraw_method'),
    path('transactions/', views.TransactionHistoryView.as_view(), name='transactions'),
    path('agents/', views.AgentsView.as_view(), name='agents'),
    path('p2p/', views.P2PView.as_view(), name='p2p'),
]