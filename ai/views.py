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
                # Convert model object to dict if needed
                if hasattr(last_message_dict, "model_dump"):
                    last_message_dict = last_message_dict.model_dump()
                parts = last_message_dict.get("parts", [])
                for part in parts:
                    if part.get("kind") == "text":
                        user_text = part.get("text", "").strip()
                        last_message_dict["parts"] = [part]
                        break

            # ✅ Validate using schema AFTER sanitizing
            rpc_request = JSONRPCRequest(**body)

            if rpc_request.method == "message/send":
                # Convert model object to dict if needed
                msg_obj = rpc_request.params.message
                if hasattr(msg_obj, "model_dump"):
                    msg_obj = msg_obj.model_dump()
                messages = [msg_obj]
            elif rpc_request.method == "execute":
                # Convert all model objects to dicts if needed
                msgs = rpc_request.params.messages
                messages = [m.model_dump() if hasattr(m, "model_dump") else m for m in msgs]
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
                # Build A2AMessage model for agent reply
                msg = A2AMessage(
                    role="agent",
                    messageId=msg_id,
                    parts=[MessagePart(kind="text", text=reply_text)],
                    taskId=task_id,
                )
                # Ensure user message has messageId and convert to model
                user_msg_raw = messages[-1]
                if isinstance(user_msg_raw, dict):
                    if "messageId" not in user_msg_raw:
                        user_msg_raw = dict(user_msg_raw)
                        user_msg_raw["messageId"] = str(uuid.uuid4())
                    user_msg = A2AMessage(**user_msg_raw)
                else:
                    user_msg = A2AMessage(
                        role="user",
                        messageId=str(uuid.uuid4()),
                        parts=[MessagePart(**p) for p in (getattr(user_msg_raw, "parts", []) or [])],
                        taskId=task_id,
                    )

                status = TaskStatus(state="completed", timestamp=now, message=msg)
                task = TaskResult(
                    id=task_id,
                    contextId="chat",
                    status=status,
                    artifacts=[],
                    history=[user_msg, msg],
                )
                resp = JSONRPCResponse(id=rpc_request.id, result=task)
                return Response(resp.model_dump())

            # ✅ Crypto data mode
            dt = parsed.get("date")
            symbol = parsed.get("symbol")
            comp = async_to_sync(get_comparison)(symbol, dt)
            analysis_text = async_to_sync(response_text)(comp)
            msg_id = str(uuid.uuid4())
            task_id = rpc_request.id or str(uuid.uuid4())
            now = datetime.utcnow().isoformat() + "Z"
            agent_msg = A2AMessage(
                role="agent",
                messageId=msg_id,
                parts=[MessagePart(kind="text", text=analysis_text)],
                taskId=task_id,
            )

            artifact_1 = Artifact(artifactId=str(uuid.uuid4()), name="comparison_data", parts=[MessagePart(kind="text", text=str(comp))])
            artifact_2 = Artifact(artifactId=str(uuid.uuid4()), name="board", parts=[MessagePart(kind="file", file_url=f"http://localhost:9000/chess-boards/crypto-{symbol.lower()}/{task_id}.png")])

            # Ensure user message has messageId and convert to model
            user_msg_raw = messages[-1]
            if isinstance(user_msg_raw, dict):
                if "messageId" not in user_msg_raw:
                    user_msg_raw = dict(user_msg_raw)
                    user_msg_raw["messageId"] = str(uuid.uuid4())
                user_msg = A2AMessage(**user_msg_raw)
            else:
                user_msg = A2AMessage(
                    role="user",
                    messageId=str(uuid.uuid4()),
                    parts=[MessagePart(**p) for p in (getattr(user_msg_raw, "parts", []) or [])],
                    taskId=task_id,
                )

            status = TaskStatus(state="completed", timestamp=now, message=agent_msg)
            task = TaskResult(
                id=task_id,
                contextId=f"crypto-{symbol.lower()}",
                status=status,
                artifacts=[artifact_1, artifact_2],
                history=[user_msg, agent_msg],
            )
            resp = JSONRPCResponse(id=rpc_request.id, result=task)
            return Response(resp.model_dump())

        except Exception as e:
            return Response({
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32603, "message": "Internal error", "data": str(e)}
            }, status=500)

