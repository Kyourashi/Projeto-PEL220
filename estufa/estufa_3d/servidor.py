"""
============================================================================
 PEL220 - Projeto do grupo: estufa agrícola inteligente
----------------------------------------------------------------------------
 ESTUFA EM 3D: serve a página (web/) e o estado ATUAL da estufa, lido do Orion.

   GET /             a cena 3D (web/index.html, Three.js)
   GET /api/estado   o "agora" das três entidades do tenant estufa, em keyValues:
                     {"no": Device, "estufa": AgriGreenhouse, "clima": WeatherObserved,
                      "agora": hora do servidor}

 O navegador nunca fala com o Orion: este servidor faz a ponte, com os
 cabeçalhos do tenant. Assim não é preciso abrir CORS no Orion nem expor a
 porta 1026. O Grafana mostra o passado (MySQL); esta página mostra o
 presente (Orion), como um gêmeo digital.

 Variáveis de ambiente (padrão entre parênteses):
   ORION (http://orion:1026)  FIWARE_SERVICE (estufa)  FIWARE_SERVICEPATH (/)
   PORTA (3003)
============================================================================
"""

import json
import os
import pathlib
import urllib.error
import urllib.request
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

ORION = os.getenv("ORION", "http://orion:1026")
TENANT = {"fiware-service": os.getenv("FIWARE_SERVICE", "estufa"),
          "fiware-servicepath": os.getenv("FIWARE_SERVICEPATH", "/")}
PORTA = int(os.getenv("PORTA", "3003"))
WEB = pathlib.Path(__file__).resolve().parent / "web"
ENTIDADES = {
    "no": "urn:ngsi-ld:Device:ESP32-001",
    "estufa": "urn:ngsi-ld:AgriGreenhouse:001",
    "clima": "urn:ngsi-ld:WeatherObserved:FEI",
}


def ler(eid):
    """Uma entidade em keyValues; None se ela ainda não existe (404)."""
    pedido = urllib.request.Request(f"{ORION}/v2/entities/{eid}?options=keyValues", headers=TENANT)
    try:
        with urllib.request.urlopen(pedido, timeout=4) as resposta:
            return json.load(resposta)
    except urllib.error.HTTPError as erro:
        if erro.code == 404:
            return None
        raise


class Pagina(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB), **kwargs)

    def do_GET(self):
        if self.path.split("?")[0] == "/api/estado":
            try:
                corpo = {nome: ler(eid) for nome, eid in ENTIDADES.items()}
                corpo["agora"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
                self._json(200, corpo)
            except (OSError, ValueError) as erro:             # Orion fora do ar ou resposta estranha
                self._json(502, {"erro": f"Orion indisponível: {erro}"})
            return
        super().do_GET()

    def _json(self, status, corpo):
        bruto = json.dumps(corpo, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(bruto)))
        self.end_headers()
        self.wfile.write(bruto)

    def end_headers(self):
        self.send_header("Cache-Control", "no-cache")           # a página nova aparece sem limpar o cache
        super().end_headers()

    def log_message(self, formato, *args):
        pass


if __name__ == "__main__":
    print(f"[estufa-3d] página em :{PORTA} · Orion {ORION} (tenant {TENANT['fiware-service']})", flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORTA), Pagina).serve_forever()
