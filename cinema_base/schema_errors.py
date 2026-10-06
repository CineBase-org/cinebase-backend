from drf_spectacular.utils import OpenApiResponse
from rest_framework import serializers


class SchemaErrorDetail(serializers.Serializer):
    detail = serializers.CharField(read_only=True)


class SchemaValidationError(serializers.Serializer):
    field_name = serializers.ListField(
        child=serializers.CharField(), read_only=True
    )


UNAUTHORIZED = {
    401: OpenApiResponse(
        response=SchemaErrorDetail,
        description="Authentication credentials were not provided "
        "or the token is invalid or expired.",
    )
}

BAD_REQUEST = {
    400: OpenApiResponse(
        response=SchemaValidationError,
        description="Validation error. The key is the field name, "
        "the value is a list of error messages.",
    )
}

FORBIDDEN = {
    403: OpenApiResponse(
        response=SchemaErrorDetail,
        description="You do not have permission to perform this action.",
    )
}

NOT_FOUND = {
    404: OpenApiResponse(
        response=SchemaErrorDetail,
        description="The requested object was not found.",
    )
}
