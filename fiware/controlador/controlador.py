"""
============================================================================
 CCM130 - Conectividade e IoT | Aula 10 - Fluxo de dados completo
 Centro Universitário FEI - Prof. Rafael Gomes Alves
----------------------------------------------------------------------------
 ESQUELETO - complete a função decidir() (seção 2).

 APLICAÇÃO DE CONTROLE: fecha o laço sensor -> plataforma -> atuador.

   1. Uma SUBSCRIÇÃO do Orion avisa esta aplicação a cada mudança de
      temperatura da ESP32:  POST http://controlador:5001/notify
   2. decidir() aplica a regra com HISTERESE:
        temperatura >= LIGA     e relé desligado  ->  comando "on"
        temperatura <= DESLIGA  e relé ligado     ->  comando "off"
        entre os dois limites                     ->  nada (mantém o estado)
   3. O comando volta pelo Orion (PATCH ...?type=ClimateStation), que o
      encaminha ao IoT Agent e daí ao dispositivo -- igual ao Postman.

 A aplicação só fala com o Orion: nunca fala direto com a ESP32 nem com o broker.

 GET http://localhost:5001/status mostra os limites, os contadores e as
 últimas decisões (os testes da coleção usam esse endereço).

 Variáveis de ambiente (padrão entre parênteses):
   ORION (http://orion:1026)  SERVICE (ccm130)  SERVICEPATH (/)
   LIGA (28)  DESLIGA (24)  ESPERA (10) s entre comandos para o mesmo dispositivo
   PORTA (5001)
============================================================================
"""

import json
import os
import threading
import time
import urllib.request
from collections import deque
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# ---------------------------------------------------------------------------
# 1. Configuração
# ---------------------------------------------------------------------------
ORION = os.getenv("ORION", "http://orion:1026")
SERVICE = os.getenv("SERVICE", "ccm130")
SERVICEPATH = os.getenv("SERVICEPATH", "/")
LIGA = float(os.getenv("LIGA", "28"))
DESLIGA = float(os.getenv("DESLIGA", "24"))
ESPERA = float(os.getenv("ESPERA", "10"))
PORTA = int(os.getenv("PORTA", "5001"))

ultimo_comando = {}                 # id da entidade -> instante do último comando enviado
historico = deque(maxlen=50)        # últimas decisões, para o /status
contadores = {"notificacoes": 0, "on": 0, "off": 0, "erros": 0}
trava = threading.Lock()


def log(*args):
    print("[controlador]", *args, flush=True)


# ---------------------------------------------------------------------------
# 2. A regra -- o coração da aplicação
# ---------------------------------------------------------------------------
def decidir(temperatura, estado):
    """Devolve "on", "off" ou None (não fazer nada).

    Histerese: dois limites em vez de um. Com um limite só (liga e desliga em
    28 °C), o ruído do sensor em torno de 28 faria o relé bater sem parar.
    """
    if temperatura is None:
        return None

    estado_atual = str(estado or "").upper()

    if temperatura >= LIGA and estado_atual != "ON":
        return "on"

    if temperatura <= DESLIGA and estado_atual != "OFF":
        return "off"

    return None


# ---------------------------------------------------------------------------
# 3. O comando volta pelo Orion
# ---------------------------------------------------------------------------
def enviar_comando(entidade, tipo, comando):
    """PATCH no Orion, como você fez no Postman na etapa 4."""
    url = f"{ORION}/v2/entities/{entidade}/attrs?type={tipo}"
    corpo = json.dumps({comando: {"type": "command", "value": ""}}).encode()
    pedido = urllib.request.Request(url, data=corpo, method="PATCH", headers={
        "Content-Type": "application/json", "fiware-service": SERVICE, "fiware-servicepath": SERVICEPATH})
    try:
        with urllib.request.urlopen(pedido, timeout=5) as resposta:
            return resposta.status                  # 204 = encaminhado ao IoT Agent
    except Exception as erro:
        log("falha ao enviar", comando, "para", entidade, ":", erro)
        return getattr(erro, "code", 0)


def tratar(entidade):
    """Uma entidade da notificação: decide e, se for o caso, comanda."""
    eid, tipo = entidade["id"], entidade.get("type", "ClimateStation")
    temperatura, estado = entidade.get("temperature"), entidade.get("state")
    comando = decidir(temperatura, estado)
    if comando is None:
        return
    with trava:
        if time.time() - ultimo_comando.get(eid, 0) < ESPERA:
            return                                  # já mandamos há pouco: o estado ainda não voltou
        ultimo_comando[eid] = time.time()
    status = enviar_comando(eid, tipo, comando)
    with trava:
        contadores[comando if status == 204 else "erros"] += 1
        historico.appendleft({"quando": datetime.now().strftime("%H:%M:%S"), "entidade": eid,
                              "temperatura": temperatura, "estado": estado, "comando": comando, "status": status})
    log(f"{eid}: {temperatura} °C, relé {estado} -> {comando} ({status})")


# ---------------------------------------------------------------------------
# 4. Servidor HTTP: recebe as notificações e mostra o status
# ---------------------------------------------------------------------------
class Controlador(BaseHTTPRequestHandler):
    def _json(self, status, corpo):
        bruto = json.dumps(corpo, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(bruto)))
        self.end_headers()
        self.wfile.write(bruto)

    def do_POST(self):
        tamanho = int(self.headers.get("Content-Length", 0))
        try:
            notificacao = json.loads(self.rfile.read(tamanho) or b"{}")
        except ValueError:
            self._json(400, {"erro": "corpo não é JSON"})
            return
        self._json(200, {"recebido": True})         # responda rápido: o Orion espera
        with trava:
            contadores["notificacoes"] += 1
        for entidade in notificacao.get("data", []):
            tratar(entidade)

    def do_GET(self):
        with trava:
            self._json(200, {"limites": {"liga": LIGA, "desliga": DESLIGA}, "contadores": contadores,
                             "ultimas": list(historico)[:10]})

    def log_message(self, formato, *args):
        pass


if __name__ == "__main__":
    log(f"Liga em >= {LIGA} °C, desliga em <= {DESLIGA} °C | notificações em :{PORTA}/notify")
    ThreadingHTTPServer(("0.0.0.0", PORTA), Controlador).serve_forever()
