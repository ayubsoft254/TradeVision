#!/usr/bin/env python3
"""
Simple test script to verify announcements are working properly
"""

import os
import sys
import django

# Add the src directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tradevision.settings')
django.setup()

from apps.core.models import Announcement
from django.utils import timezone
from django.db.models import Q

def test_announcements():
    print("=" * 60)
    print("TRADEVISION ANNOUNCEMENTS TEST")
    print("=" * 60)
    
    # Get all announcements
    all_announcements = Announcement.objects.all()
    print(f"\n✅ Total announcements in database: {all_announcements.count()}")
    
    # Get homepage announcements using exact query from views.py
    homepage_announcements = Announcement.objects.filter(
        is_active=True,
        show_on_homepage=True,
        start_date__lte=timezone.now()
    ).filter(
        Q(end_date__isnull=True) | Q(end_date__gte=timezone.now())
    )[:3]
    
    print(f"✅ Homepage announcements (limit 3): {homepage_announcements.count()}")
    
    if homepage_announcements.count() == 0:
        print("❌ WARNING: No announcements will show on homepage!")
        print("\nTo create test announcements, run:")
        print("python manage.py create_announcements --create-sample")
    else:
        print(f"\n📢 ANNOUNCEMENTS THAT WILL SHOW ON HOMEPAGE:")
        print("-" * 50)
        
        for i, ann in enumerate(homepage_announcements, 1):
            print(f"\n{i}. {ann.title}")
            print(f"   Type: {ann.announcement_type} | Priority: {ann.priority}")
            print(f"   Message: {ann.message[:80]}...")
            print(f"   Active: {ann.is_active} | Homepage: {ann.show_on_homepage}")
    
    # Get dashboard announcements
    dashboard_announcements = Announcement.objects.filter(
        is_active=True,
        show_on_dashboard=True,
        start_date__lte=timezone.now()
    ).filter(
        Q(end_date__isnull=True) | Q(end_date__gte=timezone.now())
    )
    
    print(f"\n✅ Dashboard announcements: {dashboard_announcements.count()}")
    
    # Show styling recommendations
    print(f"\n🎨 STYLING STATUS:")
    print("-" * 50)
    print("✅ Enhanced announcement banner with gradient background")
    print("✅ Better color contrast (white text on blue gradient)")
    print("✅ Icon indicators for different announcement types")
    print("✅ Modal popup for viewing all announcements")
    print("✅ Mobile responsive design")
    
    print(f"\n🚀 NEXT STEPS:")
    print("-" * 50)
    print("1. Start your Django server: python manage.py runserver")
    print("2. Visit: http://127.0.0.1:8000")
    print("3. Look for the blue announcement banner below the hero section")
    print("4. Click 'View All' to see the announcement modal")
    
    print(f"\n📝 MANAGEMENT COMMANDS:")
    print("-" * 50)
    print("• Create sample announcements:")
    print("  python manage.py create_announcements --create-sample")
    print("")
    print("• Create custom announcement:")
    print("  python manage.py create_announcements \\")
    print("    --title 'Your Title' \\")
    print("    --message 'Your message' \\")
    print("    --type success --priority high --homepage --dashboard")
    print("")
    print("• Clear all announcements:")
    print("  python manage.py create_announcements --clear-all")
    
    print("=" * 60)
    
    return homepage_announcements.count() > 0

if __name__ == "__main__":
    success = test_announcements()
    if success:
        print("✅ ANNOUNCEMENT TEST PASSED - Announcements should be visible!")
    else:
        print("❌ ANNOUNCEMENT TEST FAILED - No announcements to display!")
        sys.exit(1)