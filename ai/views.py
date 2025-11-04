from rest_framework.views import APIView
from rest_framework.response import Response
from asgiref.sync import async_to_sync
from datetime import datetime
import uuid

from .services import parse_text, response_text
from prices.services import get_comparison
from .models import (
    JSONRPCRequest, JSONRPCResponse, TaskResult, TaskStatus,
    A2AMessage, Artifact, MessagePart
)

class A2ACryptoAPIView(APIView):
    """A2A endpoint for Telex crypto agent"""

    def post(self, request):
        body = request.data
        request_id = body.get("id")

        # ✅ Basic JSON-RPC validation
        if not body.get("jsonrpc") or not request_id:
            return Response({
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32600, "message": "Invalid Request"}
            }, status=400)

        try:
            # Extract last message text
            method = body.get("method")
            params = body.get("params", {})

            last_message_dict = None
            if method == "message/send":
                last_message_dict = params.get("message")
            elif method == "execute":
                msgs = params.get("messages")
                last_message_dict = msgs[-1] if msgs else None

            user_text = ""
            if last_message_dict:
                parts = last_message_dict.get("parts", [])
                for part in parts:
                    if part.get("kind") == "text":
                        user_text = part.get("text", "").strip()
                        last_message_dict["parts"] = [part]
                        break

            # ✅ Validate using schema AFTER sanitizing
            rpc_request = JSONRPCRequest(**body)

            if rpc_request.method == "message/send":
                messages = [rpc_request.params.message]
            elif rpc_request.method == "execute":
                messages = rpc_request.params.messages
            else:
                return Response({
                    "jsonrpc": "2.0",
                    "id": rpc_request.id,
                    "error": {"code": -32601, "message": "Method not found"}
                }, status=400)

            # Parse crypto intent
            parsed = async_to_sync(parse_text)(user_text)


            # ✅ Chat mode → normal friendly assistant reply
            if parsed.get("mode") == "chat":
                reply_text = parsed.get("message", "")
                msg_id = str(uuid.uuid4())
                task_id = rpc_request.id or str(uuid.uuid4())
                now = datetime.utcnow().isoformat() + "Z"
                msg = {
                    "role": "agent",
                    "messageId": msg_id,
                    "parts": [{"kind": "text", "text": reply_text}],
                    "kind": "message",
                    "taskId": task_id
                }
                task = {
                    "id": task_id,
                    "contextId": "chat",
                    "status": {
                        "state": "completed",
                        "timestamp": now,
                        "message": msg
                    },
                    "artifacts": [],
                    "history": [messages[-1], msg],
                    "kind": "task"
                }
                return Response({"jsonrpc": "2.0", "id": rpc_request.id, "result": task})

            # ✅ Crypto data mode
            dt = parsed.get("date")
            symbol = parsed.get("symbol")
            comp = async_to_sync(get_comparison)(symbol, dt)
            analysis_text = async_to_sync(response_text)(comp)
            msg_id = str(uuid.uuid4())
            task_id = rpc_request.id or str(uuid.uuid4())
            now = datetime.utcnow().isoformat() + "Z"
            msg = {
                "role": "agent",
                "messageId": msg_id,
                "parts": [{"kind": "text", "text": analysis_text}],
                "kind": "message",
                "taskId": task_id
            }
            artifact_id_1 = str(uuid.uuid4())
            artifact_id_2 = str(uuid.uuid4())
            artifacts = [
                {
                    "artifactId": artifact_id_1,
                    "name": "comparison_data",
                    "parts": [
                        {"kind": "text", "text": str(comp)}
                    ]
                },
                {
                    "artifactId": artifact_id_2,
                    "name": "board",
                    "parts": [
                        {"kind": "file", "file_url": f"http://localhost:9000/chess-boards/crypto-{symbol.lower()}/{task_id}.png"}
                    ]
                }
            ]
            task = {
                "id": task_id,
                "contextId": f"crypto-{symbol.lower()}",
                "status": {
                    "state": "completed",
                    "timestamp": now,
                    "message": msg
                },
                "artifacts": artifacts,
                "history": [messages[-1], msg],
                "kind": "task"
            }
            return Response({"jsonrpc": "2.0", "id": rpc_request.id, "result": task})

        except Exception as e:
            return Response({
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32603, "message": "Internal error", "data": str(e)}
            }, status=500)