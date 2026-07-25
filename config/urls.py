from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include

admin.site.site_header = 'Siphira John'
admin.site.site_title = 'Siphira John — admin'
admin.site.index_title = 'Manage your site'

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('apps.site.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

handler404 = 'apps.site.views.handler404'
handler500 = 'apps.site.views.handler500'
