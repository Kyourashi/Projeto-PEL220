"""
Configura o tenant da estufa no FIWARE da Base (pode rodar mais de uma vez).

  1. cria (ou atualiza) a AgriGreenhouse:001 no Orion;
  2. provisiona o grupo de serviço e a ESP32 da estufa no IoT Agent;
  3. cria a subscrição do histórico: o Orion avisa o Cygnus a cada medida
     da estufa, e o Cygnus grava no MySQL (banco "estufa").

Rode DEPOIS de subir orion, iot-agent e cygnus, e ANTES de subir a ESP32
(senão a primeira medida chega sem provisionamento e vira Thing:estufa001):

    cd fiware
    docker compose up -d --wait orion
    docker compose up -d --wait iot-agent
    docker compose up -d --wait cygnus
    python3 ../estufa/configurar.py
    docker compose up -d --build esp32-estufa
"""

import json
import pathlib
import sys
import time
import urllib.error
import urllib.request

ORION = "http://localhost:1026"
IOTA = "http://localhost:4041"
TENANT = {"fiware-service": "estufa", "fiware-servicepath": "/"}
RAIZ = pathlib.Path(__file__).resolve().parent.parent
MODELO = RAIZ / "modelo-dados"

ATRIBUTOS_HISTORICO = ["temperature", "relativeHumidity", "soilMoisture", "lightLevel", "fanState", "pumpState"]
SUBSCRICAO = {
    "description": "Historico da estufa para o Cygnus",
    "subject": {
        "entities": [{"idPattern": ".*", "type": "Device"}],
        "condition": {"attrs": ATRIBUTOS_HISTORICO},
    },
    "notification": {
        "http": {"url": "http://cygnus:5050/notify"},   # nome do serviço: quem envia é o Orion, de dentro da rede
        "attrs": ATRIBUTOS_HISTORICO,
        "attrsFormat": "normalized",                    # o Cygnus precisa de type e metadata
    },
    "throttling": 1,
}


def req(metodo, url, corpo=None, cabecalhos=True):
    dados = json.dumps(corpo).encode() if corpo is not None else None
    cab = dict(TENANT) if cabecalhos else {}
    if dados is not None:
        cab["Content-Type"] = "application/json"
    r = urllib.request.Request(url, data=dados, headers=cab, method=metodo)
    try:
        with urllib.request.urlopen(r, timeout=10) as resp:
            texto = resp.read().decode()
            return resp.status, (json.loads(texto) if texto else None)
    except urllib.error.HTTPError as e:
        texto = e.read().decode()
        return e.code, (json.loads(texto) if texto else None)


def esperar(nome, url):
    for _ in range(30):
        try:
            s, _ = req("GET", url, cabecalhos=False)
            if s == 200:
                print(f"  ✓ {nome} no ar")
                return
        except OSError:
            pass
        time.sleep(2)
    sys.exit(f"  ✗ {nome} não respondeu em {url}: suba-o antes (docker compose up -d --wait …)")


def passo(nome, ok, detalhe=""):
    print(("  ✓ " if ok else "  ✗ ") + nome + ("" if ok else f" → {detalhe}"))
    if not ok:
        sys.exit(1)


print("0. Serviços")
esperar("Orion", f"{ORION}/version")
esperar("IoT Agent", f"{IOTA}/iot/about")
esperar("Cygnus", "http://localhost:5080/v1/version")

print("1. A estufa no Orion (tenant estufa)")
estufa = json.loads((MODELO / "exemplos" / "AgriGreenhouse.json").read_text())
s, r = req("POST", f"{ORION}/v2/op/update", {"actionType": "append", "entities": [estufa]})
passo("AgriGreenhouse:001 criada/atualizada (204)", s == 204, r)

print("2. A ESP32 da estufa no IoT Agent")
s, r = req("POST", f"{IOTA}/iot/services", json.loads((MODELO / "provisionamento" / "grupo.json").read_text()))
passo("grupo de serviço (201, ou 409 se já existe)", s in (201, 409), r)
s, r = req("POST", f"{IOTA}/iot/devices", json.loads((MODELO / "provisionamento" / "dispositivo.json").read_text()))
passo("dispositivo estufa001 (201, ou 409 se já existe)", s in (201, 409), r)

print("3. A subscrição do histórico (Orion → Cygnus → MySQL)")
s, lista = req("GET", f"{ORION}/v2/subscriptions")
existente = [x for x in (lista or []) if x.get("description") == SUBSCRICAO["description"]]
if existente:
    sid = existente[0]["id"]
    print(f"  ✓ já existe: {sid}")
else:
    dados = json.dumps(SUBSCRICAO).encode()
    pedido = urllib.request.Request(f"{ORION}/v2/subscriptions", data=dados, method="POST",
                                    headers={**TENANT, "Content-Type": "application/json"})
    with urllib.request.urlopen(pedido, timeout=10) as resp:
        sid = resp.headers["Location"].rsplit("/", 1)[-1]
    print(f"  ✓ criada (201): {sid}")

print("\nPronto. Agora suba a ESP32 da estufa e o painel:")
print("    docker compose up -d --build esp32-estufa")
print("    docker compose up -d grafana-estufa      # http://localhost:3002")
print(f"Status da subscrição: GET {ORION}/v2/subscriptions/{sid}  (fiware-service: estufa)")
