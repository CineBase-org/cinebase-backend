from rest_framework_simplejwt.serializers import (
    TokenObtainPairSerializer,
    TokenRefreshSerializer,
    TokenVerifySerializer,
)
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)

from drf_spectacular.utils import extend_schema_view, extend_schema
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication

from cinema_base.schema_errors import BAD_REQUEST, UNAUTHORIZED
from user.serializers import UserSerializer, UserProfileSerializer


@extend_schema_view(
    post=extend_schema(
        summary="Register a new user",
        description="Create a new account with an email and a password. "
        "Does not return tokens: "
        "after registering, log in via POST /api/user/token/.",
        responses={201: UserSerializer, **BAD_REQUEST},
    )
)
class CreateUserView(generics.CreateAPIView):
    serializer_class = UserSerializer


@extend_schema_view(
    get=extend_schema(
        summary="Get my profile",
        description="Return the current user's profile "
        "(first name, last name, bio, location, birth date).",
        responses={200: UserProfileSerializer, **UNAUTHORIZED},
    ),
    put=extend_schema(
        summary="Replace my profile",
        description="Update the current user's profile. "
        "All fields are optional.",
        responses={200: UserProfileSerializer, **UNAUTHORIZED, **BAD_REQUEST},
    ),
    patch=extend_schema(
        summary="Partially update my profile",
        description="Update only the provided profile fields.",
        responses={200: UserProfileSerializer, **UNAUTHORIZED, **BAD_REQUEST},
    ),
)
class UserProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = UserProfileSerializer
    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated,)

    def get_object(self):
        return self.request.user.profile


@extend_schema_view(
    post=extend_schema(
        summary="Log in (get token)",
        description="Log in with email and password. "
        "Returns an access token (valid for 60 minutes) and a refresh token "
        "(valid for 7 days). Send the access token in the header: "
        "Authorization: Bearer <access>.",
        responses={
            200: TokenObtainPairSerializer,
            **BAD_REQUEST,
            **UNAUTHORIZED,
        },
    )
)
class LoginView(TokenObtainPairView):
    pass


@extend_schema_view(
    post=extend_schema(
        summary="Refresh access token",
        description="Send a refresh token to get a new access token. "
        "Returns 401 if the refresh token is invalid or expired "
        "(it is valid for 7 days). In that case the user must log in again.",
        responses={
            200: TokenRefreshSerializer,
            **BAD_REQUEST,
            **UNAUTHORIZED,
        },
    )
)
class RefreshView(TokenRefreshView):
    pass


@extend_schema_view(
    post=extend_schema(
        summary="Verify a token",
        description="Check that a token is valid and not expired. "
        "Returns 200 with an empty object if it is valid, "
        "401 if it is invalid or expired.",
        responses={
            200: TokenVerifySerializer,
            **BAD_REQUEST,
            **UNAUTHORIZED,
        },
    )
)
class VerifyView(TokenVerifyView):
    pass
