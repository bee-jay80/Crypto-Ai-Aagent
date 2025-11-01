import time
import redis
from django.http import JsonResponse
from django.conf import settings

r = redis.from_url(settings.RATE_LIMIT_REDIS)

RATE_LIMIT = 30  # requests
WINDOW = 60      # per 60 seconds

class RateLimitMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        key = request.headers.get("X-API-KEY")

        if not key:
            return JsonResponse({"error": "API Key required"}, status=401)

        redis_key = f"rate:{key}"
        current_count = r.get(redis_key)

        if current_count and int(current_count) >= RATE_LIMIT:
            return JsonResponse({
                "error": "Rate limit exceeded. Try again later."
            }, status=429)

        if not current_count:
            r.set(redis_key, 1, ex=WINDOW)
        else:
            r.incr(redis_key)

        return self.get_response(request)
