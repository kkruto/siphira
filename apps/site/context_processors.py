from .models import SiteSettings

# Single source of truth for the header, mobile menu and footer nav. Adding a
# page here puts it in all three at once.
NAV_LINKS = [
    ('/about/', 'About'),
    ('/projects/', 'Projects'),
    ('/blog/', 'Writing'),
    ('/skills/', 'Skills'),
    ('/now/', 'Now'),
]


def site_settings(request):
    """Makes the singleton and the nav available to every template."""
    return {
        'site': SiteSettings.load(),
        'nav_links': NAV_LINKS,
    }
