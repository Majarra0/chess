from django.contrib import admin
from django.urls import path, include

from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

from chessgame.views import SignupView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('chessgame/', include('chessgame.urls')),
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),  # login
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/', include('chessgame.urls')),
    path('api/register/', SignupView.as_view(), name='signup'),  # <-- Add this line
]
