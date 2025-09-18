from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from apps.payments.admin_views import payments_dashboard

urlpatterns = [
    path('admin/', admin.site.urls),
    path('admin/payments-dashboard/', payments_dashboard, name='admin_payments_dashboard'),
    path('accounts/', include('allauth.urls')),
    path('', include('apps.core.urls')),
    path('dashboard/', include('apps.trading.urls')),
    path('payments/', include('apps.payments.urls')),
    path('profile/', include('apps.accounts.urls')),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])