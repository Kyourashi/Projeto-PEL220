"""
Testa o modelo de dados da estufa contra a pilha FIWARE (Orion + IoT Agent + Mosquitto).

O que faz, nesta ordem:
  1. cria a AgriGreenhouse:001 no Orion (exemplos/AgriGreenhouse.json);
  2. cria o grupo de serviço e provisiona a ESP32 no IoT Agent (provisionamento/);
  3. publica uma medida MQTT de exemplo (docker exec no contêiner mosquitto);
  4. lê as duas entidades de volta, no formato normalizado, e confere:
     - id em URN com o tipo;
     - value coerente com o type (regras da seção 6.7 do material complementar);
     - unitCode presente em toda grandeza numérica;
     - o alvo de cada Relationship existe;
     - não surgiu uma entidade Thing (dispositivo não provisionado).
  5. grava o que o Orion devolveu em exemplos/*.lido.json.

Uso (com orion e iot-agent no ar):
    cd fiware && docker compose up -d --wait iot-agent
    python3 ../modelo-dados/testar_modelo.py
"""

import json
import pathlib
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

ORION = "http://localhost:1026"
IOTA = "http://localhost:4041"
TENANT = {"fiware-service": "estufa", "fiware-servicepath": "/"}
APIKEY = "estufa"
DEVICE_ID = "estufa001"
MEDIDA = {"t": 26.4, "h": 62.0, "m": 38.5, "l": 71.0, "f": "OFF", "p": "OFF"}

AQUI = pathlib.Path(__file__).parent
falhas = 0


def req(metodo, url, corpo=None):
    dados = json.dumps(corpo).encode() if corpo is not None else None
    cab = dict(TENANT)
    if dados is not None:
        cab["Content-Type"] = "application/json"
    r = urllib.request.Request(url, data=dados, headers=cab, method=metodo)
    try:
        with urllib.request.urlopen(r) as resp:
            texto = resp.read().decode()
            return resp.status, (json.loads(texto) if texto else None)
    except urllib.error.HTTPError as e:
        texto = e.read().decode()
        return e.code, (json.loads(texto) if texto else None)


def teste(nome, ok, detalhe=""):
    global falhas
    print(("  ✓ " if ok else "  ✗ ") + nome + ("" if ok else f"  → {detalhe}"))
    if not ok:
        falhas += 1


REGRAS = {
    "Number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "Boolean": lambda v: isinstance(v, bool),
    "Text": lambda v: isinstance(v, str),
    "DateTime": lambda v: isinstance(v, str) and re.match(r"^\d{4}-\d{2}-\d{2}T", v) is not None,
    "Relationship": lambda v: isinstance(v, str) and re.match(r"^urn:ngsi-ld:[A-Z][A-Za-z]+:", v) is not None,
}
SEM_UNIDADE = {"TimeInstant"}  # instante, não grandeza


def conferir(eid):
    status, e = req("GET", f"{ORION}/v2/entities/{eid}")
    teste(f"{eid}: lido de volta (200)", status == 200, status)
    if status != 200:
        return None
    teste("id em URN com o tipo", re.match(rf"^urn:ngsi-ld:{e['type']}:", e["id"]) is not None, e["id"])
    for nome, a in e.items():
        if nome in ("id", "type"):
            continue
        regra = REGRAS.get(a["type"])
        if regra:
            teste(f"{nome}: value coerente com {a['type']}", regra(a["value"]), json.dumps(a["value"]))
        if a["type"] == "Number" and nome not in SEM_UNIDADE:
            teste(f"{nome}: tem unitCode", "unitCode" in a.get("metadata", {}), a.get("metadata"))
        if a["type"] == "Relationship":
            alvo, _ = req("GET", f"{ORION}/v2/entities/{a['value']}?attrs=id")
            teste(f"{nome}: alvo {a['value']} existe", alvo == 200, alvo)
    return e


print("1. AgriGreenhouse no Orion")
estufa = json.loads((AQUI / "exemplos" / "AgriGreenhouse.json").read_text())
s, _ = req("POST", f"{ORION}/v2/op/update", {"actionType": "append", "entities": [estufa]})
teste("criada/atualizada (204)", s == 204, s)

print("2. Provisionamento no IoT Agent")
s, _ = req("POST", f"{IOTA}/iot/services", json.loads((AQUI / "provisionamento" / "grupo.json").read_text()))
teste("grupo de serviço (201, ou 409 se já existe)", s in (201, 409), s)
s, _ = req("POST", f"{IOTA}/iot/devices", json.loads((AQUI / "provisionamento" / "dispositivo.json").read_text()))
teste("dispositivo (201, ou 409 se já existe)", s in (201, 409), s)

print("3. Medida MQTT de exemplo")
topico = f"/json/{APIKEY}/{DEVICE_ID}/attrs"
r = subprocess.run(["docker", "exec", "mosquitto", "mosquitto_pub", "-t", topico, "-m", json.dumps(MEDIDA)],
                   capture_output=True, text=True)
teste(f"publicada em {topico}", r.returncode == 0, r.stderr.strip())
time.sleep(3)

print("4. Leitura de volta")
lidos = {}
for eid in ("urn:ngsi-ld:AgriGreenhouse:001", "urn:ngsi-ld:Device:ESP32-001"):
    e = conferir(eid)
    if e:
        lidos[e["type"]] = e
s, _ = req("GET", f"{ORION}/v2/entities/Thing:{DEVICE_ID}")
teste("não surgiu Thing:estufa001 (404)", s == 404, s)
if "Device" in lidos:
    d = lidos["Device"]
    for nome, chave in (("temperature", "t"), ("relativeHumidity", "h"), ("soilMoisture", "m"), ("lightLevel", "l")):
        teste(f"{nome} = {MEDIDA[chave]} (veio da medida)", d.get(nome, {}).get("value") == MEDIDA[chave],
              d.get(nome, {}).get("value"))
    for cmd in ("fanOn", "fanOff", "pumpOn", "pumpOff"):
        teste(f"comando {cmd} registrado", d.get(cmd, {}).get("type") == "command", d.get(cmd))

for tipo, e in lidos.items():
    (AQUI / "exemplos" / f"{tipo}.lido.json").write_text(json.dumps(e, indent=2, ensure_ascii=False) + "\n")

print(f"\n{'OK' if falhas == 0 else 'FALHOU'}: {falhas} falha(s)")
sys.exit(1 if falhas else 0)
