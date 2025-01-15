from apps.authentication.views import login_view, register_user
from django.contrib.auth.views import LogoutView
from django.urls import path

urlpatterns = [
    path('login/', login_view, name='login'),
    path('register', register_user, name='register'),
    path('logout/', LogoutView.as_view(), name='logout'),
]
