"""
Tokens carry a stamp of the user's password, so changing the password signs
out every other phone. Simple JWT 5.3 has no setting for this.

Tokens issued before this existed have no stamp and stay valid until they
expire, so deploying it doesn't sign everyone out.
"""
import hashlib

from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

STAMP_CLAIM = "pwd"


def password_stamp(user):
    return hashlib.sha256(user.password.encode()).hexdigest()[:16]


class StampedTokenSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token[STAMP_CLAIM] = password_stamp(user)
        return token


class StampedJWTAuthentication(JWTAuthentication):
    def get_user(self, validated_token):
        user = super().get_user(validated_token)
        stamp = validated_token.get(STAMP_CLAIM)
        if stamp is not None and stamp != password_stamp(user):
            raise AuthenticationFailed("Password changed. Please sign in again.", code="password_changed")
        return user
