"""Load project .env so API keys and Iceberg settings are available everywhere."""

import os
from pathlib import Path

from dotenv import load_dotenv

_PROJECT_ROOT = Path(__file__).resolve().parent
_ENV_FILE = _PROJECT_ROOT / ".env"


def load_project_env() -> None:
    """Load .env from project root if present (CLI and dashboard on CAI)."""
    if _ENV_FILE.is_file():
        load_dotenv(_ENV_FILE, override=False)


def get_env_status() -> dict:
    """Non-secret environment status for CLI and dashboard health checks."""
    load_project_env()
    return {
        "env_file": str(_ENV_FILE) if _ENV_FILE.is_file() else None,
        "env_file_found": _ENV_FILE.is_file(),
        "openai_api_key_set": bool(os.environ.get("OPENAI_API_KEY")),
        "snowflake_pat_set": bool(os.environ.get("SNOWFLAKE_PAT")),
        "snowflake_account_url": os.environ.get("SNOWFLAKE_ACCOUNT_URL", "(default)"),
        "iceberg_jar": os.environ.get("ICEBERG_JAR", "(auto-detect)"),
        "cdsw_app_port": os.environ.get("CDSW_APP_PORT"),
    }


def print_env_status() -> None:
    """Print non-secret config status for scenario startup."""
    status = get_env_status()
    print("=== Environment ===")
    if status["env_file_found"]:
        print(f"  .env file: found ({status['env_file']})")
    else:
        print(f"  .env file: not found (optional — set keys in shell or create {_ENV_FILE})")
    print(f"  OPENAI_API_KEY: {'set' if status['openai_api_key_set'] else 'NOT SET'}")
    print(f"  SNOWFLAKE_PAT: {'set' if status['snowflake_pat_set'] else 'NOT SET'}")
    print(f"  SNOWFLAKE_ACCOUNT_URL: {status['snowflake_account_url']}")
    print(f"  ICEBERG_JAR: {status['iceberg_jar']}")
