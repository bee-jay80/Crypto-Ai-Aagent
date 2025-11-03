from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .services import get_comparison
from ai.services import parse_text, response_text
from asgiref.sync import async_to_sync
from dateutil.parser import parse as parse_date  # safer date parsing
import asyncio


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

        # Safely parse date string into datetime.date object
        try:
            dt = parse_date(ds).date()
        except Exception:
            return Response({"detail": f"invalid date format: {ds}"}, status=400)

        try:
            result = async_to_sync(get_comparison)(asset, dt)
            reply = async_to_sync(response_text)(result)

            return Response({
                "parsed": parsed,
                "comparison": result,
                "response": reply,
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
            return Response({"detail": "date queryparam required YYYY-MM-DD"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            dt = parse_date(date_str).date()
        except Exception:
            return Response({"detail": f"invalid date format: {date_str}"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            result = async_to_sync(get_comparison)(asset, dt)
            return Response(result)
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
