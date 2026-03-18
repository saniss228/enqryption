from __future__ import annotations

import base64
from pathlib import Path
from typing import Dict, Optional

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

from .config import settings

PRIVATE_KEY_FILE = settings.data_dir / "private_key.bin"


def derive_master_fernet_key(password: str) -> bytes:
    kdf = Scrypt(
        salt=settings.encryption_salt.encode(),
        length=32,
        n=2**14,
        r=8,
        p=1,
    )
    return base64.urlsafe_b64encode(kdf.derive(password.encode()))


class EncryptionError(Exception):
    pass


class EncryptionKeyStore:
    def __init__(self, master_password: str):
        self._master_password = master_password
        self._fernet = Fernet(derive_master_fernet_key(master_password))
        self._private_key: Optional[rsa.RSAPrivateKey] = None
        self._public_key_cache: Dict[str, rsa.RSAPublicKey] = {}
        self.load_or_initialize()

    def load_or_initialize(self) -> None:
        if PRIVATE_KEY_FILE.exists():
            encrypted = PRIVATE_KEY_FILE.read_bytes()
            try:
                raw = self._fernet.decrypt(encrypted)
            except InvalidToken as exc:
                raise EncryptionError("Incorrect key password.") from exc
            self._private_key = serialization.load_pem_private_key(raw, password=None)
        else:
            self._private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
            self.save_private_key()

    def save_private_key(self) -> None:
        if not self._private_key:
            raise EncryptionError("Private key not initialized.")
        raw = self._private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
        encrypted = self._fernet.encrypt(raw)
        PRIVATE_KEY_FILE.write_bytes(encrypted)

    def public_key_pem(self) -> str:
        if not self._private_key:
            raise EncryptionError("Private key missing.")
        pem = self._private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        return pem.decode()

    def set_friend_public_key(self, nick: str, pem: str) -> None:
        if not pem:
            return
        key = serialization.load_pem_public_key(pem.encode())
        self._public_key_cache[nick] = key

    def encrypt_for(self, nick: str, plaintext: str) -> str:
        key = self._public_key_cache.get(nick)
        if not key:
            raise EncryptionError("Recipient public key unknown.")
        ciphertext = key.encrypt(
            plaintext.encode(),
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None,
            ),
        )
        return base64.b64encode(ciphertext).decode()

    def decrypt(self, ciphertext: str) -> str:
        if not self._private_key:
            raise EncryptionError("Private key missing.")
        raw = base64.b64decode(ciphertext)
        plaintext = self._private_key.decrypt(
            raw,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None,
            ),
        )
        return plaintext.decode()
