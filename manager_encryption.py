import base64
import os
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.hashes import SHA256
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from functools import lru_cache

from utility import timer

class EncryptionManager:
    def __init__(self, password: str):
        if len(password) < 3:
            raise ValueError("Password must be at least 14 characters.")
        self.password = password.encode('utf-8')
        # Pre-compute common salt and key
        self._common_salt = os.urandom(16)
        self._common_key = self._derive_key(self._common_salt)
        self._key_cache = {}

    @lru_cache(maxsize=1000)
    def _derive_key(self, salt: bytes) -> bytes:
        kdf = PBKDF2HMAC(
            algorithm=SHA256(),
            length=32,
            salt=salt,
            iterations=100_000,
            backend=default_backend(),
        )
        return kdf.derive(self.password)

    @timer
    def encrypt_string(self, plain_text: str, critical: bool = False) -> str:
        # Handle empty or whitespace strings
        if not plain_text or plain_text.isspace():
            plain_text = " "  # Use single space as minimum content

        # Use pre-computed key for non-critical operations
        if not critical:
            salt = self._common_salt
            key = self._common_key
        else:
            salt = os.urandom(16)
            key = self._derive_key(salt)

        iv = os.urandom(16)
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
        encryptor = cipher.encryptor()

        # Convert string to bytes and pad to block size
        data = plain_text.encode('utf-8')
        padding_length = 16 - (len(data) % 16)
        padded_data = data + bytes([padding_length] * padding_length)

        encrypted_data = encryptor.update(padded_data) + encryptor.finalize()
        combined_data = salt + iv + encrypted_data
        return base64.b64encode(combined_data).decode('utf-8')

    @timer
    def decrypt_string(self, encrypted_text: str) -> str:
        if not encrypted_text or encrypted_text.isspace():
            return ""

        try:
            combined_data = base64.b64decode(encrypted_text)
            salt = combined_data[:16]
            iv = combined_data[16:32]
            ciphertext = combined_data[32:]

            key = self._derive_key(salt)
            cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
            decryptor = cipher.decryptor()

            decrypted_data = decryptor.update(ciphertext) + decryptor.finalize()
            padding_length = decrypted_data[-1]
            
            # Validate padding
            if padding_length > 16:
                raise ValueError("Invalid padding")
                
            return decrypted_data[:-padding_length].decode('utf-8')
            
        except Exception as e:
            print(f"Decryption error: {str(e)}")
            return ""  # Return empty string on error