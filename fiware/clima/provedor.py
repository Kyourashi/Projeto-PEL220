"""
============================================================================
 CCM130 - Conectividade e IoT | Aula 10 - Fluxo de dados completo
 Centro Universitário FEI - Prof. Rafael Gomes Alves
----------------------------------------------------------------------------
 PROVEDOR DE CONTEXTO (proxy NGSI v2) com o clima real do campus da FEI.

 O Orion não guarda estes dados: um REGISTRO (Aula 8) diz a ele que os
 atributos da entidade urn:ngsi-ld:WeatherObserved:FEI estão neste provedor.
 A cada leitura de uma aplicação, o Orion faz

     POST <url do registro>/op/query
     {"entities": [{"id": "...", "type": "WeatherObserved"}], "attrs": [...]}

 e este programa busca o clima atual na API pública Open-Meteo (sem chave),
 traduz para NGSI v2 e responde. É o padrão de qualquer integração com uma
 API externa: só a função buscar_clima() muda.

   temperature        Number   °C           (temperature_2m)
   relativeHumidity   Number   0 a 1        (relative_humidity_2m / 100)
   windSpeed          Number   m/s          (wind_speed_10m em km/h / 3,6)
   dateObserved       DateTime              (hora da observação)
   source             Text     open-meteo | simulado

 Sem internet (rede da sala bloqueada), responde com valores SIMULADOS e
 source = "simulado" -- a aula continua funcionando.

 Variáveis de ambiente (padrão entre parênteses):
   PORTA (3010)  LATITUDE (-23.7245)  LONGITUDE (-46.5793)  CACHE (60) s
   MODO (api)    "simulado" força os valores simulados
============================================================================
"""

import json
import os
import random
import time
import urllib.request
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

PORTA = int(os.getenv("PORTA", "3010"))
LATITUDE = float(os.getenv("LATITUDE", "-23.7245"))       # FEI, São Bernardo do Campo
LONGITUDE = float(os.getenv("LONGITUDE", "-46.5793"))
CACHE = float(os.getenv("CACHE", "60"))                   # não consulte a API a cada leitura
MODO = os.getenv("MODO", "api")

URL_API = ("https://api.open-meteo.com/v1/forecast"
           f"?latitude={LATITUDE}&longitude={LONGITUDE}"
           "&current=temperature_2m,relative_humidity_2m,wind_speed_10m&timezone=UTC")

_cache = {"quando": 0.0, "dados": None}


def log(*args):
    print("[clima]", *args, flush=True)


# ---------------------------------------------------------------------------
# 1. A API externa -- a única parte que muda de uma integração para outra
# ---------------------------------------------------------------------------
def buscar_clima():
    """Devolve um dicionário com as grandezas já nas unidades do modelo de dados."""
    if MODO != "simulado":
        try:
            with urllib.request.urlopen(URL_API, timeout=5) as resposta:
                atual = json.load(resposta)["current"]
            return {
                "temperature": atual["temperature_2m"],
                "relativeHumidity": round(atual["relative_humidity_2m"] / 100, 2),
                "windSpeed": round(atual["wind_speed_10m"] / 3.6, 1),
                "dateObserved": atual["time"] + ":00Z",
                "source": "open-meteo",
            }
        except Exception as erro:                     # sem internet, API fora do ar, limite de uso
            log("API indisponível, usando valores simulados:", erro)
    return {
        "temperature": round(random.uniform(16, 30), 1),
        "relativeHumidity": round(random.uniform(0.4, 0.9), 2),
        "windSpeed": round(random.uniform(0, 6), 1),
        "dateObserved": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": "simulado",
    }


def clima_atual():
    if _cache["dados"] is None or time.time() - _cache["quando"] > CACHE:
        _cache["dados"], _cache["quando"] = buscar_clima(), time.time()
        log("clima atualizado:", _cache["dados"])
    return _cache["dados"]


# ---------------------------------------------------------------------------
# 2. Tradução para NGSI v2
# ---------------------------------------------------------------------------
TIPOS = {"temperature": "Number", "relativeHumidity": "Number", "windSpeed": "Number",
         "dateObserved": "DateTime", "source": "Text"}


def responder_consulta(consulta):
    """Recebe o corpo do /op/query do Orion e devolve a lista de entidades."""
    dados = clima_atual()
    pedidos = consulta.get("attrs") or list(TIPOS)          # sem attrs = todos
    resposta = []
    for entidade in consulta.get("entities", []):
        e = {"id": entidade["id"], "type": entidade.get("type", "WeatherObserved")}
        for atributo in pedidos:
            if atributo in dados:
                e[atributo] = {"type": TIPOS[atributo], "value": dados[atributo], "metadata": {}}
        resposta.append(e)
    return resposta


class Provedor(BaseHTTPRequestHandler):
    def _json(self, status, corpo):
        bruto = json.dumps(corpo).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(bruto)))
        self.end_headers()
        self.wfile.write(bruto)

    def do_POST(self):
        if not urlsplit(self.path).path.endswith("/op/query"):      # o Orion acrescenta ?options=...
            self._json(404, {"error": "NotFound", "description": "use <base>/op/query"})
            return
        tamanho = int(self.headers.get("Content-Length", 0))
        consulta = json.loads(self.rfile.read(tamanho) or b"{}")
        log("Orion perguntou:", consulta.get("attrs"), "de", [e["id"] for e in consulta.get("entities", [])])
        self._json(200, responder_consulta(consulta))

    def do_GET(self):                                        # GET /health: o provedor está no ar?
        self._json(200, {"status": "ok", "modo": MODO, "clima": clima_atual()})

    def log_message(self, formato, *args):
        pass


if __name__ == "__main__":
    log(f"Provedor de clima em :{PORTA} | lat {LATITUDE} lon {LONGITUDE} | modo {MODO}")
    ThreadingHTTPServer(("0.0.0.0", PORTA), Provedor).serve_forever()
