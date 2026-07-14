import os
from cryptography.fernet import Fernet
import base64

# Ensure ENCRYPTION_KEY survives server reloads
KEY_FILE = ".secret_key"
if os.path.exists(KEY_FILE):
    with open(KEY_FILE, "r") as f:
        ENCRYPTION_KEY = f.read().strip()
else:
    ENCRYPTION_KEY = Fernet.generate_key().decode("utf-8")
    with open(KEY_FILE, "w") as f:
        f.write(ENCRYPTION_KEY)

fernet = Fernet(ENCRYPTION_KEY.encode("utf-8"))

def encrypt_value(value: str) -> str:
    if not value:
        return value
    return fernet.encrypt(value.encode("utf-8")).decode("utf-8")

def decrypt_value(encrypted_value: str) -> str:
    if not encrypted_value:
        return encrypted_value
    try:
        return fernet.decrypt(encrypted_value.encode("utf-8")).decode("utf-8")
    except Exception as e:
        # Handle decryption failure gracefully, might be testing
        return ""
