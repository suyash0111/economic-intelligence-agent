"""
Email Sender - Delivers reports via Gmail SMTP.
"""

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path
import logging

from config.settings import Settings

logger = logging.getLogger(__name__)


class EmailSender:
    """
    Sends email reports with attachments via Gmail SMTP.
    Requires Gmail App Password for authentication.
    """
    
    def __init__(self):
        """Initialize the email sender."""
        self.smtp_server = Settings.SMTP_SERVER
        self.smtp_port = Settings.SMTP_PORT
        self.sender_email = Settings.EMAIL_ADDRESS
        self.sender_password = Settings.EMAIL_APP_PASSWORD
        self.recipients = Settings.RECIPIENT_EMAILS
    
    def send_report(
        self,
        subject: str,
        body_html: str,
        attachments: list[Path],
        recipients: list[str] = None
    ) -> bool:
        """
        Send an email with attachments.
        
        Args:
            subject: Email subject
            body_html: HTML body content
            attachments: List of file paths to attach
            recipients: Optional override for recipient list
        
        Returns:
            True if email sent successfully, False otherwise
        """
        if recipients is None:
            recipients = self.recipients
        
        if not recipients or not recipients[0]:
            logger.error("No recipients configured")
            return False
        
        if not self.sender_email or not self.sender_password:
            logger.error("Email credentials not configured")
            return False
        
        try:
            # Create message
            msg = MIMEMultipart('mixed')
            msg['From'] = self.sender_email
            msg['To'] = ', '.join(recipients)
            msg['Subject'] = subject
            
            # Add body
            body_part = MIMEMultipart('alternative')
            
            # Plain text version
            plain_text = self._html_to_plain(body_html)
            body_part.attach(MIMEText(plain_text, 'plain'))
            
            # HTML version
            body_part.attach(MIMEText(body_html, 'html'))
            
            msg.attach(body_part)
            
            # Add attachments
            for attachment_path in attachments:
                if attachment_path.exists():
                    self._attach_file(msg, attachment_path)
                else:
                    logger.warning(f"Attachment not found: {attachment_path}")
            
            # Send email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                server.send_message(msg)
            
            logger.info(f"Email sent successfully to {', '.join(recipients)}")
            return True
            
        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"SMTP authentication failed: {e}")
            logger.error("Make sure you're using a Gmail App Password, not your regular password")
            return False
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False
    
    def _attach_file(self, msg: MIMEMultipart, file_path: Path):
        """Attach a file to the email."""
        try:
            with open(file_path, 'rb') as f:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(f.read())
            
            encoders.encode_base64(part)
            part.add_header(
                'Content-Disposition',
                f'attachment; filename="{file_path.name}"'
            )
            msg.attach(part)
            logger.debug(f"Attached: {file_path.name}")
        except Exception as e:
            logger.error(f"Failed to attach {file_path}: {e}")
    
    def _html_to_plain(self, html: str) -> str:
        """Convert HTML to plain text (simple conversion)."""
        # Simple conversion - remove tags
        import re
        text = re.sub(r'<br\s*/?>', '\n', html)
        text = re.sub(r'<p[^>]*>', '\n', text)
        text = re.sub(r'</p>', '', text)
        text = re.sub(r'<[^>]+>', '', text)
        text = text.replace('&nbsp;', ' ')
        text = text.replace('&amp;', '&')
        text = text.replace('&lt;', '<')
        text = text.replace('&gt;', '>')
        return text.strip()
    
    def send_weekly_report(
        self,
        date_range: str,
        total_articles: int,
        executive_summary: str,
        doc_path: Path,
        excel_path: Path,
        tldr_top5: str = "",
        sentiment: str = ""
    ) -> bool:
        """
        Send the weekly Global Pulse intelligence report.
        
        Args:
            date_range: Date range string
            total_articles: Total number of articles collected
            executive_summary: AI-generated executive summary
            doc_path: Path to Word document
            excel_path: Path to Excel file
            tldr_top5: TL;DR Top 5 section for mobile readers
            sentiment: Sentiment analysis for mobile readers
        
        Returns:
            True if sent successfully
        """
        subject = f"THE GLOBAL PULSE | Weekly Economic Intelligence - {date_range}"
        
        # Format the summary for HTML
        summary_html = executive_summary.replace('\n\n', '</p><p>').replace('\n', '<br>')
        
        # Format TL;DR for mobile
        tldr_html = ""
        if tldr_top5:
            tldr_lines = []
            for line in tldr_top5.split('\n'):
                if line.strip():
                    # Color code by priority
                    if '🔴' in line or 'CRITICAL' in line.upper():
                        tldr_lines.append(f'<li style="color: #c00; font-weight: bold;">{line}</li>')
                    elif '🟠' in line or 'IMPORTANT' in line.upper():
                        tldr_lines.append(f'<li style="color: #d80;">{line}</li>')
                    else:
                        tldr_lines.append(f'<li>{line}</li>')
            if tldr_lines:
                tldr_html = f'''
                <div class="tldr">
                    <h3 style="color: #1b3a4b; margin-bottom: 10px;">⚡ TOP 5 THIS WEEK</h3>
                    <ol style="margin: 0; padding-left: 20px;">{"".join(tldr_lines)}</ol>
                </div>
                '''
        
        body_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; line-height: 1.6; color: #333; margin: 0; padding: 0; }}
                .header {{ background: linear-gradient(135deg, #0d1b2a 0%, #1b3a4b 100%); color: white; padding: 30px 20px; text-align: center; }}
                .header h1 {{ margin: 0; font-size: 24px; letter-spacing: 2px; }}
                .header .subtitle {{ font-size: 14px; opacity: 0.9; margin-top: 5px; }}
                .content {{ padding: 20px; background: #f8fafc; }}
                .summary {{ background: white; padding: 20px; border-radius: 8px; margin: 15px 0; box-shadow: 0 2px 4px rgba(0,0,0,0.1); border-left: 4px solid #1b3a4b; }}
                .stats {{ display: flex; gap: 15px; margin: 15px 0; justify-content: center; flex-wrap: wrap; }}
                .stat-box {{ background: white; padding: 15px 20px; border-radius: 8px; text-align: center; box-shadow: 0 2px 4px rgba(0,0,0,0.1); min-width: 100px; }}
                .stat-number {{ font-size: 28px; font-weight: bold; color: #1b3a4b; }}
                .stat-label {{ color: #718096; font-size: 12px; }}
                .footer {{ background: #0d1b2a; color: white; padding: 20px; text-align: center; font-size: 11px; }}
                .attachments {{ background: #e2e8f0; padding: 15px; border-radius: 8px; margin: 15px 0; }}
                .tldr {{ background: #fff3cd; padding: 15px; border-radius: 8px; margin: 15px 0; font-size: 14px; }}
                h2 {{ color: #1b3a4b; border-bottom: 2px solid #e2e8f0; padding-bottom: 10px; font-size: 18px; }}
                @media (max-width: 600px) {{
                    .header h1 {{ font-size: 20px; }}
                    .stat-number {{ font-size: 24px; }}
                    .stats {{ flex-direction: column; align-items: center; }}
                }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>THE GLOBAL PULSE</h1>
                <div class="subtitle">Weekly Economic Intelligence</div>
                <p style="margin: 10px 0 0 0; opacity: 0.8; font-size: 13px;">{date_range}</p>
            </div>
            
            <div class="content">
                <div class="stats">
                    <div class="stat-box">
                        <div class="stat-number">{total_articles}</div>
                        <div class="stat-label">Articles Analyzed</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-number">44</div>
                        <div class="stat-label">Organizations</div>
                    </div>
                </div>
                
                {tldr_html}
                
                <h2>Executive Summary</h2>
                <div class="summary">
                    <p style="margin: 0; font-size: 14px;">{summary_html}</p>
                </div>
                
                <div class="attachments">
                    <strong>📎 Full Reports Attached:</strong>
                    <ul style="margin: 10px 0; padding-left: 20px; font-size: 13px;">
                        <li><strong>{doc_path.name}</strong> - Complete analysis</li>
                        <li><strong>{excel_path.name}</strong> - All articles with links</li>
                    </ul>
                </div>
                
                <p style="color: #718096; font-size: 12px;">
                    This report includes: Sentiment Analysis • Actionable Implications • Regional Breakdown • 
                    Cross-Source Intelligence • Key Economic Numbers from 44 organizations.
                </p>
            </div>
            
            <div class="footer">
                <p><strong>THE GLOBAL PULSE</strong></p>
                <p style="opacity: 0.7;">Automated Weekly Intelligence | Powered by Gemini AI</p>
            </div>
        </body>
        </html>
        """
        
        return self.send_report(
            subject=subject,
            body_html=body_html,
            attachments=[doc_path, excel_path]
        )
    
    def test_connection(self) -> bool:
        """Test the email connection without sending."""
        try:
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
            logger.info("Email connection test successful")
            return True
        except Exception as e:
            logger.error(f"Email connection test failed: {e}")
            return False
