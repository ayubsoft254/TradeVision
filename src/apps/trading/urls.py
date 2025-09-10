from django.urls import path
from . import views

app_name = 'trading'

urlpatterns = [
    path('', views.DashboardView.as_view(), name='dashboard'),
    path('packages/', views.PackagesView.as_view(), name='packages'),
    path('invest/<str:package_type>/', views.InvestView.as_view(), name='invest'),
    path('trades/', views.TradesView.as_view(), name='trades'),
    path('trade/<uuid:trade_id>/', views.TradeDetailView.as_view(), name='trade_detail'),
    path('initiate-trade/', views.InitiateTradeView.as_view(), name='initiate_trade'),
    path('history/', views.TradingHistoryView.as_view(), name='history'),
    path('profits/', views.ProfitsView.as_view(), name='profits'),
]