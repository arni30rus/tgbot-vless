import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMINS_ID = list(map(int, os.getenv("ADMINS_ID").split(",")))

XUI_BASE_URL = os.getenv("XUI_BASE_URL")
XUI_INBOUND_ID = int(os.getenv("XUI_INBOUND_ID", 1))
XUI_DB_PATH = os.getenv("XUI_DB_PATH", "/etc/x-ui/x-ui.db")
XUI_API_TOKEN = os.getenv("XUI_API_TOKEN", "")


SERVER_DOMAIN = os.getenv("SERVER_DOMAIN")
SERVER_PORT = int(os.getenv("SERVER_PORT", 443))
SHARED_SID = os.getenv("SHARED_SID")

REALITY_PUBLIC_KEY = os.getenv("REALITY_PUBLIC_KEY")
REALITY_SNI = os.getenv("REALITY_SNI")
REALITY_SPIDER_X = os.getenv("REALITY_SPIDER_X", "")
REALITY_FINGERPRINT = os.getenv("REALITY_FINGERPRINT", "chrome")


SECURITY_TYPE = os.getenv("SECURITY_TYPE", "reality")
CLIENT_FLOW = os.getenv("CLIENT_FLOW", "")
TLS_ALPN = os.getenv("TLS_ALPN", "h2,http/1.1")
TLS_SNI = os.getenv("TLS_SNI", SERVER_DOMAIN)

XUI_ADD_CLIENT_PATH = os.getenv("XUI_ADD_CLIENT_PATH", "/panel/inbound/addClient")
