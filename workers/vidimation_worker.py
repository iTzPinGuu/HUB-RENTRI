"""
workers.vidimation_worker module for RENTRI Manager.

This module contains professionally organized code with:
- Type hints for better code quality
- Proper documentation
- Clean imports
- Cancellation support
"""

import threading
import queue
import time
import traceback
from typing import Any
from api.rentri_client import RentriREST
from utils.logger import dbg


class Worker(threading.Thread):
    """Worker per gestire la vidimazione con supporto per cancellazione"""
    
    def __init__(self, rest: RentriREST, blocco: str, quanti: int,
                 out_dir: str, q: queue.Queue):
        super().__init__(daemon=True)
        self.rest = rest
        self.blocco = blocco
        self.n = quanti
        self.out = out_dir
        self.q = q
        
        # CORREZIONE: Aggiungi flag per cancellazione
        self._stop_event = threading.Event()
        self._is_cancelled = False
    
    def cancel(self):
        """Richiede la cancellazione del worker"""
        dbg("🛑 Richiesta cancellazione vidimazione")
        self._stop_event.set()
        self._is_cancelled = True
        self.q.put(("cancelled", "Operazione annullata dall'utente"))
    
    def is_cancelled(self) -> bool:
        """Verifica se è stata richiesta la cancellazione"""
        return self._stop_event.is_set()
    
    def run(self):
        try:
            # Snapshot iniziale
            if self.is_cancelled():
                return
            
            self.q.put(("msg", "Snapshot iniziale blocco…"))
            prima = {str(f.get("progressivo")) for f in self.rest.formulari(self.blocco)}
            
            # POST vidimazioni
            vidimazioni_ok = 0
            for i in range(self.n):
                # CORREZIONE: Controlla cancellazione PRIMA di ogni operazione
                if self.is_cancelled():
                    self.q.put(("cancelled", f"Annullato dopo {vidimazioni_ok} vidimazioni"))
                    return
                
                self.q.put(("msg", f"POST vidimazione {i+1}/{self.n}"))
                ok = self.rest.post_vidima(self.blocco)
                if ok:
                    vidimazioni_ok += 1
                self.q.put(("post_inc", ok))
                
                # CORREZIONE: Sleep interrompibile (controlla ogni 100ms per 2 secondi totali)
                for _ in range(20):
                    if self.is_cancelled():
                        self.q.put(("cancelled", f"Annullato dopo {vidimazioni_ok} vidimazioni"))
                        return
                    time.sleep(0.1)
            
            # Attesa registrazione
            if self.is_cancelled():
                return
            
            self.q.put(("msg", f"Attesa 8 s per registrazione ({vidimazioni_ok} vidimazioni riuscite)…"))
            
            # CORREZIONE: Sleep interrompibile per 8 secondi
            for _ in range(80):
                if self.is_cancelled():
                    self.q.put(("cancelled", "Annullato durante attesa registrazione"))
                    return
                time.sleep(0.1)
            
            # Recupera nuovi formulari
            if self.is_cancelled():
                return
            
            after = self.rest.formulari(self.blocco)
            nuovi = [f for f in after if str(f.get("progressivo")) not in prima]
            nuovi.sort(key=lambda x: int(x.get("progressivo", 0)), reverse=True)
            nuovi = nuovi[:vidimazioni_ok]
            
            self.q.put(("pdf_max", len(nuovi)))
            
            # Download PDF
            pdf_ok = 0
            for i, f in enumerate(nuovi):
                # CORREZIONE: Controlla cancellazione
                if self.is_cancelled():
                    self.q.put(("cancelled", f"Annullato dopo {pdf_ok} PDF scaricati"))
                    return
                
                prog = f.get("progressivo")
                nfir = f.get("numero_fir", f"{prog}")
                self.q.put(("msg", f"Scarico PDF {i+1}/{len(nuovi)} – {nfir}"))
                ok = self.rest.dl_pdf(self.blocco, prog, nfir, self.out)
                if ok:
                    pdf_ok += 1
                self.q.put(("pdf_inc", ok))
                
                # CORREZIONE: Sleep interrompibile
                for _ in range(10):
                    if self.is_cancelled():
                        self.q.put(("cancelled", f"Annullato dopo {pdf_ok} PDF scaricati"))
                        return
                    time.sleep(0.1)
            
            # Completato con successo
            if not self.is_cancelled():
                self.q.put(("done", f"Completato: {vidimazioni_ok} vidimazioni, {pdf_ok} PDF scaricati"))
        
        except Exception as e:
            traceback.print_exc()
            self.q.put(("err", str(e)))
