"""
============================================================================
 PEL 220 - Internet das Coisas e Gêmeos Digitais | Plataforma FIWARE, Etapa 8
 Centro Universitário FEI - Prof. Rafael Gomes Alves
----------------------------------------------------------------------------
 VERSÃO PRONTA do controlador (a dos alunos é controlador/controlador.py).

 APLICAÇÃO DE CONTROLE AUTOMÁTICA: fecha o laço sensor -> plataforma -> atuador
 sem nenhum passo manual.

   1. Ao iniciar, cria SOZINHA a subscrição no Orion (se ainda não existir):
      a cada medida de temperatura de qualquer ClimateStation, o Orion
      notifica  POST <NOTIFICAR_EM>  com temperature e state (keyValues).
   2. decidir() aplica a regra com HISTERESE:
        temperatura >= LIGA     e relé que não está ON   ->  comando "on"
        temperatura <= DESLIGA  e relé que não está OFF  ->  comando "off"
        entre os dois limites                            ->  nada
   3. O comando volta pelo Orion (PATCH ...?type=ClimateStation), que o
      encaminha ao IoT Agent e daí ao dispositivo.

 Vale para todas as ClimateStation do tenant: provisionou outra ESP32, ela
 passa a ser controlada também, sem mudar nada aqui.

 GET http://localhost:5002/status mostra os limites, a subscrição, os
 contadores e as últimas decisões (mesmo formato da versão dos alunos).

 Variáveis de ambiente (padrão entre parênteses):
   ORION (http://orion:1026)  SERVICE (ccm130)  SERVICEPATH (/)
   LIGA (28)  DESLIGA (24)  ESPERA (10) s entre comandos para o mesmo dispositivo
   PORTA (5002)  NOTIFICAR_EM (http://controlador-pronto:5002/notify)
============================================================================
"""

import json
import os
import threading
import time
import urllib.error
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
PORTA = int(os.getenv("PORTA", "5002"))
NOTIFICAR_EM = os.getenv("NOTIFICAR_EM", f"http://controlador-pronto:{PORTA}/notify")

TENANT = {"fiware-service": SERVICE, "fiware-servicepath": SERVICEPATH}
DESCRICAO = "Controlador pronto: temperatura das ClimateStation"

ultimo_comando = {}                 # id da entidade -> instante do último comando enviado
historico = deque(maxlen=50)        # últimas decisões, para o /status
contadores = {"notificacoes": 0, "on": 0, "off": 0, "erros": 0}
subscricao = {"id": None, "situacao": "aguardando o Orion"}
trava = threading.Lock()


def log(*args):
    print("[controlador-pronto]", *args, flush=True)


# ---------------------------------------------------------------------------
# 2. A regra -- o coração da aplicação
# ---------------------------------------------------------------------------
def decidir(temperatura, estado):
    """Devolve "on", "off" ou None (não fazer nada).

    Histerese: dois limites em vez de um. Com um limite só (liga e desliga em
    28 °C), o ruído do sensor em torno de 28 faria o relé bater sem parar.
    Comparar com o estado evita mandar de novo o comando que já foi cumprido.
    """
    try:
        temperatura = float(temperatura)        # tolera "24.7" entre aspas (Aula 6, seção 5.5)
    except (TypeError, ValueError):
        return None                             # sem temperatura válida, não decide nada

    estado_atual = str(estado or "").upper()
    if temperatura >= LIGA and estado_atual != "ON":
        return "on"
    if temperatura <= DESLIGA and estado_atual != "OFF":
        return "off"
    return None


# ---------------------------------------------------------------------------
# 3. Conversa com o Orion
# ---------------------------------------------------------------------------
def orion(metodo, caminho, corpo=None):
    """Uma requisição ao Orion no tenant da plataforma. Devolve (status, json ou None, cabeçalhos)."""
    cabecalhos = dict(TENANT)
    dados = None
    if corpo is not None:
        dados = json.dumps(corpo).encode()
        cabecalhos["Content-Type"] = "application/json"   # só com corpo: GET com Content-Type dá 400
    pedido = urllib.request.Request(ORION + caminho, data=dados, method=metodo, headers=cabecalhos)
    try:
        with urllib.request.urlopen(pedido, timeout=5) as resposta:
            bruto = resposta.read()
            return resposta.status, (json.loads(bruto) if bruto else None), resposta.headers
    except urllib.error.HTTPError as erro:
        return erro.code, None, erro.headers


def garantir_subscricao():
    """Espera o Orion, procura uma subscrição que já notifique este controlador e, se não houver, cria."""
    while True:
        try:
            status, lista, _ = orion("GET", "/v2/subscriptions?limit=1000")
            if status != 200:
                raise RuntimeError(f"GET /v2/subscriptions respondeu {status}")
            for s in lista:
                if s.get("notification", {}).get("http", {}).get("url") == NOTIFICAR_EM:
                    with trava:
                        subscricao.update(id=s["id"], situacao="já existia")
                    log("subscrição já existia:", s["id"])
                    return
            corpo = {
                "description": DESCRICAO,
                "subject": {"entities": [{"idPattern": ".*", "type": "ClimateStation"}],
                            "condition": {"attrs": ["temperature"]}},
                "notification": {"http": {"url": NOTIFICAR_EM},
                                 "attrs": ["temperature", "state"],
                                 "attrsFormat": "keyValues"},
            }
            status, _, cabecalhos = orion("POST", "/v2/subscriptions", corpo)
            if status != 201:
                raise RuntimeError(f"POST /v2/subscriptions respondeu {status}")
            novo = cabecalhos.get("Location", "").rsplit("/", 1)[-1]
            with trava:
                subscricao.update(id=novo, situacao="criada")
            log("subscrição criada:", novo, "->", NOTIFICAR_EM)
            return
        except Exception as erro:                       # Orion ainda subindo, rede, etc.
            with trava:
                subscricao["situacao"] = f"tentando de novo: {erro}"
            log("Orion indisponível, nova tentativa em 5 s:", erro)
            time.sleep(5)


def enviar_comando(entidade, tipo, comando):
    """PATCH no Orion, como na Etapa 4: o Orion encaminha ao IoT Agent."""
    try:
        status, _, _ = orion("PATCH", f"/v2/entities/{entidade}/attrs?type={tipo}",
                             {comando: {"type": "command", "value": ""}})
        return status                                   # 204 = encaminhado ao IoT Agent
    except Exception as erro:
        log("falha ao enviar", comando, "para", entidade, ":", erro)
        return 0


def tratar(entidade):
    """Uma entidade da notificação: decide e, se for o caso, comanda."""
    eid, tipo = entidade["id"], entidade.get("type", "ClimateStation")
    temperatura, estado = entidade.get("temperature"), entidade.get("state")
    comando = decidir(temperatura, estado)
    if comando is None:
        return
    with trava:
        if time.time() - ultimo_comando.get(eid, 0) < ESPERA:
            return                                      # já mandamos há pouco: o estado ainda não voltou
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
            self._json(200, {"limites": {"liga": LIGA, "desliga": DESLIGA}, "subscricao": dict(subscricao),
                             "contadores": contadores, "ultimas": list(historico)[:10]})

    def log_message(self, formato, *args):
        pass


if __name__ == "__main__":
    log(f"Liga em >= {LIGA} °C, desliga em <= {DESLIGA} °C | notificações em {NOTIFICAR_EM}")
    threading.Thread(target=garantir_subscricao, daemon=True).start()
    ThreadingHTTPServer(("0.0.0.0", PORTA), Controlador).serve_forever()
