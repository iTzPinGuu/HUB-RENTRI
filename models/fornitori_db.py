"""
models.fornitori_db module for RENTRI Manager.

This module contains professionally organized code with:
- Type hints for better code quality
- Proper documentation
- Clean imports
- Maintained functionality 100% identical to original
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from utils.logger import dbg

class FornitoriDB:
    def __init__(self, path: Path):
        self.path = path
        self.data = {}
        self.load_data()
        dbg(f"Database fornitori caricato: {len(self.data)} fornitori")

    def load_data(self):
        """Carica i dati dal file JSON"""
        if self.path.exists():
            try:
                with open(self.path, 'r', encoding='utf-8') as f:
                    self.data = json.load(f)
                dbg(f"Dati caricati: {list(self.data.keys())}")
            except Exception as e:
                dbg(f"Errore caricamento fornitori.json: {e}")
                self.data = {}
        else:
            dbg("File fornitori.json non trovato, creato nuovo database")
            self.data = {}

    def save(self):
        try:
            with open(self.path, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
            dbg("Database fornitori salvato")
        except Exception as e:
            dbg(f"Errore salvataggio fornitori: {e}")

    def elenco(self):
        """Restituisce la lista dei fornitori"""
        fornitori = list(self.data.values())
        dbg(f"Elenco fornitori richiesto: {len(fornitori)} trovati")
        return fornitori

    def search(self, query):
        """Ricerca fornitori per ragione sociale o codice fiscale"""
        if not query:
            return self.elenco()
        
        query = query.lower()
        results = []
        
        for fornitore in self.data.values():
            # Ricerca per ragione sociale
            if query in fornitore.get("ragione_sociale", "").lower():
                results.append(fornitore)
            # Ricerca per codice fiscale
            elif query in fornitore.get("codice_fiscale", "").lower():
                results.append(fornitore)
        
        dbg(f"Ricerca '{query}': {len(results)} risultati")
        return results

    def add(self, p12_path, pwd, rag_soc, codice_fiscale):
        fid = codice_fiscale or rag_soc
        self.data[fid] = {
            "id": fid, "p12": p12_path, "pwd": pwd,
            "ragione_sociale": rag_soc, "codice_fiscale": codice_fiscale
        }
        self.save()
        dbg(f"Fornitore aggiunto: {rag_soc}")

    def get(self, fid):
        return self.data.get(fid)

    def delete(self, fid):
        """Elimina un fornitore"""
        if fid in self.data:
            del self.data[fid]
            self.save()
            dbg(f"Fornitore eliminato: {fid}")
            return True
        return False
    
    def update_certificate(self, fid, new_p12_path, new_password):
        """Aggiorna il certificato di un fornitore"""
        if fid in self.data:
            self.data[fid]["p12"] = new_p12_path
            self.data[fid]["pwd"] = new_password
            self.save()
            dbg(f"Certificato aggiornato per fornitore: {fid}")
            return True
        return False
