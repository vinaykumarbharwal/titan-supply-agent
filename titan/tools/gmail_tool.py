import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
from titan.tools.mock_email_tool import log_mock_email

load_dotenv()

def send_email(to_email: str, subject: str, body: str):
    """
    Sends an email using configured SMTP settings.
    Falls back to mock_email_tool if SMTP settings are not configured.
    """
    smtp_server = os.getenv("SMTP_SERVER")
    smtp_port = os.getenv("SMTP_PORT")
    smtp_user = os.getenv("SMTP_USERNAME")
    smtp_pass = os.getenv("SMTP_PASSWORD")
    
    # Check if SMTP details are populated
    if not all([smtp_server, smtp_port, smtp_user, smtp_pass]):
        print("[SMTP Info Missing] Falling back to Mock Outbox...")
        return log_mock_email(to_email, subject, body)
        
    try:
        msg = MIMEMultipart()
        msg['From'] = smtp_user
        msg['To'] = to_email
        msg['Subject'] = subject
        
        msg.attach(MIMEText(body, 'plain'))
        
        server = smtplib.SMTP(smtp_server, int(smtp_port))
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.sendmail(smtp_user, to_email, msg.as_string())
        server.quit()
        
        print(f"[EMAIL SUCCESS] Sent to {to_email}")
        return "sent_successfully"
    except Exception as e:
        print(f"[SMTP ERROR] Failed to send email to {to_email} via SMTP: {e}")
        print("Falling back to Mock Outbox...")
        return log_mock_email(to_email, subject, body)
