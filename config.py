import os
from dotenv import load_dotenv

load_dotenv()

DATA_DIR = os.getenv("DATA_DIR", ".")
FLASK_PORT = int(os.getenv("FLASK_PORT", 8000))
FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "dev-secret-key")

# Google Drive — OAuth 2.0 (preferred, set up via the Connect button in the UI)
GOOGLE_OAUTH_CLIENT_ID     = os.getenv("GOOGLE_OAUTH_CLIENT_ID", "")
GOOGLE_OAUTH_CLIENT_SECRET = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", "")
GOOGLE_OAUTH_TOKEN_FILE    = os.getenv("GOOGLE_OAUTH_TOKEN_FILE", "credentials/oauth_token.json")

# Google Drive — Service Account (alternative)
GOOGLE_SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "credentials/service_account.json")
GOOGLE_DRIVE_FOLDER_ID      = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "")

COMPANY_NAME    = os.getenv("COMPANY_NAME", "Your Company")
COMPANY_ADDRESS = os.getenv("COMPANY_ADDRESS", "123 Main Street, City, Country")
PDF_OUTPUT_DIR  = os.getenv("PDF_OUTPUT_DIR", "generated_pdfs")
