"""
ui.components.progress_window module for RENTRI Manager.

This module contains professionally organized code with:
- Type hints for better code quality
- Proper documentation
- Clean imports
- Cancellation button support
"""

import customtkinter as ctk
from tkinter import messagebox
from typing import Optional, Callable
from config.constants import COLORS


class ModernProgressWindow:
    """Finestra di progresso con supporto per cancellazione"""
    
    def __init__(self, parent, title: str, fornitore_info: str,
                 on_cancel_callback: Optional[Callable] = None):
        self.window = ctk.CTkToplevel(parent)
        self.window.title(title)
        self.window.geometry("600x500")  # Aumentato per il bottone
        self.window.resizable(True, True)
        
        # CORREZIONE: Aggiungi callback per cancellazione
        self._on_cancel_callback = on_cancel_callback
        self._is_cancelled = False
        
        # Assicura che la finestra si apra in primo piano
        self.window.lift()
        self.window.focus_force()
        
        # Centra la finestra sullo schermo
        self.window.update_idletasks()
        width = self.window.winfo_width()
        height = self.window.winfo_height()
        x = (self.window.winfo_screenwidth() // 2) - (width // 2)
        y = (self.window.winfo_screenheight() // 2) - (height // 2)
        self.window.geometry(f"{width}x{height}+{x}+{y}")
        
        # Mantieni sempre in primo piano ma permetti minimizzazione
        self.window.attributes("-topmost", True)
        try:
            self.window.wm_attributes("-toolwindow", False)
        except:
            pass
        
        # CORREZIONE: Gestisci chiusura finestra (X)
        self.window.protocol("WM_DELETE_WINDOW", self._on_close_window)
        
        self._setup_ui(title, fornitore_info)
    
    def _setup_ui(self, title: str, fornitore_info: str):
        """Crea l'interfaccia della finestra"""
        
        # Header
        header_frame = ctk.CTkFrame(self.window, height=80, fg_color=COLORS["primary"])
        header_frame.pack(fill="x", padx=0, pady=0)
        header_frame.pack_propagate(False)
        
        title_label = ctk.CTkLabel(
            header_frame,
            text=title,
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color="white"
        )
        title_label.pack(pady=20)
        
        # Content frame
        content_frame = ctk.CTkFrame(self.window, fg_color="transparent")
        content_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Fornitore info
        self.info_label = ctk.CTkLabel(
            content_frame,
            text=fornitore_info,
            font=ctk.CTkFont(size=14),
            anchor="w",
            justify="left"
        )
        self.info_label.pack(pady=(0, 20), fill="x")
        
        # Status label
        self.status_label = ctk.CTkLabel(
            content_frame,
            text="Preparazione...",
            font=ctk.CTkFont(size=16, weight="bold"),
            anchor="w"
        )
        self.status_label.pack(pady=(0, 10), fill="x")
        
        # Progress bars frame
        progress_frame = ctk.CTkFrame(content_frame, fg_color="transparent")
        progress_frame.pack(fill="x", pady=(0, 20))
        
        # Vidimazioni progress
        vidim_label = ctk.CTkLabel(
            progress_frame,
            text="Vidimazioni:",
            font=ctk.CTkFont(size=14)
        )
        vidim_label.pack(anchor="w")
        
        self.vidim_progress = ctk.CTkProgressBar(progress_frame, height=20)
        self.vidim_progress.pack(fill="x", pady=(5, 15))
        self.vidim_progress.set(0)
        
        # PDF progress
        pdf_label = ctk.CTkLabel(
            progress_frame,
            text="Download PDF:",
            font=ctk.CTkFont(size=14)
        )
        pdf_label.pack(anchor="w")
        
        self.pdf_progress = ctk.CTkProgressBar(progress_frame, height=20)
        self.pdf_progress.pack(fill="x", pady=(5, 0))
        self.pdf_progress.set(0)
        
        # Stats frame
        stats_frame = ctk.CTkFrame(content_frame)
        stats_frame.pack(fill="x", pady=(0, 20))
        
        self.stats_label = ctk.CTkLabel(
            stats_frame,
            text="Statistiche operazione",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        self.stats_label.pack(pady=10)
        
        # CORREZIONE: Bottone ANNULLA ROSSO
        self.cancel_button = ctk.CTkButton(
            content_frame,
            text="❌ ANNULLA VIDIMAZIONE",
            command=self._confirm_cancel,
            fg_color="#DC143C",  # Rosso cremisi
            hover_color="#8B0000",  # Rosso scuro
            font=ctk.CTkFont(size=16, weight="bold"),
            height=50
        )
        self.cancel_button.pack(pady=(10, 0), fill="x")
        
        self.vidim_max = 0
        self.pdf_max = 0
    
    def _confirm_cancel(self):
        """CORREZIONE: Chiede conferma prima di cancellare"""
        response = messagebox.askyesno(
            "Conferma Cancellazione",
            "Sei sicuro di voler annullare la vidimazione in corso?\n\n"
            "Le vidimazioni già completate rimarranno valide.",
            parent=self.window
        )
        
        if response:
            self._cancel_operation()
    
    def _cancel_operation(self):
        """CORREZIONE: Cancella l'operazione"""
        if not self._is_cancelled:
            self._is_cancelled = True
            self.status_label.configure(text="⚠️ Annullamento in corso...")
            self.cancel_button.configure(
                state="disabled",
                text="Annullando...",
                fg_color="gray"
            )
            
            # CORREZIONE: Chiama il callback per fermare il worker
            if self._on_cancel_callback:
                self._on_cancel_callback()
    
    def _on_close_window(self):
        """CORREZIONE: Gestisce la chiusura della finestra con la X"""
        if not self._is_cancelled:
            self._confirm_cancel()
        else:
            self.close()
    
    def update_status(self, message: str):
        """Aggiorna il messaggio di stato"""
        self.status_label.configure(text=message)
        self.window.update()
    
    def update_vidim_progress(self, value: Optional[int] = None):
        """Aggiorna la progress bar delle vidimazioni"""
        if value is not None:
            self.vidim_progress.set(value / self.vidim_max if self.vidim_max > 0 else 0)
        self.window.update()
    
    def update_pdf_progress(self, value: Optional[int] = None):
        """Aggiorna la progress bar dei PDF"""
        if value is not None:
            self.pdf_progress.set(value / self.pdf_max if self.pdf_max > 0 else 0)
        self.window.update()
    
    def set_vidim_max(self, max_val: int):
        """Imposta il massimo per le vidimazioni"""
        self.vidim_max = max_val
    
    def set_pdf_max(self, max_val: int):
        """Imposta il massimo per i PDF"""
        self.pdf_max = max_val
    
    def close(self):
        """Chiude la finestra"""
        try:
            self.window.destroy()
        except:
            pass
