from django.shortcuts import render

# Create your views here.
from django.http import JsonResponse
from .models import ChessGame
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required

def chess_index(request):
    return render(request, "index.html")

def create_or_join_game(request):
    if request.method == "POST":
        room_name = request.POST.get("room_name")
        game, created = ChessGame.objects.get_or_create(room_name=room_name)
        return JsonResponse({"room_name": game.room_name, "created": created})
    return JsonResponse({"error": "POST required"}, status=400)

@login_required
def get_game_state(request, room_name):
    game = ChessGame.objects.get(room_name=room_name)
    return JsonResponse({
        "fen": game.fen,
        "player_white": game.player_white.username if game.player_white else None,
        "player_black": game.player_black.username if game.player_black else None,
        "status": game.status,
    })

def create_game(request):
    import uuid
    room = str(uuid.uuid4())[:8]
    game = ChessGame.objects.create(room_name=room)
    return JsonResponse({'room_name': room, 'game_id': game.id})

def get_game(request, room_name):
    try:
        game = ChessGame.objects.get(room_name=room_name)
        return JsonResponse({'room_name': game.room_name, 'status': game.status})
    except ChessGame.DoesNotExist:
        return JsonResponse({'error': 'Game not found'}, status=404)
    
from rest_framework import generics
from .serializers import UserSignupSerializer
from rest_framework.permissions import AllowAny

class SignupView(generics.CreateAPIView):
    serializer_class = UserSignupSerializer
    permission_classes = [AllowAny]