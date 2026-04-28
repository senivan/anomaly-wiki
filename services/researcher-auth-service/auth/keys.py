import os
import logging
from pathlib import Path
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend

logger = logging.getLogger(__name__)

# Resolve path once from environment or fallback
DEFAULT_KEY_PATH = Path(os.getenv("AUTH_PRIVATE_KEY_PATH", "/etc/secrets/auth/rsa_private.pem")).resolve()

def generate_keys(path: Path = DEFAULT_KEY_PATH):
    """
    Helper function to generate a new RSA private key and save it to the specified path.
    """
    logger.info(f"Generating new RSA keys at {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend()
    )
    
    with open(path, "wb") as f:
        f.write(
            private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            )
        )
    return path

def load_keys(path: Path = DEFAULT_KEY_PATH):
    """
    Load keys from the specified path. Fails if the file does not exist.
    """
    if not path.exists():
        raise FileNotFoundError(
            f"Private key not found at {path}. "
            "Please ensure keys are generated and mounted correctly."
        )

    # Load private key
    with open(path, "rb") as f:
        private_key = serialization.load_pem_private_key(
            f.read(),
            password=None,
            backend=default_backend()
        )
    
    # Get public key
    public_key = private_key.public_key()
    
    # Return keys in PEM format
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    ).decode("utf-8")
    
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode("utf-8")
    
    return private_pem, public_pem
