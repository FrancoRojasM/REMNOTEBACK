# remnote_api/middleware.py
from django.utils import timezone

class ActivateLimaTimezoneMiddleware:
    """
    Activa 'America/Lima' por request para que timezone.get_current_timezone()
    sea Lima y la serialización use hora local (si tu serializer o DRF lo respetan).
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            timezone.activate("America/Lima")
        except Exception:
            timezone.deactivate()
        return self.get_response(request)
