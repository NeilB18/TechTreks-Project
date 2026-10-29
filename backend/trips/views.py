"""HTTP API for the agent (tool calls) and the trip page (read-only trip data).

All endpoints require "Authorization: Bearer <AGENT_API_TOKEN>". Budgets are
shared with everyone on the trip, so the trip data includes them.
"""

import hmac

from django.conf import settings
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView

from agent.backend.protocol import BACKEND_TOOLS, ToolError, dispatch
from trips.services import DjangoBackend


class HasAgentToken(BasePermission):
    def has_permission(self, request, view):
        token = settings.AGENT_API_TOKEN
        header = request.headers.get("Authorization", "")
        return bool(token) and hmac.compare_digest(header, f"Bearer {token}")


class ToolView(APIView):
    permission_classes = [HasAgentToken]

    def post(self, request, tool_name: str):
        if tool_name not in BACKEND_TOOLS:
            return Response({"error": f"Unknown tool {tool_name!r}"}, status=404)
        if not isinstance(request.data, dict):
            return Response({"error": "Body must be a JSON object of tool arguments"}, status=400)
        try:
            return Response(dispatch(DjangoBackend(), tool_name, dict(request.data)))
        except ToolError as e:
            return Response({"error": str(e)}, status=400)


class TripSummaryView(APIView):
    permission_classes = [HasAgentToken]

    def get(self, request, trip_id: str):
        try:
            return Response(DjangoBackend().summary(trip_id))
        except ToolError as e:
            return Response({"error": str(e)}, status=404)


class TripDetailView(APIView):
    permission_classes = [HasAgentToken]

    def get(self, request, trip_id: str):
        try:
            return Response(DjangoBackend().get_trip(trip_id=trip_id))
        except ToolError as e:
            return Response({"error": str(e)}, status=404)


class TripBalancesView(APIView):
    permission_classes = [HasAgentToken]

    def get(self, request, trip_id: str):
        try:
            return Response(DjangoBackend().get_balances(trip_id=trip_id))
        except ToolError as e:
            return Response({"error": str(e)}, status=404)
