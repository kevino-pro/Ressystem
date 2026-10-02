import hmac
import secrets
import threading
import time
from collections import defaultdict, deque
from functools import wraps

from flask import current_app, jsonify, request, session

CSRF_SESSION_KEY = '_csrf_token'


def constant_time_equals(kandidaat, verwacht):
    """Constant-time vergelijking; fail-closed bij ontbrekende waarden."""
    if not kandidaat or not verwacht:
        return False
    return hmac.compare_digest(str(kandidaat).encode('utf-8'), str(verwacht).encode('utf-8'))


class RateLimiter:
    """Sliding-window limiter in het geheugen. Let op: de teller is per proces (per gunicorn-worker)."""

    def __init__(self):
        self._hits = defaultdict(deque)
        self._lock = threading.Lock()

    def hit(self, sleutel, limiet, venster_seconden):
        """Registreert een poging; geeft True als die binnen de limiet valt."""
        nu = time.monotonic()
        with self._lock:
            hits = self._hits[sleutel]
            while hits and hits[0] <= nu - venster_seconden:
                hits.popleft()
            if len(hits) >= limiet:
                return False
            hits.append(nu)
            if len(self._hits) > 10000:
                self._opruimen(nu - venster_seconden)
            return True

    def _opruimen(self, grens):
        for sleutel in [k for k, v in self._hits.items() if not v or v[-1] <= grens]:
            del self._hits[sleutel]


_limiter = RateLimiter()


def rate_limit_check(naam, limiet, venster_seconden):
    """Geeft False als de huidige client over de limiet is. Altijd True als limiting is uitgeschakeld."""
    if not current_app.config.get('RATELIMIT_ENABLED', True):
        return True
    return _limiter.hit(f'{naam}:{request.remote_addr}', limiet, venster_seconden)


def reset_rate_limits():
    with _limiter._lock:
        _limiter._hits.clear()


def rate_limit(naam, limiet, venster_seconden, json_response=False):
    def decorator(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            if not rate_limit_check(naam, limiet, venster_seconden):
                if json_response:
                    return jsonify({"status": "fout", "bericht": "Te veel verzoeken, probeer het later opnieuw."}), 429
                return "Te veel verzoeken, probeer het later opnieuw.", 429
            return view(*args, **kwargs)
        return wrapper
    return decorator


def csrf_token():
    token = session.get(CSRF_SESSION_KEY)
    if not token:
        token = secrets.token_urlsafe(32)
        session[CSRF_SESSION_KEY] = token
    return token


def valideer_csrf():
    """before_request-hook voor sessie/formulier-routes; API-blueprint gebruikt key-auth en is uitgezonderd."""
    if not current_app.config.get('CSRF_ENABLED', True):
        return None
    if request.method in ('GET', 'HEAD', 'OPTIONS'):
        return None
    verwacht = session.get(CSRF_SESSION_KEY)
    ontvangen = request.headers.get('X-CSRF-Token') or request.form.get('csrf_token')
    if not constant_time_equals(ontvangen, verwacht):
        bericht = 'Ongeldig of ontbrekend CSRF-token, ververs de pagina en probeer opnieuw.'
        if request.is_json:
            return jsonify({"status": "fout", "bericht": bericht}), 400
        return bericht, 400
    return None
