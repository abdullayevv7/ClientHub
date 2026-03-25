import time
import logging
import json
from django.http import JsonResponse
from django.conf import settings
from django.core.cache import cache
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware(MiddlewareMixin):
    """Logs all incoming requests with timing information."""

    def process_request(self, request):
        request._start_time = time.time()
        request._request_id = f"{int(time.time() * 1000)}"

    def process_response(self, request, response):
        if hasattr(request, '_start_time'):
            duration = time.time() - request._start_time
            log_data = {
                'request_id': getattr(request, '_request_id', ''),
                'method': request.method,
                'path': request.path,
                'status': response.status_code,
                'duration_ms': round(duration * 1000, 2),
                'user': str(request.user) if hasattr(request, 'user') and request.user.is_authenticated else 'anonymous',
                'ip': self.get_client_ip(request),
                'user_agent': request.META.get('HTTP_USER_AGENT', '')[:200],
            }

            if response.status_code >= 500:
                logger.error('Server error', extra=log_data)
            elif response.status_code >= 400:
                logger.warning('Client error', extra=log_data)
            else:
                logger.info('Request completed', extra=log_data)

        return response

    @staticmethod
    def get_client_ip(request):
        x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded:
            return x_forwarded.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '')


class RateLimitMiddleware(MiddlewareMixin):
    """Rate limiting middleware using Django cache."""

    RATE_LIMIT = getattr(settings, 'RATE_LIMIT_REQUESTS', 100)
    RATE_LIMIT_WINDOW = getattr(settings, 'RATE_LIMIT_WINDOW', 60)

    def process_request(self, request):
        if request.path.startswith('/admin/'):
            return None

        identifier = self._get_identifier(request)
        cache_key = f'ratelimit:{identifier}'

        request_count = cache.get(cache_key, 0)
        if request_count >= self.RATE_LIMIT:
            logger.warning(f'Rate limit exceeded for {identifier}')
            return JsonResponse(
                {'detail': 'Rate limit exceeded. Please try again later.'},
                status=429,
                headers={
                    'Retry-After': str(self.RATE_LIMIT_WINDOW),
                    'X-RateLimit-Limit': str(self.RATE_LIMIT),
                    'X-RateLimit-Remaining': '0',
                }
            )

        cache.set(cache_key, request_count + 1, self.RATE_LIMIT_WINDOW)
        return None

    def process_response(self, request, response):
        identifier = self._get_identifier(request)
        cache_key = f'ratelimit:{identifier}'
        request_count = cache.get(cache_key, 0)

        response['X-RateLimit-Limit'] = str(self.RATE_LIMIT)
        response['X-RateLimit-Remaining'] = str(max(0, self.RATE_LIMIT - request_count))
        return response

    @staticmethod
    def _get_identifier(request):
        if hasattr(request, 'user') and request.user.is_authenticated:
            return f'user:{request.user.pk}'
        x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded:
            return f'ip:{x_forwarded.split(",")[0].strip()}'
        return f'ip:{request.META.get("REMOTE_ADDR", "unknown")}'


class CORSMiddleware(MiddlewareMixin):
    """Simple CORS middleware for development."""

    ALLOWED_ORIGINS = getattr(settings, 'CORS_ALLOWED_ORIGINS', [
        'http://localhost:3000',
        'http://localhost:5173',
        'http://127.0.0.1:3000',
    ])

    def process_response(self, request, response):
        origin = request.META.get('HTTP_ORIGIN', '')
        if origin in self.ALLOWED_ORIGINS or getattr(settings, 'CORS_ALLOW_ALL', False):
            response['Access-Control-Allow-Origin'] = origin
            response['Access-Control-Allow-Methods'] = 'GET, POST, PUT, PATCH, DELETE, OPTIONS'
            response['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, X-Requested-With'
            response['Access-Control-Allow-Credentials'] = 'true'
            response['Access-Control-Max-Age'] = '86400'
        return response

    def process_request(self, request):
        if request.method == 'OPTIONS':
            response = JsonResponse({}, status=200)
            return response
        return None


class SecurityHeadersMiddleware(MiddlewareMixin):
    """Adds security headers to all responses."""

    def process_response(self, request, response):
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['X-XSS-Protection'] = '1; mode=block'
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        if not settings.DEBUG:
            response['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        return response
