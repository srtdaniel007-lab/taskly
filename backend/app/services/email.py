import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional
import aiosmtplib

from app.core.config import settings

logger = logging.getLogger("taskpulse.email")


async def send_email_async(
    to_email: str,
    subject: str,
    html_content: str,
    text_content: Optional[str] = None
) -> bool:
    """
    Sends an email asynchronously via SMTP.
    If SMTP credentials are not configured, logs the email output safely.
    """
    if not settings.SMTP_HOST or not settings.SMTP_USER or "your-app-password" in (settings.SMTP_PASSWORD or ""):
        print(f"📧 [Email Simulated] To: {to_email} | Subject: {subject}")
        logger.info(
            f"[SMTP Simulation] To: {to_email} | Subject: {subject}\n"
            f"Content Preview: {text_content or 'HTML content provided'}"
        )
        return True

    try:
        print(f"📧 [Email Dispatching] Sending email to: {to_email} via {settings.SMTP_HOST}...")
        message = MIMEMultipart("alternative")
        message["From"] = settings.SMTP_FROM_EMAIL
        message["To"] = to_email
        message["Subject"] = subject

        if text_content:
            message.attach(MIMEText(text_content, "plain", "utf-8"))
        if html_content:
            message.attach(MIMEText(html_content, "html", "utf-8"))

        await aiosmtplib.send(
            message,
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            username=settings.SMTP_USER,
            password=settings.SMTP_PASSWORD,
            use_tls=False,
            start_tls=settings.SMTP_TLS
        )
        print(f"✅ [Email Delivered] Successfully sent to: {to_email} | Subject: '{subject}'")
        logger.info(f"Email successfully delivered to {to_email} with subject: '{subject}'")
        return True
    except Exception as exc:
        print(f"❌ [Email Failed] Error sending to {to_email}: {exc}")
        logger.error(f"Failed to send email to {to_email}: {exc}", exc_info=True)
        return False


def get_task_assigned_email(
    member_name: str,
    task_title: str,
    priority: str,
    due_date_str: str,
    task_id: str
) -> tuple[str, str, str]:
    """Builds subject, text, and responsive HTML email for task assignment."""
    subject = f"📋 New Task Assigned: {task_title} [{priority}]"
    task_url = f"{settings.APP_BASE_URL}/#task-{task_id}"

    text_body = f"""Hello {member_name},

You have been assigned a new task on TaskPulse:

Title: {task_title}
Priority: {priority}
Due Date: {due_date_str}

View task: {task_url}

Please open the task to acknowledge receipt and start tracking progress.
"""

    priority_colors = {
        "LOW": "#10b981",
        "MEDIUM": "#3b82f6",
        "HIGH": "#f59e0b",
        "CRITICAL": "#ef4444"
    }
    badge_color = priority_colors.get(priority.upper(), "#3b82f6")

    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #0f172a; color: #f8fafc; margin: 0; padding: 24px; }}
        .card {{ max-width: 560px; margin: 0 auto; background-color: #1e293b; border: 1px solid #334155; border-radius: 12px; padding: 32px; box-shadow: 0 10px 25px -5px rgba(0,0,0,0.5); }}
        .header {{ border-bottom: 1px solid #334155; padding-bottom: 20px; margin-bottom: 24px; }}
        .brand {{ font-size: 22px; font-weight: 800; color: #38bdf8; letter-spacing: -0.5px; }}
        .title {{ font-size: 20px; font-weight: 700; color: #f8fafc; margin-top: 12px; }}
        .badge {{ display: inline-block; padding: 4px 10px; font-size: 12px; font-weight: 700; border-radius: 9999px; color: #ffffff; background-color: {badge_color}; }}
        .info-row {{ margin: 16px 0; color: #94a3b8; font-size: 14px; }}
        .info-value {{ color: #f1f5f9; font-weight: 600; }}
        .cta-btn {{ display: inline-block; margin-top: 24px; padding: 12px 24px; background-color: #2563eb; color: #ffffff !important; font-weight: 600; text-decoration: none; border-radius: 8px; }}
        .footer {{ margin-top: 32px; font-size: 12px; color: #64748b; text-align: center; }}
      </style>
    </head>
    <body>
      <div class="card">
        <div class="header">
          <div class="brand">⚡ TaskPulse</div>
          <div class="title">New Task Assignment</div>
        </div>
        <p>Hello <strong>{member_name}</strong>,</p>
        <p>A new task has been assigned to you with the following details:</p>
        
        <div class="info-row">
          <strong>Task:</strong> <span class="info-value">{task_title}</span>
        </div>
        <div class="info-row">
          <strong>Priority:</strong> <span class="badge">{priority}</span>
        </div>
        <div class="info-row">
          <strong>Due Date:</strong> <span class="info-value">{due_date_str}</span>
        </div>
        
        <a href="{task_url}" class="cta-btn">Open & Acknowledge Task</a>
        
        <div class="footer">
          Opening the task automatically acknowledges receipt (Seen status) for your team leader.
        </div>
      </div>
    </body>
    </html>
    """
    return subject, text_body, html_body


def get_task_update_email(
    leader_name: str,
    task_title: str,
    member_name: str,
    action_type: str,
    details: str,
    task_id: str
) -> tuple[str, str, str]:
    """Builds email notification for leaders when member updates task or requests review."""
    subject = f"🔔 Task Alert [{action_type}]: {task_title}"
    task_url = f"{settings.APP_BASE_URL}/#task-{task_id}"

    text_body = f"""Hello {leader_name},

{member_name} has made an update on: "{task_title}".
Action: {action_type}
Notes: {details}

Review task here: {task_url}
"""

    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #0f172a; color: #f8fafc; margin: 0; padding: 24px; }}
        .card {{ max-width: 560px; margin: 0 auto; background-color: #1e293b; border: 1px solid #334155; border-radius: 12px; padding: 32px; }}
        .brand {{ font-size: 22px; font-weight: 800; color: #38bdf8; }}
        .badge {{ display: inline-block; padding: 4px 10px; font-size: 12px; font-weight: 700; border-radius: 9999px; color: #ffffff; background-color: #8b5cf6; }}
        .cta-btn {{ display: inline-block; margin-top: 24px; padding: 12px 24px; background-color: #2563eb; color: #ffffff !important; font-weight: 600; text-decoration: none; border-radius: 8px; }}
        .quote {{ background: #0f172a; border-left: 3px solid #38bdf8; padding: 12px; margin: 16px 0; border-radius: 4px; color: #e2e8f0; font-style: italic; }}
      </style>
    </head>
    <body>
      <div class="card">
        <div class="brand">⚡ TaskPulse</div>
        <h2 style="color: #f8fafc; margin-top: 12px;">Task Update Notification</h2>
        <p>Hello <strong>{leader_name}</strong>,</p>
        <p><strong>{member_name}</strong> updated the task <strong>"{task_title}"</strong>.</p>
        <p><strong>Event:</strong> <span class="badge">{action_type}</span></p>
        
        <div class="quote">{details}</div>
        
        <a href="{task_url}" class="cta-btn">Review Deliverables on Dashboard</a>
      </div>
    </body>
    </html>
    """
    return subject, text_body, html_body

