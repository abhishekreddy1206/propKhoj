import logging
from django.utils.timezone import now

class AccessLoggingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # ✅ Ensure authentication middleware has run before accessing `request.user`
        user = getattr(request, "user", None)
        if user and hasattr(user, "is_authenticated"):
            user_display = user if user.is_authenticated else "Guest"
        else:
            user_display = "Anonymous"

        logging.getLogger("django.request").info(
            f"[{now()}] {request.method} {request.path} {response.status_code} - {user_display}"
        )

        return response
