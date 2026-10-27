from django.contrib.auth import get_user_model
from rest_framework import serializers

from user.models import UserProfile

MAX_AVATAR_SIZE = 5 * 1024 * 1024
ALLOWED_AVATAR_FORMATS = ["JPEG", "PNG", "WEBP"]


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = get_user_model()
        fields = ("id", "email", "password", "is_staff")
        read_only_fields = ("is_staff",)
        extra_kwargs = {"password": {"write_only": True, "min_length": 5}}

    def create(self, validated_data):
        """Create a new user with encrypted password and return it"""
        return get_user_model().objects.create_user(**validated_data)

    def update(self, instance, validated_data):
        """Update a user, set the password correctly and return it"""
        password = validated_data.pop("password", None)
        user = super().update(instance, validated_data)
        if password:
            user.set_password(password)
            user.save()

        return user


class UserProfileSerializer(serializers.ModelSerializer):
    first_name = serializers.CharField(
        source="user.first_name", required=False, allow_blank=True
    )
    last_name = serializers.CharField(
        source="user.last_name", required=False, allow_blank=True
    )

    class Meta:
        model = UserProfile
        fields = (
            "first_name",
            "last_name",
            "bio",
            "location",
            "birth_date",
            "avatar",
        )

    def update(self, instance, validated_data):
        user_data = validated_data.pop("user", None)
        if user_data:
            instance.user.first_name = user_data.get(
                "first_name", instance.user.first_name
            )
            instance.user.last_name = user_data.get(
                "last_name", instance.user.last_name
            )
            instance.user.save()

        user_profile = super().update(instance, validated_data)
        return user_profile

    def validate_avatar(self, value):
        if value is None:
            return value

        if value.size > MAX_AVATAR_SIZE:
            raise serializers.ValidationError("Avatar must be at most 5 MB")

        if value.image.format not in ALLOWED_AVATAR_FORMATS:
            raise serializers.ValidationError(
                "Allowed formats: JPEG, PNG, WEBP"
            )
        return value
