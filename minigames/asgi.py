import os
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application
from channels.sessions import SessionMiddlewareStack

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'minigames.settings')

# Call this first so Django sets up apps
django_asgi_app = get_asgi_application()

# Now import Django-dependent things
from chessgame.middleware import JWTAuthMiddleware
import chessgame.routing

# ...existing code...
application = ProtocolTypeRouter({
    'http': django_asgi_app,
    'websocket': SessionMiddlewareStack(
        JWTAuthMiddleware(
            URLRouter(
                chessgame.routing.websocket_urlpatterns
            )
        )
    ),
})
# ...existing code...