from cinema_base.healthy import Healthy

_health_view = Healthy.as_view()


class HealthCheckMiddleware:
    """Answer /health/ before ALLOWED_HOSTS validation (for ALB health checks)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path == "/health/":
            response = _health_view(request)
            response.render()
            return response
        return self.get_response(request)
