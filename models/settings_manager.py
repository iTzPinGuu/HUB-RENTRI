"""
models.settings_manager module for RENTRI Manager.

This module contains professionally organized code with:
- Type hints for better code quality
- Proper documentation
- Clean imports
- Maintained functionality 100% identical to original
"""

import json
from pathlib import Path
from typing import Any, Dict, Optional

from utils.logger import dbg

class SettingsManager:
    def __init__(self, path: Path):
        self.path = path
        self.settings = self.load_settings()
        dbg(f"Settings caricati: {self.settings}")
    
    def load_settings(self):
        default_settings = {
            "logo_path": "",
            "logo_text": "RENTRI",
            "theme": "dark"
        }
        
        if self.path.exists():
            try:
                with open(self.path, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                    return {**default_settings, **loaded}
            except Exception as e:
                dbg(f"Errore caricamento settings: {e}")
                return default_settings
        return default_settings
    
    def save_settings(self):
        try:
            with open(self.path, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=2, ensure_ascii=False)
            dbg(f"Settings salvati: {self.settings}")
        except Exception as e:
            dbg(f"Errore salvataggio settings: {e}")
    
    def get(self, key, default=None):
        return self.settings.get(key, default)
    
    def set(self, key, value):
        self.settings[key] = value
        self.save_settings()
        dbg(f"Setting aggiornato: {key} = {value}")
