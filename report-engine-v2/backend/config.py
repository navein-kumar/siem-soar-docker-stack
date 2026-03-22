import os

OPENSEARCH_URL = os.getenv("OPENSEARCH_URL", "https://wazuh.indexer:9200")
OPENSEARCH_USER = os.getenv("OPENSEARCH_USER", "admin")
OPENSEARCH_PASS = os.getenv("OPENSEARCH_PASS", "SecretPassword@123")
OPENSEARCH_INDEX = os.getenv("OPENSEARCH_INDEX", "wazuh-alerts-*")
OPENSEARCH_VERIFY_SSL = False

GOTENBERG_URL = os.getenv("GOTENBERG_URL", "http://gotenberg:3000")

# Report storage
REPORTS_DIR = os.getenv("REPORTS_DIR", "/app/reports")
TEMPLATES_DIR = os.getenv("TEMPLATES_DIR", "/app/data/templates")
DB_PATH = os.getenv("DB_PATH", "/app/data/report_engine.db")

# Auto-cleanup: "daily", "weekly", "off" (default: off)
CLEANUP_SCHEDULE = os.getenv("CLEANUP_SCHEDULE", "off")
