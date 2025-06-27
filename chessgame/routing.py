from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/chessgame/(?P<room_name>\w+)/$', consumers.ChessConsumer.as_asgi()),
]