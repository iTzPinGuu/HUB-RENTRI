#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RENTRI Manager - Main Entry Point

Complete Edition with Certificate Management + Gestione FIR
Version: 2.0 (Refactored)
Author: Giovanni Pio Familiari
"""

import sys
from tkinter import messagebox

from ui.main_window import ModernRentriManager


def main() -> None:
    """
    Main entry point of the application.

    Initializes and runs the RENTRI Manager application.
    Handles fatal errors with user notification.
    """
    try:
        app = ModernRentriManager()
        app.run()
    except Exception as e:
        messagebox.showerror(
            "Errore Fatale",
            f"Errore durante l'avvio dell'applicazione:\n{str(e)}"
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
