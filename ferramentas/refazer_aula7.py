"""
Refaz a Aula 7 da Base no tenant ccm130, com o exercício "Para aprofundar" (pode rodar mais de uma vez).

Serve para um Codespace novo, ou para quando o Grafana da Base volta vazio (volume grafana-data novo):

  1. para a ESP32 da aula (ela volta depois do cadastro) e sobe orion, iot-agent e cygnus;
  2. Etapa 1: a sala urn:ngsi-ld:Room:K501;
     Etapa 2: o grupo de serviço e a ESP32 esp32001 no IoT Agent; se ela tiver virado
     Thing:esp32001 (medida antes do provisionamento), apaga e provisiona de novo;
  3. Etapa 6: a subscrição "Historico da ESP32 para o Cygnus";
     exercício: a subscrição "Umidade alta via MQTT" (humidity>70, avisa em pel220/umida);
  4. sobe a ESP32 da aula e o Grafana da Base (porta 3000);
  5. Etapa 7: a fonte de dados MySQL (banco ccm130) e o painel da aula, com a etiqueta aula10:
     temperatura agora (Stat), temperatura (Time series), relé (State timeline), média por minuto
     (Bar chart) e, do exercício, a umidade (Time series) e a máxima do período (Stat);
  6. confere o resultado, como os testes das Etapas 3, 6 e 7 da coleção da Base.

Da raiz do repositório:

    python3 ferramentas/refazer_aula7.py

- Senha do Grafana trocada: GRAFANA_SENHA=suasenha python3 ferramentas/refazer_aula7.py
- O painel é regravado a cada execução: o que for mudado nele pela interface se perde.
- SEM_BUILD=1 não reconstrói a imagem da ESP32 (só para testes sem acesso ao PyPI).
"""

import base64
import json
import os
import pathlib
import subprocess
import sys
import time
import urllib.error
import urllib.request

ORION = "http://localhost:1026"
IOTA = "http://localhost:4041"
GRAFANA = "http://localhost:3000"
TENANT = {"fiware-service": "ccm130", "fiware-servicepath": "/"}
APIKEY, DEVICE = "ccm130", "esp32001"
ESTACAO, SALA = "urn:ngsi-ld:ClimateStation:ESP32001", "urn:ngsi-ld:Room:K501"
TABELA = "`urn_ngsi-ld_ClimateStation_ESP32001_ClimateStation`"      # uma tabela por entidade (Cygnus)
FIWARE = pathlib.Path(__file__).resolve().parent.parent / "fiware"
UID_FONTE, UID_PAINEL = "mysql-ccm130", "pel220-aula7-k501"
UMIDADE_ALTA, TOPICO = 70, "pel220/umida"                            # o exercício: humidity>70 em pel220/umida
USUARIO, SENHA = os.getenv("GRAFANA_USUARIO", "admin"), os.getenv("GRAFANA_SENHA", "admin")
LOGIN = "Basic " + base64.b64encode(f"{USUARIO}:{SENHA}".encode()).decode()

# --- corpos das requisições: os mesmos da coleção da Base ----------------------------------------
SALA_K501 = {"actionType": "append", "entities": [{
    "id": SALA, "type": "Room",
    "name": {"type": "Text", "value": "Laboratório K5-01"},
    "capacity": {"type": "Number", "value": 40}}]}

GRUPO = {"services": [{"apikey": APIKEY, "cbroker": "http://orion:1026", "entity_type": "Thing",
                       "resource": "/iot/json"}]}

ESP32 = {"devices": [{
    "device_id": DEVICE, "apikey": APIKEY, "entity_name": ESTACAO, "entity_type": "ClimateStation",
    "transport": "MQTT",
    "attributes": [{"object_id": "t", "name": "temperature", "type": "Number"},
                   {"object_id": "h", "name": "humidity", "type": "Number"},
                   {"object_id": "s", "name": "state", "type": "Text"}],
    "commands": [{"name": "on", "type": "command"}, {"name": "off", "type": "command"}],
    "static_attributes": [{"name": "refRoom", "type": "Relationship", "value": SALA}]}]}

SUB_CYGNUS = {
    "description": "Historico da ESP32 para o Cygnus",
    "subject": {"entities": [{"idPattern": ".*", "type": "ClimateStation"}],
                "condition": {"attrs": ["temperature", "humidity", "state"]}},
    "notification": {"http": {"url": "http://cygnus:5050/notify"},
                     "attrs": ["temperature", "humidity", "state"], "attrsFormat": "normalized"},
    "throttling": 1}

SUB_UMIDA = {                                   # no formato da "Sala quente via MQTT" (pasta C5)
    "description": "Umidade alta via MQTT",     # sem parênteses: o Orion recusa
    "subject": {"entities": [{"idPattern": ".*", "type": "ClimateStation"}],
                "condition": {"attrs": ["humidity"], "expression": {"q": f"humidity>{UMIDADE_ALTA}"}}},
    "notification": {"mqtt": {"url": "mqtt://mosquitto:1883", "topic": TOPICO},
                     "attrs": ["humidity", "refRoom"], "attrsFormat": "keyValues"}}


def eh_cygnus(s):
    return (s.get("notification", {}).get("http", {}).get("url") == "http://cygnus:5050/notify"
            and any(e.get("type") == "ClimateStation" for e in s["subject"]["entities"]))


def eh_umida(s):
    return s.get("notification", {}).get("mqtt", {}).get("topic") == TOPICO


# --- consultas do painel: as de fiware/queries.txt, mais as do exercício ----------------------------
SQL_AGORA = f"""SELECT
  recvTimeTs / 1000 AS "time",
  CAST(attrValue AS DECIMAL(6,1)) AS "agora"
FROM {TABELA}
WHERE attrName = 'temperature'
ORDER BY recvTimeTs DESC
LIMIT 1"""

SQL_TEMPERATURA = f"""SELECT
  recvTimeTs / 1000 AS "time",
  CAST(attrValue AS DECIMAL(6,1)) AS "temperatura"
FROM {TABELA}
WHERE attrName = 'temperature'
  AND $__unixEpochFilter(recvTimeTs / 1000)
ORDER BY recvTimeTs ASC"""

SQL_RELE = f"""SELECT
  recvTimeTs / 1000 AS "time",
  attrValue AS "relé"
FROM {TABELA}
WHERE attrName = 'state'
  AND $__unixEpochFilter(recvTimeTs / 1000)
ORDER BY recvTimeTs ASC"""

SQL_MEDIA = f"""SELECT
  $__unixEpochGroupAlias(recvTimeTs / 1000, '1m'),
  AVG(CAST(attrValue AS DECIMAL(6,1))) AS "média"
FROM {TABELA}
WHERE attrName = 'temperature'
  AND $__unixEpochFilter(recvTimeTs / 1000)
GROUP BY 1
ORDER BY 1"""

SQL_UMIDADE = f"""SELECT
  recvTimeTs / 1000 AS "time",
  CAST(attrValue AS DECIMAL(6,1)) AS "umidade"
FROM {TABELA}
WHERE attrName = 'humidity'
  AND $__unixEpochFilter(recvTimeTs / 1000)
ORDER BY recvTimeTs ASC"""

SQL_UMIDADE_MAX = f"""SELECT
  MAX(CAST(attrValue AS DECIMAL(6,1))) AS "máxima"
FROM {TABELA}
WHERE attrName = 'humidity'
  AND $__unixEpochFilter(recvTimeTs / 1000)"""


def faixas(*passos):
    """Limites de cor: faixas((cor, None), (cor, valor), ...)."""
    return {"mode": "absolute", "steps": [{"color": c, "value": v} for c, v in passos]}


def montar_painel(uid_fonte):
    fonte = {"type": "mysql", "uid": uid_fonte}

    def visual(n, tipo, titulo, x, y, w, h, sql, formato="time_series", padrao=None, opcoes=None):
        return {"id": n, "type": tipo, "title": titulo, "gridPos": {"x": x, "y": y, "w": w, "h": h},
                "datasource": fonte,
                "targets": [{"refId": "A", "datasource": fonte, "editorMode": "code", "rawQuery": True,
                             "format": formato, "rawSql": sql}],
                "fieldConfig": {"defaults": padrao or {}, "overrides": []}, "options": opcoes or {}}

    ultimo = {"reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
              "colorMode": "background", "graphMode": "none", "textMode": "auto"}
    linha = {"lineWidth": 2, "showPoints": "never"}
    paineis = [
        # Etapa 7, Passos 3 a 5 (o roteiro da Aula 7 e o fiware/queries.txt)
        visual(1, "stat", "Temperatura agora", 0, 0, 6, 8, SQL_AGORA,
               padrao={"unit": "celsius", "decimals": 1,
                       "thresholds": faixas(("blue", None), ("green", 24), ("red", 28))},
               opcoes=ultimo),
        visual(2, "timeseries", "Temperatura e os limites da regra (24 e 28 °C)", 6, 0, 18, 8, SQL_TEMPERATURA,
               padrao={"unit": "celsius", "color": {"mode": "fixed", "fixedColor": "green"},
                       "thresholds": faixas(("blue", None), ("transparent", 24), ("red", 28)),
                       "custom": {**linha, "thresholdsStyle": {"mode": "dashed+area"}}},
               opcoes={"legend": {"showLegend": False}, "tooltip": {"mode": "single"}}),
        visual(3, "state-timeline", "Relé da ESP32", 0, 8, 12, 7, SQL_RELE,
               padrao={"color": {"mode": "thresholds"},
                       "mappings": [{"type": "value", "options": {
                           "ON": {"color": "green", "index": 0, "text": "Ligado"},
                           "OFF": {"color": "gray", "index": 1, "text": "Desligado"}}}]},
               opcoes={"showValue": "auto", "mergeValues": True, "legend": {"showLegend": False}}),
        visual(4, "barchart", "Média da temperatura por minuto", 12, 8, 12, 7, SQL_MEDIA,
               padrao={"unit": "celsius", "decimals": 1, "color": {"mode": "fixed", "fixedColor": "blue"},
                       "custom": {"axisSoftMin": 20, "axisSoftMax": 30}},     # de 0 °C, as barras ficam iguais
               opcoes={"xTickLabelRotation": 0, "showValue": "auto", "legend": {"showLegend": False}}),
        # Para aprofundar (antes da Aula 8): a umidade e a máxima do período
        visual(5, "timeseries", f"Umidade e o limite do aviso MQTT ({UMIDADE_ALTA} %)", 0, 15, 16, 8, SQL_UMIDADE,
               padrao={"unit": "percent", "decimals": 1, "color": {"mode": "fixed", "fixedColor": "blue"},
                       "thresholds": faixas(("transparent", None), ("red", UMIDADE_ALTA)),
                       "custom": {**linha, "axisSoftMin": 40, "axisSoftMax": 80,
                                  "thresholdsStyle": {"mode": "dashed"}}},
               opcoes={"legend": {"showLegend": False}, "tooltip": {"mode": "single"}}),
        visual(6, "stat", "Umidade máxima no período", 16, 15, 8, 8, SQL_UMIDADE_MAX, formato="table",
               padrao={"unit": "percent", "decimals": 1,
                       "thresholds": faixas(("green", None), ("red", UMIDADE_ALTA))},
               opcoes=ultimo),
    ]
    return {"uid": UID_PAINEL, "title": "PEL 220 - Sala K501 - Aula 7", "tags": ["aula10"],
            "description": "Painel da Aula 7 (Etapa 7 da Base) com o exercício de antes da Aula 8: umidade e "
                           "máxima do período. Histórico gravado pelo Cygnus no MySQL (banco ccm130).",
            "timezone": "browser", "schemaVersion": 39, "editable": True, "refresh": "5s",
            "time": {"from": "now-15m", "to": "now"}, "panels": paineis}


# --- HTTP e docker compose --------------------------------------------------------------------------
def req(metodo, url, corpo=None, cabecalhos=None):
    dados = json.dumps(corpo).encode() if corpo is not None else None
    cab = dict(cabecalhos or {})
    if dados is not None:
        cab["Content-Type"] = "application/json"
    r = urllib.request.Request(url, data=dados, headers=cab, method=metodo)
    try:
        with urllib.request.urlopen(r, timeout=15) as resp:
            texto = resp.read().decode()
            return resp.status, (json.loads(texto) if texto else None), resp.headers
    except urllib.error.HTTPError as e:
        texto = e.read().decode()
        try:
            return e.code, (json.loads(texto) if texto else None), e.headers
        except ValueError:
            return e.code, texto, e.headers
    except (urllib.error.URLError, ConnectionError, TimeoutError) as e:
        return 0, str(e), None


def fiware(metodo, url, corpo=None):
    return req(metodo, url, corpo, TENANT)


def grafana(metodo, caminho, corpo=None):
    return req(metodo, GRAFANA + caminho, corpo, {"Authorization": LOGIN})


def compose(*args):
    print("   $ docker compose " + " ".join(args), flush=True)
    subprocess.run(["docker", "compose", *args], cwd=FIWARE, check=True)


def falhar(texto):
    print(f"\nERRO: {texto}")
    sys.exit(1)


def esperar(teste, segundos, passo=3):
    """Repete teste() até ele devolver algo verdadeiro ou o tempo acabar; devolve o último resultado."""
    fim = time.time() + segundos
    while True:
        r = teste()
        if r or time.time() > fim:
            return r
        time.sleep(passo)


def consultar(sql, desde="now-15m", formato="table"):
    """Roda uma consulta na fonte de dados pelo Grafana; devolve (linhas, erro)."""
    corpo = {"from": desde, "to": "now", "queries": [{"refId": "A", "datasource": {"uid": UID_ATUAL[0]},
                                                      "rawSql": sql, "format": formato}]}
    st, r, _ = grafana("POST", "/api/ds/query", corpo)
    if st != 200:
        return 0, f"HTTP {st}: {str(r)[:200]}"
    res = r["results"]["A"]
    if res.get("error"):
        return 0, res["error"]
    quadros = res.get("frames") or []
    valores = quadros[0]["data"]["values"] if quadros else []
    return (len(valores[0]) if valores else 0), None


UID_ATUAL = [UID_FONTE]          # o uid da fonte de dados em uso (pode ser uma que já existia)


# --- os passos ---------------------------------------------------------------------------------------
def cadastrar():
    st, r, _ = fiware("POST", ORION + "/v2/op/update", SALA_K501)
    if st != 204:
        falhar(f"sala K501 no Orion: HTTP {st} {r}")
    print("   sala urn:ngsi-ld:Room:K501 no Orion")

    st, r, _ = fiware("POST", IOTA + "/iot/services", GRUPO)
    if st not in (201, 409):
        falhar(f"grupo de serviço no IoT Agent: HTTP {st} {r}")
    print("   grupo de serviço (apikey ccm130):", "criado" if st == 201 else "já existia")

    st, r, _ = fiware("GET", IOTA + f"/iot/devices/{DEVICE}")
    if st == 200 and (r.get("entity_name") != ESTACAO or r.get("entity_type") != "ClimateStation"):
        print(f"   a ESP32 estava provisionada como {r.get('entity_name')}: apagando para provisionar de novo")
        fiware("DELETE", IOTA + f"/iot/devices/{DEVICE}")
        st = 404
    if st == 404:
        st2, r2, _ = fiware("POST", IOTA + "/iot/devices", ESP32)
        if st2 != 201:
            falhar(f"provisionamento da ESP32: HTTP {st2} {r2}")
        print("   ESP32 esp32001 provisionada (urn:ngsi-ld:ClimateStation:ESP32001)")
    elif st == 200:
        print("   ESP32 esp32001 já estava provisionada")
    else:
        falhar(f"consulta da ESP32 no IoT Agent: HTTP {st} {r}")

    st, _, _ = fiware("DELETE", ORION + "/v2/entities/Thing:esp32001")
    if st == 204:
        print("   apagada a entidade Thing:esp32001 (surgiu de uma medida sem provisionamento)")


def garantir_subscricao(corpo, e_esta):
    st, subs, _ = fiware("GET", ORION + "/v2/subscriptions?limit=100")
    if st != 200:
        falhar(f"lista de subscrições: HTTP {st} {subs}")
    achadas = [s for s in subs if e_esta(s)]
    if not achadas:
        st, r, cab = fiware("POST", ORION + "/v2/subscriptions", corpo)
        if st != 201:
            falhar(f"subscrição \"{corpo['description']}\": HTTP {st} {r}")
        print(f"   \"{corpo['description']}\": criada")
        return cab["Location"].rsplit("/", 1)[-1]
    sid = achadas[0]["id"]
    st, r, _ = fiware("PATCH", ORION + f"/v2/subscriptions/{sid}", corpo)
    if st != 204:
        falhar(f"subscrição \"{corpo['description']}\": HTTP {st} {r}")
    print(f"   \"{corpo['description']}\": já existia, conferida")
    for copia in achadas[1:]:                 # duas iguais gravariam (ou avisariam) cada medida duas vezes
        fiware("DELETE", ORION + f"/v2/subscriptions/{copia['id']}")
        print(f"   apagada uma cópia repetida ({copia['id']})")
    return sid


def fonte_de_dados():
    if esperar(lambda: grafana("GET", "/api/health")[0] == 200, 120) is not True:
        falhar("o Grafana da Base não respondeu em http://localhost:3000")
    st, fontes, _ = grafana("GET", "/api/datasources")
    if st == 401:
        falhar(f"o Grafana recusou {USUARIO}/{SENHA}: rode de novo com GRAFANA_SENHA=suasenha")
    if st != 200:
        falhar(f"lista de fontes de dados: HTTP {st} {fontes}")
    for f in fontes:
        banco = (f.get("jsonData") or {}).get("database") or f.get("database")
        if f["type"] == "mysql" and f.get("url") == "mysql-db:3306" and banco == "ccm130":
            print(f"   fonte de dados \"{f['name']}\": já existia")
            return f["uid"]
    corpo = {"name": "mysql", "uid": UID_FONTE, "type": "mysql", "access": "proxy", "url": "mysql-db:3306",
             "user": "root", "jsonData": {"database": "ccm130", "maxOpenConns": 10},
             "secureJsonData": {"password": "123"}, "isDefault": True}       # senha de laboratório da Base
    st, r, _ = grafana("POST", "/api/datasources", corpo)
    if st == 409:                             # nome ou uid já usados por outra fonte
        corpo.update(name="mysql ccm130", uid=UID_FONTE + "-aula7")
        st, r, _ = grafana("POST", "/api/datasources", corpo)
    if st != 200:
        falhar(f"fonte de dados: HTTP {st} {r}")
    print(f"   fonte de dados \"{corpo['name']}\": criada (MySQL, mysql-db:3306, banco ccm130)")
    return r["datasource"]["uid"]


def gravar_painel(uid_fonte):
    corpo = {"dashboard": montar_painel(uid_fonte), "overwrite": True, "message": "ferramentas/refazer_aula7.py"}
    st, r, _ = grafana("POST", "/api/dashboards/db", corpo)
    if st != 200:
        falhar(f"painel: HTTP {st} {r}")
    print(f"   painel \"{corpo['dashboard']['title']}\" gravado (etiqueta aula10, 6 visualizações)")
    return r["url"]


def conferir(sub_cygnus, sub_umida):
    falhas = []

    def item(ok, texto):
        print(("   ✓ " if ok else "   ✗ ") + texto, flush=True)
        if not ok:
            falhas.append(texto)

    def medidas():
        st, e, _ = fiware("GET", ORION + f"/v2/entities/{ESTACAO}?options=keyValues")
        return e if st == 200 and "temperature" in e else None
    e = esperar(medidas, 60)
    item(e, "Etapa 3: as medidas da ESP32 chegam ao Orion"
         + (f" (t = {e['temperature']} °C, h = {e['humidity']} %, relé {e['state']})" if e else ""))
    item(fiware("GET", ORION + "/v2/entities/Thing:esp32001")[0] == 404, "Etapa 3: não surgiu Thing:esp32001")

    def notificou():
        st, s, _ = fiware("GET", ORION + f"/v2/subscriptions/{sub_cygnus}")
        n = s.get("notification", {}) if st == 200 else {}
        return n if n.get("timesSent", 0) > 0 and n.get("lastSuccessCode") == 200 else None
    n = esperar(notificou, 60)
    item(n, "Etapa 6: o Orion notifica o Cygnus"
         + (f" (timesSent = {n['timesSent']}, última resposta 200)" if n else ""))

    st, fontes, _ = grafana("GET", "/api/datasources")
    f = next((x for x in fontes if x["type"] == "mysql"), None) if st == 200 else None
    item(f and f.get("url") == "mysql-db:3306", "Etapa 7: a fonte MySQL aponta para mysql-db:3306")
    sql = (f"SELECT recvTimeTs / 1000 AS time, CAST(attrValue AS DECIMAL(6,1)) AS value FROM {TABELA} "
           "WHERE attrName = 'temperature' ORDER BY recvTimeTs DESC LIMIT 50")      # a da coleção
    linhas = esperar(lambda: consultar(sql, "now-1h")[0], 90)
    item(linhas, f"Etapa 7: a fonte enxerga o histórico ({linhas} {'medida' if linhas == 1 else 'medidas'} "
                 "de temperatura)")

    st, achados, _ = grafana("GET", "/api/search?tag=aula10&type=dash-db")
    item(st == 200 and achados, "Etapa 7: há um painel com a etiqueta aula10")
    st, d, _ = grafana("GET", f"/api/dashboards/uid/{UID_PAINEL}")
    paineis = d["dashboard"]["panels"] if st == 200 else []
    tipos = {p["type"] for p in paineis}
    item({"timeseries", "stat", "state-timeline"} <= tipos, "Etapa 7: Time series, Stat e State timeline")
    for p in paineis:
        for alvo in p.get("targets", []):
            n_linhas, erro = consultar(alvo["rawSql"], "now-15m", alvo["format"])
            item(not erro, f"consulta de \"{p['title']}\": {erro or f'{n_linhas} linha(s)'}")

    item(any(p["type"] == "timeseries" and "'humidity'" in p["targets"][0]["rawSql"] for p in paineis),
         "exercício: umidade em Time series")
    item(any(p["type"] == "stat" and "MAX(" in p["targets"][0]["rawSql"] for p in paineis),
         "exercício: Stat com a máxima do período")
    st, s, _ = fiware("GET", ORION + f"/v2/subscriptions/{sub_umida}")
    ok = (st == 200 and s.get("status") == "active"
          and s["subject"]["condition"].get("expression", {}).get("q") == f"humidity>{UMIDADE_ALTA}"
          and s["notification"].get("mqtt", {}).get("topic") == TOPICO)
    item(ok, f"exercício: subscrição MQTT ativa, humidity>{UMIDADE_ALTA} avisa em {TOPICO}")
    return falhas


def link(porta, caminho=""):
    nome = os.getenv("CODESPACE_NAME")
    if nome:
        dominio = os.getenv("GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN", "app.github.dev")
        return f"https://{nome}-{porta}.{dominio}{caminho}"
    return f"http://localhost:{porta}{caminho}"


def main():
    print("== 1/6 Parando a ESP32 da aula (volta depois do cadastro); orion, iot-agent e cygnus")
    compose("stop", "esp32-simulada")
    compose("up", "-d", "--wait", "orion")
    compose("up", "-d", "--wait", "iot-agent")
    compose("up", "-d", "--wait", "cygnus")

    print("== 2/6 Etapas 1 e 2: a sala K501 e a ESP32 no IoT Agent")
    cadastrar()

    print("== 3/6 Etapa 6 e exercício: as subscrições do histórico e da umidade alta")
    sub_cygnus = garantir_subscricao(SUB_CYGNUS, eh_cygnus)
    sub_umida = garantir_subscricao(SUB_UMIDA, eh_umida)

    print("== 4/6 A ESP32 da aula e o Grafana da Base")
    compose("up", "-d", *([] if os.getenv("SEM_BUILD") == "1" else ["--build"]), "esp32-simulada")
    compose("up", "-d", "grafana")

    print("== 5/6 Etapa 7: a fonte de dados e o painel")
    UID_ATUAL[0] = fonte_de_dados()
    url = gravar_painel(UID_ATUAL[0])

    print("== 6/6 Conferência (os testes das Etapas 3, 6 e 7 da coleção, mais o exercício)")
    falhas = conferir(sub_cygnus, sub_umida)

    print()
    print(f"Painel da aula:  {link(3000, url)}  (login {USUARIO}/{SENHA})")
    print("Aviso de umidade alta, num terminal:")
    print(f"  docker exec mosquitto mosquitto_sub -t '{TOPICO}' -v")
    print("Para forçar um aviso (a ESP32 manda h = 75 %, e o valor vai também para o histórico):")
    print("  docker exec mosquitto mosquitto_pub -t /json/ccm130/esp32001/attrs -m '{\"h\": 75}'")
    if os.getenv("CODESPACE_NAME"):
        print("Se o link der 404: aba PORTAS → Adicionar Porta → 3000 → Enter.")
    if falhas:
        print(f"\n{len(falhas)} item(ns) não conferiram. Rode de novo em 1 minuto: o histórico pode estar começando.")
        sys.exit(1)
    print("\nTudo conferido.")


if __name__ == "__main__":
    main()
