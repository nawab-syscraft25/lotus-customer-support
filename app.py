from fastapi import FastAPI, Request, Depends, Form
from pydantic import BaseModel
from tools import tool_registry
from memory.memory_store import get_session_memory, authenticate_user, add_chat_message, is_authenticated
from fastapi.responses import RedirectResponse
import uvicorn
from fastapi.templating import Jinja2Templates
from fastapi import FastAPI, Request, HTTPException, Depends, Header
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
from tools.auth import check_user, send_otp, verify_otp, sign_in
import sqlite3
from starlette.middleware.sessions import SessionMiddleware
# from setup_db import init_db 
import sqlite3


# from openai_agent import chat_with_agent


from agentic_ai import chat_with_agent, get_chat_history, get_context_from_history, get_db



app = FastAPI(title="Lotus Shopping Assistant")
static_path = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=static_path), name="static")

templates = Jinja2Templates(directory="templates")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(SessionMiddleware, secret_key="your_secret_key_here")  # Add this for session support

class ChatRequest(BaseModel):
    message: str
    session_id: str

class AuthRequest(BaseModel):
    phone: str
    session_id: str

class OTPRequest(BaseModel):
    phone: str
    otp: str
    session_id: str

class SignInRequest(BaseModel):
    phone: str
    password: str
    session_id: str


@app.post("/chat")
async def chat_endpoint(req: ChatRequest):
    mem = get_session_memory(req.session_id)
    add_chat_message(req.session_id, "user", req.message)
    resp = await chat_with_agent(req.message, req.session_id, mem)
    if resp.get("data", {}).get("answer"):
        add_chat_message(req.session_id, "assistant", resp["data"]["answer"])
    return {"response": resp}


@app.post("/auth/check-user")
async def check_user_endpoint(request: AuthRequest):
    """Check if a user exists"""
    try:
        result = await check_user(request.phone)
        return JSONResponse(content=result)
    except Exception as e:
        return JSONResponse(content={"error": "1", "message": str(e)}, status_code=500)

@app.post("/auth/send-otp")
async def send_otp_endpoint(request: AuthRequest):
    """Send OTP to user's phone"""
    try:
        result = await send_otp(request.phone)
        return JSONResponse(content=result)
    except Exception as e:
        return JSONResponse(content={"error": "1", "message": str(e)}, status_code=500)

@app.post("/auth/verify-otp")
async def verify_otp_endpoint(request: OTPRequest):
    """Verify OTP and authenticate user"""
    try:
        result = await verify_otp(request.phone, request.otp, request.session_id)
        
        # If authentication successful, store in database
        if result.get("error") == "0":
            auth_token = (
                result.get("auth_token") or
                (result.get("data", {}).get("auth_token") if isinstance(result.get("data"), dict) else None)
            )
            if auth_token:
                # Authenticate user and store in database
                user_data = result.get("data") if isinstance(result.get("data"), dict) else None
                authenticate_user(request.session_id, request.phone, auth_token, user_data)
        
        return JSONResponse(content=result)
    except Exception as e:
        return JSONResponse(content={"error": "1", "message": str(e)}, status_code=500)

@app.post("/auth/sign-in")
async def sign_in_endpoint(request: SignInRequest):
    """Sign in with phone and password"""
    try:
        result = await sign_in(request.phone, request.password, request.session_id)
        
        # If authentication successful, store in database
        if result.get("error") == "0":
            auth_token = (
                result.get("auth_token") or
                (result.get("data", {}).get("auth_token") if isinstance(result.get("data"), dict) else None)
            )
            if auth_token:
                # Authenticate user and store in database
                user_data = result.get("data") if isinstance(result.get("data"), dict) else None
                authenticate_user(request.session_id, request.phone, auth_token, user_data)
        
        return JSONResponse(content=result)
    except Exception as e:
        return JSONResponse(content={"error": "1", "message": str(e)}, status_code=500)

@app.get("/auth/status/{session_id}")
async def auth_status_endpoint(session_id: str):
    """Check authentication status for a session"""
    try:
        authenticated = is_authenticated(session_id)
        memory = get_session_memory(session_id)
        
        return JSONResponse(content={
            "authenticated": authenticated,
            "phone": memory.get("phone") if authenticated else None,
            "user_data": memory.get("user_data") if authenticated else None
        })
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)

@app.get("/")
async def read_root(request: Request):
    return templates.TemplateResponse("chatbot.html", {"request": request})

# === Run Server ===




ADMIN_USER = os.getenv("ADMIN_USER")
ADMIN_PASS = os.getenv("ADMIN_PASS")
DB_FILE = 'tickets.db'

@app.get("/admin")
async def admin_login_get(request: Request):
    return templates.TemplateResponse("admin_login.html", {"request": request, "error": None})

@app.post("/admin")
async def admin_login_post(request: Request, user: str = Form(...), password: str = Form(...)):
    if user == ADMIN_USER and password == ADMIN_PASS:
        request.session["admin_logged_in"] = True
        return RedirectResponse(url="/admin/tickets", status_code=303)
    else:
        return templates.TemplateResponse("admin_login.html", {"request": request, "error": "Invalid credentials"})

@app.get("/admin/tickets")
async def admin_tickets(request: Request):
    if not request.session.get("admin_logged_in"):
        return RedirectResponse(url="/admin", status_code=303)
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT id, timestamp, phone, name, problem, order_id, invoice_no FROM tickets ORDER BY id DESC')
    tickets = c.fetchall()
    conn.close()
    return templates.TemplateResponse("admin_tickets.html", {"request": request, "tickets": tickets}) 


@app.get("/admin/conversations")
async def admin_conversations(request: Request):
    if not request.session.get("admin_logged_in"):
        return RedirectResponse(url="/admin", status_code=303)
    
    conn = sqlite3.connect("chat_history.db")  # or your actual DB file
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # Fetch distinct sessions with latest timestamp
    c.execute("""
        SELECT session_id, MAX(timestamp) as last_seen
        FROM history
        GROUP BY session_id
        ORDER BY last_seen DESC
    """)
    sessions = c.fetchall()

    conn.close()
    return templates.TemplateResponse("admin_conversations.html", {"request": request, "sessions": sessions})


@app.get("/admin/conversations/{session_id}")
async def view_conversation(request: Request, session_id: str):
    if not request.session.get("admin_logged_in"):
        return RedirectResponse(url="/admin", status_code=303)

    conn = sqlite3.connect("chat_history.db")
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("""
        SELECT role, content, timestamp FROM history
        WHERE session_id = ?
        ORDER BY timestamp ASC
    """, (session_id,))
    messages = c.fetchall()
    conn.close()

    return templates.TemplateResponse("admin_view_conversation.html", {
        "request": request,
        "session_id": session_id,
        "messages": messages
    })


@app.get("/admin/logout")
async def admin_logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/admin", status_code=303)

import os

DB_PATH = "chat_history.db"
print(f"[DEBUG] Using DB at: {os.path.abspath(DB_PATH)}")  # <--- add this

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn





if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000) 