"""
RENTRI API client with JWT authentication and rate limiting.

Functionality identical to original, plus:
- check_status() -> reachability of BASE_URL
- check_service_statuses() -> status for all RENTRI services provided
- CORREZIONE: formulari() con paginazione automatica per > 100 risultati
"""

import base64
import hashlib
import time
import socket
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import jwt
import requests
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import rsa, ec
from cryptography.hazmat.primitives.serialization import (
    pkcs12, Encoding, PrivateFormat, NoEncryption
)

from config.constants import (
    BASE_URL, AUDIENCE, RATE_WINDOW_SEC, RATE_MAX_5S,
    API_STATUS_TIMEOUT_S, API_STATUS_RETRY
)
from utils.logger import dbg


class RentriREST:
    def __init__(self, cfg: dict):
        self.p12 = cfg["p12"]
        self.pwd = cfg["pwd"]
        self.rag = cfg["ragione_sociale"]
        self.cf = cfg["codice_fiscale"]
        self.req_t: List[float] = []
        self.jwt_alg = None
        self.pk = None
        self.cert: Optional[x509.Certificate] = None
        self._load_p12()

    def _load_p12(self):
        for enc in ('utf-8', 'latin-1', None):
            try:
                pw = self.pwd.encode(enc) if (enc and self.pwd) else None
                pk, cert, _ = pkcs12.load_key_and_certificates(
                    Path(self.p12).read_bytes(), pw, backend=default_backend())
                self.pk, self.cert = pk, cert
                self.jwt_alg = "RS256" if isinstance(pk, rsa.RSAPrivateKey) else "ES256"
                dbg(f"Certificato caricato per CF: {self.cf}")
                return
            except Exception:
                continue
        raise RuntimeError("Certificato P12 non valido")

    def _jwt_auth(self) -> str:
        now = datetime.now(timezone.utc)
        hdr = {
            "alg": self.jwt_alg, "typ": "JWT",
            "x5c": [base64.b64encode(self.cert.public_bytes(Encoding.DER)).decode()]
        }
        pay = {
            "aud": AUDIENCE, "iss": self.cf, "sub": self.cf,
            "iat": int(now.timestamp()), "nbf": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=5)).timestamp()),
            "jti": f"auth-{int(now.timestamp()*1000)}"
        }
        key = self.pk.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()).decode()
        return jwt.encode(pay, key, algorithm=self.jwt_alg, headers=hdr)

    def _jwt_sig(self, body: bytes, ctype: str) -> Tuple[str, str]:
        dig = base64.b64encode(hashlib.sha256(body).digest()).decode()
        now = datetime.now(timezone.utc)
        hdr = {
            "alg": self.jwt_alg, "typ": "JWT",
            "x5c": [base64.b64encode(self.cert.public_bytes(Encoding.DER)).decode()]
        }
        pay = {
            "aud": AUDIENCE, "iss": self.cf, "sub": self.cf,
            "iat": int(now.timestamp()), "nbf": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=5)).timestamp()),
            "jti": f"sig-{int(now.timestamp()*1000)}",
            "signed_headers": [{"digest": f"SHA-256={dig}"}, {"content-type": ctype}]
        }
        key = self.pk.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()).decode()
        return jwt.encode(pay, key, algorithm=self.jwt_alg, headers=hdr), f"SHA-256={dig}"

    def _slot(self):
        t = time.time()
        self.req_t = [x for x in self.req_t if t - x < RATE_WINDOW_SEC]
        if len(self.req_t) >= RATE_MAX_5S:
            time.sleep(RATE_WINDOW_SEC - (t - self.req_t[0]) + 0.05)
        self.req_t.append(time.time())

    def _call(self, meth, url, **kw):
        self._slot()
        r = meth(url, **kw, timeout=30)
        if r.status_code == 429:
            dbg("HTTP 429 – sleep 10s")
            time.sleep(10)
            self._slot()
            r = meth(url, **kw, timeout=30)
        return r

    # Public API
    
    def blocchi(self):
        """Recupera tutti i blocchi vidimazione per il CF corrente"""
        h = {"Authorization": f"Bearer {self._jwt_auth()}"}
        r = self._call(requests.get, f"{BASE_URL}/vidimazione-formulari/v1.0",
                      headers=h, params={"identificativo": self.cf})
        return r.json() if r.ok else []

    def formulari(self, blocco):
        """
        CORREZIONE: Recupera TUTTI i formulari di un blocco con paginazione automatica.
        
        L'API RENTRI restituisce max 100 formulari per chiamata.
        Questo metodo fa chiamate multiple per recuperare tutti i formulari.
        
        Args:
            blocco: Codice del blocco vidimazione
            
        Returns:
            Lista completa di tutti i formulari (può contenere > 100 elementi)
        """
        all_formulari = []
        page = 1
        page_size = 100  # Max consentito dall'API RENTRI
        
        while True:
            # Headers con paginazione
            h = {
                "Authorization": f"Bearer {self._jwt_auth()}",
                "Paging-Page": str(page),
                "Paging-PageSize": str(page_size)
            }
            
            url = f"{BASE_URL}/vidimazione-formulari/v1.0/{blocco}"
            
            try:
                r = self._call(requests.get, url, headers=h)
                
                if r.ok:
                    formulari_page = r.json()
                    
                    # Se la risposta non è una lista, prova a estrarre i dati
                    if isinstance(formulari_page, dict):
                        formulari_page = formulari_page.get('data', formulari_page.get('items', []))
                    
                    # Se la pagina è vuota, abbiamo finito
                    if not formulari_page or len(formulari_page) == 0:
                        break
                    
                    all_formulari.extend(formulari_page)
                    
                    dbg(f"📄 Pagina {page} blocco {blocco}: {len(formulari_page)} FIR (totale: {len(all_formulari)})")
                    
                    # Se abbiamo ricevuto meno di page_size, è l'ultima pagina
                    if len(formulari_page) < page_size:
                        break
                    
                    # Vai alla pagina successiva
                    page += 1
                    
                else:
                    dbg(f"❌ Errore API pagina {page}: {r.status_code} - {r.text}")
                    break
                    
            except Exception as e:
                dbg(f"❌ Errore durante paginazione blocco {blocco} pagina {page}: {e}")
                break
        
        dbg(f"✅ Totale FIR caricati per blocco {blocco}: {len(all_formulari)}")
        return all_formulari

    def post_vidima(self, blocco):
        """Effettua una vidimazione per il blocco specificato"""
        tok = self._jwt_auth()
        sig, dig = self._jwt_sig(b"", "application/json; charset=utf-8")
        h = {
            "Authorization": f"Bearer {tok}", "Agid-JWT-Signature": sig,
            "Digest": dig, "Content-Type": "application/json; charset=utf-8"
        }
        r = self._call(requests.post, f"{BASE_URL}/vidimazione-formulari/v1.0/{blocco}", headers=h)
        return r.ok

    def dl_pdf(self, blocco, prog, nfir, outdir):
        """Scarica il PDF di un formulario"""
        h = {"Authorization": f"Bearer {self._jwt_auth()}", "Accept": "application/json"}
        r = self._call(requests.get, f"{BASE_URL}/vidimazione-formulari/v1.0/{blocco}/{prog}/pdf", headers=h)
        
        if not r.ok:
            dbg(f"Errore download PDF: {r.status_code} - {r.text}")
            return False
        
        try:
            json_resp = r.json()
            b64 = json_resp.get("content", "")
            if not b64:
                dbg("Nessun contenuto base64 nel PDF")
                return False
            
            filename = f"{nfir.replace('/','-').replace(' ','_')}.pdf"
            Path(outdir, filename).write_bytes(base64.b64decode(b64))
            dbg(f"PDF salvato: {filename}")
            return True
            
        except Exception as e:
            dbg(f"Errore parsing PDF: {e}")
            return False

    def annulla_fir(self, codice_blocco, progressivo):
        """Annulla un FIR vidimato"""
        try:
            tok = self._jwt_auth()
            sig, dig = self._jwt_sig(b"", "application/json; charset=utf-8")
            h = {
                "Authorization": f"Bearer {tok}",
                "Agid-JWT-Signature": sig,
                "Digest": dig,
                "Content-Type": "application/json; charset=utf-8",
                "Accept": "application/problem+json, application/json"
            }
            
            r = self._call(
                requests.put,
                f"{BASE_URL}/vidimazione-formulari/v1.0/{codice_blocco}/{progressivo}/annulla",
                headers=h
            )
            
            dbg(f"Annullamento FIR {codice_blocco}/{progressivo}: {r.status_code}")
            return r.ok, r.status_code, r.text
            
        except Exception as e:
            dbg(f"Errore annullamento FIR {codice_blocco}/{progressivo}: {e}")
            return False, 500, str(e)

    def verify_fir_exists(self, numero_fir):
        """Verifica l'esistenza di un FIR"""
        try:
            h = {"Authorization": f"Bearer {self._jwt_auth()}"}
            r = self._call(requests.get, f"{BASE_URL}/vidimazione-formulari/v1.0/verifica/{numero_fir}", headers=h)
            return r.json() if r.ok else None
        except Exception as e:
            dbg(f"Errore verifica FIR {numero_fir}: {e}")
            return None

    # NEW: Stato BASE_URL
    
    def check_status(self) -> dict:
        """Verifica la raggiungibilità del BASE_URL"""
        host = BASE_URL.replace("https://", "").split("/")[0]
        t0 = time.perf_counter()
        note = []
        
        # TCP check
        try:
            ip = socket.gethostbyname(host)
            s = socket.create_connection((ip, 443), timeout=API_STATUS_TIMEOUT_S)
            s.close()
            note.append("TCP_OK")
        except Exception as e:
            return {"reachable": False, "http_code": None, "latency_ms": None, "note": f"TCP_FAIL:{e}"}
        
        # HTTP check
        http_code = None
        for _ in range(API_STATUS_RETRY + 1):
            try:
                try:
                    r = requests.head(BASE_URL, timeout=API_STATUS_TIMEOUT_S)
                except Exception:
                    r = requests.get(BASE_URL, timeout=API_STATUS_TIMEOUT_S)
                http_code = r.status_code
                break
            except Exception as e:
                note.append(f"HTTP_RETRY:{e}")
        
        dt = int((time.perf_counter() - t0) * 1000)
        up_codes = {200, 301, 302, 400, 401, 403, 404, 405}
        reachable = http_code in up_codes
        
        if reachable:
            note.append("HTTP_OK")
        else:
            note.append(f"HTTP_CODE:{http_code}")
        
        return {
            "reachable": reachable,
            "http_code": http_code,
            "latency_ms": dt,
            "note": ",".join(note)
        }

    # NEW: Stato dei servizi specifici /status
    
    def check_service_statuses(self) -> Dict[str, dict]:
        """
        Interroga tutti gli endpoint /status richiesti (no auth).
        Ritorna: { service_name: {code:int|None, latency_ms:int|None, ok:bool, error:str|None} }
        """
        services = {
            "formulari": f"{BASE_URL}/formulari/v1.0/status",
            "vidimazione-formulari": f"{BASE_URL}/vidimazione-formulari/v1.0/status",
            "dati-registri": f"{BASE_URL}/dati-registri/v1.0/status",
            "codifiche": f"{BASE_URL}/codifiche/v1.0/status",
            "ca-rentri": f"{BASE_URL}/ca-rentri/v1.0/status",
            "anagrafiche": f"{BASE_URL}/anagrafiche/v1.0/status",
        }
        
        out: Dict[str, dict] = {}
        for name, url in services.items():
            out[name] = self._status_get(url)
        return out

    def _status_get(self, url: str) -> dict:
        """Helper per controllare un singolo endpoint /status"""
        t0 = time.perf_counter()
        try:
            r = requests.get(url, timeout=API_STATUS_TIMEOUT_S)
            dt = int((time.perf_counter() - t0) * 1000)
            code = r.status_code
            ok = 200 <= code < 300
            return {"code": code, "latency_ms": dt, "ok": ok, "error": None}
        except Exception as e:
            return {"code": None, "latency_ms": None, "ok": False, "error": str(e)}
