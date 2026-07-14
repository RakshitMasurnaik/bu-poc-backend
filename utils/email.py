import os
import resend

resend.api_key = os.getenv("RESEND_API_KEY")

def send_invitation_email(to_email: str, token: str):
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
    activation_link = f"{frontend_url}/activate?token={token}"
    
    # Resend requires a verified domain to send from, 
    # but for testing you can often use 'onboarding@resend.dev' to send to yourself.
    # However, it's better to allow the user to specify their sending domain via env vars.
    from_email = os.getenv("RESEND_FROM_EMAIL", "onboarding@resend.dev")

    html_content = f"""
    <h2>You've been invited!</h2>
    <p>You have been invited to join an organization on our platform.</p>
    <p>Click the button below to activate your account:</p>
    <a href="{activation_link}" style="display:inline-block;padding:10px 20px;color:white;background-color:#007bff;text-decoration:none;border-radius:5px;">Activate Account</a>
    <p>Or copy and paste this link into your browser: <br>{activation_link}</p>
    """

    try:
        if not resend.api_key:
            print("WARNING: RESEND_API_KEY not set. Email not sent.")
            print(f"Mock email to {to_email}: {activation_link}")
            return False

        r = resend.Emails.send({
            "from": from_email,
            "to": [to_email],
            "subject": "You have been invited to join an Organization",
            "html": html_content
        })
        print(f"Email sent successfully via Resend: {r}")
        return True
    except Exception as e:
        print(f"Failed to send email via Resend: {e}")
        return False
