import threading
import webbrowser
import customtkinter as ctk
from tkinter import messagebox
from typing import Optional, Dict

from config.constants import COLORS
from api.rentri_client import RentriREST

DOCS_URL = "https://api.rentri.gov.it/docs?page=home"

# Mappatura severità per colore (non cambia la palette)
def _color_for_code(code: Optional[int]) -> str:
    if code is None:
        return "gray"
    if 200 <= code < 300:
        return COLORS["success"]  # verde
    if code in (301, 302, 304) or code == 429 or code == 423:
        return COLORS["warning"]  # giallo
    if 300 <= code < 400:
        return COLORS["warning"]
    if 400 <= code < 500:
        # 4xx: in generale richieste client; non è “down” ma segnaliamo in giallo
        return COLORS["warning"]
    return COLORS["error"]  # 5xx rosso

# Legenda sintetica (puoi mostrare questo testo in basso)
LEGEND_LINES = [
    "200-299: OK (verde)",
    "301/302/304: Redirect/Not Modified (giallo, non è down)",
    "400: Richiesta non valida (giallo, controllare il client)",
    "401: Non autenticato (giallo)",
    "403: Proibito/permessi (giallo)",
    "404: Non trovato (giallo se atteso; rosso solo per /status non esistente)",
    "405: Metodo non consentito (giallo)",
    "409: Conflitto (giallo)",
    "412: Precondition Failed (giallo)",
    "415: Unsupported Media Type (giallo)",
    "423: Troppe richieste non valide dall’Issuer (ban parziale, giallo)",
    "429: Too Many Requests (rate limit, giallo)",
    "500/502/503/504: Errore server / servizio non disponibile (rosso)"
]

class APIStatusView(ctk.CTkFrame):
    """Vista per verifica stato API RENTRI (BASE_URL + servizi /status)."""
    def __init__(self, parent, rest_client: Optional[RentriREST]):
        super().__init__(parent)
        self.rest = rest_client
        self.grid_columnconfigure(0, weight=1)

        title = ctk.CTkLabel(self, text="🩺 Stato API RENTRI", font=ctk.CTkFont(size=32, weight="bold"))
        title.grid(row=0, column=0, sticky="w", pady=(0, 20))

        # Stato BASE_URL
        self.base_status = ctk.CTkLabel(self, text="Stato base: premi “Controlla tutti”", font=ctk.CTkFont(size=14))
        self.base_status.grid(row=1, column=0, sticky="w", pady=(0, 10))

        # Tabella servizi
        self.table = ctk.CTkScrollableFrame(self, label_text="Servizi /status")
        self.table.grid(row=2, column=0, sticky="nsew", pady=(0, 10))
        self.table.grid_columnconfigure(0, weight=1)
        self._rows: Dict[str, Dict[str, ctk.CTkLabel]] = {}
        self._ensure_rows()

        # Azioni
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=3, column=0, sticky="w", pady=(10, 10))
        check_btn = ctk.CTkButton(btn_frame, text="🔎 Controlla tutti", command=self.check_all, height=36)
        check_btn.pack(side="left", padx=(0, 10))
        docs_btn = ctk.CTkButton(btn_frame, text="📖 Documentazione", command=lambda: webbrowser.open(DOCS_URL), height=36)
        docs_btn.pack(side="left")

        # Legenda
        legend_text = "\n".join(LEGEND_LINES)
        self.legend = ctk.CTkTextbox(self, height=140)
        self.legend.grid(row=4, column=0, sticky="ew")
        self.legend.insert("1.0", legend_text)
        self.legend.configure(state="disabled")

    def _ensure_rows(self):
        services = [
            ("formulari", "Formulari"),
            ("vidimazione-formulari", "Vidimazione formulari"),
            ("dati-registri", "Dati registri"),
            ("codifiche", "Codifiche"),
            ("ca-rentri", "CA RENTRI"),
            ("anagrafiche", "Anagrafiche"),
        ]
        for i, (key, label) in enumerate(services):
            row = ctk.CTkFrame(self.table)
            row.pack(fill="x", padx=10, pady=3)
            name = ctk.CTkLabel(row, text=label, font=ctk.CTkFont(size=14, weight="bold"))
            name.pack(side="left")
            status = ctk.CTkLabel(row, text="—", font=ctk.CTkFont(size=14))
            status.pack(side="left", padx=10)
            lat = ctk.CTkLabel(row, text="", font=ctk.CTkFont(size=12), text_color="gray")
            lat.pack(side="right")
            self._rows[key] = {"status": status, "lat": lat}

    def check_all(self):
        if not self.rest:
            messagebox.showwarning("Attenzione", "Nessun fornitore selezionato. I test verranno eseguiti in modalità pubblica.")
        self.base_status.configure(text="Verifica BASE_URL in corso…")
        for key, widgets in self._rows.items():
            widgets["status"].configure(text="…", text_color="gray")
            widgets["lat"].configure(text="")
        threading.Thread(target=self._do_check_all, daemon=True).start()

    def _do_check_all(self):
        try:
            # BASE_URL
            base = self.rest.check_status() if self.rest else {"reachable": False, "http_code": None, "latency_ms": None, "note": "NO_CLIENT"}
            base_color = COLORS["success"] if base.get("reachable") else COLORS["error"]
            base_txt = f"Stato base: {'ONLINE' if base.get('reachable') else 'OFFLINE'} • HTTP: {base.get('http_code')} • Latenza: {base.get('latency_ms')} ms • Note: {base.get('note')}"
            self.base_status.configure(text=base_txt, text_color=base_color)

            # SERVIZI /status
            results = self.rest.check_service_statuses() if self.rest else {}
            for key, widgets in self._rows.items():
                r = results.get(key, {"code": None, "latency_ms": None, "ok": False})
                code = r.get("code")
                color = _color_for_code(code)
                txt = f"{code if code is not None else '—'}"
                widgets["status"].configure(text=txt, text_color=color)
                lat = r.get("latency_ms")
                widgets["lat"].configure(text=f"{lat} ms" if lat is not None else "")
        except Exception as e:
            self.base_status.configure(text=f"Errore verifica: {e}", text_color=COLORS["error"])
