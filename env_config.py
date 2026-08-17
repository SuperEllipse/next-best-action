"""Load project .env so API keys and Iceberg settings are available everywhere."""

import os
from pathlib import Path

from dotenv import load_dotenv

_PROJECT_ROOT = Path(__file__).resolve().parent
_ENV_FILE = _PROJECT_ROOT / ".env"


def load_project_env() -> None:
    """Load /home/cdsw/.env into os.environ (existing env vars take precedence)."""
    if _ENV_FILE.is_file():
        load_dotenv(_ENV_FILE, override=False)


def print_env_status() -> None:
    """Print non-secret config status for scenario startup."""
    load_project_env()
    print("=== Environment ===")
    print(f"  .env file: {'found' if _ENV_FILE.is_file() else 'missing'}")
    print(f"  OPENAI_API_KEY: {'set' if os.environ.get('OPENAI_API_KEY') else 'NOT SET'}")
    print(f"  SNOWFLAKE_PAT: {'set' if os.environ.get('SNOWFLAKE_PAT') else 'NOT SET'}")
    print(f"  SNOWFLAKE_ACCOUNT_URL: {os.environ.get('SNOWFLAKE_ACCOUNT_URL', '(default)')}")
    print(f"  ICEBERG_JAR: {os.environ.get('ICEBERG_JAR', '(auto-detect)')}")
