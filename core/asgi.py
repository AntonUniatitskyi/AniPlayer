"""
ASGI config for core project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/howto/deployment/asgi/
"""

import os

from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
import myanime.routing

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django_asgi_app = get_asgi_application()
application = ProtocolTypeRouter({
    # Если пришел HTTP запрос -> отдаем его стандартному Django
    "http": django_asgi_app,

    # Если пришел WebSocket запрос (ws://)
    "websocket": AuthMiddlewareStack(
        URLRouter(
            myanime.routing.websocket_urlpatterns
        )
    ),
})
