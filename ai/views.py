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
            request_id = body.get("id") # Get ID early
            
            if not body.get("jsonrpc") or not request_id:
                return Response({
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {"code": -32600, "message": "Invalid Request"}
                }, status=400)

            # --- START MODIFICATION ---
            # Manually parse the body to find the user_text and sanitize
            # the 'parts' list *before* Pydantic validation.
            # This prevents a validation crash on the invalid 'data' part.

            user_text = ""
            method = body.get("method")
            params = body.get("params", {})
            last_message_dict = None
            found_text_part = None

            if method == "message/send":
                last_message_dict = params.get("message")
            elif method == "execute":
                messages_list = params.get("messages")
                if messages_list and isinstance(messages_list, list):
                    last_message_dict = messages_list[-1] # Get last message

            if last_message_dict and isinstance(last_message_dict, dict):
                parts = last_message_dict.get("parts", [])
                if isinstance(parts, list):
                    for part in parts:
                        # Find the *first* text part and break
                        if isinstance(part, dict) and part.get("kind") == "text":
                            user_text = part.get("text", "").strip()
                            found_text_part = part
                            break
            
            # Now, sanitize the 'body' dict by replacing the 'parts' list
            # with *only* the valid text part we found.
            if last_message_dict and found_text_part:
                last_message_dict["parts"] = [found_text_part]
                
                # Update the body itself
                if method == "message/send":
                    body["params"]["message"] = last_message_dict
                elif method == "execute":
                    body["params"]["messages"][-1] = last_message_dict
            
            # --- END MODIFICATION ---


            # Now this line will succeed because the 'body' is sanitized
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

            # We already have 'user_text' from our manual parse above.
            # The original logic block to find it is no longer needed.

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
            # Use the request_id we saved at the top
            current_id = request_id if "request_id" in locals() else (body.get("id") if "body" in locals() else None)
            return Response({
                "jsonrpc": "2.0",
                "id": current_id,
                "error": {"code": -32603, "message": "Internal error", "data": str(e)}
            }, status=500)



# class A2ACryptoAPIView(APIView):
#     """Main A2A endpoint for crypto agent"""
#     def post(self, request):
#         try:
#             body = request.data
#             if not body.get("jsonrpc") or not body.get("id"):
#                 return Response({
#                     "jsonrpc": "2.0",
#                     "id": body.get("id"),
#                     "error": {"code": -32600, "message": "Invalid Request"}
#                 }, status=400)

#             rpc_request = JSONRPCRequest(**body)

#             # Determine messages
#             if rpc_request.method == "message/send":
#                 messages = [rpc_request.params.message]
#             elif rpc_request.method == "execute":
#                 messages = rpc_request.params.messages
#             else:
#                 return Response({
#                     "jsonrpc": "2.0",
#                     "id": rpc_request.id,
#                     "error": {"code": -32601, "message": "Method not found"}
#                 }, status=400)

#             # Get user text from last message
#             user_text = ""
#             if messages:
#                 for part in messages[-1].parts:
#                     if part.kind == "text":
#                         user_text = part.text.strip()
#                         break

#             # Parse text → JSON (asset, symbol, date)
#             parsed = async_to_sync(parse_text)(user_text)
#             if parsed.get("mode") == "chat":
#                 # Chat mode reply
#                 response_message = A2AMessage(
#                     role="agent",
#                     parts=[MessagePart(kind="text", text=parsed.get("message"))]
#                 )
#                 task_result = TaskResult(
#                     id=rpc_request.id,
#                     contextId="chat-context",
#                     status=TaskStatus(state="completed", message=response_message),
#                     artifacts=[],
#                     history=[messages[-1], response_message]
#                 )
#                 response = JSONRPCResponse(id=rpc_request.id, result=task_result)
#                 return Response(response.model_dump())

#             # Fetch historical + current prices
#             dt = parsed.get("date")
#             asset = parsed.get("symbol")
#             result = async_to_sync(get_comparison)(asset, dt)

#             # Generate AI formatted response
#             reply_text = async_to_sync(response_text)(result)

#             # Build A2A message & artifacts
#             response_message = A2AMessage(
#                 role="agent",
#                 parts=[MessagePart(kind="text", text=reply_text)]
#             )

#             artifacts = [
#                 Artifact(name="comparison_data", parts=[MessagePart(kind="data", data=result)])
#             ]

#             task_result = TaskResult(
#                 id=rpc_request.id,
#                 contextId="crypto-context",
#                 status=TaskStatus(state="completed", message=response_message),
#                 artifacts=artifacts,
#                 history=[messages[-1], response_message]
#             )

#             response = JSONRPCResponse(id=rpc_request.id, result=task_result)
#             return Response(response.model_dump())

#         except Exception as e:
#             return Response({
#                 "jsonrpc": "2.0",
#                 "id": body.get("id") if "body" in locals() else None,
#                 "error": {"code": -32603, "message": "Internal error", "data": str(e)}
#             }, status=500)
