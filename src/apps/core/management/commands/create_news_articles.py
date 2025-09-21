from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from apps.core.models import NewsUpdate
import random

User = get_user_model()


class Command(BaseCommand):
    help = 'Create sample news articles for the platform'

    def add_arguments(self, parser):
        parser.add_argument(
            '--count',
            type=int,
            default=5,
            help='Number of articles to create',
        )
        parser.add_argument(
            '--clear-first',
            action='store_true',
            help='Clear existing news articles first',
        )
        parser.add_argument(
            '--unpublished',
            action='store_true',
            help='Create articles as unpublished drafts',
        )

    def handle(self, *args, **options):
        # Get or create admin user for articles
        try:
            admin_user = User.objects.filter(is_superuser=True).first()
            if not admin_user:
                admin_user = User.objects.filter(is_staff=True).first()
            if not admin_user:
                self.stdout.write(
                    self.style.WARNING('No admin user found. Creating articles without author.')
                )
                admin_user = None
        except Exception as e:
            self.stdout.write(
                self.style.WARNING(f'Error finding admin user: {e}. Creating articles without author.')
            )
            admin_user = None

        # Clear existing articles if requested
        if options['clear_first']:
            count = NewsUpdate.objects.count()
            NewsUpdate.objects.all().delete()
            self.stdout.write(
                self.style.SUCCESS(f'Cleared {count} existing news articles.')
            )

        # Determine published status
        is_published = not options['unpublished']

        # Create sample articles
        created_count = 0
        for i in range(options['count']):
            article_data = self.get_sample_article_data(i)
            
            try:
                article = NewsUpdate.objects.create(
                    title=article_data['title'],
                    content=article_data['content'],
                    excerpt=article_data['excerpt'],
                    is_published=is_published,
                    author=admin_user,
                    view_count=random.randint(50, 500)  # Add some realistic view counts
                )
                
                status = "Published" if is_published else "Draft"
                self.stdout.write(
                    self.style.SUCCESS(f'Created {status}: "{article.title}" (Slug: {article.slug})')
                )
                created_count += 1
                
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'Error creating article: {e}')
                )

        # Show summary
        total_articles = NewsUpdate.objects.count()
        published_articles = NewsUpdate.objects.filter(is_published=True).count()
        
        self.stdout.write(
            self.style.SUCCESS(f'\nSUCCESS: Created {created_count} news articles!')
        )
        self.stdout.write(f'Total articles: {total_articles}')
        self.stdout.write(f'Published articles: {published_articles}')
        
        if published_articles > 0:
            self.stdout.write(f'\nYou can now visit:')
            self.stdout.write(f'• News List: http://127.0.0.1:8000/news/')
            self.stdout.write(f'• Individual articles will have URLs like: http://127.0.0.1:8000/news/[slug]/')

    def get_sample_article_data(self, index):
        """Get sample article data"""
        
        sample_articles = [
            {
                'title': 'TradeVision Launches Advanced AI Trading Algorithm',
                'content': self.get_ai_algorithm_content(),
                'excerpt': 'TradeVision unveils its revolutionary AI-powered trading algorithm with 25% improved profit generation and advanced risk management features.',
            },
            {
                'title': 'Market Analysis: Cryptocurrency Trends for Q4 2025',
                'content': self.get_crypto_analysis_content(),
                'excerpt': 'Comprehensive analysis of Q4 2025 cryptocurrency trends and trading opportunities with Bitcoin maintaining strong momentum above $75K.',
            },
            {
                'title': 'New Partnership: Enhanced Security Features',
                'content': self.get_security_partnership_content(),
                'excerpt': 'TradeVision partners with CyberSafe Technologies to implement military-grade security measures including biometric verification and real-time fraud detection.',
            },
            {
                'title': 'Success Story: User Achieves $50K Profit in 3 Months',
                'content': self.get_success_story_content(),
                'excerpt': 'TradeVision user Sarah Johnson shares how she earned $50,000 in three months starting with a $5,000 investment in our Premium trading package.',
            },
            {
                'title': 'Platform Update: Mobile App Version 3.0 Released',
                'content': self.get_mobile_app_content(),
                'excerpt': 'TradeVision Mobile App Version 3.0 now available with redesigned interface, real-time notifications, and 40% performance improvement.',
            },
            {
                'title': 'Weekly Trading Report: Exceptional Performance Metrics',
                'content': self.get_trading_report_content(),
                'excerpt': 'This week showed outstanding results with 94.7% success rate and average daily returns of 8.3% across all trading packages.',
            },
            {
                'title': 'New Feature: Automated Profit Compounding',
                'content': self.get_compounding_feature_content(),
                'excerpt': 'Introducing automated profit compounding that can increase your returns by up to 40% through intelligent reinvestment strategies.',
            },
            {
                'title': 'Expert Interview: Future of Automated Trading',
                'content': self.get_expert_interview_content(),
                'excerpt': 'Industry expert Dr. Michael Roberts shares insights on the future of automated trading and AI in financial markets.',
            },
            {
                'title': 'TradeVision Reaches 50,000 Active Users Milestone',
                'content': self.get_milestone_content(),
                'excerpt': 'Celebrating a major milestone as TradeVision surpasses 50,000 active users with over $100M in successful trades processed.',
            },
            {
                'title': 'Important: New Regulatory Compliance Features',
                'content': self.get_compliance_content(),
                'excerpt': 'TradeVision implements new regulatory compliance features to ensure full adherence to international financial regulations.',
            }
        ]
        
        # Use modulo to cycle through articles if more are requested than available
        return sample_articles[index % len(sample_articles)]

    def get_ai_algorithm_content(self):
        return '''
        <p>We're excited to announce the launch of our revolutionary AI-powered trading algorithm that promises to deliver even higher returns for our investors.</p>
        
        <h3>Key Features</h3>
        <ul>
            <li>Advanced machine learning capabilities</li>
            <li>Real-time market analysis</li>
            <li>Risk management optimization</li>
            <li>24/7 automated trading</li>
        </ul>
        
        <p>Our new algorithm has been tested extensively and shows a 25% improvement in profit generation compared to our previous system. This means higher daily returns for all our users.</p>
        
        <h3>What This Means for You</h3>
        <p>Starting today, all new and existing investments will benefit from this enhanced trading system. You can expect to see improved performance across all trading packages.</p>
        
        <p>We're committed to providing the best trading experience possible, and this update represents a significant step forward in achieving that goal.</p>
        '''

    def get_crypto_analysis_content(self):
        return '''
        <p>As we approach the final quarter of 2025, the cryptocurrency market continues to show strong momentum with several key trends emerging.</p>
        
        <h3>Major Market Movements</h3>
        <p>Bitcoin has maintained its position above $75,000, while Ethereum continues to benefit from increased institutional adoption. Our trading algorithms have successfully capitalized on these trends.</p>
        
        <h3>Key Opportunities</h3>
        <ul>
            <li>DeFi protocols showing 40% growth</li>
            <li>NFT market stabilization</li>
            <li>Institutional crypto adoption increasing</li>
            <li>Regulatory clarity improving globally</li>
        </ul>
        
        <p>Our analysis suggests that Q4 2025 will be a particularly profitable period for cryptocurrency trading, with our AI systems already identifying multiple high-probability trading opportunities.</p>
        '''

    def get_security_partnership_content(self):
        return '''
        <p>TradeVision is proud to announce our partnership with CyberSafe Technologies to implement state-of-the-art security measures for our platform.</p>
        
        <h3>Enhanced Security Measures</h3>
        <ul>
            <li>Multi-factor authentication</li>
            <li>Advanced encryption protocols</li>
            <li>Real-time fraud detection</li>
            <li>Secure wallet integration</li>
            <li>Biometric verification options</li>
        </ul>
        
        <p>Your security is our top priority. These new measures ensure that your investments and personal information are protected with military-grade security.</p>
        '''

    def get_success_story_content(self):
        return '''
        <p>Meet Sarah Johnson, a TradeVision user who transformed her financial future by earning over $50,000 in just three months through our advanced trading platform.</p>
        
        <h3>Sarah's Journey</h3>
        <p>"I started with a modest investment of $5,000 in the Premium package. The results exceeded all my expectations," says Sarah, a teacher from California.</p>
        
        <blockquote>
        <p>"The daily profits were consistent, and the withdrawal process was instant. I've never experienced anything like this before. TradeVision has completely changed my life."</p>
        </blockquote>
        
        <p>Start your own success story today with our proven trading packages.</p>
        '''

    def get_mobile_app_content(self):
        return '''
        <p>We're excited to announce the release of TradeVision Mobile App Version 3.0, featuring a completely redesigned interface and powerful new features.</p>
        
        <h3>What's New</h3>
        <ul>
            <li>Redesigned user interface for better navigation</li>
            <li>Real-time profit tracking with push notifications</li>
            <li>One-tap deposit and withdrawal functionality</li>
            <li>Dark mode support</li>
            <li>Enhanced security with biometric login</li>
        </ul>
        
        <p>Version 3.0 is available for download from both the App Store and Google Play Store.</p>
        '''

    def get_trading_report_content(self):
        return '''
        <p>This week delivered exceptional results for TradeVision users across all trading packages.</p>
        
        <h3>Performance Highlights</h3>
        <ul>
            <li>Overall success rate: 94.7%</li>
            <li>Average daily return: 8.3%</li>
            <li>Total profit generated: $2.3M</li>
            <li>Active trading sessions: 12,847</li>
        </ul>
        
        <p>These results demonstrate the continued effectiveness of our AI-powered trading system.</p>
        '''

    def get_compounding_feature_content(self):
        return '''
        <p>Introducing our new automated profit compounding feature that intelligently reinvests your profits for exponential growth.</p>
        
        <h3>How It Works</h3>
        <p>The system automatically reinvests a portion of your daily profits back into your trading account, compounding your returns over time.</p>
        
        <ul>
            <li>Customizable compounding rates</li>
            <li>Minimum threshold settings</li>
            <li>Real-time compounding analytics</li>
        </ul>
        
        <p>Users who enable compounding see an average 40% increase in total returns.</p>
        '''

    def get_expert_interview_content(self):
        return '''
        <p>We sat down with Dr. Michael Roberts, a leading expert in algorithmic trading, to discuss the future of automated trading systems.</p>
        
        <h3>Key Insights</h3>
        <p>"AI-powered trading represents the future of financial markets. The ability to process vast amounts of data in real-time gives automated systems a significant advantage," says Dr. Roberts.</p>
        
        <p>He also highlighted the importance of risk management and the role of human oversight in automated trading systems.</p>
        '''

    def get_milestone_content(self):
        return '''
        <p>We're proud to announce that TradeVision has reached a significant milestone: 50,000 active users and over $100 million in successful trades processed.</p>
        
        <h3>Growth Statistics</h3>
        <ul>
            <li>50,000+ active users</li>
            <li>$100M+ in processed trades</li>
            <li>$15M+ in profits paid out</li>
            <li>95% user satisfaction rate</li>
        </ul>
        
        <p>Thank you to all our users for making this milestone possible. Here's to the next 50,000!</p>
        '''

    def get_compliance_content(self):
        return '''
        <p>In our ongoing commitment to transparency and regulatory compliance, TradeVision has implemented new features to ensure full adherence to international financial regulations.</p>
        
        <h3>New Compliance Features</h3>
        <ul>
            <li>Enhanced KYC verification</li>
            <li>Automated transaction reporting</li>
            <li>Real-time compliance monitoring</li>
            <li>Regulatory audit trail</li>
        </ul>
        
        <p>These measures ensure that TradeVision remains fully compliant with all applicable regulations while maintaining our high standards of service.</p>
        '''