from django.db import models
from django.contrib.auth.models import User

class ChessGame(models.Model):
    room_name = models.CharField(max_length=100, unique=True)
    player_white = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='games_as_white')
    player_black = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='games_as_black')
    fen = models.TextField(default="startpos")  # optional if you want to resume state
    status = models.CharField(max_length=20, default="waiting")  # waiting, in_progress, finished
    winner = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='wins')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class ChessMove(models.Model):
    game = models.ForeignKey(ChessGame, on_delete=models.CASCADE, related_name="moves")
    move = models.CharField(max_length=10)  # e.g. e2e4
    timestamp = models.DateTimeField(auto_now_add=True)
    move_number = models.PositiveIntegerField()
