from django.contrib import admin

from django.conf import settings
from django.urls import re_path, include
from django.conf.urls.static import static
from django.urls import path

from core.views import admin_login

urlpatterns = [
    # antes de admin.site.urls: o login do admin passa a ser a tela própria (/login/)
    path('admin/login/', admin_login, name='admin_login'),
    re_path(r'^admin/', admin.site.urls),
    re_path(r'^', include('utils.urls')),
    re_path(r'^', include('core.urls')),
    re_path(r'^admin_tools/', include('admin_tools.urls'),),

] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

if settings.DEBUG_TOOLBAR:
    import debug_toolbar

    urlpatterns += [
        path("__debug__/", include(debug_toolbar.urls)),
    ]

