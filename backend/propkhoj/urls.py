"""
URL configuration for propkhoj project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.http import JsonResponse
from django.contrib import admin
from django.urls import path, include
from django.views import View
from django.middleware.csrf import get_token
from django.views.decorators.csrf import ensure_csrf_cookie
from django.utils.decorators import method_decorator
from dj_rest_auth.registration.views import SocialLoginView
from allauth.socialaccount.providers.google.views import GoogleOAuth2Adapter
from allauth.socialaccount.providers.facebook.views import FacebookOAuth2Adapter
from allauth.socialaccount.providers.github.views import GitHubOAuth2Adapter
from allauth.socialaccount.providers.oauth2.client import OAuth2Client
from .auth_views import (
    GoogleLoginInit, GoogleLoginCallback,
    FacebookLoginInit, FacebookLoginCallback,
    GithubLoginInit, GithubLoginCallback
)

class GoogleLogin(SocialLoginView):
    adapter_class = GoogleOAuth2Adapter
    callback_url = "http://localhost:3000"
    client_class = OAuth2Client

class FacebookLogin(SocialLoginView):
    adapter_class = FacebookOAuth2Adapter
    callback_url = "http://localhost:3000"
    client_class = OAuth2Client


class GithubLogin(SocialLoginView):
    adapter_class = GitHubOAuth2Adapter
    callback_url = "http://localhost:3000"
    client_class = OAuth2Client


@method_decorator(ensure_csrf_cookie, name='dispatch')
class CSRFTokenView(View):
    def get(self, request):
        return JsonResponse({"csrfToken": get_token(request)})


urlpatterns = [
    path('admin/', admin.site.urls),
    
    # 🔹 Email/Password Auth
    path('auth/', include('dj_rest_auth.urls')),
    path('auth/registration/', include('dj_rest_auth.registration.urls')),
    path('auth/csrf/', CSRFTokenView.as_view(), name="csrf_token"),

    # 🔹 Social Authentication Endpoints
    path('auth/google/', GoogleLogin.as_view(), name='google_login'),
    path('auth/facebook/', FacebookLogin.as_view(), name='facebook_login'),
    path('auth/github/', GithubLogin.as_view(), name='github_login'),

    path('auth/google/init/', GoogleLoginInit.as_view(), name='google_login_init'),
    path('auth/google/callback/', GoogleLoginCallback.as_view(), name='google_login_callback'),
    
    path('auth/facebook/init/', FacebookLoginInit.as_view(), name='facebook_login_init'),
    path('auth/facebook/callback/', FacebookLoginCallback.as_view(), name='facebook_login_callback'),
    
    path('auth/github/init/', GithubLoginInit.as_view(), name='github_login_init'),
    path('auth/github/callback/', GithubLoginCallback.as_view(), name='github_login_callback'),

    # 🔹 API Routes
    path('api/', include('api.urls')),
]
