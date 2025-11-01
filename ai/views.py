# ai/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .services import parse_text, response_text
from asgiref.sync import async_to_sync

class NLPParseAPIView(APIView):
    """
    POST { "text": "check BTC on 2025-01-01" }
    returns:
      { asset: 'bitcoin', symbol: 'BTC', date: '2025-01-01' }
    """
    def post(self, request):
        text = request.data.get("text")
        if not text:
            return Response({"detail": "text is required"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            result = async_to_sync(parse_text)(text)
            # result = parse_text(text)
            return Response(result)
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class NLPResponseAPIView(APIView):
    """
    POST { "text": "check BTC on 2025-01-01" }
    returns:
      { asset: 'bitcoin', symbol: 'BTC', date: '2025-01-01' }
    """
    def post(self, request):
        data = request.data.get("data")
        if not data:
            return Response({"detail": "text is required"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            result = async_to_sync(response_text)(data)
            return Response({"response":result}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
