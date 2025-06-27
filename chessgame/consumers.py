from channels.generic.websocket import AsyncWebsocketConsumer
import json
from chess import Board, WHITE, BLACK
from asgiref.sync import sync_to_async

@sync_to_async
def get_real_user(user):
    if not user.is_authenticated:
        return None
    return user

@sync_to_async
def assign_player(game, user):
    # Remove inactive users from slots
    if game.player_white and not game.player_white.is_active:
        game.player_white = None
    if game.player_black and not game.player_black.is_active:
        game.player_black = None

    # If user is already assigned, return their color
    if game.player_white == user:
        return "white"
    if game.player_black == user:
        return "black"
    # Assign to an empty slot, but don't assign the same user to both
    if not game.player_white:
        game.player_white = user
        game.save()
        return "white"
    elif not game.player_black:
        game.player_black = user
        game.save()
        return "black"
    # Both slots taken by other users
    return None

class ChessConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_name = self.scope['url_route']['kwargs']['room_name']
        self.room_group_name = f"chessgame_{self.room_name}"

        from .models import ChessGame, ChessMove
        user = self.scope["user"]
        if not user or not user.is_authenticated:
            await self.close()
            return
        await self.accept()

        # Get or create the game
        self.game_obj, _ = await sync_to_async(ChessGame.objects.get_or_create)(room_name=self.room_name)
        initial_fen = self.game_obj.fen
        self.board = Board() if not initial_fen or initial_fen == "startpos" else Board(initial_fen)

        # Authenticate user
        self.user = await get_real_user(self.scope['user'])
        if not self.user:
            await self.close()
            return

        # Assign player color
        white = await sync_to_async(lambda g: g.player_white)(self.game_obj)
        black = await sync_to_async(lambda g: g.player_black)(self.game_obj)
        print("Before assign_player: white =", white, "black =", black)
        self.color = await assign_player(self.game_obj, self.user)
        print("Assigned color:", self.color)
        if self.color is None:
            await self.send(text_data=json.dumps({'error': 'Game is full.'}))
            await self.close()
            return

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)

        # Send initial board state and move history
        moves = await sync_to_async(list)(self.game_obj.moves.order_by('move_number'))
        move_list = [m.move for m in moves]
        await self.send(text_data=json.dumps({
            'fen': self.board.fen(),
            'moves': move_list,
            'color': self.color
        }))

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)
        # Optionally clear player slot
        from .models import ChessGame
        if hasattr(self, "room_group_name"):
            await self.channel_layer.group_discard(self.room_group_name, self.channel_name)
        if hasattr(self, 'user') and self.user:
            def clear_slot(game, user):
                changed = False
                if game.player_white == user:
                    game.player_white = None
                    changed = True
                if game.player_black == user:
                    game.player_black = None
                    changed = True
                if changed:
                    game.save()
            await sync_to_async(clear_slot)(self.game_obj, self.user)

    async def receive(self, text_data):
        from .models import ChessMove, ChessGame
        data = json.loads(text_data)
        move_data = data.get('move')

        # Handle resign action
        if data.get('action') == 'resign':
            winner_color = 'black' if self.color == 'white' else 'white'
            winner_user = getattr(self.game_obj, f'player_{winner_color}')
            await sync_to_async(ChessGame.objects.filter(id=self.game_obj.id).update)(
                status='finished',
                winner=winner_user
            )
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'game_over',
                    'result': f'{self.color.capitalize()} resigned. {winner_color.capitalize()} wins.'
                }
            )
            return

        if data.get('action') == 'draw_offer':
            # Broadcast draw offer to the other player only
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'draw_offer',
                    'from_user': self.user.username,
                    'sender_channel': self.channel_name,  # Add sender's channel name
                }
            )
            return

        if data.get('action') == 'accept_draw':
            await sync_to_async(ChessGame.objects.filter(id=self.game_obj.id).update)(
                status='finished',
                winner=None
            )
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'game_over',
                    'result': 'Draw agreed by both players.'
                }
            )
            return

        if data.get('action') == 'decline_draw':
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'draw_declined',
                    'from_user': self.user.username,
                }
            )
            return

        # Validate and apply move
        try:
            if not move_data or 'from' not in move_data or 'to' not in move_data:
                await self.send(text_data=json.dumps({'error': 'Invalid move data: Both "from" and "to" squares are required.'}))
                return

            uci = move_data['from'] + move_data['to']
            if 'promotion' in move_data:
                uci += move_data['promotion'].lower()
            try:
                chess_move = self.board.parse_uci(uci)
            except Exception:
                await self.send(text_data=json.dumps({'error': f'Invalid move notation: {uci} is not a valid move.'}))
                return

            # Check turn
            if (self.board.turn == WHITE and self.color != "white") or \
            (self.board.turn == BLACK and self.color != "black"):
                await self.send(text_data=json.dumps({'error': 'It is not your turn. Please wait for your opponent.'}))
                return

            if chess_move not in self.board.legal_moves:
                await self.send(text_data=json.dumps({'error': f'Illegal move: {uci} is not allowed in the current position.'}))
                return

            self.board.push(chess_move)
            await sync_to_async(ChessMove.objects.create)(
                game=self.game_obj,
                move=uci,
                move_number=self.board.fullmove_number
            )
            await sync_to_async(ChessGame.objects.filter(id=self.game_obj.id).update)(
                fen=self.board.fen()
            )

            # Broadcast move
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'send_move',
                    'move': move_data
                }
            )

            # Game end checks
            if self.board.is_checkmate():
                await sync_to_async(ChessGame.objects.filter(id=self.game_obj.id).update)(
                    status='finished',
                    winner=self.user
                )
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'game_over',
                        'result': f'Checkmate! {self.color.capitalize()} wins.'
                    }
                )
            elif self.board.is_stalemate():
                await sync_to_async(ChessGame.objects.filter(id=self.game_obj.id).update)(
                    status='finished',
                    winner=None
                )
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'game_over',
                        'result': 'Draw by stalemate.'
                    }
                )
            elif self.board.is_insufficient_material():
                await sync_to_async(ChessGame.objects.filter(id=self.game_obj.id).update)(
                    status='finished',
                    winner=None
                )
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'game_over',
                        'result': 'Draw by insufficient material.'
                    }
                )
            elif self.board.can_claim_fifty_moves():
                await sync_to_async(ChessGame.objects.filter(id=self.game_obj.id).update)(
                    status='finished',
                    winner=None
                )
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'game_over',
                        'result': 'Draw by fifty-move rule.'
                    }
                )
            elif self.board.can_claim_threefold_repetition():
                await sync_to_async(ChessGame.objects.filter(id=self.game_obj.id).update)(
                    status='finished',
                    winner=None
                )
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'game_over',
                        'result': 'Draw by threefold repetition.'
                    }
                )

        except Exception as e:
            await self.send(text_data=json.dumps({'error': str(e)}))

    async def send_move(self, event):
        move = event['move']
        # Update local board state
        try:
            uci = move['from'] + move['to']
            if 'promotion' in move:
                uci += move['promotion'].lower()
            self.board.push_uci(uci)
        except Exception as e:
            print("Error updating board in send_move:", e)
        await self.send(text_data=json.dumps({'move': move, 'fen': self.board.fen()}))

    async def game_over(self, event):
        await self.send(text_data=json.dumps({'game_over': event['result']}))

    async def draw_offer(self, event):
        if self.channel_name != event.get('sender_channel'):
            await self.send(text_data=json.dumps({'draw_offer': True, 'from_user': event.get('from_user')}))

    async def draw_declined(self, event):
        await self.send(text_data=json.dumps({'draw_declined': True, 'from_user': event.get('from_user')}))

# Game history endpoint (for HTTP, not WebSocket)
from django.http import JsonResponse
def game_history(request, room_name):
    from .models import ChessGame, ChessMove
    game = ChessGame.objects.get(room_name=room_name)
    moves = ChessMove.objects.filter(game=game).order_by('move_number')
    return JsonResponse({'moves': [m.move for m in moves]})
