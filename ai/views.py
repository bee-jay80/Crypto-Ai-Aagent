from rest_framework.views import APIView
from rest_framework.response import Response
from .services import parse_text, response_text
from prices.services import get_comparison
from .models import JSONRPCRequest, JSONRPCResponse, TaskResult, TaskStatus, A2AMessage, Artifact, MessagePart
from asgiref.sync import async_to_sync

class A2ACryptoAPIView(APIView):
    """Main A2A endpoint for crypto agent"""
    def post(self, request):
        try:
            body = request.data
            if not body.get("jsonrpc") or not body.get("id"):
                return Response({
                    "jsonrpc": "2.0",
                    "id": body.get("id"),
                    "error": {"code": -32600, "message": "Invalid Request"}
                }, status=400)

            rpc_request = JSONRPCRequest(**body)

            # Determine messages
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

            # Get user text from last message
            user_text = ""
            if messages:
                for part in messages[-1].parts:
                    if part.kind == "text":
                        user_text = part.text.strip()
                        break

            # Parse text → JSON (asset, symbol, date)
            parsed = async_to_sync(parse_text)(user_text)
            if parsed.get("mode") == "chat":
                # Chat mode reply
                response_message = A2AMessage(
                    role="agent",
                    parts=[MessagePart(kind="text", text=parsed.get("message"))]
                )
                task_result = TaskResult(
                    id=rpc_request.id,
                    contextId="chat-context",
                    status=TaskStatus(state="completed", message=response_message),
                    artifacts=[],
                    history=[messages[-1], response_message]
                )
                response = JSONRPCResponse(id=rpc_request.id, result=task_result)
                return Response(response.model_dump())

            # Fetch historical + current prices
            dt = parsed.get("date")
            asset = parsed.get("symbol")
            result = async_to_sync(get_comparison)(asset, dt)

            # Generate AI formatted response
            reply_text = async_to_sync(response_text)(result)

            # Build A2A message & artifacts
            response_message = A2AMessage(
                role="agent",
                parts=[MessagePart(kind="text", text=reply_text)]
            )

            artifacts = [
                Artifact(name="comparison_data", parts=[MessagePart(kind="data", data=result)])
            ]

            task_result = TaskResult(
                id=rpc_request.id,
                contextId="crypto-context",
                status=TaskStatus(state="completed", message=response_message),
                artifacts=artifacts,
                history=[messages[-1], response_message]
            )

            response = JSONRPCResponse(id=rpc_request.id, result=task_result)
            return Response(response.model_dump())

        except Exception as e:
            return Response({
                "jsonrpc": "2.0",
                "id": body.get("id") if "body" in locals() else None,
                "error": {"code": -32603, "message": "Internal error", "data": str(e)}
            }, status=500)
