from django.shortcuts import redirect
from django.conf import settings
from django.urls import reverse
from django.http import JsonResponse
from rest_framework.views import APIView
from allauth.socialaccount.providers.google.views import GoogleOAuth2Adapter
from allauth.socialaccount.providers.facebook.views import FacebookOAuth2Adapter
from allauth.socialaccount.providers.github.views import GitHubOAuth2Adapter
from allauth.socialaccount.providers.oauth2.client import OAuth2Client
from dj_rest_auth.registration.views import SocialLoginView
import requests

class GoogleLoginInit(APIView):
    def get(self, request, *args, **kwargs):
        client_id = settings.SOCIALACCOUNT_PROVIDERS['google']['APP']['client_id']
        redirect_uri = 'http://localhost:3000/login'
        scope = 'email profile'
        
        google_auth_url = f'https://accounts.google.com/o/oauth2/v2/auth?'
        google_auth_url += f'client_id={client_id}&'
        google_auth_url += f'redirect_uri={redirect_uri}&'
        google_auth_url += 'response_type=code&'
        google_auth_url += f'scope={scope}'
        
        return redirect(google_auth_url)

class FacebookLoginInit(APIView):
    def get(self, request, *args, **kwargs):
        client_id = settings.SOCIALACCOUNT_PROVIDERS['facebook']['APP']['client_id']
        redirect_uri = 'http://localhost:3000/login'
        scope = 'email public_profile'
        
        facebook_auth_url = f'https://www.facebook.com/v12.0/dialog/oauth?'
        facebook_auth_url += f'client_id={client_id}&'
        facebook_auth_url += f'redirect_uri={redirect_uri}&'
        facebook_auth_url += 'response_type=code&'
        facebook_auth_url += f'scope={scope}'
        
        return redirect(facebook_auth_url)

class GithubLoginInit(APIView):
    def get(self, request, *args, **kwargs):
        client_id = settings.SOCIALACCOUNT_PROVIDERS['github']['APP']['client_id']
        redirect_uri = 'http://localhost:3000/login'
        scope = 'user:email'
        
        github_auth_url = f'https://github.com/login/oauth/authorize?'
        github_auth_url += f'client_id={client_id}&'
        github_auth_url += f'redirect_uri={redirect_uri}&'
        github_auth_url += f'scope={scope}'
        
        return redirect(github_auth_url)

class GoogleLoginCallback(SocialLoginView):
    adapter_class = GoogleOAuth2Adapter
    callback_url = 'http://localhost:3000/login'
    client_class = OAuth2Client

    def post(self, request, *args, **kwargs):
        code = request.data.get('code')
        
        if not code:
            return JsonResponse({'error': 'No code provided'}, status=400)
            
        try:
            client_id = settings.SOCIALACCOUNT_PROVIDERS['google']['APP']['client_id']
            client_secret = settings.SOCIALACCOUNT_PROVIDERS['google']['APP']['secret']
            
            token_url = 'https://oauth2.googleapis.com/token'
            data = {
                'code': code,
                'client_id': client_id,
                'client_secret': client_secret,
                'redirect_uri': self.callback_url,
                'grant_type': 'authorization_code'
            }
            
            response = requests.post(token_url, data=data)
            response.raise_for_status()
            access_token = response.json()['access_token']
            
            user_info_response = requests.get(
                'https://www.googleapis.com/oauth2/v2/userinfo',
                headers={'Authorization': f'Bearer {access_token}'}
            )
            user_info_response.raise_for_status()
            user_info = user_info_response.json()
            
            adapter = self.adapter_class(request)
            app = adapter.get_provider().get_app(request)
            token = adapter.parse_token({'access_token': access_token})
            token.app = app
            
            login = adapter.complete_login(request, app, token, user_info)
            login.token = access_token
            
            return JsonResponse({
                'key': self.get_response().data['key'],
                'user': user_info
            })
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)

class FacebookLoginCallback(SocialLoginView):
    adapter_class = FacebookOAuth2Adapter
    callback_url = 'http://localhost:3000/login'
    client_class = OAuth2Client

    def post(self, request, *args, **kwargs):
        code = request.data.get('code')
        
        if not code:
            return JsonResponse({'error': 'No code provided'}, status=400)
            
        try:
            client_id = settings.SOCIALACCOUNT_PROVIDERS['facebook']['APP']['client_id']
            client_secret = settings.SOCIALACCOUNT_PROVIDERS['facebook']['APP']['secret']
            
            token_url = 'https://graph.facebook.com/v12.0/oauth/access_token'
            data = {
                'code': code,
                'client_id': client_id,
                'client_secret': client_secret,
                'redirect_uri': self.callback_url
            }
            
            response = requests.get(token_url, params=data)
            response.raise_for_status()
            access_token = response.json()['access_token']
            
            user_info_response = requests.get(
                'https://graph.facebook.com/me',
                params={'fields': 'id,email,first_name,last_name', 'access_token': access_token}
            )
            user_info_response.raise_for_status()
            user_info = user_info_response.json()
            
            adapter = self.adapter_class(request)
            app = adapter.get_provider().get_app(request)
            token = adapter.parse_token({'access_token': access_token})
            token.app = app
            
            login = adapter.complete_login(request, app, token, user_info)
            login.token = access_token
            
            return JsonResponse({
                'key': self.get_response().data['key'],
                'user': user_info
            })
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)

class GithubLoginCallback(SocialLoginView):
    adapter_class = GitHubOAuth2Adapter
    callback_url = 'http://localhost:3000/login'
    client_class = OAuth2Client

    def post(self, request, *args, **kwargs):
        code = request.data.get('code')
        
        if not code:
            return JsonResponse({'error': 'No code provided'}, status=400)
            
        try:
            client_id = settings.SOCIALACCOUNT_PROVIDERS['github']['APP']['client_id']
            client_secret = settings.SOCIALACCOUNT_PROVIDERS['github']['APP']['secret']
            
            token_url = 'https://github.com/login/oauth/access_token'
            data = {
                'code': code,
                'client_id': client_id,
                'client_secret': client_secret,
                'redirect_uri': self.callback_url
            }
            headers = {'Accept': 'application/json'}
            
            response = requests.post(token_url, data=data, headers=headers)
            response.raise_for_status()
            access_token = response.json()['access_token']
            
            user_info_response = requests.get(
                'https://api.github.com/user',
                headers={
                    'Authorization': f'token {access_token}',
                    'Accept': 'application/json'
                }
            )
            user_info_response.raise_for_status()
            user_info = user_info_response.json()
            
            # Get email if not included in user info
            if 'email' not in user_info or not user_info['email']:
                email_response = requests.get(
                    'https://api.github.com/user/emails',
                    headers={
                        'Authorization': f'token {access_token}',
                        'Accept': 'application/json'
                    }
                )
                emails = email_response.json()
                primary_email = next((email for email in emails if email['primary']), emails[0])
                user_info['email'] = primary_email['email']
            
            adapter = self.adapter_class(request)
            app = adapter.get_provider().get_app(request)
            token = adapter.parse_token({'access_token': access_token})
            token.app = app
            
            login = adapter.complete_login(request, app, token, user_info)
            login.token = access_token
            
            return JsonResponse({
                'key': self.get_response().data['key'],
                'user': user_info
            })
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
