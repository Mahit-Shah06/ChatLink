import io
import json
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

# Project Imports
from memory import gdrive_utils
from security.encrypting_utils import crypting

# Scope: strict access only to files created by this bot
SCOPES = ['https://www.googleapis.com/auth/drive.file']

class GDriveService:
    def __init__(self):
        # Instantiate crypto once to avoid overhead
        self.crypto = crypting()

    def _encrypt_dict(self, data: dict) -> bytes:
        """Helper: Serialize Dict -> JSON -> Encrypt -> Bytes"""
        try:
            json_str = json.dumps(data)
            return self.crypto.encrypting(json_str)
        except Exception as e:
            print(f"❌ Encryption Error: {e}")
            return None

    def _decrypt_bytes(self, data: bytes) -> dict:
        """Helper: Decrypt Bytes -> JSON -> Dict"""
        if not data: 
            return None
        try:
            # Your crypting class returns a string, so we load that
            json_str = self.crypto.decrypting(data)
            return json.loads(json_str)
        except Exception as e:
            print(f"❌ Decryption Error: {e}")
            return None

    def _get_app_config(self):
        """Fetches the App Credentials (client secret) from DB."""
        # We assume the app config in DB is NOT encrypted (based on your setup_db.py).
        # If you encrypted it in setup_db.py, you must decrypt it here.
        config = gdrive_utils.get_client_secrets()
        if not config:
            print("❌ Critical: 'gdrive_app_config' missing in MongoDB.")
        return config

    def get_auth_url(self, redirect_uri="urn:ietf:wg:oauth:2.0:oob"):
        """Generates the OAuth2 login URL."""
        config = self._get_app_config()
        if not config: return None
            
        flow = Flow.from_client_config(
            config,
            scopes=SCOPES,
            redirect_uri=redirect_uri
        )
        
        # 'prompt=consent' is mandatory to ensure we get a refresh_token
        auth_url, _ = flow.authorization_url(
            access_type='offline', 
            include_granted_scopes='true',
            prompt='consent' 
        )
        return auth_url

    def authenticate_user(self, user_id, auth_code, redirect_uri="urn:ietf:wg:oauth:2.0:oob"):
        """Exchanges auth code for tokens and saves encrypted version to DB."""
        try:
            config = self._get_app_config()
            if not config: return False

            flow = Flow.from_client_config(
                config,
                scopes=SCOPES,
                redirect_uri=redirect_uri
            )
            
            # Exchange code for tokens
            flow.fetch_token(code=auth_code)
            creds = flow.credentials

            # Prepare data structure
            creds_data = {
                "token": creds.token,
                "refresh_token": creds.refresh_token,
                "token_uri": creds.token_uri,
                "client_id": creds.client_id,
                "client_secret": creds.client_secret,
                "scopes": creds.scopes
            }
            
            # Encrypt and Save
            encrypted_token = self._encrypt_dict(creds_data)
            if encrypted_token:
                gdrive_utils.save_gdrive_token(user_id, encrypted_token)
                return True
            return False
            
        except Exception as e:
            print(f"❌ Auth Flow Failed: {e}")
            return False

    def get_service(self, user_id):
        """Constructs the Drive Service, handling automatic token refresh."""
        # 1. Retrieve and Decrypt
        encrypted_token = gdrive_utils.get_gdrive_token(user_id)
        token_data = self._decrypt_bytes(encrypted_token)
        
        if not token_data:
            return None # User not logged in

        # 2. Build Credentials Object
        creds = Credentials(**token_data)

        # 3. Check Validity & Refresh
        if creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                
                # Update DB with new token
                new_creds_data = {
                    "token": creds.token,
                    "refresh_token": creds.refresh_token,
                    "token_uri": creds.token_uri,
                    "client_id": creds.client_id,
                    "client_secret": creds.client_secret,
                    "scopes": creds.scopes
                }
                encrypted_new = self._encrypt_dict(new_creds_data)
                gdrive_utils.save_gdrive_token(user_id, encrypted_new)
            except Exception as e:
                print(f"❌ Token Refresh Failed (User likely revoked access): {e}")
                gdrive_utils.delete_gdrive_token(user_id)
                return None

        # 4. Return Service
        return build('drive', 'v3', credentials=creds)

    def create_folder(self, user_id, folder_name, parent_id=None):
        """Creates a folder and returns (id, link)."""
        service = self.get_service(user_id)
        if not service: return None, None

        metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder'
        }
        if parent_id:
            metadata['parents'] = [parent_id]

        try:
            file = service.files().create(body=metadata, fields='id, webViewLink').execute()
            return file.get('id'), file.get('webViewLink')
        except Exception as e:
            print(f"❌ Create Folder Failed: {e}")
            return None, None

    def upload_bytes(self, user_id, file_content: bytes, file_name: str, parent_id=None):
        """Uploads file from RAM (bytes) to Drive."""
        service = self.get_service(user_id)
        if not service: return None

        metadata = {'name': file_name}
        if parent_id:
            metadata['parents'] = [parent_id]

        # Convert bytes to file-like stream
        media_stream = io.BytesIO(file_content)
        
        media = MediaIoBaseUpload(
            media_stream, 
            mimetype='application/octet-stream',
            resumable=True
        )

        try:
            uploaded = service.files().create(
                body=metadata,
                media_body=media,
                fields='webViewLink'
            ).execute()
            return uploaded.get('webViewLink')
        except Exception as e:
            print(f"❌ Upload Failed: {e}")
            return None