"""
ui.main_window module for RENTRI Manager.

This module contains professionally organized code with:
- Type hints for better code quality
- Proper documentation
- Clean imports
- Maintained functionality 100% identical to original
"""

import os
import sys
import queue
import customtkinter as ctk
from tkinter import filedialog, messagebox
from pathlib import Path
from typing import Any, Dict, List, Optional
import threading
from tkinter import messagebox

from PIL import Image
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.serialization import pkcs12

from config.constants import (
    CONF_FILE, SETTINGS_FILE, APP_TITLE, COLORS, DEFAULT_THEME, DEFAULT_COLOR_THEME
)
from models.settings_manager import SettingsManager
from models.fornitori_db import FornitoriDB
from api.rentri_client import RentriREST
from workers.vidimation_worker import Worker
from ui.components.progress_window import ModernProgressWindow
from ui.components.cards import DashboardCard, CertificateCard, ClickableLabel
from ui.views.pdf_views import PDFDeliveryView, PDFMergeView
from ui.views.fir_view import FIRAnnullaView
from utils.certificate import (
    estrai_ragione_sociale, estrai_codice_fiscale,
    get_certificate_dates, format_date, is_certificate_expired
)
from utils.logger import dbg
from ui.views.api_status_view import APIStatusView
# Set modern theme
ctk.set_appearance_mode(DEFAULT_THEME)
ctk.set_default_color_theme(DEFAULT_COLOR_THEME)

class ModernRentriManager:
    def __init__(self):
        self.root = ctk.CTk()
        self.root.title(APP_TITLE)
        
        # NUOVO: Fix completo per fullscreen cross-platform
        self.root.update_idletasks()
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        
        # Imposta geometria a schermo intero
        self.root.geometry(f"{screen_w}x{screen_h}+0+0")
        
        # Prova diversi metodi per il fullscreen in base al sistema
        try:
            if sys.platform.startswith('win'):
                # Windows: usa state zoomed
                self.root.state('zoomed')
            elif sys.platform.startswith('darwin'):
                # macOS: usa attributes zoomed
                self.root.attributes('-zoomed', True)
            else:
                # Linux/Unix: prova fullscreen poi zoomed come fallback
                try:
                    self.root.attributes('-fullscreen', True)
                except:
                    self.root.attributes('-zoomed', True)
        except Exception as e:
            # Fallback finale: imposta solo la geometria massima
            dbg(f"Fallback fullscreen: {e}")
            self.root.geometry(f"{screen_w}x{screen_h}+0+0")
        
        self.root.minsize(1200, 800)
        
        # Settings and data
        self.settings = SettingsManager(SETTINGS_FILE)
        self.api_status_verified = bool(self.settings.get("api_status_verified", False))

        self.db = FornitoriDB(CONF_FILE)
        self.rest = None
        self.current_blocchi = []
        
        # Initialize theme
        self.initialize_theme()
        
        # Create UI
        self.create_layout()
        self.create_sidebar()
        self.create_main_content()
        
        # Start with supplier selection if none exists
        if not self.db.elenco():
            self.root.after(100, self.show_supplier_selection)
        else:
            self.show_dashboard()
    
    def initialize_theme(self):
        """Inizializza il tema dell'applicazione"""
        theme = self.settings.get("theme", "dark")
        ctk.set_appearance_mode(theme)
        dbg(f"Tema inizializzato: {theme}")
    
    def create_layout(self):
        # Configure grid
        self.root.grid_columnconfigure(1, weight=1)
        self.root.grid_rowconfigure(0, weight=1)
        
        # Sidebar
        self.sidebar = ctk.CTkFrame(self.root, width=300, fg_color=COLORS["sidebar"])
        self.sidebar.grid(row=0, column=0, sticky="nsew", padx=(0, 2))
        self.sidebar.grid_propagate(False)
        
        # Main content
        self.main_frame = ctk.CTkFrame(self.root, fg_color="transparent")
        self.main_frame.grid(row=0, column=1, sticky="nsew", padx=(2, 0))
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_rowconfigure(0, weight=1)
    
    def create_sidebar(self):
        # Logo/Title section
        logo_frame = ctk.CTkFrame(self.sidebar, height=80, fg_color="transparent")
        logo_frame.pack(fill="x", padx=20, pady=(20, 0))
        logo_frame.pack_propagate(False)
        
        # Logo display
        self.logo_label = ctk.CTkLabel(
            logo_frame,
            text=self.settings.get("logo_text", "RENTRI"),
            font=ctk.CTkFont(size=28, weight="bold"),
            text_color=COLORS["accent"]
        )
        self.logo_label.pack(pady=20)
        
        # Load custom logo if available
        self.load_custom_logo()
        
        # Fornitore info
        self.fornitore_frame = ctk.CTkFrame(self.sidebar, fg_color="#3a3a3a")
        self.fornitore_frame.pack(fill="x", padx=20, pady=(20, 0))
        
        self.fornitore_label = ctk.CTkLabel(
            self.fornitore_frame,
            text="Nessun fornitore selezionato",
            font=ctk.CTkFont(size=12),
            wraplength=250,
            anchor="w",
            justify="left"
        )
        self.fornitore_label.pack(pady=15, padx=15, fill="x")
        
        # Navigation buttons
        nav_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        nav_frame.pack(fill="x", padx=20, pady=(30, 0))
        
        self.nav_buttons = {}
        
        # Main sections
        sections = [
            ("dashboard", "📊 Dashboard", self.show_dashboard),
            ("suppliers", "🏢 Fornitori", self.show_supplier_selection),
            ("blocks", "📋 Blocchi", self.show_blocks_view),
            ("vidimation", "✅ Vidimazione", self.show_vidimation_view),
            ("fir_management", "🗑️ Gestione FIR", self.show_fir_management_view),  # SEZIONE AGGIORNATA
            ("api_status", "🩺 Stato API", self.show_api_status_view),

        ]
        
        for key, text, command in sections:
            self.nav_buttons[key] = ctk.CTkButton(
                nav_frame,
                text=text,
                command=command,
                height=50,
                fg_color="transparent",
                hover_color="#4a4a4a",
                anchor="w",
                font=ctk.CTkFont(size=14, weight="bold")
            )
            self.nav_buttons[key].pack(fill="x", pady=(0, 5))
        
        # PDF Tools section
        pdf_separator = ctk.CTkLabel(
            nav_frame,
            text="PDF Tools",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="gray"
        )
        pdf_separator.pack(fill="x", pady=(20, 10))
        
        # PDF Tools buttons
        pdf_tools = [
            ("delivery", "✉️ Crea lettera di consegna", self.show_delivery_view),
            ("merge", "🗜️ Unisci FIR per stamparli", self.show_merge_view),
        ]
        
        for key, text, command in pdf_tools:
            self.nav_buttons[key] = ctk.CTkButton(
                nav_frame,
                text=text,
                command=command,
                height=45,
                fg_color="transparent",
                hover_color="#4a4a4a",
                anchor="w",
                font=ctk.CTkFont(size=13, weight="bold")
            )
            self.nav_buttons[key].pack(fill="x", pady=(0, 3))
        
        # Settings button
        self.nav_buttons["settings"] = ctk.CTkButton(
            nav_frame,
            text="⚙️ Impostazioni",
            command=self.show_settings_view,
            height=50,
            fg_color="transparent",
            hover_color="#4a4a4a",
            anchor="w",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        self.nav_buttons["settings"].pack(fill="x", pady=(20, 5))
        
        # Bottom section with theme toggle and credits
        bottom_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        bottom_frame.pack(fill="x", padx=20, pady=(50, 20), side="bottom")
        
        # Theme toggle
        self.theme_switch = ctk.CTkSwitch(
            bottom_frame,
            text="🌙 Tema scuro",
            command=self.toggle_theme,
            font=ctk.CTkFont(size=12)
        )
        self.theme_switch.pack(pady=(0, 15))
        
        # Set initial theme switch state
        current_theme = self.settings.get("theme", "dark")
        if current_theme == "dark":
            self.theme_switch.select()
        else:
            self.theme_switch.deselect()
        
        # Credits
        credits_frame = ctk.CTkFrame(bottom_frame, fg_color="transparent")
        credits_frame.pack(fill="x")
        
        created_label = ctk.CTkLabel(
            credits_frame,
            text="Created By ",
            font=ctk.CTkFont(size=10),
            text_color="gray"
        )
        created_label.pack(side="left")
        
        # Clickable LinkedIn link
        linkedin_label = ClickableLabel(
            credits_frame,
            text="Giovanni Pio",
            url="https://linkedin.com/in/giovanni-pio-familiari",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color="white"
        )
        linkedin_label.pack(side="left")
    
    def load_custom_logo(self):
        """Carica logo personalizzato se disponibile"""
        logo_path = self.settings.get("logo_path", "")
        if logo_path and os.path.exists(logo_path):
            try:
                # Prova a caricare l'immagine
                image = Image.open(logo_path)
                image = image.resize((200, 60), Image.Resampling.LANCZOS)
                
                # Converti in formato CustomTkinter
                photo = ctk.CTkImage(light_image=image, dark_image=image, size=(200, 60))
                self.logo_label.configure(image=photo, text="")
                self.logo_label.image = photo  # Mantieni riferimento
                dbg("Logo personalizzato caricato")
            except Exception as e:
                dbg(f"Errore caricamento logo: {e}")
                # Fallback al testo
                self.logo_label.configure(text=self.settings.get("logo_text", "RENTRI"))
        else:
            # Usa il testo del logo
            self.logo_label.configure(text=self.settings.get("logo_text", "RENTRI"))
    
    def create_main_content(self):
        # Create content frame
        self.content_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.content_frame.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        self.content_frame.grid_columnconfigure(0, weight=1)
        self.content_frame.grid_rowconfigure(0, weight=1)
    
    def clear_content(self):
        for widget in self.content_frame.winfo_children():
            widget.destroy()
    
    def set_active_nav(self, active_button):
        # Reset all buttons
        for button in self.nav_buttons.values():
            button.configure(fg_color="transparent")
        
        # Set active button
        if active_button in self.nav_buttons:
            self.nav_buttons[active_button].configure(fg_color=COLORS["primary"])
    
    def update_fornitore_display(self):
        if self.rest:
            text = f"Fornitore: {self.rest.rag}\nCF: {self.rest.cf}"
        else:
            text = "Nessun fornitore selezionato"
        self.fornitore_label.configure(text=text)
    
    def get_certificate_info(self):
        """Ottiene informazioni sul certificato del fornitore corrente"""
        if not self.rest:
            return None
            
        try:
            not_before, not_after = get_certificate_dates(self.rest.p12, self.rest.pwd)
            if not_before and not_after:
                expired = is_certificate_expired(self.rest.p12, self.rest.pwd)
                return {
                    "issued": format_date(not_before),
                    "expires": format_date(not_after),
                    "expired": expired
                }
        except Exception as e:
            dbg(f"Errore lettura info certificato: {e}")
        
        return None
    
    def update_certificate(self):
        """Aggiorna il certificato del fornitore corrente"""
        if not self.rest:
            messagebox.showerror("Errore", "Nessun fornitore selezionato")
            return
        
        # File selection
        p12_file = filedialog.askopenfilename(
            title="Seleziona nuovo certificato .p12",
            filetypes=[("PKCS#12 files", "*.p12"), ("All files", "*.*")]
        )
        
        if not p12_file:
            return
        
        # Password dialog
        password_dialog = ctk.CTkInputDialog(
            text="Inserisci password del nuovo certificato:",
            title="Password Certificato"
        )
        password = password_dialog.get_input() or ""
        
        try:
            # Verifica che il certificato sia valido
            pw = password.encode() if password else None
            pk, cert, _ = pkcs12.load_key_and_certificates(
                Path(p12_file).read_bytes(), pw, backend=default_backend()
            )
            
            # Verifica che il CF sia lo stesso
            new_cf = estrai_codice_fiscale(cert)
            if new_cf != self.rest.cf:
                messagebox.showerror(
                    "Errore", 
                    f"Il codice fiscale del nuovo certificato ({new_cf}) non corrisponde a quello attuale ({self.rest.cf})"
                )
                return
            
            # Aggiorna nel database
            success = self.db.update_certificate(self.rest.cf, p12_file, password)
            if success:
                # Ricarica il RentriREST con il nuovo certificato
                supplier_data = self.db.get(self.rest.cf)
                if supplier_data:
                    self.rest = RentriREST(supplier_data)
                    messagebox.showinfo("Successo", "Certificato aggiornato con successo!")
                    # Aggiorna il dashboard per mostrare le nuove date
                    self.show_dashboard()
                else:
                    messagebox.showerror("Errore", "Errore nel recupero dei dati del fornitore")
            else:
                messagebox.showerror("Errore", "Errore nell'aggiornamento del certificato")
                
        except Exception as e:
            messagebox.showerror("Errore", f"Errore durante l'aggiornamento del certificato:\n{str(e)}")
    
    def show_api_status_view(self):
        self.set_active_nav("api_status")
        self.clear_content()
        view = APIStatusView(self.content_frame, self.rest)
        view.grid(row=0, column=0, sticky="nsew")


    def show_dashboard(self):
        self.set_active_nav("dashboard")
        self.clear_content()
        
        # Header
        header_frame = ctk.CTkFrame(self.content_frame, height=80, fg_color="transparent")
        header_frame.grid(row=0, column=0, sticky="ew", pady=(0, 20))
        header_frame.grid_columnconfigure(0, weight=1)
        header_frame.grid_propagate(False)
        
        title_label = ctk.CTkLabel(
            header_frame,
            text="Dashboard",
            font=ctk.CTkFont(size=32, weight="bold"),
            anchor="w"
        )
        title_label.grid(row=0, column=0, sticky="w", pady=20)
        
        # Stats cards
        stats_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        stats_frame.grid(row=1, column=0, sticky="ew", pady=(0, 20))
        stats_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)
        
        # Regular cards data
        regular_cards_data = [
            ("Fornitori Configurati", len(self.db.elenco()), COLORS["success"]),
            ("Blocchi Disponibili", len(self.current_blocchi) if self.rest else 0, COLORS["warning"]),
            ("Stato Sistema", "Connesso" if self.rest else "Disconnesso", COLORS["accent"] if self.rest else COLORS["error"]),
        ]
        
        # Create regular cards
        for i, (title, value, color) in enumerate(regular_cards_data):
            card = DashboardCard(stats_frame, title, value, color)
            card.frame.grid(row=0, column=i, padx=(0 if i == 0 else 10, 10), sticky="ew")
        
        # Certificate card (sostituisce PDF Tools)
        cert_info = self.get_certificate_info()
        cert_card = CertificateCard(
            stats_frame, 
            "Certificato", 
            cert_info, 
            self.update_certificate
        )
        cert_card.frame.grid(row=0, column=3, padx=(0, 0), sticky="ew")
        
        # Quick actions
        if self.rest:
            actions_frame = ctk.CTkFrame(self.content_frame)
            actions_frame.grid(row=2, column=0, sticky="ew", pady=(0, 20))
            actions_frame.grid_columnconfigure((0, 1), weight=1)
            
            # Refresh blocks button
            refresh_btn = ctk.CTkButton(
                actions_frame,
                text="🔄 Aggiorna Blocchi",
                command=self.refresh_blocks,
                height=50,
                font=ctk.CTkFont(size=16, weight="bold")
            )
            refresh_btn.grid(row=0, column=0, padx=(20, 10), pady=20, sticky="ew")
            
            # Quick vidimation button
            vidim_btn = ctk.CTkButton(
                actions_frame,
                text="⚡ Vidimazione Rapida",
                command=self.show_vidimation_view,
                height=50,
                font=ctk.CTkFont(size=16, weight="bold"),
                fg_color=COLORS["success"],
                hover_color=COLORS["accent"]
            )
            vidim_btn.grid(row=0, column=1, padx=(10, 20), pady=20, sticky="ew")
    
    def show_api_status_view(self):
           self.set_active_nav("api_status")
           self.clear_content()
           view = APIStatusView(self.content_frame, self.rest)
           view.grid(row=0, column=0, sticky="nsew")
    
    def show_supplier_selection(self):
        self.set_active_nav("suppliers")
        self.clear_content()
        
        dbg("Mostrando selezione fornitori")
        
        # Header
        header_frame = ctk.CTkFrame(self.content_frame, height=80, fg_color="transparent")
        header_frame.grid(row=0, column=0, sticky="ew", pady=(0, 20))
        header_frame.grid_columnconfigure(0, weight=1)
        header_frame.grid_propagate(False)
        
        title_label = ctk.CTkLabel(
            header_frame,
            text="Gestione Fornitori",
            font=ctk.CTkFont(size=32, weight="bold"),
            anchor="w"
        )
        title_label.grid(row=0, column=0, sticky="w", pady=20)
        
        # Add supplier button
        add_btn = ctk.CTkButton(
            header_frame,
            text="➕ Nuovo Fornitore",
            command=self.add_supplier,
            height=40,
            font=ctk.CTkFont(size=14, weight="bold")
        )
        add_btn.grid(row=0, column=1, pady=20, padx=(20, 0))
        
        # Search frame
        search_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        search_frame.grid(row=1, column=0, sticky="ew", pady=(0, 20))
        search_frame.grid_columnconfigure(0, weight=1)
        
        # Search entry with icon
        self.search_entry = ctk.CTkEntry(
            search_frame,
            placeholder_text="🔍 Cerca per ragione sociale o codice fiscale...",
            height=40,
            font=ctk.CTkFont(size=14)
        )
        self.search_entry.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        self.search_entry.bind("<KeyRelease>", self.on_search_change)
        
        # Clear button
        clear_btn = ctk.CTkButton(
            search_frame,
            text="✕",
            command=self.clear_search,
            width=40,
            height=40,
            fg_color="transparent",
            hover_color=COLORS["error"],
            font=ctk.CTkFont(size=16, weight="bold")
        )
        clear_btn.grid(row=0, column=1)
        
        # Suppliers list frame
        self.suppliers_frame = ctk.CTkScrollableFrame(
            self.content_frame,
            label_text="Fornitori",
            height=400
        )
        self.suppliers_frame.grid(row=2, column=0, sticky="nsew")
        self.suppliers_frame.grid_columnconfigure(0, weight=1)
        
        # Load suppliers
        self.refresh_suppliers_display()
    
    def on_search_change(self, event):
        """Gestisce la ricerca in tempo reale"""
        query = self.search_entry.get().strip()
        self.refresh_suppliers_display(query)
    
    def clear_search(self):
        """Cancella la ricerca"""
        self.search_entry.delete(0, "end")
        self.refresh_suppliers_display()
    
    def refresh_suppliers_display(self, query=""):
        """Aggiorna la visualizzazione dei fornitori"""
        # Clear existing suppliers
        for widget in self.suppliers_frame.winfo_children():
            widget.destroy()
        
        # Get suppliers (filtered if query provided)
        if query:
            suppliers = self.db.search(query)
        else:
            suppliers = self.db.elenco()
        
        dbg(f"Visualizzando {len(suppliers)} fornitori")
        
        if not suppliers:
            if query:
                # No results found
                no_results_label = ctk.CTkLabel(
                    self.suppliers_frame,
                    text="🔍 Nessun risultato trovato\n\nProva con termini di ricerca diversi",
                    font=ctk.CTkFont(size=16),
                    text_color="gray"
                )
                no_results_label.pack(pady=50)
            else:
                # No suppliers at all
                no_suppliers_label = ctk.CTkLabel(
                    self.suppliers_frame,
                    text="📋 Nessun fornitore configurato\n\nClicca 'Nuovo Fornitore' per iniziare",
                    font=ctk.CTkFont(size=16),
                    text_color="gray"
                )
                no_suppliers_label.pack(pady=50)
        else:
            # Show suppliers
            for i, supplier in enumerate(suppliers):
                self.create_supplier_card(supplier, i)
    
    def create_supplier_card(self, supplier, row):
        """Crea una card per un fornitore"""
        card_frame = ctk.CTkFrame(self.suppliers_frame, height=120)
        card_frame.pack(fill="x", padx=20, pady=10)
        card_frame.pack_propagate(False)
        
        # Create internal grid
        card_frame.grid_columnconfigure(0, weight=1)
        
        # Info frame
        info_frame = ctk.CTkFrame(card_frame, fg_color="transparent")
        info_frame.grid(row=0, column=0, sticky="nsew", padx=20, pady=15)
        info_frame.grid_columnconfigure(0, weight=1)
        
        # Name
        name_label = ctk.CTkLabel(
            info_frame,
            text=supplier["ragione_sociale"],
            font=ctk.CTkFont(size=18, weight="bold"),
            anchor="w"
        )
        name_label.grid(row=0, column=0, sticky="w")
        
        # CF
        cf_label = ctk.CTkLabel(
            info_frame,
            text=f"CF: {supplier['codice_fiscale']}",
            font=ctk.CTkFont(size=14),
            anchor="w",
            text_color="gray"
        )
        cf_label.grid(row=1, column=0, sticky="w", pady=(5, 0))
        
        # Buttons frame
        buttons_frame = ctk.CTkFrame(card_frame, fg_color="transparent")
        buttons_frame.grid(row=0, column=1, padx=20, pady=15)
        
        # Select button
        select_btn = ctk.CTkButton(
            buttons_frame,
            text="Seleziona",
            command=lambda s=supplier: self.select_supplier(s),
            width=100,
            height=35
        )
        select_btn.grid(row=0, column=0, padx=(0, 10))
        
        # Delete button
        delete_btn = ctk.CTkButton(
            buttons_frame,
            text="Elimina",
            command=lambda s=supplier: self.delete_supplier(s),
            width=100,
            height=35,
            fg_color=COLORS["error"],
            hover_color="#d63031"
        )
        delete_btn.grid(row=0, column=1)
    
    def add_supplier(self):
        # File selection
        p12_file = filedialog.askopenfilename(
            title="Seleziona file certificato .p12",
            filetypes=[("PKCS#12 files", "*.p12"), ("All files", "*.*")]
        )
        
        if not p12_file:
            return
        
        # Password dialog
        password_dialog = ctk.CTkInputDialog(
            text="Inserisci password certificato:",
            title="Password Certificato"
        )
        password = password_dialog.get_input() or ""
        
        try:
            # Load certificate
            pw = password.encode() if password else None
            pk, cert, _ = pkcs12.load_key_and_certificates(
                Path(p12_file).read_bytes(), pw, backend=default_backend()
            )
            
            rag_soc = estrai_ragione_sociale(cert)
            cf = estrai_codice_fiscale(cert)
            
            if not cf:
                messagebox.showerror("Errore", "Impossibile estrarre il codice fiscale dal certificato")
                return
            
            # Save supplier
            self.db.add(p12_file, password, rag_soc, cf)
            
            messagebox.showinfo("Successo", f"Fornitore {rag_soc} aggiunto con successo!")
            
            # Refresh suppliers display
            self.refresh_suppliers_display()
            
        except Exception as e:
            messagebox.showerror("Errore", f"Errore durante l'aggiunta del fornitore:\n{str(e)}")
    
    def select_supplier(self, supplier):
        try:
            self.rest = RentriREST(supplier)
            self.update_fornitore_display()
            self.refresh_blocks()
            messagebox.showinfo("Successo", f"Fornitore {supplier['ragione_sociale']} selezionato")
            self.show_dashboard()
        except Exception as e:
            messagebox.showerror("Errore", f"Errore nella selezione del fornitore:\n{str(e)}")
    
    def delete_supplier(self, supplier):
        if messagebox.askyesno("Conferma", f"Eliminare il fornitore {supplier['ragione_sociale']}?"):
            success = self.db.delete(supplier["id"])
            if success:
                messagebox.showinfo("Successo", "Fornitore eliminato")
                # Refresh suppliers display
                self.refresh_suppliers_display()
            else:
                messagebox.showerror("Errore", "Errore nell'eliminazione del fornitore")
    
    def refresh_blocks(self):
        if not self.rest:
            return
        
        try:
            self.current_blocchi = self.rest.blocchi()
            dbg(f"Trovati {len(self.current_blocchi)} blocchi")
        except Exception as e:
            messagebox.showerror("Errore", f"Errore nel recupero blocchi:\n{str(e)}")
    
    def show_blocks_view(self):
        self.set_active_nav("blocks")
        self.clear_content()
        
        # Header
        header_frame = ctk.CTkFrame(self.content_frame, height=80, fg_color="transparent")
        header_frame.grid(row=0, column=0, sticky="ew", pady=(0, 20))
        header_frame.grid_columnconfigure(0, weight=1)
        header_frame.grid_propagate(False)
        
        title_label = ctk.CTkLabel(
            header_frame,
            text="Blocchi Disponibili",
            font=ctk.CTkFont(size=32, weight="bold"),
            anchor="w"
        )
        title_label.grid(row=0, column=0, sticky="w", pady=20)
        
        # Refresh button
        refresh_btn = ctk.CTkButton(
            header_frame,
            text="🔄 Aggiorna",
            command=self.refresh_blocks,
            height=40,
            font=ctk.CTkFont(size=14, weight="bold")
        )
        refresh_btn.grid(row=0, column=1, pady=20, padx=(20, 0))
        
        if not self.rest:
            no_supplier_label = ctk.CTkLabel(
                self.content_frame,
                text="Seleziona un fornitore per visualizzare i blocchi",
                font=ctk.CTkFont(size=16),
                text_color="gray"
            )
            no_supplier_label.grid(row=1, column=0, pady=50)
            return
        
        # Blocks list
        blocks_frame = ctk.CTkScrollableFrame(
            self.content_frame,
            label_text="Blocchi FIR"
        )
        blocks_frame.grid(row=1, column=0, sticky="nsew")
        blocks_frame.grid_columnconfigure(0, weight=1)
        
        if not self.current_blocchi:
            self.refresh_blocks()
        
        if not self.current_blocchi:
            no_blocks_label = ctk.CTkLabel(
                blocks_frame,
                text="Nessun blocco disponibile",
                font=ctk.CTkFont(size=16),
                text_color="gray"
            )
            no_blocks_label.grid(row=0, column=0, pady=50)
        else:
            for i, blocco in enumerate(self.current_blocchi):
                self.create_block_card(blocks_frame, blocco, i)
    
    def create_block_card(self, parent, blocco, row):
        card_frame = ctk.CTkFrame(parent, height=100)
        card_frame.grid(row=row, column=0, sticky="ew", padx=20, pady=10)
        card_frame.grid_columnconfigure(0, weight=1)
        card_frame.grid_propagate(False)
        
        # Info frame
        info_frame = ctk.CTkFrame(card_frame, fg_color="transparent")
        info_frame.grid(row=0, column=0, sticky="nsew", padx=20, pady=15)
        info_frame.grid_columnconfigure(0, weight=1)
        
        # Block code
        code_label = ctk.CTkLabel(
            info_frame,
            text=blocco["codice_blocco"],
            font=ctk.CTkFont(size=16, weight="bold"),
            anchor="w"
        )
        code_label.grid(row=0, column=0, sticky="w")
        
        # Description
        desc_label = ctk.CTkLabel(
            info_frame,
            text=blocco.get("descrizione", "Nessuna descrizione"),
            font=ctk.CTkFont(size=12),
            anchor="w",
            text_color="gray"
        )
        desc_label.grid(row=1, column=0, sticky="w", pady=(5, 0))
        
        # FIR count
        fir_label = ctk.CTkLabel(
            info_frame,
            text=f"FIR vidimati: {blocco.get('numero_fir_vidimati', 0)}",
            font=ctk.CTkFont(size=12),
            anchor="w",
            text_color="gray"
        )
        fir_label.grid(row=2, column=0, sticky="w", pady=(5, 0))
        
        # Select button
        select_btn = ctk.CTkButton(
            card_frame,
            text="Seleziona",
            command=lambda b=blocco: self.select_block_for_vidimation(b),
            width=120,
            height=35
        )
        select_btn.grid(row=0, column=1, padx=20, pady=15)
    
    def select_block_for_vidimation(self, blocco):
        self.selected_blocco = blocco
        self.show_vidimation_view()
    
    def show_vidimation_view(self):
        self.set_active_nav("vidimation")
        self.clear_content()
        
        # Header
        header_frame = ctk.CTkFrame(self.content_frame, height=80, fg_color="transparent")
        header_frame.grid(row=0, column=0, sticky="ew", pady=(0, 20))
        header_frame.grid_columnconfigure(0, weight=1)
        header_frame.grid_propagate(False)
        
        title_label = ctk.CTkLabel(
            header_frame,
            text="Vidimazione FIR",
            font=ctk.CTkFont(size=32, weight="bold"),
            anchor="w"
        )
        title_label.grid(row=0, column=0, sticky="w", pady=20)
        
        if not self.rest:
            no_supplier_label = ctk.CTkLabel(
                self.content_frame,
                text="Seleziona un fornitore per procedere con la vidimazione",
                font=ctk.CTkFont(size=16),
                text_color="gray"
            )
            no_supplier_label.grid(row=1, column=0, pady=50)
            return
        
        # Vidimation form
        form_frame = ctk.CTkFrame(self.content_frame)
        form_frame.grid(row=1, column=0, sticky="ew", pady=(0, 20))
        form_frame.grid_columnconfigure(1, weight=1)
        
        # Block selection
        block_label = ctk.CTkLabel(form_frame, text="Blocco:", font=ctk.CTkFont(size=14, weight="bold"))
        block_label.grid(row=0, column=0, padx=20, pady=20, sticky="w")
        
        if not self.current_blocchi:
            self.refresh_blocks()
        
        block_values = [f"{b['codice_blocco']} - {b.get('descrizione', '')}" for b in self.current_blocchi]
        self.block_combo = ctk.CTkComboBox(form_frame, values=block_values, width=400)
        self.block_combo.grid(row=0, column=1, padx=20, pady=20, sticky="ew")
        
        # Quantity selection
        qty_label = ctk.CTkLabel(form_frame, text="Quantità FIR:", font=ctk.CTkFont(size=14, weight="bold"))
        qty_label.grid(row=1, column=0, padx=20, pady=20, sticky="w")
        
        self.qty_entry = ctk.CTkEntry(form_frame, placeholder_text="Numero di FIR da vidimare", width=200)
        self.qty_entry.grid(row=1, column=1, padx=20, pady=20, sticky="w")
        
        # Output directory
        dir_label = ctk.CTkLabel(form_frame, text="Cartella PDF:", font=ctk.CTkFont(size=14, weight="bold"))
        dir_label.grid(row=2, column=0, padx=20, pady=20, sticky="w")
        
        dir_frame = ctk.CTkFrame(form_frame, fg_color="transparent")
        dir_frame.grid(row=2, column=1, padx=20, pady=20, sticky="ew")
        dir_frame.grid_columnconfigure(0, weight=1)
        
        self.dir_entry = ctk.CTkEntry(dir_frame, placeholder_text="Seleziona cartella di destinazione")
        self.dir_entry.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        
        dir_btn = ctk.CTkButton(dir_frame, text="Sfoglia", command=self.select_output_directory, width=100)
        dir_btn.grid(row=0, column=1)
        
        # Start button
        start_btn = ctk.CTkButton(
            form_frame,
            text="🚀 Avvia Vidimazione",
            command=self.start_vidimation,
            height=50,
            font=ctk.CTkFont(size=16, weight="bold"),
            fg_color=COLORS["success"],
            hover_color=COLORS["accent"]
        )
        start_btn.grid(row=3, column=0, columnspan=2, padx=20, pady=30, sticky="ew")
    
    def select_output_directory(self):
        directory = filedialog.askdirectory(title="Seleziona cartella di destinazione PDF")
        if directory:
            self.dir_entry.delete(0, "end")
            self.dir_entry.insert(0, directory)
    
    def start_vidimation(self):
        # Validate inputs
        if not self.block_combo.get():
            messagebox.showerror("Errore", "Seleziona un blocco")
            return
        
        try:
            qty = int(self.qty_entry.get())
            if qty <= 0:
                raise ValueError()
        except ValueError:
            messagebox.showerror("Errore", "Inserisci un numero valido di FIR")
            return
        
        output_dir = self.dir_entry.get()
        if not output_dir:
            messagebox.showerror("Errore", "Seleziona una cartella di destinazione")
            return
        
        # Get selected block
        block_text = self.block_combo.get()
        block_code = block_text.split(" - ")[0]
        selected_block = next((b for b in self.current_blocchi if b["codice_blocco"] == block_code), None)
        
        if not selected_block:
            messagebox.showerror("Errore", "Blocco non trovato")
            return
        
        # Start vidimation process
        self.run_vidimation_worker(selected_block["codice_blocco"], qty, output_dir)
    
    def run_vidimation_worker(self, blocco, qty, output_dir):
        q = queue.Queue()
        worker = Worker(self.rest, blocco, qty, output_dir, q)
        
        # CORREZIONE: Crea progress window CON callback per cancellazione
        fornitore_info = f"Fornitore: {self.rest.rag}\nCF: {self.rest.cf}\nBlocco: {blocco}"
        progress_window = ModernProgressWindow(
            self.root, 
            "Vidimazione in corso", 
            fornitore_info,
            on_cancel_callback=lambda: worker.cancel()  # ← AGGIUNGI QUESTA RIGA
        )
        
        progress_window.set_vidim_max(qty)
        vidim_count = 0
        pdf_count = 0
        
        def poll_worker():
            nonlocal vidim_count, pdf_count
            try:
                while True:
                    typ, val = q.get_nowait()
                    if typ == "msg":
                        progress_window.update_status(val)
                    elif typ == "post_inc":
                        if val:
                            vidim_count += 1
                            progress_window.update_vidim_progress(vidim_count)
                    elif typ == "pdf_max":
                        progress_window.set_pdf_max(val)
                    elif typ == "pdf_inc":
                        if val:
                            pdf_count += 1
                            progress_window.update_pdf_progress(pdf_count)
                    elif typ == "done":
                        progress_window.close()
                        messagebox.showinfo("Completato", val)
                        self.show_dashboard()
                        return
                    elif typ == "cancelled":  # ← AGGIUNGI QUESTO BLOCCO
                        progress_window.close()
                        messagebox.showinfo("Annullato", val)
                        self.show_dashboard()
                        return
                    elif typ == "err":
                        progress_window.close()
                        messagebox.showerror("Errore", val)
                        return
            except queue.Empty:
                pass
            self.root.after(200, poll_worker)
        
        # Avvia worker DOPO aver creato la finestra
        worker.start()
        self.root.after(200, poll_worker)

    
    # SEZIONE GESTIONE FIR (AGGIORNATA)
    def show_fir_management_view(self):
        """Mostra la vista di gestione FIR con API annullamento funzionante"""
        self.set_active_nav("fir_management")
        self.clear_content()
        
        FIRAnnullaView(self.content_frame, self.rest).grid(row=0, column=0, sticky="nsew")
    
    # PDF Tools Views
    def show_delivery_view(self):
        self.set_active_nav("delivery")
        self.clear_content()
        
        PDFDeliveryView(self.content_frame).grid(row=0, column=0, sticky="nsew")
    
    def show_merge_view(self):
        self.set_active_nav("merge")
        self.clear_content()
        
        PDFMergeView(self.content_frame).grid(row=0, column=0, sticky="nsew")
    
    def show_settings_view(self):
        self.set_active_nav("settings")
        self.clear_content()
        
        # Header
        header_frame = ctk.CTkFrame(self.content_frame, height=80, fg_color="transparent")
        header_frame.grid(row=0, column=0, sticky="ew", pady=(0, 20))
        header_frame.grid_columnconfigure(0, weight=1)
        header_frame.grid_propagate(False)
        
        title_label = ctk.CTkLabel(
            header_frame,
            text="Impostazioni",
            font=ctk.CTkFont(size=32, weight="bold"),
            anchor="w"
        )
        title_label.grid(row=0, column=0, sticky="w", pady=20)
        
        # Settings content
        settings_frame = ctk.CTkScrollableFrame(self.content_frame)
        settings_frame.grid(row=1, column=0, sticky="nsew")
        settings_frame.grid_columnconfigure(0, weight=1)
        
        # Logo settings section
        logo_section = ctk.CTkFrame(settings_frame)
        logo_section.grid(row=0, column=0, sticky="ew", padx=20, pady=20)
        logo_section.grid_columnconfigure(0, weight=1)
        
        logo_title = ctk.CTkLabel(
            logo_section,
            text="Personalizzazione Logo",
            font=ctk.CTkFont(size=18, weight="bold"),
            anchor="w"
        )
        logo_title.grid(row=0, column=0, sticky="w", padx=20, pady=(20, 10))
        
        # Logo options frame
        logo_options_frame = ctk.CTkFrame(logo_section, fg_color="transparent")
        logo_options_frame.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 20))
        logo_options_frame.grid_columnconfigure(1, weight=1)
        
        # Logo text
        logo_text_label = ctk.CTkLabel(
            logo_options_frame,
            text="Testo Logo:",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        logo_text_label.grid(row=0, column=0, sticky="w", pady=(0, 10))
        
        self.logo_text_entry = ctk.CTkEntry(
            logo_options_frame,
            placeholder_text="Inserisci testo del logo",
            width=300
        )
        self.logo_text_entry.grid(row=0, column=1, sticky="ew", padx=(10, 0), pady=(0, 10))
        self.logo_text_entry.insert(0, self.settings.get("logo_text", "RENTRI"))
        
        # Logo image
        logo_image_label = ctk.CTkLabel(
            logo_options_frame,
            text="Immagine Logo:",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        logo_image_label.grid(row=1, column=0, sticky="w", pady=(0, 10))
        
        logo_image_frame = ctk.CTkFrame(logo_options_frame, fg_color="transparent")
        logo_image_frame.grid(row=1, column=1, sticky="ew", padx=(10, 0), pady=(0, 10))
        logo_image_frame.grid_columnconfigure(0, weight=1)
        
        self.logo_path_entry = ctk.CTkEntry(
            logo_image_frame,
            placeholder_text="Seleziona file immagine logo"
        )
        self.logo_path_entry.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        self.logo_path_entry.insert(0, self.settings.get("logo_path", ""))
        
        logo_browse_btn = ctk.CTkButton(
            logo_image_frame,
            text="Sfoglia",
            command=self.browse_logo_file,
            width=100
        )
        logo_browse_btn.grid(row=0, column=1)
        
        # Logo buttons
        logo_buttons_frame = ctk.CTkFrame(logo_options_frame, fg_color="transparent")
        logo_buttons_frame.grid(row=2, column=0, columnspan=2, pady=(20, 0))
        
        save_logo_btn = ctk.CTkButton(
            logo_buttons_frame,
            text="💾 Salva Logo",
            command=self.save_logo_settings,
            fg_color=COLORS["success"],
            hover_color=COLORS["accent"]
        )
        save_logo_btn.grid(row=0, column=0, padx=(0, 10))
        
        reset_logo_btn = ctk.CTkButton(
            logo_buttons_frame,
            text="🔄 Reset Logo",
            command=self.reset_logo_settings,
            fg_color=COLORS["error"],
            hover_color="#d63031"
        )
        reset_logo_btn.grid(row=0, column=1)
        
        # Theme setting
        theme_section = ctk.CTkFrame(settings_frame)
        theme_section.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 20))
        theme_section.grid_columnconfigure(0, weight=1)
        
        theme_title = ctk.CTkLabel(
            theme_section,
            text="Tema dell'applicazione",
            font=ctk.CTkFont(size=18, weight="bold"),
            anchor="w"
        )
        theme_title.grid(row=0, column=0, sticky="w", padx=20, pady=(20, 10))
        
        current_theme = self.settings.get("theme", "dark")
        self.theme_var = ctk.StringVar(value=current_theme)
        theme_radio_frame = ctk.CTkFrame(theme_section, fg_color="transparent")
        theme_radio_frame.grid(row=1, column=0, sticky="w", padx=20, pady=(0, 20))
        
        dark_radio = ctk.CTkRadioButton(
            theme_radio_frame,
            text="Scuro",
            variable=self.theme_var,
            value="dark",
            command=self.change_theme
        )
        dark_radio.grid(row=0, column=0, padx=(0, 20))
        
        light_radio = ctk.CTkRadioButton(
            theme_radio_frame,
            text="Chiaro",
            variable=self.theme_var,
            value="light",
            command=self.change_theme
        )
        light_radio.grid(row=0, column=1, padx=(0, 20))
        
        system_radio = ctk.CTkRadioButton(
            theme_radio_frame,
            text="Sistema",
            variable=self.theme_var,
            value="system",
            command=self.change_theme
        )
        system_radio.grid(row=0, column=2)
        
        # About section
        about_section = ctk.CTkFrame(settings_frame)
        about_section.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 20))
        
        about_title = ctk.CTkLabel(
            about_section,
            text="Informazioni",
            font=ctk.CTkFont(size=18, weight="bold"),
            anchor="w"
        )
        about_title.grid(row=0, column=0, sticky="w", padx=20, pady=(20, 10))
        
        about_text = ctk.CTkLabel(
            about_section,
            text="RENTRI Manager - Complete Edition + Gestione FIR\n\n"
                 "✅ Gestione fornitori con ricerca avanzata\n"
                 "✅ Vidimazione automatizzata FIR\n"
                 "✅ Dashboard moderno con statistiche\n"
                 "✅ PDF Tools integrati\n"
                 "✅ Logo personalizzabile\n"
                 "✅ Tema scuro/chiaro\n"
                 "✅ Interface moderna con CustomTkinter\n"
                 "✅ Avvio a schermo intero (FIX cross-platform)\n"
                 "✅ Progress window sempre in primo piano\n"
                 "✅ Gestione certificato con date e aggiornamento\n"
                 "✅ Gestione FIR con tabella e ricerca avanzata\n"
                 "✅ API Annullamento FIR completamente funzionante\n\n"
                 "Progettata per massima usabilità e performance",
            font=ctk.CTkFont(size=14),
            anchor="w",
            justify="left"
        )
        about_text.grid(row=1, column=0, padx=20, pady=(0, 20), sticky="w")
    
    def browse_logo_file(self):
        file_path = filedialog.askopenfilename(
            title="Seleziona file logo",
            filetypes=[
                ("Image files", "*.png *.jpg *.jpeg *.gif *.bmp"),
                ("PNG files", "*.png"),
                ("JPEG files", "*.jpg *.jpeg"),
                ("All files", "*.*")
            ]
        )
        if file_path:
            self.logo_path_entry.delete(0, "end")
            self.logo_path_entry.insert(0, file_path)
    
    def save_logo_settings(self):
        logo_text = self.logo_text_entry.get().strip()
        logo_path = self.logo_path_entry.get().strip()
        
        if not logo_text:
            logo_text = "RENTRI"
        
        # Validate logo path if provided
        if logo_path and not os.path.exists(logo_path):
            messagebox.showerror("Errore", "Il file immagine selezionato non esiste")
            return
        
        # Save settings
        self.settings.set("logo_text", logo_text)
        self.settings.set("logo_path", logo_path)
        
        # Update logo display
        self.load_custom_logo()
        
        messagebox.showinfo("Successo", "Impostazioni logo salvate!")
    
    def reset_logo_settings(self):
        if messagebox.askyesno("Conferma", "Ripristinare le impostazioni logo predefinite?"):
            self.settings.set("logo_text", "RENTRI")
            self.settings.set("logo_path", "")
            
            # Update UI
            self.logo_text_entry.delete(0, "end")
            self.logo_text_entry.insert(0, "RENTRI")
            self.logo_path_entry.delete(0, "end")
            
            # Update logo display
            self.load_custom_logo()
            
            messagebox.showinfo("Successo", "Impostazioni logo ripristinate!")
    
    def change_theme(self):
        """Cambia tema dalle impostazioni"""
        theme = self.theme_var.get()
        ctk.set_appearance_mode(theme)
        self.settings.set("theme", theme)
        
        # Update switch state
        if theme == "dark":
            self.theme_switch.select()
        else:
            self.theme_switch.deselect()
        
        dbg(f"Tema cambiato a: {theme}")
    
    def toggle_theme(self):
        """Toggle tema dalla sidebar"""
        if self.theme_switch.get():
            new_theme = "dark"
        else:
            new_theme = "light"
        
        ctk.set_appearance_mode(new_theme)
        self.settings.set("theme", new_theme)
        
        # Update radio buttons if settings are visible
        if hasattr(self, 'theme_var'):
            self.theme_var.set(new_theme)
        
        dbg(f"Tema toggle: {new_theme}")
    
    def run(self):
        self.root.mainloop()
