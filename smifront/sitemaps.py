from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from django.utils import timezone
from datetime import datetime
from django.http import HttpResponse
from django.views import View
from django.conf import settings


class StaticViewSitemap(Sitemap):
    """Sitemap pour les pages statiques"""
    priority = 0.5
    changefreq = 'daily'

    def items(self):
        # Utilisez les noms corrects des URLs de votre urls.py
        return ['index', 'login', 'signup']

    def location(self, item):
        return reverse(item)

    def lastmod(self, item):
        return timezone.now()


class DashboardSitemap(Sitemap):
    """Sitemap pour les pages du dashboard"""
    changefreq = "weekly"
    priority = 0.7

    def items(self):
        return [
            'dashboard',
            'admin_products',
            'admin_categories',
            'dashboard_employe'
        ]

    def location(self, item):
        return reverse(item)

    def lastmod(self, item):
        return timezone.now()

    def priority(self, item):
        # Priorité différente selon l'importance
        if item == 'dashboard':
            return 0.8
        return 0.6


# Dictionnaire de toutes les sitemaps
sitemaps = {
    'static': StaticViewSitemap,
    'dashboard': DashboardSitemap,
}


class RobotsTxtView(View):
    """Vue pour générer robots.txt dynamiquement"""

    def get(self, request):
        lines = [
            "User-agent: *",
            "Disallow: /admin/",
            "Disallow: /verify-account/",
            "Disallow: /resend-verification/",
            "Allow: /static/",
            "Allow: /media/",
            "",
            f"Sitemap: {request.scheme}://{request.get_host()}/sitemap.xml",
            "",
            "Crawl-delay: 1",
            "",
        ]

        # Ajouter des règles spécifiques selon l'environnement
        if not settings.DEBUG:
            lines.extend([
                "# Production rules",
                "User-agent: Googlebot",
                "Allow: /",
                "Crawl-delay: 0",
                "",
                "User-agent: Bingbot",
                "Allow: /",
                "Crawl-delay: 0",
                "",
            ])

        # Bloquer les mauvais bots
        bad_bots = ['AhrefsBot', 'SemrushBot', 'DotBot', 'MJ12bot']
        for bot in bad_bots:
            lines.extend([
                f"User-agent: {bot}",
                "Disallow: /",
                "",
            ])

        return HttpResponse("\n".join(lines), content_type="text/plain")