from django.test import TestCase, Client
from django.contrib.auth.models import User
from .models import ChessGame
from channels.testing import WebsocketCommunicator
from minigames.asgi import application
import pytest
import asyncio
from channels.db import database_sync_to_async
from django.test import TransactionTestCase
from chess import Board, STARTING_FEN

class ChessGameModelTest(TestCase):
    def test_game_history_endpoint(self):
        user = User.objects.create_user(username='testuser', password='testpass')
        game = ChessGame.objects.create(room_name='testroom2', player_white=user)
        # Add a move
        from .models import ChessMove
        ChessMove.objects.create(game=game, move='e2e4', move_number=1)
        client = Client()
        response = client.get(f'/chessgame/game_history/{game.room_name}/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('e2e4', response.json()['moves'])

@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class ChessConsumerTest(TransactionTestCase):
    async def test_websocket_move(self):
        user = await database_sync_to_async(User.objects.create_user)(
            username='testuser3', password='testpass3'
        )
        game = await database_sync_to_async(ChessGame.objects.create)(
            room_name='wsroom2',
            fen=STARTING_FEN
        )

        communicator = WebsocketCommunicator(application, "/ws/chessgame/wsroom2/")
        communicator.scope['user'] = user
        connected, _ = await communicator.connect()
        assert connected

        # Receive and discard the initial board state message
        initial = await communicator.receive_json_from()

        # Send a legal move (e2e4)
        await communicator.send_json_to({'move': {'from': 'e2', 'to': 'e4'}})
        for _ in range(3):
            response = await communicator.receive_json_from()
            if 'move' in response:
                assert response['move'] == {'from': 'e2', 'to': 'e4'}
                break
            elif 'error' in response:
                assert False, f"Error received: {response['error']}"
        else:
            assert False, "Did not receive move response"

        await communicator.disconnect()

    async def test_websocket_illegal_move(self):
        user = await database_sync_to_async(User.objects.create_user)(
            username='testuser4', password='testpass4'
        )
        
        game = await database_sync_to_async(ChessGame.objects.create)(
            room_name='wsroom3',
            fen=STARTING_FEN
        )

        communicator = WebsocketCommunicator(application, "/ws/chessgame/wsroom3/")
        communicator.scope['user'] = user
        connected, _ = await communicator.connect()
        assert connected

        # Receive and discard the initial board state message
        initial = await communicator.receive_json_from()

        # Send an illegal move (e2e5)
        await communicator.send_json_to({'move': {'from': 'e2', 'to': 'e5'}})
        response = await communicator.receive_json_from()
        assert 'error' in response

        await communicator.disconnect()

        