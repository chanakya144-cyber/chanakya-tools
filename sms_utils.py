import sqlite3
from datetime import datetime

def init_sms_db():
    conn = sqlite3.connect('chanakya_tools.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS sms_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tool_code TEXT,
                    recipient TEXT,
                    message TEXT,
                    status TEXT,
                    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )''')
    conn.commit()
    conn.close()

def log_sms(tool_code, recipient, message, status):
    init_sms_db()
    conn = sqlite3.connect('chanakya_tools.db')
    c = conn.cursor()
    c.execute("INSERT INTO sms_logs (tool_code, recipient, message, status) VALUES (?, ?, ?, ?)", 
              (tool_code, recipient, message, status))
    conn.commit()
    conn.close()

def get_sms_logs(tool_code=None):
    init_sms_db()
    conn = sqlite3.connect('chanakya_tools.db')
    c = conn.cursor()
    if tool_code:
        c.execute("SELECT tool_code, recipient, message, status, sent_at FROM sms_logs WHERE tool_code = ? ORDER BY id DESC", (tool_code,))
    else:
        c.execute("SELECT tool_code, recipient, message, status, sent_at FROM sms_logs ORDER BY id DESC")
    logs = c.fetchall()
    conn.close()
    return logs