"""
Configuration and constants for RENTRI Manager.

This module contains all application-wide constants including:
- File paths
- API endpoints
- Rate limiting configuration
- Color scheme
- Application metadata
"""

from pathlib import Path

# File paths
CONF_FILE = Path("fornitori.json")
SETTINGS_FILE = Path("settings.json")

# API Configuration
BASE_URL = "https://api.rentri.gov.it"
AUDIENCE = "rentrigov.api"

# Rate limiting
RATE_WINDOW_SEC = 5
RATE_MAX_5S = 90

# Application metadata
APP_TITLE = "RENTRI Manager - Complete Edition"
APP_VERSION = "2.0"

# Modern color palette (identica)
COLORS = {
    "primary": "#1f538d",
    "secondary": "#14375e",
    "accent": "#00d4aa",
    "success": "#00b894",
    "warning": "#fdcb6e",
    "error": "#e17055",
    "text": "#2d3436",
    "bg": "#dfe6e9",
    "card": "#ffffff",
    "sidebar": "#2d3436"
}

# Theme settings
DEFAULT_THEME = "dark"
DEFAULT_COLOR_THEME = "blue"

# NEW: Timeout e tentativi per verifica stato API
API_STATUS_TIMEOUT_S = 5
API_STATUS_RETRY = 1  # tentativo extra rapido

# NEW: Altezza massima del logo (ridimensionato proporzionalmente, nessun crop)
LOGO_MAX_HEIGHT = 120
