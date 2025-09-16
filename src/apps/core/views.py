# apps/core/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import TemplateView, ListView, DetailView, CreateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.http import JsonResponse, Http404
from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.utils import timezone
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
import logging

from .models import (
    SiteConfiguration, Announcement, FAQ, SupportTicket, 
    SupportMessage, NewsUpdate, SystemLog
)
from apps.accounts.forms import ContactForm
from apps.trading.models import  TradingPackage

logger = logging.getLogger(__name__)

class HomeView(TemplateView):
    """Main homepage view"""
    template_name = 'core/home.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get site configuration
        try:
            site_config = SiteConfiguration.objects.first()
        except SiteConfiguration.DoesNotExist:
            site_config = None
        
        # Get trading packages from database
        packages = TradingPackage.objects.filter(is_active=True).order_by('min_stake')
        context['packages'] = packages
        
        # Get active announcements for homepage
        announcements = Announcement.objects.filter(
            is_active=True,
            show_on_homepage=True,
            start_date__lte=timezone.now()
        ).filter(
            Q(end_date__isnull=True) | Q(end_date__gte=timezone.now())
        )[:3]
        
        # Get featured FAQs
        featured_faqs = FAQ.objects.filter(
            is_active=True,
            is_featured=True
        )[:6]
        
        # Get recent news updates
        recent_news = NewsUpdate.objects.filter(
            is_published=True,
            publish_date__lte=timezone.now()
        )[:3]
        
        # Platform statistics
        stats = {
            'total_users': site_config.total_users if site_config else 500,
            'total_invested': site_config.total_invested if site_config else 250,
            'total_profits_paid': site_config.total_profits_paid if site_config else 150,
            'platform_uptime': site_config.platform_uptime if site_config else 99.9,
        }
        
        context.update({
            'site_config': site_config,
            'announcements': announcements,
            'featured_faqs': featured_faqs,
            'recent_news': recent_news,
            'stats': stats,
        })
        
        # Handle referral code from URL
        referral_code = self.request.GET.get('ref')
        if referral_code:
            context['referral_code'] = referral_code
            self.request.session['referral_code'] = referral_code
        
        return context

class AboutView(TemplateView):
    """About us page"""
    template_name = 'core/about.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get site configuration
        try:
            site_config = SiteConfiguration.objects.first()
        except SiteConfiguration.DoesNotExist:
            site_config = None
        
        # Get trading packages from database
        trading_packages = TradingPackage.objects.filter(is_active=True).order_by('min_stake')
        context['packages'] = trading_packages
        
        # Get platform statistics
        stats = {
            'total_users': site_config.total_users if site_config else 500,
            'total_invested': site_config.total_invested if site_config else 2500000,
            'total_profits_paid': site_config.total_profits_paid if site_config else 150000,
            'platform_uptime': site_config.platform_uptime if site_config else 99.9,
        }
        
        context.update({
            'site_config': site_config,
            'stats': stats,
        })
        
        return context

class TermsView(TemplateView):
    """Terms and conditions page"""
    template_name = 'core/terms.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get site configuration for contact details
        try:
            site_config = SiteConfiguration.objects.first()
            context['site_config'] = site_config
        except SiteConfiguration.DoesNotExist:
            context['site_config'] = None
        
        return context

class PrivacyView(TemplateView):
    """Privacy policy page"""
    template_name = 'core/privacy.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get site configuration for contact details
        try:
            site_config = SiteConfiguration.objects.first()
            context['site_config'] = site_config
        except SiteConfiguration.DoesNotExist:
            context['site_config'] = None
        
        return context

class FAQView(ListView):
    """FAQ page with categories"""
    model = FAQ
    template_name = 'core/faq.html'
    context_object_name = 'faqs'
    
    def get_queryset(self):
        queryset = FAQ.objects.filter(is_active=True)
        
        # Filter by category if specified
        category = self.request.GET.get('category')
        if category:
            queryset = queryset.filter(category=category)
        
        # Search functionality
        search_query = self.request.GET.get('search')
        if search_query:
            queryset = queryset.filter(
                Q(question__icontains=search_query) |
                Q(answer__icontains=search_query)
            )
        
        return queryset.order_by('category', 'order', '-is_featured')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Group FAQs by category
        faqs_by_category = {}
        for faq in context['faqs']:
            if faq.category not in faqs_by_category:
                faqs_by_category[faq.category] = []
            faqs_by_category[faq.category].append(faq)
        
        # Get category choices for filter
        categories = FAQ.CATEGORY_CHOICES
        
        # Get featured FAQs
        featured_faqs = FAQ.objects.filter(
            is_active=True,
            is_featured=True
        )[:5]
        
        context.update({
            'faqs_by_category': faqs_by_category,
            'categories': categories,
            'featured_faqs': featured_faqs,
            'selected_category': self.request.GET.get('category'),
            'search_query': self.request.GET.get('search'),
        })
        
        return context

class ContactView(TemplateView):
    """Contact us page"""
    template_name = 'core/contact.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get site configuration for contact details
        try:
            site_config = SiteConfiguration.objects.first()
        except SiteConfiguration.DoesNotExist:
            site_config = None
        
        context.update({
            'site_config': site_config,
            'contact_form': ContactForm(),
        })
        
        return context
    
    def post(self, request, *args, **kwargs):
        form = ContactForm(request.POST)
        
        if form.is_valid():
            # Create support ticket if user is authenticated
            if request.user.is_authenticated:
                ticket = SupportTicket.objects.create(
                    user=request.user,
                    subject=form.cleaned_data['subject'],
                    description=form.cleaned_data['message'],
                    category=form.cleaned_data['subject']
                )
                
                # Create initial message
                SupportMessage.objects.create(
                    ticket=ticket,
                    sender=request.user,
                    message=form.cleaned_data['message']
                )
                
                messages.success(
                    request,
                    f'Support ticket #{ticket.ticket_number} created successfully! We will respond within 24 hours.'
                )
            else:
                # Send email for non-authenticated users
                try:
                    send_mail(
                        subject=f"Contact Form: {form.cleaned_data['subject']}",
                        message=f"From: {form.cleaned_data['name']} ({form.cleaned_data['email']})\n\n{form.cleaned_data['message']}",
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[settings.DEFAULT_FROM_EMAIL],
                        fail_silently=False,
                    )
                    messages.success(request, 'Your message has been sent successfully! We will respond within 24 hours.')
                except Exception as e:
                    logger.error(f"Error sending contact email: {e}")
                    messages.error(request, 'There was an error sending your message. Please try again later.')
            
            return redirect('core:contact')
        
        context = self.get_context_data()
        context['contact_form'] = form
        return self.render_to_response(context)

class NewsListView(ListView):
    """News and updates listing"""
    model = NewsUpdate
    template_name = 'core/news_list.html'
    context_object_name = 'news_list'
    paginate_by = 10
    
    def get_queryset(self):
        return NewsUpdate.objects.filter(
            is_published=True,
            publish_date__lte=timezone.now()
        ).order_by('-publish_date')

class NewsDetailView(DetailView):
    """Individual news article view"""
    model = NewsUpdate
    template_name = 'core/news_detail.html'
    context_object_name = 'news_article'
    slug_field = 'slug'
    slug_url_kwarg = 'slug'
    
    def get_queryset(self):
        return NewsUpdate.objects.filter(
            is_published=True,
            publish_date__lte=timezone.now()
        )
    
    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        
        # Increment view count
        obj.view_count += 1
        obj.save(update_fields=['view_count'])
        
        return obj
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get related news articles
        related_news = NewsUpdate.objects.filter(
            is_published=True,
            publish_date__lte=timezone.now()
        ).exclude(
            pk=self.object.pk
        ).order_by('-publish_date')[:3]
        
        context['related_news'] = related_news
        return context

class SupportTicketListView(LoginRequiredMixin, ListView):
    """User support tickets list"""
    model = SupportTicket
    template_name = 'core/support_tickets.html'
    context_object_name = 'tickets'
    paginate_by = 10
    
    def get_queryset(self):
        return SupportTicket.objects.filter(
            user=self.request.user
        ).order_by('-created_at')

class SupportTicketDetailView(LoginRequiredMixin, DetailView):
    """Individual support ticket view"""
    model = SupportTicket
    template_name = 'core/support_ticket_detail.html'
    context_object_name = 'ticket'
    pk_url_kwarg = 'ticket_id'
    
    def get_queryset(self):
        return SupportTicket.objects.filter(user=self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get ticket messages
        messages = SupportMessage.objects.filter(
            ticket=self.object,
            is_internal=False
        ).order_by('created_at')
        
        context['messages'] = messages
        return context
    
    def post(self, request, *args, **kwargs):
        """Handle new message submission"""
        self.object = self.get_object()
        message_content = request.POST.get('message')
        
        if message_content:
            SupportMessage.objects.create(
                ticket=self.object,
                sender=request.user,
                message=message_content
            )
            
            # Update ticket status
            if self.object.status == 'waiting_customer':
                self.object.status = 'in_progress'
                self.object.save()
            
            messages.success(request, 'Message sent successfully!')
        
        return redirect('core:support_ticket_detail', ticket_id=self.object.pk)

class CreateSupportTicketView(LoginRequiredMixin, CreateView):
    """Create new support ticket"""
    model = SupportTicket
    template_name = 'core/create_support_ticket.html'
    fields = ['subject', 'description', 'category', 'priority']
    
    def form_valid(self, form):
        form.instance.user = self.request.user
        response = super().form_valid(form)
        
        # Create initial message
        SupportMessage.objects.create(
            ticket=self.object,
            sender=self.request.user,
            message=form.instance.description
        )
        
        messages.success(
            self.request,
            f'Support ticket #{self.object.ticket_number} created successfully!'
        )
        
        return response
    
    def get_success_url(self):
        return f"/support/ticket/{self.object.pk}/"

def search_view(request):
    """Global search functionality"""
    query = request.GET.get('q', '').strip()
    
    if not query:
        return render(request, 'core/search_results.html', {
            'query': query,
            'results': [],
            'total_results': 0
        })
    
    # Search in FAQs
    faq_results = FAQ.objects.filter(
        Q(question__icontains=query) | Q(answer__icontains=query),
        is_active=True
    )[:5]
    
    # Search in News
    news_results = NewsUpdate.objects.filter(
        Q(title__icontains=query) | Q(content__icontains=query),
        is_published=True,
        publish_date__lte=timezone.now()
    )[:5]
    
    # Combine results
    results = []
    
    for faq in faq_results:
        results.append({
            'type': 'FAQ',
            'title': faq.question,
            'content': faq.answer[:200] + '...' if len(faq.answer) > 200 else faq.answer,
            'url': f'/faq/?search={query}',
        })
    
    for news in news_results:
        results.append({
            'type': 'News',
            'title': news.title,
            'content': news.excerpt or (news.content[:200] + '...' if len(news.content) > 200 else news.content),
            'url': f'/news/{news.slug}/',
        })
    
    return render(request, 'core/search_results.html', {
        'query': query,
        'results': results,
        'total_results': len(results),
        'faq_count': len(faq_results),
        'news_count': len(news_results),
    })

def maintenance_view(request):
    """Maintenance mode page"""
    try:
        site_config = SiteConfiguration.objects.first()
        if not site_config or not site_config.maintenance_mode:
            return redirect('core:home')
    except SiteConfiguration.DoesNotExist:
        return redirect('core:home')
    
    return render(request, 'core/maintenance.html', {
        'site_config': site_config
    })

def health_check(request):
    """Health check endpoint for monitoring"""
    try:
        # Check database connection
        SiteConfiguration.objects.first()
        
        # Check if maintenance mode is enabled
        try:
            site_config = SiteConfiguration.objects.first()
            if site_config and site_config.maintenance_mode:
                return JsonResponse({
                    'status': 'maintenance',
                    'message': 'Site is in maintenance mode'
                }, status=503)
        except:
            pass
        
        return JsonResponse({
            'status': 'healthy',
            'timestamp': timezone.now().isoformat(),
            'version': '1.0.0'
        })
    
    except Exception as e:
        return JsonResponse({
            'status': 'unhealthy',
            'error': str(e)
        }, status=500)

# AJAX Views
def faq_vote(request):
    """AJAX view for FAQ helpful voting"""
    if request.method == 'POST' and request.user.is_authenticated:
        faq_id = request.POST.get('faq_id')
        vote_type = request.POST.get('vote_type')  # 'helpful' or 'not_helpful'
        
        try:
            faq = FAQ.objects.get(id=faq_id, is_active=True)
            
            if vote_type == 'helpful':
                faq.helpful_votes += 1
                faq.save()
                
                return JsonResponse({
                    'success': True,
                    'message': 'Thank you for your feedback!',
                    'helpful_votes': faq.helpful_votes
                })
            
        except FAQ.DoesNotExist:
            pass
    
    return JsonResponse({'success': False, 'message': 'Invalid request'})

def log_system_activity(request, action_type, message, level='INFO', metadata=None):
    """Utility function to log system activities"""
    try:
        SystemLog.objects.create(
            user=request.user if request.user.is_authenticated else None,
            action_type=action_type,
            level=level,
            message=message,
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            request_path=request.path,
            metadata=metadata or {}
        )
    except Exception as e:
        logger.error(f"Error logging system activity: {e}")

# Middleware for system logging (add to views that need logging)
class SystemLogMixin:
    """Mixin to add system logging to views"""
    
    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        
        # Log the activity
        log_system_activity(
            request,
            action_type=getattr(self, 'log_action_type', 'page_view'),
            message=f"User accessed {self.__class__.__name__}",
            metadata={
                'view_name': self.__class__.__name__,
                'method': request.method,
                'status_code': response.status_code
            }
        )
        
        return response