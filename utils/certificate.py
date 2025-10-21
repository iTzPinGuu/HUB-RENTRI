"""
Certificate utility functions for RENTRI Manager.

Handles PKCS#12 certificate operations including:
- Extraction of organization name and fiscal code
- Certificate date validation
- Expiration checking
"""

import re
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.hazmat.backends import default_backend

from .logger import dbg


def estrai_ragione_sociale(cert: x509.Certificate) -> str:
    """
    Extract organization name from certificate.

    Args:
        cert: X.509 certificate object

    Returns:
        Organization name or "Sconosciuto" if not found
    """
    for oid in (NameOID.ORGANIZATION_NAME, NameOID.COMMON_NAME):
        try:
            return cert.subject.get_attributes_for_oid(oid)[0].value
        except Exception:
            pass
    return "Sconosciuto"


def estrai_codice_fiscale(cert: x509.Certificate) -> str:
    """
    Extract fiscal code from certificate.

    Tries multiple patterns:
    - CF:IT-XXXXXXXXXXX
    - IT-XXXXXXXXXXX
    - 16-character alphanumeric code
    - 11-digit numeric code

    Args:
        cert: X.509 certificate object

    Returns:
        Fiscal code or empty string if not found
    """
    testo = cert.subject.rfc4514_string()

    # Pattern CF:IT-XXXXXXXXXXX o IT-XXXXXXXXXXX
    m = re.search(r"CF:IT-([A-Z0-9]{11,16})", testo)
    if m:
        return m.group(1)

    m = re.search(r"IT-([A-Z0-9]{11,16})", testo)
    if m:
        return m.group(1)

    # Codice fiscale 16 caratteri alfanumerici
    m = re.search(r"\b([A-Z]{6}[0-9]{2}[A-Z][0-9]{2}[A-Z][0-9]{3}[A-Z])\b", testo)
    if m:
        return m.group(1)

    # Codice fiscale 11 cifre numeriche
    m = re.search(r"\b(\d{11})\b", testo)
    if m:
        return m.group(1)

    # Cerca nel campo SERIAL_NUMBER
    try:
        serial = cert.subject.get_attributes_for_oid(NameOID.SERIAL_NUMBER)[0].value
        m = re.search(r"\b([A-Z0-9]{11,16})\b", serial)
        if m:
            return m.group(1)
    except Exception:
        pass

    return ""


def get_certificate_dates(cert_path: str, password: str) -> Tuple[Optional[datetime], Optional[datetime]]:
    """
    Extract issue and expiration dates from certificate.

    Args:
        cert_path: Path to P12 certificate file
        password: Certificate password

    Returns:
        Tuple of (not_before, not_after) datetime objects, or (None, None) on error
    """
    try:
        pw = password.encode() if password else None
        pk, cert, _ = pkcs12.load_key_and_certificates(
            Path(cert_path).read_bytes(), pw, backend=default_backend()
        )

        not_before = cert.not_valid_before
        not_after = cert.not_valid_after

        return not_before, not_after
    except Exception as e:
        dbg(f"Errore estrazione date certificato: {e}")
        return None, None


def format_date(date_obj: Optional[datetime]) -> str:
    """
    Format datetime object for display.

    Args:
        date_obj: Datetime object to format

    Returns:
        Formatted date string (DD/MM/YYYY) or "N/A"
    """
    if date_obj is None:
        return "N/A"
    return date_obj.strftime("%d/%m/%Y")


def is_certificate_expired(cert_path: str, password: str) -> bool:
    """
    Check if certificate is expired.

    Args:
        cert_path: Path to P12 certificate file
        password: Certificate password

    Returns:
        True if expired or invalid, False otherwise
    """
    try:
        _, not_after = get_certificate_dates(cert_path, password)
        if not_after is None:
            return True
        return datetime.now() > not_after.replace(tzinfo=None)
    except Exception:
        return True
