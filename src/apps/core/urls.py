from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    # Main Pages
    path('', views.HomeView.as_view(), name='home'),
    path('about/', views.AboutView.as_view(), name='about'),
    path('terms/', views.TermsView.as_view(), name='terms'),
    path('privacy/', views.PrivacyView.as_view(), name='privacy'),
    
    # FAQ System
    path('faq/', views.FAQView.as_view(), name='faq'),
    path('api/faq/vote/', views.faq_vote, name='faq_vote'),
    
    # Contact & Support
    path('contact/', views.ContactView.as_view(), name='contact'),
    path('support/', views.SupportTicketListView.as_view(), name='support_tickets'),
    path('support/create/', views.CreateSupportTicketView.as_view(), name='create_support_ticket'),
    path('support/ticket/<uuid:ticket_id>/', views.SupportTicketDetailView.as_view(), name='support_ticket_detail'),
    
    # News & Updates
    path('news/', views.NewsListView.as_view(), name='news_list'),
    path('news/<slug:slug>/', views.NewsDetailView.as_view(), name='news_detail'),
    
    # Search
    path('search/', views.search_view, name='search'),
    
    # System Pages
    path('maintenance/', views.maintenance_view, name='maintenance'),
    path('health/', views.health_check, name='health_check'),
]