import os
import base64
from cryptography.fernet import Fernet
from sqlalchemy.types import TypeDecorator, String

FERNET_KEY = os.getenv("FERNET_KEY")
if not FERNET_KEY:
    raise RuntimeError("FERNET_KEY debe estar definida en el entorno")

cipher = Fernet(FERNET_KEY.encode() if isinstance(FERNET_KEY, str) else FERNET_KEY)

class EncryptedString(TypeDecorator):
    impl = String
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return cipher.encrypt(value.encode()).decode()

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return cipher.decrypt(value.encode()).decode()
