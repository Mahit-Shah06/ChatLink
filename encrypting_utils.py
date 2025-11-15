import os
from cryptography.fernet import Fernet

class crypting:
    def __init__(self):
        MASTER_KEY = os.getenv("MASTER_KEY")
        self.fernet = Fernet(MASTER_KEY)

    def encrypting(self, api_key):
        return self.fernet.encrypt(api_key.encode())
    
    def decrypting(self, encrypted_api_key):
        return self.fernet.decrypt(encrypted_api_key).decode()