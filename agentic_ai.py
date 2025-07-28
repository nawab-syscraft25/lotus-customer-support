# openai_agent.py

import os
import re
import json
import asyncio
import openai
import sqlite3
import time
from datetime import datetime
from typing import Dict, List, Optional, Any

from tools.tool_registry import tool_registry  # your { name: (func, schema) }
from datetime import datetime
from zoneinfo import ZoneInfo

DB_FILE = 'tickets.db'


def get_india_time():
    return datetime.now(ZoneInfo("Asia/Kolkata")).isoformat()


openai.api_key = os.getenv("OPENAI_API_KEY")

DB_PATH = "chat_history.db"
print(f"[DEBUG] Using DB at: {os.path.abspath(DB_PATH)}")

def extract_json_from_response(text: str):
    """Enhanced JSON extraction with better error handling"""
    if not text:
        return None
        
    print(f"[DEBUG] Extracting JSON from: {text[:200]}...")
    
    # Clean the text
    text = text.strip()
    if text.startswith("```json"): text = text[7:]
    if text.startswith("```"):     text = text[3:]
    if text.endswith("```"):       text = text[:-3]
    text = text.strip()
    
    # Remove trailing commas before } or ]
    text = re.sub(r',(\s*[}\]])', r'\1', text)
    
    # Try direct parsing first
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        print(f"[DEBUG] Direct JSON parse failed: {e}")
    
    # Try to find JSON objects in the text
    matches = list(re.finditer(r"(\{.*\})", text, re.DOTALL))
    matches.sort(key=lambda m: len(m.group(1)), reverse=True)
    
    for m in matches:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            continue
    
    print("[ERROR] Could not extract valid JSON from response")
    return None

def get_db():
    """Get database connection with row factory"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def initialize_database():
    """Initialize database with required tables"""
    conn = get_db()
    cursor = conn.cursor()
    
    # Create session table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS session (
            session_id TEXT PRIMARY KEY,
            is_logged_in BOOLEAN DEFAULT 0,
            user_phone TEXT,
            user_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create enhanced history table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            tool_name TEXT,
            tool_args TEXT,
            tool_response TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            message_index INTEGER,
            FOREIGN KEY (session_id) REFERENCES session(session_id)
        )
    """)
    
    # Create tickets table for issue tracking
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tickets (
            ticket_id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            user_phone TEXT,
            issue_description TEXT NOT NULL,
            product_info TEXT,
            troubleshooting_steps TEXT,
            status TEXT DEFAULT 'open',
            priority TEXT DEFAULT 'medium',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.commit()
    conn.close()

def is_user_logged_in(session_id: str) -> bool:
    """Check if user is logged in for the session"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT is_logged_in FROM session WHERE session_id = ?", (session_id,))
    row = cursor.fetchone()
    conn.close()
    return bool(row and row["is_logged_in"])

def ensure_session_exists(session_id: str):
    """Ensure session exists in database"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR IGNORE INTO session (session_id, is_logged_in, created_at, updated_at)
        VALUES (?, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
    """, (session_id,))
    conn.commit()
    conn.close()

def save_chat_to_db(session_id: str, role: str, content: str, tool_name: str = None, 
                   tool_args: str = None, tool_response: str = None, message_index: int = 0):
    """Enhanced chat saving with tool information"""
    ensure_session_exists(session_id)
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO history (session_id, role, content, tool_name, tool_args, tool_response, message_index)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (session_id, role, content, tool_name, tool_args, tool_response, message_index))
    conn.commit()
    conn.close()

def get_chat_history(session_id: str, limit: int = 50) -> List[Dict]:
    """Retrieve chat history for a session"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT role, content, tool_name, tool_args, tool_response, timestamp, message_index
        FROM history 
        WHERE session_id = ? 
        ORDER BY timestamp DESC, message_index DESC
        LIMIT ?
    """, (session_id, limit))
    
    rows = cursor.fetchall()
    conn.close()
    
    history = []
    for row in rows:
        msg = {"role": row["role"], "content": row["content"]}
        if row["tool_name"]:
            msg["function_call"] = {
                "name": row["tool_name"],
                "arguments": row["tool_args"]
            }
        history.append(msg)
    
    return list(reversed(history))  # Return in chronological order

def save_ticket(session_id: str, ticket_id: str, user_phone: str, issue_description: str, 
                product_info: str = None, troubleshooting_steps: str = None):
    """Save ticket information to database"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO tickets (ticket_id, session_id, user_phone, issue_description, 
                           product_info, troubleshooting_steps)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (ticket_id, session_id, user_phone, issue_description, product_info, troubleshooting_steps))
    conn.commit()
    conn.close()

def analyze_user_frustration(messages: List[Dict]) -> Dict[str, Any]:
    """Analyze user messages for frustration indicators"""
    frustration_keywords = [
        "frustrated", "angry", "disappointed", "terrible", "awful", "hate",
        "stupid", "useless", "not working", "broken", "fed up", "annoyed"
    ]
    
    repetitive_issues = []
    frustration_score = 0
    
    user_messages = [msg for msg in messages if msg.get("role") == "user"]
    
    for msg in user_messages:
        content = msg.get("content", "").lower()
        
        # Check for frustration keywords
        for keyword in frustration_keywords:
            if keyword in content:
                frustration_score += 1
        
        # Check for repetitive issues
        if any(phrase in content for phrase in ["again", "still", "same issue", "not fixed"]):
            repetitive_issues.append(msg)
    
    return {
        "frustration_score": frustration_score,
        "is_frustrated": frustration_score > 2,
        "repetitive_issues": len(repetitive_issues) > 0,
        "user_message_count": len(user_messages)
    }

def get_context_from_history(session_id: str) -> Dict[str, Any]:
    """Get relevant context from chat history"""
    history = get_chat_history(session_id)
    
    context = {
        "previous_issues": [],
        "user_products": [],
        "troubleshooting_attempted": [],
        "user_phone": None,
        "user_logged_in": is_user_logged_in(session_id)
    }
    
    for msg in history:
        content = msg.get("content", "")
        
        # Extract user phone if mentioned
        if msg.get("role") == "user" and not context["user_phone"]:
            phone_match = re.search(r'\b(\d{10})\b', content)
            if phone_match:
                context["user_phone"] = phone_match.group(1)
        
        # Extract product mentions
        if "product" in content.lower() or "order" in content.lower():
            context["user_products"].append(content)
        
        # Extract troubleshooting steps
        if msg.get("tool_name") == "troubleshoot" or "troubleshoot" in content.lower():
            context["troubleshooting_attempted"].append(content)
    
    return context

# ENHANCED_LOTUS_SYSTEM_PROMPT = """
# You are Lotus, the official AI assistant for Lotus Electronics Customer Support.

# CORE PRINCIPLES:
# 1. Be empathetic and understanding
# 2. Provide clear, step-by-step guidance
# 3. Use simple language and avoid technical jargon
# 4. Always confirm user understanding before proceeding
# 5. Be patient with frustrated customers

# CONVERSATION FLOW:
# 1. Greet warmly and ask for phone number
# 2. Call check_user with phone number
# 3. If registered, ask for password
# 4. Call sign_in tool with credentials
# 5. After successful login, call get_orders if no products found please try again
# 6. For product issues: ask user to select specific product/order
# 7. Ask for detailed issue description
# 8. Provide troubleshooting steps ONE AT A TIME
# 9. After each step, ask: "What happened when you tried this?"
# 10. If user seems confused, simplify the instruction
# 11. Only raise ticket if ALL troubleshooting fails

# TROUBLESHOOTING BEST PRACTICES:
# - Give one instruction at a time
# - Wait for user confirmation before next step
# - If user says "it's not working", ask specific questions
# - Adapt language complexity based on user responses
# - If user seems frustrated, acknowledge their feelings

# ESCALATION TRIGGERS:
# - User explicitly asks for human agent
# - Same issue reported multiple times
# - User expresses high frustration
# - Technical issue beyond basic troubleshooting

# RESPONSE FORMAT:
# Always respond in valid JSON:
# {
#   "status": "success",
#   "data": {
#     "answer": "Your helpful response here",
#     "next_action": "suggested next step",
#     "escalation_needed": false,
#     "frustration_detected": false
#   }
# }

# For orders, include:
# {
#   "status": "success",
#   "data": {
#     "answer": "...",
#     "orders": [
#       {
#         "itemname": "...",
#         "order_id": "...",
#         "order_date": "...",
#         "product_image": "...",
#         "invoice_no": "...",
#         "invoice_url": "...",
#         "status": "..."
#       }
#     ]
#   }
# }

# REMEMBER: Never recommend new products or provide pricing. Focus on solving existing issues.
# """


ENHANCED_LOTUS_SYSTEM_PROMPT = """
You are Lotus, the official AI assistant for Lotus Electronics Customer Support.

CORE PRINCIPLES:
1. Be empathetic and understanding
2. Provide clear, step-by-step guidance
3. Use simple language and avoid technical jargon
4. Always confirm user understanding before proceeding
5. Be patient with frustrated customers
6. Remember this is our website: https://www.lotuselectronics.com/, To Create Account Say to user "Please visit our website to create an account."


CONVERSATION FLOW:
1. Greet warmly and ask for phone number
2. Call check_user with phone number
3. If registered, then call send_otp tool to send OTP
4. Ask for OTP, call sign_in tool with OTP use OTP instead of password
5. After successful login, call get_orders if no products found please try again
6. For product issues: ask user to select specific product/order
7. Ask for detailed issue description
8. Provide troubleshooting steps ONE AT A TIME
9. After each step, ask: "What happened when you tried this?"
10. If user seems confused, simplify the instruction
11. Only raise ticket if ALL troubleshooting fails

TROUBLESHOOTING BEST PRACTICES:
- Give one instruction at a time
- Wait for user confirmation before next step
- If user says "it's not working", ask specific questions
- Adapt language complexity based on user responses
- If user seems frustrated, acknowledge their feelings

ESCALATION TRIGGERS:
- User explicitly asks for human agent
- Same issue reported multiple times
- User expresses high frustration
- Technical issue beyond basic troubleshooting

RESPONSE FORMAT:
Always respond in valid JSON:
{
  "status": "success",
  "data": {
    "answer": "Your helpful response here",
    "next_action": "suggested next step",
    "escalation_needed": false,
    "frustration_detected": false
  }
}

For orders, include:
{
  "status": "success",
  "data": {
    "answer": "...",
    "orders": [
      {
        "itemname": "...",
        "order_id": "...",
        "order_date": "...",
        "product_image": "...",
        "invoice_no": "...",
        "invoice_url": "...",
        "status": "..."
      }
    ]
  }
}

REMEMBER: Never recommend new products or provide pricing. Focus on solving existing issues.
"""



async def chat_with_agent(message: str, session_id: str, memory: dict) -> Dict[str, Any]:
    """Enhanced chat function with robust error handling and context awareness"""
    
    # Initialize database if needed
    initialize_database()
    ensure_session_exists(session_id)
    
    try:
        # Get conversation context
        context = get_context_from_history(session_id)
        
        # Build message history
        history = memory.get("history", [])
        if not history:
            # Load from database if memory is empty
            history = get_chat_history(session_id)
        
        # Analyze user frustration
        frustration_analysis = analyze_user_frustration(history + [{"role": "user", "content": message}])
        
        # Build messages for AI
        messages = [{"role": "system", "content": ENHANCED_LOTUS_SYSTEM_PROMPT}]
        
        # Add context if available
        if context["user_phone"]:
            messages.append({
                "role": "system", 
                "content": f"Context: User phone is {context['user_phone']}, logged in: {context['user_logged_in']}"
            })
        
        messages.extend(history)
        messages.append({"role": "user", "content": message})
        
        # Save user message
        save_chat_to_db(session_id, "user", message, message_index=len(messages))
        
        # Get AI response with function calling
        function_schemas = [schema for _, schema in tool_registry.values()]
        
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            functions=function_schemas,
            function_call="auto",
            temperature=0.7,
            max_tokens=1500
        )
        
        plan = response.choices[0].message
        
        # Handle function calls
        if plan.function_call:
            function_name = plan.function_call.name
            function_args = json.loads(plan.function_call.arguments or "{}")
            
            print(f"[DEBUG] Calling function: {function_name} with args: {function_args}")
            
            # Execute function
            fn, _ = tool_registry.get(function_name, (None, None))
            if fn:
                if asyncio.iscoroutinefunction(fn):
                    tool_response = await fn(**function_args)
                else:
                    tool_response = fn(**function_args)
            else:
                tool_response = {"error": f"Function {function_name} not found"}
            
            print(f"[DEBUG] Function response: {tool_response}")
            
            # Save function call
            save_chat_to_db(
                session_id, 
                "assistant", 
                f"Called {function_name}",
                tool_name=function_name,
                tool_args=json.dumps(function_args),
                tool_response=json.dumps(tool_response),
                message_index=len(messages) + 1
            )
            
            # Add function call to message history
            messages.append({
                "role": "assistant",
                "function_call": {"name": function_name, "arguments": json.dumps(function_args)}
            })
            messages.append({
                "role": "function",
                "name": function_name,
                "content": json.dumps(tool_response)
            })
            
            # Auto-call send_otp after successful check_user
            if function_name == "check_user" and tool_response.get("is_register"):
                send_otp_fn, _ = tool_registry.get("send_otp", (None, None))
                if send_otp_fn:
                    otp_args = {"phone": function_args.get("phone")}
                    if asyncio.iscoroutinefunction(send_otp_fn):
                        otp_response = await send_otp_fn(**otp_args)
                    else:
                        otp_response = send_otp_fn(**otp_args)
                    
                    # Save OTP call
                    save_chat_to_db(
                        session_id,
                        "assistant",
                        "Called send_otp",
                        tool_name="send_otp",
                        tool_args=json.dumps(otp_args),
                        tool_response=json.dumps(otp_response),
                        message_index=len(messages) + 2
                    )
                    
                    messages.append({
                        "role": "assistant",
                        "function_call": {"name": "send_otp", "arguments": json.dumps(otp_args)}
                    })
                    messages.append({
                        "role": "function",
                        "name": "send_otp",
                        "content": json.dumps(otp_response)
                    })
            
            # Get final response
            final_response = openai.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                temperature=0.7,
                max_tokens=1500
            )
            
            assistant_content = final_response.choices[0].message.content
        else:
            assistant_content = plan.content
        
        # Save assistant response
        save_chat_to_db(session_id, "assistant", assistant_content, message_index=len(messages) + 3)
        
        # Parse JSON response
        parsed_response = extract_json_from_response(assistant_content)
        
        if not parsed_response:
            # Fallback response
            parsed_response = {
                "status": "error",
                "data": {
                    "answer": assistant_content,
                    "next_action": "The Response Should be in josn.",
                    "escalation_needed": True
                }
            }
        
        # Add frustration analysis to response
        if frustration_analysis["is_frustrated"]:
            parsed_response["data"]["frustration_detected"] = True
            parsed_response["data"]["escalation_needed"] = True
        
        # Update memory
        memory["history"] = messages + [{"role": "assistant", "content": assistant_content}]
        memory["context"] = context
        memory["frustration_analysis"] = frustration_analysis
        
        return parsed_response
        
    except Exception as e:
        print(f"[ERROR] Chat processing failed: {str(e)}")
        
        # Save error to database
        save_chat_to_db(session_id, "system", f"Error: {str(e)}")
        
        return {
            "status": "error",
            "data": {
                "answer": "I apologize, but I'm experiencing technical difficulties. Please try again in a moment, or I can connect you with a human agent.",
                "escalation_needed": True,
                "error": str(e)
            }
        }

# Initialize database on module import
initialize_database()