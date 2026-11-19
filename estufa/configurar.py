"""
Configura o tenant da estufa no FIWARE da Base (pode rodar mais de uma vez).

  1. cria (ou atualiza) a AgriGreenhouse:001 no Orion;
  2. confere que o clima não tem registro no tenant (o gravador-clima o substitui);
  3. provisiona o grupo de serviço e a ESP32 da estufa no IoT Agent;
     se o provisionamento mudou (dispositivo.json), reprovisiona a ESP32;
  4. cria (ou atualiza) as duas subscrições do histórico, para o Cygnus gravar
     no MySQL (banco "estufa"):
       - "Historico da estufa para o Cygnus": as medidas da ESP32;
       - "Clima externo para o Cygnus": cada leitura do gravador-clima.

Rode DEPOIS de subir orion, iot-agent e cygnus, e ANTES de subir a ESP32
(senão a primeira medida chega sem provisionamento e vira Thing:estufa001):

    cd fiware
    docker compose up -d --wait orion
    docker compose up -d --wait iot-agent
    docker compose up -d --wait cygnus
    python3 ../estufa/configurar.py
    docker compose up -d --build esp32-estufa
    docker compose up -d --build gravador-clima

Numa pilha que já roda, pare a ESP32 antes (docker compose stop esp32-estufa):
o reprovisionamento apaga e recria a entidade do nó.
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
CLIMA = "urn:ngsi-ld:WeatherObserved:FEI"

ATRIBUTOS_NO = ["temperature", "relativeHumidity", "vaporPressureDeficit", "soilMoisture", "illuminance",
                "fanState", "pumpState"]
ATRIBUTOS_CLIMA = ["temperature", "relativeHumidity", "windSpeed", "dateObserved", "source"]


def subscricao(descricao, entidades, atributos):
    return {
        "description": descricao,
        "subject": {"entities": entidades, "condition": {"attrs": atributos}},
        "notification": {
            "http": {"url": "http://cygnus:5050/notify"},   # nome do serviço: quem envia é o Orion, de dentro da rede
            "attrs": atributos,
            "attrsFormat": "normalized",                    # o Cygnus precisa de type e metadata
        },
        "throttling": 1,
    }


SUBSCRICOES = [
    subscricao("Historico da estufa para o Cygnus", [{"idPattern": ".*", "type": "Device"}], ATRIBUTOS_NO),
    subscricao("Clima externo para o Cygnus", [{"id": CLIMA, "type": "WeatherObserved"}], ATRIBUTOS_CLIMA),
]


def req(metodo, url, corpo=None, cabecalhos=True):
    dados = json.dumps(corpo).encode() if corpo is not None else None
    cab = dict(TENANT) if cabecalhos else {}
    if dados is not None:
        cab["Content-Type"] = "application/json"
    r = urllib.request.Request(url, data=dados, headers=cab, method=metodo)
    try:
        with urllib.request.urlopen(r, timeout=10) as resp:
            texto = resp.read().decode()
            return resp.status, (json.loads(texto) if texto else None), resp.headers
    except urllib.error.HTTPError as e:
        texto = e.read().decode()
        return e.code, (json.loads(texto) if texto else None), e.headers


def esperar(nome, url):
    for _ in range(30):
        try:
            s, _, _ = req("GET", url, cabecalhos=False)
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


def essencia(d):
    """O que importa comparar entre o dispositivo provisionado e o arquivo."""
    return {
        "entidade": (d.get("entity_name"), d.get("entity_type"), d.get("transport")),
        "medidas": sorted((a["object_id"], a["name"], a["type"], json.dumps(a.get("metadata"), sort_keys=True))
                          for a in d.get("attributes", [])),
        "comandos": sorted(c["name"] for c in d.get("commands", [])),
        "estaticos": sorted((a["name"], a["type"], json.dumps(a["value"]), json.dumps(a.get("metadata"), sort_keys=True))
                            for a in d.get("static_attributes", [])),
    }


def essencia_sub(s):
    n = s.get("notification", {})
    return (s["subject"]["entities"], s["subject"].get("condition", {}).get("attrs"), n.get("attrs"),
            n.get("http", {}).get("url"), n.get("attrsFormat"), s.get("throttling"))


print("0. Serviços")
esperar("Orion", f"{ORION}/version")
esperar("IoT Agent", f"{IOTA}/iot/about")
esperar("Cygnus", "http://localhost:5080/v1/version")

print("1. A estufa no Orion (tenant estufa)")
estufa = json.loads((MODELO / "exemplos" / "AgriGreenhouse.json").read_text())
s, r, _ = req("POST", f"{ORION}/v2/op/update", {"actionType": "append", "entities": [estufa]})
passo("AgriGreenhouse:001 criada/atualizada (204)", s == 204, r)

print("2. O clima vem do gravador-clima, não de registro")
s, registros, _ = req("GET", f"{ORION}/v2/registrations")
do_clima = [x["id"] for x in (registros or [])
            if any(e.get("id") == CLIMA or e.get("type") == "WeatherObserved"
                   for e in x.get("dataProvided", {}).get("entities", []))]
passo("nenhum registro do clima no tenant estufa", not do_clima,
      f"apague {do_clima} (DELETE /v2/registrations/<id>, fiware-service: estufa): com registro e "
      "gravação juntos, o Orion mistura as fontes (o gravado sai do Orion; o que falta, do provedor)")

print("3. A ESP32 da estufa no IoT Agent")
s, r, _ = req("POST", f"{IOTA}/iot/services", json.loads((MODELO / "provisionamento" / "grupo.json").read_text()))
passo("grupo de serviço (201, ou 409 se já existe)", s in (201, 409), r)
provisionamento = json.loads((MODELO / "provisionamento" / "dispositivo.json").read_text())
arquivo = provisionamento["devices"][0]
s, atual, _ = req("GET", f"{IOTA}/iot/devices/{arquivo['device_id']}")
if s == 200 and essencia(atual) == essencia(arquivo):
    print(f"  ✓ dispositivo {arquivo['device_id']} já provisionado como em dispositivo.json")
else:
    if s == 200:
        print(f"  • dispositivo.json mudou: reprovisionando {arquivo['device_id']}")
        req("DELETE", f"{IOTA}/iot/devices/{arquivo['device_id']}")
        req("DELETE", f"{ORION}/v2/entities/{arquivo['entity_name']}?type={arquivo['entity_type']}")
    s, r, _ = req("POST", f"{IOTA}/iot/devices", provisionamento)
    passo(f"dispositivo {arquivo['device_id']} provisionado (201)", s == 201, r)

print("4. As subscrições do histórico (Orion → Cygnus → MySQL)")
s, lista, _ = req("GET", f"{ORION}/v2/subscriptions?limit=100")
ids = {}
for sub in SUBSCRICOES:
    existente = [x for x in (lista or []) if x.get("description") == sub["description"]]
    if existente and essencia_sub(existente[0]) == essencia_sub(sub):
        ids[sub["description"]] = existente[0]["id"]
        print(f"  ✓ \"{sub['description']}\" já existe: {existente[0]['id']}")
    elif existente:
        sid = existente[0]["id"]
        s, r, _ = req("PATCH", f"{ORION}/v2/subscriptions/{sid}",
                      {k: sub[k] for k in ("subject", "notification", "throttling")})
        passo(f"\"{sub['description']}\" atualizada (204): {sid}", s == 204, r)
        ids[sub["description"]] = sid
    else:
        s, r, cab = req("POST", f"{ORION}/v2/subscriptions", sub)
        passo(f"\"{sub['description']}\" criada (201)", s == 201, r)
        ids[sub["description"]] = cab["Location"].rsplit("/", 1)[-1]

print("\nPronto. Agora suba (ou reconstrua) a ESP32, o gravador do clima e o painel:")
print("    docker compose up -d --build esp32-estufa")
print("    docker compose up -d --build gravador-clima")
print("    docker compose up -d grafana-estufa      # http://localhost:3002")
print("Status das subscrições (fiware-service: estufa):")
for descricao, sid in ids.items():
    print(f"    GET {ORION}/v2/subscriptions/{sid}   ({descricao})")
