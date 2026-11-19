"""
Testa o modelo de dados da estufa contra a pilha FIWARE (Orion + IoT Agent + Mosquitto).

Critério do marco (Aula 7): cada JSON de exemplo é enviado ao Orion, num tenant do grupo,
e lido de volta sem surpresa.

Roda num tenant SÓ DE TESTE (estufa_teste), com chave e device_id próprios: assim não
reprovisiona a ESP32 que está no ar nem põe valores de exemplo no histórico da estufa.
Os JSON são os mesmos do projeto; só a chave, o device_id e o tenant mudam.

O que faz, nesta ordem:
  1. cria a WeatherObserved:FEI e a AgriGreenhouse:001 no Orion (exemplos/*.json);
  2. reprovisiona a ESP32 de teste no IoT Agent (apaga a antiga, se houver);
  3. publica uma medida MQTT de exemplo (docker exec no contêiner mosquitto);
  4. faz o ciclo completo de um comando: PATCH fanOn → cmd → cmdexe → fanOn_status = OK;
  5. lê as três entidades de volta (formato normalizado) e confere:
     - id em URN com o tipo;
     - value coerente com o type (regras da seção 6.7 do material complementar);
     - unitCode presente em toda grandeza numérica, igual ao do provisionamento;
     - relativeHumidity entre 0 e 1;
     - vaporPressureDeficit coerente com temperature e relativeHumidity (Tetens);
     - potências e vazão nominais iguais às do provisionamento;
     - o alvo de cada Relationship existe;
     - não surgiu uma entidade Thing (dispositivo não provisionado);
  6. grava o que o Orion devolveu em exemplos/*.lido.json.

Uso (com orion e iot-agent no ar):
    cd fiware && docker compose up -d --wait iot-agent
    python3 ../modelo-dados/testar_modelo.py
"""

import json
import math
import pathlib
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

ORION = "http://localhost:1026"
IOTA = "http://localhost:4041"
TENANT = {"fiware-service": "estufa_teste", "fiware-servicepath": "/"}   # não é o tenant estufa
APIKEY = "estufateste"                                                  # nem a chave da ESP32 no ar
DEVICE_ID = "teste001"
DEVICE = "urn:ngsi-ld:Device:ESP32-001"
ESTUFA = "urn:ngsi-ld:AgriGreenhouse:001"
CLIMA = "urn:ngsi-ld:WeatherObserved:FEI"
# v = e_s(26,4 °C) · (1 - 0,62) = 3,442 kPa · 0,38 = 1,31 kPa
MEDIDA = {"t": 26.4, "h": 0.62, "v": 1.31, "m": 38.5, "l": 21500, "f": "OFF", "p": "OFF"}

AQUI = pathlib.Path(__file__).parent
falhas = 0
total = 0


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
    global falhas, total
    total += 1
    print(("  ✓ " if ok else "  ✗ ") + nome + ("" if ok else f"  → {detalhe}"))
    if not ok:
        falhas += 1


def mqtt_pub(topico, msg):
    r = subprocess.run(["docker", "exec", "mosquitto", "mosquitto_pub", "-t", topico, "-m", json.dumps(msg)],
                       capture_output=True, text=True)
    return r.returncode == 0, r.stderr.strip()


REGRAS = {
    "Number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "Boolean": lambda v: isinstance(v, bool),
    "Text": lambda v: isinstance(v, str),
    "DateTime": lambda v: isinstance(v, str) and re.match(r"^\d{4}-\d{2}-\d{2}T", v) is not None,
    "Relationship": lambda v: isinstance(v, str) and re.match(r"^urn:ngsi-ld:[A-Z][A-Za-z]+:", v) is not None,
}


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
        if a["type"] == "Number":
            teste(f"{nome}: tem unitCode", "unitCode" in a.get("metadata", {}), a.get("metadata"))
        if nome == "relativeHumidity":
            teste("relativeHumidity entre 0 e 1", 0 <= a["value"] <= 1, a["value"])
        if a["type"] == "Relationship":
            alvo, _ = req("GET", f"{ORION}/v2/entities/{a['value']}?attrs=id")
            teste(f"{nome}: alvo {a['value']} existe", alvo == 200, alvo)
    return e


print("1. WeatherObserved e AgriGreenhouse no Orion (criadas pela aplicação)")
clima = json.loads((AQUI / "exemplos" / "WeatherObserved.json").read_text())
estufa = json.loads((AQUI / "exemplos" / "AgriGreenhouse.json").read_text())
s, _ = req("POST", f"{ORION}/v2/op/update", {"actionType": "append", "entities": [clima, estufa]})
teste("criadas/atualizadas (204)", s == 204, s)

print("2. Provisionamento no IoT Agent (chave e device_id de teste)")
grupo = json.loads((AQUI / "provisionamento" / "grupo.json").read_text())
grupo["services"][0]["apikey"] = APIKEY
provisionamento = json.loads((AQUI / "provisionamento" / "dispositivo.json").read_text())
dispositivo = provisionamento["devices"][0]
dispositivo.update(apikey=APIKEY, device_id=DEVICE_ID)
s, _ = req("POST", f"{IOTA}/iot/services", grupo)
teste("grupo de serviço (201, ou 409 se já existe)", s in (201, 409), s)
req("DELETE", f"{IOTA}/iot/devices/{DEVICE_ID}")          # reprovisiona do zero
req("DELETE", f"{ORION}/v2/entities/{DEVICE}?type=Device")  # e limpa a entidade antiga
s, _ = req("POST", f"{IOTA}/iot/devices", provisionamento)
teste("dispositivo (201)", s == 201, s)

print("3. Medida MQTT de exemplo")
topico = f"/json/{APIKEY}/{DEVICE_ID}/attrs"
ok, err = mqtt_pub(topico, MEDIDA)
teste(f"publicada em {topico}", ok, err)
time.sleep(3)

print("4. Ciclo do comando: PATCH → cmd → cmdexe → fanOn_status")
sub = subprocess.Popen(["docker", "exec", "mosquitto", "mosquitto_sub", "-t", f"/{APIKEY}/{DEVICE_ID}/cmd",
                        "-C", "1", "-W", "10"], stdout=subprocess.PIPE, text=True)
time.sleep(1)
s, _ = req("PATCH", f"{ORION}/v2/entities/{DEVICE}/attrs?type=Device", {"fanOn": {"type": "command", "value": ""}})
teste("PATCH fanOn aceito (204 = encaminhado ao IoT Agent)", s == 204, s)
cmd = (sub.communicate(timeout=15)[0] or "").strip()
teste(f"IoT Agent publicou o comando em /{APIKEY}/{DEVICE_ID}/cmd", "fanOn" in cmd, cmd)
_, e = req("GET", f"{ORION}/v2/entities/{DEVICE}?options=keyValues&attrs=fanOn_status")
teste("fanOn_status = PENDING antes da resposta", (e or {}).get("fanOn_status") == "PENDING", e)
ok, err = mqtt_pub(f"/json/{APIKEY}/{DEVICE_ID}/cmdexe", {"fanOn": "OK - ventilador ligado"})
ok2, _ = mqtt_pub(topico, {"f": "ON"})
teste("ESP32 (simulada à mão) respondeu em cmdexe e publicou o novo estado", ok and ok2, err)
time.sleep(3)
_, e = req("GET", f"{ORION}/v2/entities/{DEVICE}?options=keyValues&attrs=fanOn_status,fanOn_info,fanState")
teste("fanOn_status = OK", (e or {}).get("fanOn_status") == "OK", e)
teste("fanOn_info = 'OK - ventilador ligado'", (e or {}).get("fanOn_info") == "OK - ventilador ligado", e)
teste("fanState = ON (estado informado pela ESP32)", (e or {}).get("fanState") == "ON", e)

print("5. Leitura de volta")
lidos = {}
for eid in (CLIMA, ESTUFA, DEVICE):
    e = conferir(eid)
    if e:
        lidos[e["type"]] = e
s, _ = req("GET", f"{ORION}/v2/entities/Thing:{DEVICE_ID}")
teste(f"não surgiu Thing:{DEVICE_ID} (404)", s == 404, s)
if "Device" in lidos:
    d = lidos["Device"]
    unidade = lambda a: a.get("metadata", {}).get("unitCode", {}).get("value")
    for a in dispositivo["attributes"]:
        if a["object_id"] in MEDIDA and a["type"] == "Number":
            lido = d.get(a["name"], {})
            teste(f"{a['name']} = {MEDIDA[a['object_id']]} (veio da medida '{a['object_id']}')",
                  lido.get("value") == MEDIDA[a["object_id"]], lido.get("value"))
            teste(f"{a['name']}: unitCode {unidade(a)} como no provisionamento", unidade(lido) == unidade(a),
                  unidade(lido))
    t, h = d["temperature"]["value"], d["relativeHumidity"]["value"]
    vpd = 0.6108 * math.exp(17.27 * t / (t + 237.3)) * (1 - h)
    teste(f"vaporPressureDeficit coerente com t e h (Tetens: {vpd:.3f} kPa)",
          abs(d["vaporPressureDeficit"]["value"] - vpd) <= 0.01, d["vaporPressureDeficit"]["value"])
    for a in dispositivo["static_attributes"]:
        if a["type"] == "Number":
            lido = d.get(a["name"], {})
            teste(f"{a['name']} = {a['value']} {unidade(a)} (nominal, do provisionamento)",
                  lido.get("value") == a["value"] and unidade(lido) == unidade(a), lido)
    for c in ("fanOn", "fanOff", "pumpOn", "pumpOff"):
        teste(f"comando {c} registrado", d.get(c, {}).get("type") == "command", d.get(c))
    teste("controlledProperty (exigido pelo SDM Device)",
          d.get("controlledProperty", {}).get("value") == ["temperature", "humidity", "soilMoisture", "light"],
          d.get("controlledProperty"))
if "AgriGreenhouse" in lidos:
    g = lidos["AgriGreenhouse"]
    for nome in ("fanOnTemperature", "fanOffTemperature", "irrigationOnSoilMoisture", "irrigationOffSoilMoisture"):
        teste(f"{nome} = {estufa[nome]['value']} (limite de controle)", g.get(nome, {}).get("value") == estufa[nome]["value"],
              g.get(nome))

for tipo, e in lidos.items():
    (AQUI / "exemplos" / f"{tipo}.lido.json").write_text(json.dumps(e, indent=2, ensure_ascii=False) + "\n")

print(f"\n{'OK' if falhas == 0 else 'FALHOU'}: {total} verificações, {falhas} falha(s)")
sys.exit(1 if falhas else 0)
