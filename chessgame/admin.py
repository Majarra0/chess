from django.contrib import admin
from .models import ChessGame, ChessMove

admin.site.register(ChessGame)
admin.site.register(ChessMove)
