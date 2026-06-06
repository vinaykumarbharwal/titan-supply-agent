import os
from datetime import datetime

def log_mock_email(to_email: str, subject: str, body: str):
    """
    Simulates sending an email by writing it to the local outbox directory.
    """
    outbox_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "outbox"))
    os.makedirs(outbox_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    clean_email = to_email.replace("@", "_at_").replace(".", "_")
    filename = f"{timestamp}_{clean_email}.txt"
    file_path = os.path.join(outbox_dir, filename)
    
    content = f"""==================================================
MOCK OUTBOX: EMAIL TRANSMITTED
Timestamp: {datetime.now().isoformat()}
To: {to_email}
Subject: {subject}
==================================================
{body}
==================================================
"""
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
        
    print(f"\n[MOCK EMAIL SENT] Written to: {file_path}")
    print(f"To: {to_email}")
    print(f"Subject: {subject}")
    print("-" * 40)
    return file_path
