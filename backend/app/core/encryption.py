from cryptography.fernet import Fernet
from sqlalchemy.types import String, TypeDecorator

from .config import settings

cipher = Fernet(settings.FERNET_KEY.encode())


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
