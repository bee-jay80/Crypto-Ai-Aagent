from rest_framework.views import APIView
from rest_framework.response import Response
from datetime import datetime
from uuid import uuid4
from .services import get_comparison
from ai.services import parse_text, response_text
from asgiref.sync import async_to_sync
from dateutil.parser import parse as parse_date  # safer date parsing
import asyncio

def build_task_result(message_text, task_id=None, context_id=None):
    """Wrap message in TaskResult structure for Telex"""
    task_id = task_id or str(uuid4())
    context_id = context_id or str(uuid4())
    timestamp = datetime.utcnow().isoformat()

    return {
        "id": task_id,
        "contextId": context_id,
        "status": {
            "state": "completed",
            "timestamp": timestamp,
            "message": {
                "messageId": str(uuid4()),
                "role": "agent",
                "parts": [{"kind": "text", "text": message_text}],
                "kind": "message",
                "taskId": task_id
            }
        },
        "artifacts": [],
        "history": [],
        "kind": "task"
    }

class NLPToCompareAPIView(APIView):
    def post(self, request):
        text = request.data.get("text", "")
        if not text:
            return Response({
                "jsonrpc": "2.0",
                "id": str(uuid4()),
                "result": build_task_result("text required")
            }, status=400)

        parsed = async_to_sync(parse_text)(text)
        asset = parsed.get("symbol")
        ds = parsed.get("date")

        if not asset or not ds:
            return Response({
                "jsonrpc": "2.0",
                "id": str(uuid4()),
                "result": build_task_result("Could not detect crypto/date")
            }, status=400)

        try:
            dt = datetime.fromisoformat(ds).date()
        except Exception:
            return Response({
                "jsonrpc": "2.0",
                "id": str(uuid4()),
                "result": build_task_result("Invalid date format")
            }, status=400)

        try:
            result = async_to_sync(get_comparison)(asset, dt)
            reply = async_to_sync(response_text)(result)
            task_result = build_task_result(reply)

            return Response({
                "jsonrpc": "2.0",
                "id": str(uuid4()),
                "result": task_result
            })

        except Exception as e:
            return Response({
                "jsonrpc": "2.0",
                "id": str(uuid4()),
                "error": {
                    "code": -32603,
                    "message": "Internal error",
                    "data": {"details": str(e)}
                }
            }, status=500)



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
