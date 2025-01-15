from django.contrib import admin
from django.urls import include, path  # add this

urlpatterns = [
    path('admin/', admin.site.urls),  # Django admin route
    path(
        '', include('apps.authentication.urls')
    ),  # Auth routes - login / register
    # Django Debug Toolbar
    # path('__debug__/', include('debug_toolbar.urls')),
    path('clientes/', include('apps.clientes.urls')),
    path('django_plotly_dash/', include('django_plotly_dash.urls')),
    # Leave `Home.Urls` as last the last line
    path('', include('apps.home.urls')),
]
