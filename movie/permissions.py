from rest_framework.permissions import SAFE_METHODS, BasePermission


class IsAdminOrReadOnly(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.method in SAFE_METHODS
            or (request.user and request.user.is_staff)
        )


class IsAuthorOrAdminOrReadOnly(BasePermission):
    def has_object_permission(self, request, view, obj):
        return bool(
            request.method in SAFE_METHODS
            or (request.user == obj.user or request.user.is_staff)
        )
