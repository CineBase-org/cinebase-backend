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
