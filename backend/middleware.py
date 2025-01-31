import logging
from django.utils.timezone import now

class AccessLoggingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        user = request.user if request.user.is_authenticated else "Guest"
        
        logging.getLogger("django.request").info(
            f"[{now()}] {request.method} {request.path} {response.status_code} - {user}"
        )
        
        return response
