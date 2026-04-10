"""
JWT auth views. TokenObtainPairView and TokenRefreshView are provided by simplejwt
and wired directly in urls.py. This file adds custom claim injection.

account_id is injected into the JWT payload so frontend doesn't need a separate
/me endpoint just to get the account context.
"""
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView


class SafeNetTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        # Inject account_id into JWT payload for convenience
        try:
            token["account_id"] = user.account.id
        except AttributeError:
            token["account_id"] = None
        return token


class SafeNetTokenObtainPairView(TokenObtainPairView):
    serializer_class = SafeNetTokenObtainPairSerializer
