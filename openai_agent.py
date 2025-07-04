# openai_agent.py

import os
import re
import json
import asyncio
import openai

from tools.tool_registry import tool_registry  # your { name: (func, schema) }

openai.api_key = os.getenv("OPENAI_API_KEY")

def extract_json_from_response(text: str):
    print(f"RESPONE FRO THE  EXTRACTION {text}")
    text = text.strip()
    if text.startswith("```json"): text = text[7:]
    if text.startswith("```"):     text = text[3:]
    if text.endswith("```"):       text = text[:-3]
    text = text.strip()
    try:
        return json.loads(text)
    except:
        pass
    matches = list(re.finditer(r"(\{.*\})", text, re.DOTALL))
    matches.sort(key=lambda m: len(m.group(1)), reverse=True)
    for m in matches:
        try:
            return json.loads(m.group(1))
        except:
            continue
    return None

# LOTUS_SYSTEM_PROMPT = (
#     "You are Lotus, the official AI assistant for Lotus Electronics Customer Support.\n"
#     "You are a helpful assistant that can help the user with their queries.\n"
#     "Follow this flow strictly:\n"
#     "1. Address the user queary and Ask for phone number.\n"
#     "2. On phone, call check_user.\n"
#     "3. If registered, call send_otp automatically and tell user OTP has been sent.\n"
#     "4. On OTP input, call verify_otp.\n"
#     "5. After success, call get_orders, etc.\n"
#     "6. If the user has a problem with a product/order, ask them to select the relevant product/order.\n"
#     "7. Ask the user to describe their issue.\n"
#     "8. Try to solve the user's issue with troubleshooting steps or information.\n"
#     "9. If the issue cannot be solved, say: 'I have raised a ticket for you. Our team will contact you as soon as possible.'\n"
#     "Never recommend or sell new products. Never provide product prices or catalog information.\n"
#     "If the user asks about delivery, use the check_delivery tool.\n"
#     "If the user asks about their cart, use the get_cart tool.\n"
#     "Respond ONLY in valid JSON with top‑level `status` and `data.answer`.\n"
#     "If you have to show the order details, the Response ONLY in valid JSON like this:\n"
#     "{\n"
#     "  \"status\": \"success\",\n"
#     "  \"data\": {\n"
#     "    \"answer\": \"...\",\n"
#     "    \"orders\": [ { \"order_id\": ..., \"product_name\": ..., \"product_image\": ..., \"status\": ... } ],\n"
#     "  }\n"
#     "}"
# )




LOTUS_SYSTEM_PROMPT = (
    "You are Lotus, the official AI assistant for Lotus Electronics Customer Support.\n"
    "You are a helpful assistant that can help the user with their queries.\n"
    "Follow this flow strictly:\n"
    "1. Address the user queary and Ask for phone number.\n"
    "2. On phone, call check_user.\n"
    "3. If registered, Ask for Password\n"
    "4. On Password input, call sign_in tool.\n"
    "5. After success, call get_orders, etc.\n"
    "6. If the user has a problem with a product/order, ask them to select the relevant product/order.\n"
    "7. Ask the user to describe their issue.\n"
    "8. Try to solve the user's issue with troubleshooting steps or information.\n"
    "9. If the issue cannot be solved, say: 'I have raised a ticket for you. Our team will contact you as soon as possible.'\n"
    "Never recommend or sell new products. Never provide product prices or catalog information.\n"
    "If the user asks about delivery, use the check_delivery tool.\n"
    "If the user asks about their cart, use the get_cart tool.\n"
    "Respond ONLY in valid JSON with top‑level `status` and `data.answer`.\n"
    "If you have to show the order details, the Response ONLY in valid JSON like this:\n"
    "{\n"  
    "  \"status\": \"success\",\n"  
    "  \"data\": {\n"  
    "    \"answer\": \"...\",\n"  
    "    \"orders\": [\n"  
    "      {\n"  
    "        \"itemname\": \"...\",\n"  
    "        \"order_id\": \"...\",\n"  
    "        \"order_date\": \"...\",\n"  
    "        \"product_image\": \"...\",\n"  
    "        \"invoice_no\": \"...\",\n"  
    "        \"invoice_url\": \"...\",\n"  
    "        \"status\": \"...\"\n"  
    "      }\n"  
    "    ]\n"  
    "  }\n"  
    "}"

)


async def chat_with_agent(message: str, session_id: str, memory: dict):
    # 1. build the message list
    history = memory.get("history", [])
    messages = [{"role": "system", "content": LOTUS_SYSTEM_PROMPT}] + history + [
        {"role": "user", "content": message}
    ]

    # 2. let the LLM plan (maybe call check_user)
    function_schemas = [schema for _, schema in tool_registry.values()]
    plan = openai.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        functions=function_schemas,
        function_call="auto"
    ).choices[0].message

    # 3. if it wants to call a tool...
    if plan.function_call:
        name = plan.function_call.name
        args = json.loads(plan.function_call.arguments or "{}")
        fn, _ = tool_registry.get(name, (None, None))

        # run the tool (await if needed)
        if fn:
            tool_resp = await fn(**args) if asyncio.iscoroutinefunction(fn) else fn(**args)
        else:
            tool_resp = {"error": f"Tool {name} not found"}

        # append the assistant's tool invocation
        messages.append({
            "role": "assistant",
            "function_call": {"name": name, "arguments": json.dumps(args)}
        })
        messages.append({
            "role": "function",
            "name": name,
            "content": json.dumps(tool_resp)
        })

        # **Special injection**: after check_user success, automatically call send_otp
        if name == "check_user" and tool_resp.get("is_register"):
            # assume send_otp signature: send_otp(phone=...)
            send_fn, _ = tool_registry.get("send_otp", (None, None))
            send_args = {"phone": args.get("phone")}
            if send_fn:
                send_resp = await send_fn(**send_args) if asyncio.iscoroutinefunction(send_fn) else send_fn(**send_args)
            else:
                send_resp = {"error": "send_otp tool not found"}

            messages.append({
                "role": "assistant",
                "function_call": {"name": "send_otp", "arguments": json.dumps(send_args)}
            })
            messages.append({
                "role": "function",
                "name": "send_otp",
                "content": json.dumps(send_resp)
            })

        # 4. now ask LLM to finish the answer with all tool calls in context
        followup = openai.chat.completions.create(
            model="gpt-4o",
            messages=messages
        ).choices[0].message.content
    else:
        # no tool call, just LLM reply
        followup = plan.content

    # 5. parse JSON out of the final assistant message
    parsed = extract_json_from_response(followup)
    if not parsed:
        return {
            "status": "error",
            "data": {
                "answer": "Sorry, I couldn't parse the response.",
                "end": ""
            }
        }

    # 6. update memory and return
    memory["history"] = messages + [{"role": "assistant", "content": followup}]
    return parsed
