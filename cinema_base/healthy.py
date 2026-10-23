from django.db import connection
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView


@extend_schema(exclude=True)
class Healthy(APIView):
    permission_classes = (AllowAny,)
    authentication_classes = ()

    def get(self, request, format=None):
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                return Response({"status": "OK"})
        except Exception as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
