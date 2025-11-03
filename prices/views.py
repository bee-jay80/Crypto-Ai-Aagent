from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .services import get_comparison
from ai.services import parse_text, response_text
from asgiref.sync import async_to_sync
from datetime import datetime
from uuid import uuid4


def build_telex_message(texts, role="agent", task_id=None):
    """
    Builds a Telex A2A-compliant message dictionary.
    texts: list of strings -> each becomes a separate part
    """
    parts = [{"kind": "text", "text": t} for t in texts]
    return {
        "kind": "message",
        "role": role,
        "parts": parts,
        "messageId": str(uuid4()),
        "taskId": task_id or str(uuid4())
    }


class NLPToCompareAPIView(APIView):
    def post(self, request):
        text = request.data.get("text", "")
        if not text:
            return Response({"detail": "text required"}, status=400)

        parsed = async_to_sync(parse_text)(text)
        asset = parsed.get("symbol")
        ds = parsed.get("date")

        if not asset or not ds:
            return Response({"detail": "could not detect crypto/date"}, status=400)

        try:
            dt = datetime.fromisoformat(ds).date()
        except Exception:
            return Response({"detail": "invalid date"}, status=400)

        try:
            # Fetch comparison
            result = async_to_sync(get_comparison)(asset, dt)

            # Generate Telex-compliant agent message
            reply_text = async_to_sync(response_text)(result)
            telex_message = build_telex_message([reply_text], role="agent")

            return Response({
                "parsed": parsed,
                "comparison": result,
                "telex_message": telex_message
            })

        except Exception as e:
            return Response({"response": str(e)}, status=400)


class CompareAPIView(APIView):
    """
    GET /api/v1/crypto/<asset>/compare/?date=YYYY-MM-DD
    """
    def get(self, request, asset):
        date_str = request.query_params.get("date")
        if not date_str:
            return Response(
                {"detail": "date queryparam required YYYY-MM-DD"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            dt = datetime.fromisoformat(date_str).date()
        except Exception:
            return Response(
                {"detail": "invalid date format; use YYYY-MM-DD"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Fetch comparison
            result = async_to_sync(get_comparison)(asset, dt)

            # Build Telex-compliant message
            reply_text = async_to_sync(response_text)(result)
            telex_message = build_telex_message([reply_text], role="agent")

            return Response({
                "comparison": result,
                "telex_message": telex_message
            })

        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
