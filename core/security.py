import os
import json
from pathlib import Path
from cryptography.fernet import Fernet
from typing import Optional


class SecurityManager:
    def __init__(self, config_dir: Optional[Path] = None):
        self.config_dir = config_dir or Path.home() / ".dalle2_app"
        self.config_dir.mkdir(exist_ok=True)
        self.key_file = self.config_dir / "key.key"
        self.config_file = self.config_dir / "config.enc"
        self._ensure_key_exists()
    
    def _ensure_key_exists(self):
        if not self.key_file.exists():
            key = Fernet.generate_key()
            with open(self.key_file, 'wb') as f:
                f.write(key)
            os.chmod(self.key_file, 0o600)
    
    def _get_cipher(self) -> Fernet:
        with open(self.key_file, 'rb') as f:
            key = f.read()
        return Fernet(key)
    
    def save_api_key(self, api_key: str) -> bool:
        try:
            cipher = self._get_cipher()
            config = {"openai_api_key": api_key}
            encrypted_data = cipher.encrypt(json.dumps(config).encode())
            
            with open(self.config_file, 'wb') as f:
                f.write(encrypted_data)
            os.chmod(self.config_file, 0o600)
            return True
        except Exception as e:
            print(f"Error saving API key: {e}")
            return False
    
    def load_api_key(self) -> Optional[str]:
        try:
            if not self.config_file.exists():
                return None
            
            cipher = self._get_cipher()
            with open(self.config_file, 'rb') as f:
                encrypted_data = f.read()
            
            decrypted_data = cipher.decrypt(encrypted_data)
            config = json.loads(decrypted_data.decode())
            return config.get("openai_api_key")
        except Exception as e:
            print(f"Error loading API key: {e}")
            return None
    
    def has_api_key(self) -> bool:
        return self.config_file.exists() and self.load_api_key() is not None
    
    def clear_api_key(self) -> bool:
        try:
            if self.config_file.exists():
                os.remove(self.config_file)
            return True
        except Exception as e:
            print(f"Error clearing API key: {e}")
            return False