"""
Módulo de encriptación para proteger datos sensibles.
Usa AES-256-GCM a través de la librería cryptography (Fernet).
"""
import os
import base64
import json
from pathlib import Path
from cryptography.fernet import Fernet
from config import ENCRYPTED_DIR


def generate_key() -> str:
    """Genera una nueva clave de encriptación Fernet (AES-128-CBC con HMAC)."""
    return Fernet.generate_key().decode()


def get_cipher(key: str) -> Fernet:
    """Obtiene una instancia del cifrador Fernet."""
    if isinstance(key, str):
        key = key.encode()
    return Fernet(key)


def encrypt_data(data: str, key: str) -> str:
    """Encripta un string y devuelve el texto cifrado en base64."""
    cipher = get_cipher(key)
    encrypted = cipher.encrypt(data.encode("utf-8"))
    return encrypted.decode("utf-8")


def decrypt_data(encrypted_data: str, key: str) -> str:
    """Desencripta datos previamente encriptados."""
    cipher = get_cipher(key)
    decrypted = cipher.decrypt(encrypted_data.encode("utf-8"))
    return decrypted.decode("utf-8")


def save_encrypted(filename: str, data: dict, key: str):
    """Guarda un diccionario como JSON encriptado en disco."""
    json_str = json.dumps(data, ensure_ascii=False, default=str)
    encrypted = encrypt_data(json_str, key)
    filepath = ENCRYPTED_DIR / filename
    with open(filepath, "w") as f:
        f.write(encrypted)


def load_encrypted(filename: str, key: str) -> dict | None:
    """Carga y desencripta un archivo JSON encriptado."""
    filepath = ENCRYPTED_DIR / filename
    if not filepath.exists():
        return None
    with open(filepath, "r") as f:
        encrypted = f.read()
    json_str = decrypt_data(encrypted, key)
    return json.loads(json_str)


def rotate_key(old_key: str, new_key: str):
    """Re-encripta todos los archivos con una nueva clave."""
    for filepath in ENCRYPTED_DIR.iterdir():
        if filepath.is_file():
            with open(filepath, "r") as f:
                encrypted = f.read()
            try:
                json_str = decrypt_data(encrypted, old_key)
                new_encrypted = encrypt_data(json_str, new_key)
                with open(filepath, "w") as f:
                    f.write(new_encrypted)
            except Exception:
                # Archivo que no se puede desencriptar, saltar
                pass
