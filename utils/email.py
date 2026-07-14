import os
import smtplib
from email.message import EmailMessage

def send_invitation_email(to_email: str, token: str):
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
    activation_link = f"{frontend_url}/activate?token={token}"
    
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USERNAME")
    smtp_pass = os.getenv("SMTP_PASSWORD")

    html_content = f"""
    <h2>You've been invited!</h2>
    <p>You have been invited to join an organization on our platform.</p>
    <p>Click the button below to activate your account:</p>
    <a href="{activation_link}" style="display:inline-block;padding:10px 20px;color:white;background-color:#007bff;text-decoration:none;border-radius:5px;">Activate Account</a>
    <p>Or copy and paste this link into your browser: <br>{activation_link}</p>
    """

    if not smtp_user or not smtp_pass:
        print("WARNING: SMTP_USERNAME or SMTP_PASSWORD not set. Email not sent.")
        print(f"Mock email to {to_email}: {activation_link}")
        return False

    msg = EmailMessage()
    msg['Subject'] = "You have been invited to join an Organization"
    msg['From'] = smtp_user
    msg['To'] = to_email
    msg.set_content("You have been invited to join an Organization. Please click the link to activate your account.")
    msg.add_alternative(html_content, subtype='html')

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
            
        print(f"Email sent successfully to {to_email} via SMTP")
        return True
    except Exception as e:
        print(f"Failed to send email via SMTP: {e}")
        return False

