# apps/trading/urls.py
from django.urls import path
from . import views

app_name = 'trading'

urlpatterns = [
    # Main Dashboard
    path('', views.DashboardView.as_view(), name='dashboard'),
    
    # Trading Packages
    path('packages/', views.PackagesView.as_view(), name='packages'),
    path('packages/<str:package_type>/', views.InvestView.as_view(), name='invest'),
    
    # Investments Management
    path('investments/', views.InvestmentListView.as_view(), name='investments'),
    
    # Trading Operations
    path('trades/', views.TradesView.as_view(), name='trades'),
    path('trades/<uuid:trade_id>/', views.TradeDetailView.as_view(), name='trade_detail'),
    path('initiate-trade/', views.InitiateTradeView.as_view(), name='initiate_trade'),
    
    # Profit Management
    path('profits/', views.ProfitHistoryView.as_view(), name='profits'),
    
    # AJAX Endpoints
    path('api/package-calculator/', views.get_package_calculator, name='package_calculator'),
    path('api/trade-countdown/<uuid:trade_id>/', views.get_trade_countdown, name='trade_countdown'),
    path('api/trading-statistics/', views.trading_statistics, name='trading_statistics'),
]