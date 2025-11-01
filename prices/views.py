# prices/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .services import get_comparison
from ai.services import parse_text, response_text
from asgiref.sync import async_to_sync
from datetime import datetime

class CompareAPIView(APIView):
    """
    GET /api/v1/crypto/<asset>/compare/?date=YYYY-MM-DD
    """
    def get(self, request, asset):
        date_str = request.query_params.get("date")
        if not date_str:
            return Response({"detail": "date queryparam required YYYY-MM-DD"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            dt = datetime.fromisoformat(date_str).date()
        except Exception:
            return Response({"detail": "invalid date format; use YYYY-MM-DD"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            result = async_to_sync(get_comparison)(asset, dt)
            return Response(result)
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

class NLPToCompareAPIView(APIView):
    """
    POST { "text": "tell me Bitcoin on 2024-02-01" }
    Flow: parse text -> compute comparison -> return combined
    """
    def post(self, request):
        text = request.data.get("text", "")
        if not text:
            return Response({"detail": "text required"}, status=status.HTTP_400_BAD_REQUEST)
        parsed = async_to_sync(parse_text)(text)
        asset = parsed.get("asset")
        ds = parsed.get("date")
        if not asset:
            return Response({"detail": "asset could not be parsed"}, status=status.HTTP_400_BAD_REQUEST)
        if not ds:
            return Response({"detail": "date could not be parsed; specify date or e.g., 'on 2025-01-01' "}, status=status.HTTP_400_BAD_REQUEST)
        try:
            dt = datetime.fromisoformat(ds).date()
        except Exception:
            return Response({"detail": "failed to parse date into YYYY-MM-DD"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            result = async_to_sync(get_comparison)(asset, dt)
            response = async_to_sync(response_text)(result)
            combined = {
                "parsed": parsed,
                "comparison": result,
                "response": response
            }
            return Response(combined)
        except Exception as e:
            return Response({"detail": str(e),"coin data": parsed}, status=status.HTTP_400_BAD_REQUEST)
