# openai_agent.py

import os
import openai
import asyncio
from tools.tool_registry import tool_registry
import re
import json
import traceback
import sys
sys.path.append('.')

openai.api_key = os.getenv("OPENAI_API_KEY")


# Lotus System Prompt Only
LOTUS_SYSTEM_PROMPT = (
    "You are Lotus, the official AI assistant for Lotus Electronics Customer Support. "
    "Your flow is as follows: "
    "1. When a user starts a chat, always ask for their phone number to begin authentication. "
    "2. When a user provides their phone number, always call the check_user tool And say Account found Please continue with the authentication. "
    "3. Then use the send_otp tool to send an OTP to their phone and email. Only after the send_otp tool responds successfully, tell the user: 'An OTP has been sent to your phone and email. Please enter the OTP to continue with the authentication.' "
    "4. When the user provides an OTP, always call the verify_otp tool with the phone number and OTP to authenticate the user. If verify_otp is successful, then complete authentication. Do not ask for the phone number again if it is already known. "
    "5. After successful authentication, fetch and show all the user's orders using the get_orders tool. "
    "6. If the user has a problem with a product/order, ask them to select the relevant product/order. "
    "7. Ask the user to describe their issue. "
    "8. Try to solve the user's issue with troubleshooting steps or information. "
    "9. If the issue cannot be solved, say: 'I have raised a ticket for you. Our team will contact you as soon as possible.' "
    "Never recommend or sell new products. Never provide product prices or catalog information. "
    "If the user asks about delivery, use the check_delivery tool. "
    "If the user asks about their cart, use the get_cart tool. "
    "Respond in strict JSON format: "
    "{"
    "  \"status\": \"success\","
    "  \"data\": {"
    "    \"answer\": \"...\","
    "    \"orders\": [ { \"order_id\": ..., \"product_name\": ..., \"status\": ... } ],"
    "    \"cart_products\": [ { \"name\": ..., \"qty\": ..., \"price\": ... } ],"
    "    \"end\": \"...\""
    "  }"
    "}"
    "Omit the orders and cart_products fields if not relevant to the user's query. "
    "If the user's message is a greeting or unclear, respond with a friendly greeting and ask for their phone number to begin support. "
    "Please be Strict with the flow and do not skip any step. "
)



# Comprehensive category and subcategory mapping

def extract_json_from_response(text):
    # Remove Markdown code block formatting if present
    text = text.strip()
    if text.startswith('```json'):
        text = text[7:]
    if text.startswith('```'):
        text = text[3:]
    if text.endswith('```'):
        text = text[:-3]
    text = text.strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    # Try to extract the largest JSON object
    matches = list(re.finditer(r'({.*?})', text, re.DOTALL))
    if matches:
        matches = sorted(matches, key=lambda m: len(m.group(0)), reverse=True)
        for match in matches:
            try:
                return json.loads(match.group(0))
            except Exception:
                continue
    # If still not valid, return None to trigger a retry
    return None

async def chat_with_agent(message: str, session_id: str, memory: dict):
    """
    Orchestrate chat with OpenAI GPT-4o, handle tool-calling, and manage memory.
    """
    # Prepare conversation history for OpenAI
    history = memory.get("history", [])
    # Only include the last 2 conversation turns (user and assistant) from history
    last_two_turns = []
    if history:
        last_two_turns = history[-10:]

    print(last_two_turns)
    messages = (
        ([{"role": "system", "content": LOTUS_SYSTEM_PROMPT}]) +
        last_two_turns +
        [{"role": "user", "content": message}]
    )

    # Prepare function schemas for OpenAI
    function_schemas = [schema for _, schema in tool_registry.values()]

    # Call OpenAI with function-calling enabled
    response = openai.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        functions=function_schemas,
        function_call="auto"
    )
    reply = response.choices[0].message

    # If the LLM wants to call a function/tool
    if reply.function_call:
        func_name = reply.function_call.name
        func_args = reply.function_call.arguments
        tool_func, _ = tool_registry.get(func_name, (None, None))
        if tool_func is None:
            tool_response = {"error": f"Tool '{func_name}' not found."}
        else:
            try:
                parsed_args = json.loads(func_args) if isinstance(func_args, str) else func_args
                # Inject auth_token from memory for get_orders, get_cart, check_delivery if not present
                if func_name in ["get_orders", "get_cart", "check_delivery"]:
                    if "auth_token" not in parsed_args or not parsed_args["auth_token"]:
                        parsed_args["auth_token"] = memory.get("auth_token")
                # Await async tools
                if asyncio.iscoroutinefunction(tool_func):
                    tool_response = await tool_func(**parsed_args)
                else:
                    tool_response = tool_func(**parsed_args)
            except Exception as e:
                tool_response = {"error": str(e)}
        # Add tool call and result to messages
        messages.append({
            "role": "assistant",
            "content": None,
            "function_call": {
                "name": func_name,
                "arguments": func_args
            }
        })
        messages.append({
            "role": "function",
            "name": func_name,
            "content": str(tool_response)
        })
        print("[DEBUG] Tool response for check_user:", tool_response)
        # Call LLM again to generate the final response
        response2 = openai.chat.completions.create(
            model="gpt-4o",
            messages=messages,
        )
        final_reply = response2.choices[0].message.content
        # Extract JSON from the response
        final_json = extract_json_from_response(final_reply)
        if final_json is None:
            # Retry with a stricter prompt
            retry_prompt = (
                "Your previous response was not valid JSON. "
                "Please respond ONLY with a valid JSON object as instructed in the system prompt."
            )
            messages.append({"role": "user", "content": retry_prompt})
            response_retry = openai.chat.completions.create(
                model="gpt-4o",
                messages=messages,
            )
            final_reply = response_retry.choices[0].message.content
            print(final_reply)
            final_json = extract_json_from_response(final_reply)
            print(final_json)

            if final_json is None:
                # Still failed, return error
                return {
                    "status": "error",
                    "data": {
                        "answer": "Sorry, I could not process the response properly.",
                        "end": ""
                    }
                }
        # Update memory
        memory["history"] = messages + [{"role": "assistant", "content": final_reply}]
        if func_name in ["verify_otp", "sign_in"] and tool_response.get("error") == "0":
            auth_token = (
                tool_response.get("auth_token") or
                (tool_response.get("data", {}).get("auth_token") if isinstance(tool_response.get("data"), dict) else None)
            )
            if auth_token:
                memory["auth_token"] = auth_token
                memory["phone"] = parsed_args.get("phone")
                memory["is_authenticated"] = True
                if "data" in tool_response:
                    memory["user_data"] = tool_response["data"]
        if func_name == "check_user" and tool_response.get("is_register"):
            # Automatically call send_otp
            send_otp_func, _ = tool_registry.get("send_otp", (None, None))
            if send_otp_func:
                otp_response = send_otp_func(phone=parsed_args["phone"])
                # Add send_otp tool call and result to messages
                messages.append({
                    "role": "assistant",
                    "content": None,
                    "function_call": {
                        "name": "send_otp",
                        "arguments": json.dumps({"phone": parsed_args["phone"]})
                    }
                })
                messages.append({
                    "role": "function",
                    "name": "send_otp",
                    "content": str(otp_response)
                })
                # Now let the LLM generate the next message
        return final_json
    else:
        # Normal chat, no tool call - extract JSON from response
        final_json = extract_json_from_response(reply.content)
        # Update memory
        memory["history"] = messages + [{"role": "assistant", "content": reply.content}]
        if final_json is not None:
            return final_json
        else:
            # Log the invalid response for debugging
            print("[DEBUG] Invalid JSON from LLM:", reply.content)
            # Return a default error JSON response
            return {
                "status": "error",
                "data": {
                    "answer": "Sorry, I did not understand that.",
                    "end": ""
                }
            }


