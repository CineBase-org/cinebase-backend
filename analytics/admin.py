from django.contrib import admin

from analytics.models import Event, Session, Visitor


class ReadOnlyAdmin(admin.ModelAdmin):
    """Analytics data comes from the frontend: it is only viewed, not edited"""

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(Visitor)
class VisitorAdmin(ReadOnlyAdmin):
    list_display = ("id", "user", "first_seen_at", "is_synthetic")
    list_filter = ("is_synthetic",)
    date_hierarchy = "first_seen_at"
    raw_id_fields = ("user",)


@admin.register(Session)
class SessionAdmin(ReadOnlyAdmin):
    list_display = (
        "id",
        "visitor",
        "started_at",
        "ended_at",
        "device_type",
        "is_synthetic",
    )
    list_filter = ("device_type", "is_synthetic")
    date_hierarchy = "started_at"
    raw_id_fields = ("visitor",)


@admin.register(Event)
class EventAdmin(ReadOnlyAdmin):
    list_display = (
        "event_name",
        "event_timestamp",
        "page_path",
        "movie",
        "is_synthetic",
    )
    list_filter = ("event_name", "is_synthetic")
    date_hierarchy = "event_timestamp"
    list_select_related = ("movie",)
    raw_id_fields = ("session", "movie")
    show_full_result_count = False
