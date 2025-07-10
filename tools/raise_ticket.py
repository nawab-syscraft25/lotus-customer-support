import sqlite3
from datetime import datetime
from datetime import datetime
from zoneinfo import ZoneInfo

DB_FILE = 'tickets.db'


def get_india_time():
    return datetime.now(ZoneInfo("Asia/Kolkata")).isoformat()


def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            phone TEXT,
            name TEXT,
            problem TEXT,
            order_id TEXT,
            invoice_no TEXT
        )
    ''')
    conn.commit()
    conn.close()

def save_ticket_sqlite(ticket: dict):
    init_db()
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        INSERT INTO tickets (timestamp, phone, name, problem, order_id, invoice_no)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (
        ticket['timestamp'],
        ticket['phone'],
        ticket['name'],
        ticket['problem'],
        ticket.get('order_id'),
        ticket.get('invoice_no')
    ))
    conn.commit()
    conn.close()

async def raise_ticket(phone: str, name: str, problem: str, order_id: str = None, invoice_no: str = None) -> dict:
    ticket = {
        'timestamp': get_india_time(),
        'phone': phone,
        'name': name,
        'problem': problem,
        'order_id': order_id,
        'invoice_no': invoice_no
    }
    save_ticket_sqlite(ticket)
    return {
        'status': 'success',
        'data': {
            'answer': 'Your ticket has been raised. Our team will contact you as soon as possible.',
            'ticket': ticket
        }
    }

raise_ticket_schema = {
    "name": "raise_ticket",
    "description": "Raise a support ticket for the user. If order-related, include order_id and invoice_no.",
    "parameters": {
        "type": "object",
        "properties": {
            "phone": {"type": "string"},
            "name": {"type": "string"},
            "problem": {"type": "string"},
            "order_id": {"type": "string"},
            "invoice_no": {"type": "string"}
        },
        "required": ["phone", "name", "problem"]
    }
} 