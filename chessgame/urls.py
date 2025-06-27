from django.urls import path
from . import views
from . import consumers
from .views import SignupView

urlpatterns = [
    path('', views.chess_index, name='chess_index'),
    path('create/', views.create_game, name='create_game'),
    path('join/', views.create_or_join_game, name='create_or_join_game'),
    path('state/<str:room_name>/', views.get_game_state, name='get_game_state'),
    path('game/<str:room_name>/', views.get_game, name='get_game'),
    path('game_history/<str:room_name>/', consumers.game_history, name='game_history'),
    path('signup/', SignupView.as_view(), name='signup'),
]