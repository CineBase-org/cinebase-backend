import io

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from PIL import Image, ImageOps
from rest_framework import serializers

from user.models import UserProfile

MAX_AVATAR_SIZE = 5 * 1024 * 1024
ALLOWED_AVATAR_FORMATS = ["JPEG", "PNG", "WEBP"]
AVATAR_WEBP_QUALITY = 85


def convert_to_webp(uploaded_file):
    """Return the image as a WEBP file, so every avatar has the same format.

    Pillow does not copy EXIF data (for example GPS) to the new file.
    """
    image = Image.open(uploaded_file)
    image = ImageOps.exif_transpose(image)  # apply the camera rotation

    has_alpha = "A" in image.getbands() or "transparency" in image.info
    mode = "RGBA" if has_alpha else "RGB"
    if image.mode != mode:
        image = image.convert(mode)

    buffer = io.BytesIO()
    image.save(buffer, format="WEBP", quality=AVATAR_WEBP_QUALITY)
    return ContentFile(buffer.getvalue(), name="avatar.webp")


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

        avatar_changed = "avatar" in validated_data
        old_avatar_name = instance.avatar.name if avatar_changed else None

        user_profile = super().update(instance, validated_data)

        # Same name (S3 overwrites the object): nothing to delete. A different
        # name means a leftover: an old avatar with a random name or a file
        # in local storage, which never overwrites. A removed avatar too.
        if old_avatar_name and old_avatar_name != user_profile.avatar.name:
            user_profile.avatar.storage.delete(old_avatar_name)
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
        return convert_to_webp(value)
