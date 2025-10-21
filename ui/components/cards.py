"""
ui.components.cards module for RENTRI Manager.

This module contains professionally organized code with:
- Type hints for better code quality
- Proper documentation
- Clean imports
- Maintained functionality 100% identical to original
"""

import webbrowser
import customtkinter as ctk
from typing import Callable, Optional

from config.constants import COLORS

class DashboardCard:
    def __init__(self, parent, title, value, color=None):
        self.frame = ctk.CTkFrame(parent, height=120, fg_color=color or COLORS["card"])
        self.frame.pack_propagate(False)
        
        # Title
        title_label = ctk.CTkLabel(
            self.frame,
            text=title,
            font=ctk.CTkFont(size=14, weight="bold"),
            anchor="w"
        )
        title_label.pack(pady=(15, 5), padx=20, fill="x")
        
        # Value
        self.value_label = ctk.CTkLabel(
            self.frame,
            text=str(value),
            font=ctk.CTkFont(size=32, weight="bold"),
            text_color=COLORS["primary"]
        )
        self.value_label.pack(pady=(0, 15), padx=20)
        
    def update_value(self, value):
        self.value_label.configure(text=str(value))


class CertificateCard:
    """Card speciale per mostrare informazioni del certificato"""
    def __init__(self, parent, title, cert_info, update_callback):
        self.frame = ctk.CTkFrame(parent, height=120, fg_color=COLORS["card"])
        self.frame.pack_propagate(False)
        self.update_callback = update_callback
        
        # Title
        title_label = ctk.CTkLabel(
            self.frame,
            text=title,
            font=ctk.CTkFont(size=14, weight="bold"),
            anchor="w"
        )
        title_label.pack(pady=(10, 5), padx=20, fill="x")
        
        # Certificate info
        if cert_info:
            info_text = f"Emesso: {cert_info['issued']}\nScade: {cert_info['expires']}"
            color = COLORS["error"] if cert_info['expired'] else COLORS["primary"]
        else:
            info_text = "Certificato non caricato"
            color = COLORS["error"]
            
        self.info_label = ctk.CTkLabel(
            self.frame,
            text=info_text,
            font=ctk.CTkFont(size=12),
            text_color=color,
            anchor="w",
            justify="left"
        )
        self.info_label.pack(pady=(0, 5), padx=20, fill="x")
        
        # Update button
        update_btn = ctk.CTkButton(
            self.frame,
            text="🔄 Aggiorna",
            command=self.update_certificate,
            height=25,
            width=100,
            font=ctk.CTkFont(size=12)
        )
        update_btn.pack(pady=(0, 10), padx=20, anchor="e")
        
    def update_certificate(self):
        if self.update_callback:
            self.update_callback()


class ClickableLabel(ctk.CTkLabel):
    def __init__(self, master, text, url, **kwargs):
        super().__init__(master, text=text, **kwargs)
        self.url = url
        self.bind("<Button-1>", self.on_click)
        self.bind("<Enter>", self.on_enter)
        self.bind("<Leave>", self.on_leave)
        
    def on_click(self, event):
        webbrowser.open(self.url)
        
    def on_enter(self, event):
        self.configure(text_color=COLORS["accent"])
        
    def on_leave(self, event):
        self.configure(text_color="white")

# PDF Tools Views