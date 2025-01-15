from apps.home import views
from django.urls import path, re_path

urlpatterns = [
    # The home page
    path('', views.index, name='home'),
    # Matches any html file
    re_path(r'^.*\.*', views.pages, name='pages'),
]
