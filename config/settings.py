"""
Settings and configuration management for Economic Intelligence Agent.
Loads environment variables and organization configurations.
"""

import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
import yaml

# Load environment variables
load_dotenv()


class Settings:
    """Central configuration class for the agent."""
    
    # API Keys
    GEMINI_API_KEY: str = os.getenv('GEMINI_API_KEY', '')
    OPENROUTER_API_KEY: str = os.getenv('OPENROUTER_API_KEY', '')
    
    # Email Configuration
    EMAIL_ADDRESS: str = os.getenv('EMAIL_ADDRESS', '')
    EMAIL_APP_PASSWORD: str = os.getenv('EMAIL_APP_PASSWORD', '')
    RECIPIENT_EMAIL: str = os.getenv('RECIPIENT_EMAIL', '')
    RECIPIENT_EMAILS: list[str] = [
        e.strip() for e in os.getenv('RECIPIENT_EMAILS', '').split(',') if e.strip()
    ] or [os.getenv('RECIPIENT_EMAIL', '')]
    
    # Gmail SMTP Settings
    SMTP_SERVER: str = 'smtp.gmail.com'
    SMTP_PORT: int = 587
    
    # Report Settings
    LOOKBACK_DAYS: int = int(os.getenv('LOOKBACK_DAYS', '7'))
    MAX_ARTICLES_PER_ORG: int = int(os.getenv('MAX_ARTICLES_PER_ORG', '20'))
    
    # Paths
    BASE_DIR: Path = Path(__file__).parent.parent
    CONFIG_DIR: Path = BASE_DIR / 'config'
    OUTPUT_DIR: Path = BASE_DIR / 'output'
    
    # User Agent for web requests
    USER_AGENT: str = (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
        '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    )
    
    # Request settings
    REQUEST_TIMEOUT: int = 30
    REQUEST_DELAY: float = 1.0  # Delay between requests to be polite
    
    @classmethod
    def load_organizations(cls) -> list[dict]:
        """Load organization configurations from YAML file."""
        org_file = cls.CONFIG_DIR / 'organizations.yaml'
        if org_file.exists():
            with open(org_file, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
                return data.get('organizations', [])
        return []
    
    @classmethod
    def ensure_output_dir(cls) -> Path:
        """Ensure output directory exists and return its path."""
        cls.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        return cls.OUTPUT_DIR
    
    @classmethod
    def validate(cls) -> list[str]:
        """Validate required settings and return list of missing items."""
        missing = []
        if not cls.GEMINI_API_KEY:
            missing.append('GEMINI_API_KEY')
        if not cls.EMAIL_ADDRESS:
            missing.append('EMAIL_ADDRESS')
        if not cls.EMAIL_APP_PASSWORD:
            missing.append('EMAIL_APP_PASSWORD')
        if not cls.RECIPIENT_EMAIL and not cls.RECIPIENT_EMAILS:
            missing.append('RECIPIENT_EMAIL or RECIPIENT_EMAILS')
        return missing
