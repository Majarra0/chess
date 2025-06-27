from urllib.parse import parse_qs
from django.contrib.auth.models import AnonymousUser
from channels.middleware import BaseMiddleware
from rest_framework_simplejwt.tokens import UntypedToken
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.db import close_old_connections
from asgiref.sync import sync_to_async

class JWTAuthMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        # Get token from query string
        query_string = scope.get('query_string', b'').decode()
        token = parse_qs(query_string).get('token')
        if token:
            token = token[0]
        else:
            token = None

        user = None
        if token:
            try:
                print("JWT token received:", token)
                UntypedToken(token)
                validated_token = JWTAuthentication().get_validated_token(token)
                # Use sync_to_async for DB access
                user = await sync_to_async(JWTAuthentication().get_user)(validated_token)
                print("JWT user:", user)
            except Exception as e:
                print("JWT auth failed:", e)

        # If no JWT user, fall back to whatever is already in scope, or AnonymousUser
        if not user:
            user = scope.get("user", AnonymousUser())
        scope["user"] = user

        close_old_connections()
        return await super().__call__(scope, receive, send)