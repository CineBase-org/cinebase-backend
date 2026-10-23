from django.urls import path

from user.views import (
    CreateUserView,
    UserProfileView,
    LoginView,
    RefreshView,
    VerifyView,
)

urlpatterns = [
    path("register/", CreateUserView.as_view(), name="create"),
    path("token/", LoginView.as_view(), name="token_obtain_pair"),
    path("token/refresh/", RefreshView.as_view(), name="token_refresh"),
    path("token/verify/", VerifyView.as_view(), name="token_verify"),
    path("me/", UserProfileView.as_view(), name="user_profile"),
]

app_name = "user"
