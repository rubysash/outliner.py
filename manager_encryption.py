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
        """
        Initialize EncryptionManager with a user-provided password.
        """
        if len(password) < 3:
            raise ValueError("Password must be at least 14 characters.")
        self.password = password.encode('utf-8')  # Convert password to bytes

    @timer
    @lru_cache(maxsize=1000)  # Cache up to 1000 salt-key pairs
    def _derive_key(self, salt: bytes) -> bytes:
        """
        Derive a 256-bit key from the password and salt using PBKDF2.
        """
        kdf = PBKDF2HMAC(
            algorithm=SHA256(),
            length=32,
            salt=salt,
            iterations=100_000,
            backend=default_backend(),
        )
        return kdf.derive(self.password)

    @timer
    def encrypt_string(self, plain_text: str) -> str:
        if not plain_text:  # Handle empty input
            plain_text = " "  # Default to a single space
        salt = os.urandom(16)
        key = self._derive_key(salt)
        iv = os.urandom(16)
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
        encryptor = cipher.encryptor()

        # Apply PKCS7 padding
        padding_length = 16 - (len(plain_text) % 16)
        padded_text = plain_text + chr(padding_length) * padding_length

        encrypted_data = encryptor.update(padded_text.encode('utf-8')) + encryptor.finalize()
        combined_data = salt + iv + encrypted_data
        #print(f"Encrypting: Salt={salt.hex()}, IV={iv.hex()}, Padded Text={padded_text}")
        return base64.b64encode(combined_data).decode('utf-8')

    @timer
    def decrypt_string(self, encrypted_text: str) -> str:
        if not encrypted_text:
            return ""  # Handle empty input
        combined_data = base64.b64decode(encrypted_text)
        salt = combined_data[:16]
        iv = combined_data[16:32]
        ciphertext = combined_data[32:]

        key = self._derive_key(salt)
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
        decryptor = cipher.decryptor()

        decrypted_data = decryptor.update(ciphertext) + decryptor.finalize()

        # Remove PKCS7 padding
        padding_length = decrypted_data[-1]
        result = decrypted_data[:-padding_length].decode('utf-8')
        #print(f"Decrypting: Salt={salt.hex()}, IV={iv.hex()}, Result={result}")
        return result

