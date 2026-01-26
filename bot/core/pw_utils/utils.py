import uuid
import requests
import time

BASE_URL = "https://api.penpencil.co"
ORGANIZATION_ID = "5eb393ee95fab7468a79d189"
REFERER = "https://www.pw.live/"
CONTENT_TYPE = "application/json"
ACCEPT = "application/json"
CLIENT_ID = "system-admin"
CLIENT_SECRET = "KjPXuAVfC5xbmgreETNMaL7z"
GRANT_TYPE = "password"
LATITUDE = 0
LONGITUDE = 0

def get_default_headers(random_id=None):
    if not random_id:
        random_id = str(uuid.uuid4())
    return {
        "Content-Type": CONTENT_TYPE,
        "Accept": ACCEPT,
        "Referer": REFERER,
        "Randomid": random_id,
    }

def get_auth_headers(token, random_id=None):
    headers = get_default_headers(random_id)
    headers["Authorization"] = f"Bearer {token}"
    return headers

def verify_token(token):
    url = f"{BASE_URL}/v3/oauth/verify-token"
    headers = get_auth_headers(token)
    try:
        resp = requests.post(url, headers=headers, timeout=10)
        data = resp.json()
        if data.get("success") and data.get("data", {}).get("isVerified"):
            return {"success": True}
        else:
            error = data.get("error", {})
            return {
                "success": False,
                "error_message": error.get("message", data.get("message", "Unknown error")),
                "error_status": error.get("status", resp.status_code)
            }
    except Exception as e:
        return {"success": False, "error_message": str(e), "error_status": None}
    
def get_token_expiry_info(expires_in):
    current_time_ms = int(time.time() * 1000)
    ms_remaining = expires_in - current_time_ms
    days_remaining = ms_remaining // (1000 * 60 * 60 * 24)
    is_expired = ms_remaining <= 0
    return {
        "is_expired": is_expired,
        "days_remaining": days_remaining if not is_expired else 0
    }
