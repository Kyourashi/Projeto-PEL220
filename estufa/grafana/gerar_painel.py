"""
Gera estufa/grafana/paineis/painel_estufa.json (o painel do grupo, marco da Aula 8).

O JSON é o que o Grafana carrega por provisionamento; este script só existe para
deixar as consultas SQL legíveis e fáceis de revisar. Depois de editar:

    python3 estufa/grafana/gerar_painel.py
    cd fiware && docker compose restart grafana-estufa
"""

import json
import pathlib

DS = {"type": "mysql", "uid": "mysql-estufa"}
TABELA = "`urn_ngsi-ld_Device_ESP32-001_Device`"     # Cygnus: <id>_<type>, ':' trocado por '_'
SAIDA = pathlib.Path(__file__).parent / "paineis" / "painel_estufa.json"

LIGADO = [{"type": "value", "options": {
    "ON": {"color": "green", "index": 0, "text": "Ligado"},
    "OFF": {"color": "gray", "index": 1, "text": "Desligado"}}}]

_id = 0


def proximo_id():
    global _id
    _id += 1
    return _id


def alvo(sql, ref="A", formato="time_series"):
    return {"refId": ref, "datasource": DS, "editorMode": "code", "format": formato,
            "rawQuery": True, "rawSql": sql.strip()}


def linha(titulo, y):
    return {"id": proximo_id(), "type": "row", "title": titulo, "collapsed": False,
            "gridPos": {"x": 0, "y": y, "w": 24, "h": 1}, "panels": []}


def agora(atributo, apelido):
    return f"""
SELECT
  recvTimeTs / 1000 AS "time",
  CAST(attrValue AS DECIMAL(6,2)) AS "{apelido}"
FROM {TABELA}
WHERE attrName = '{atributo}'
ORDER BY recvTimeTs DESC
LIMIT 1"""


def estado_agora(atributo, apelido):
    return f"""
SELECT attrValue AS "{apelido}"
FROM {TABELA}
WHERE attrName = '{atributo}'
ORDER BY recvTimeTs DESC
LIMIT 1"""


def historico(atributo, apelido, cast=True):
    valor = f"CAST(attrValue AS DECIMAL(6,1))" if cast else "attrValue"
    return f"""
SELECT
  recvTimeTs / 1000 AS "time",
  {valor} AS "{apelido}"
FROM {TABELA}
WHERE attrName = '{atributo}'
  AND $__unixEpochFilter(recvTimeTs / 1000)
ORDER BY recvTimeTs ASC"""


def stat(titulo, x, y, w, h, alvos, unidade=None, decimais=None, limiares=None, mapas=None,
         campos="", modo_cor="background", texto=None, descricao=None):
    defaults = {}
    if unidade:
        defaults["unit"] = unidade
    if decimais is not None:
        defaults["decimals"] = decimais
    if limiares:
        defaults["thresholds"] = {"mode": "absolute", "steps": limiares}
        defaults["color"] = {"mode": "thresholds"}
    else:
        defaults["color"] = {"mode": "fixed", "fixedColor": "text"}
    if mapas:
        defaults["mappings"] = mapas
    opcoes = {"reduceOptions": {"calcs": ["lastNotNull"], "fields": campos, "values": False},
              "colorMode": modo_cor if (limiares or mapas) else "value", "graphMode": "none",
              "justifyMode": "center"}
    if texto:
        opcoes["textMode"] = texto
    p = {"id": proximo_id(), "title": titulo, "type": "stat", "datasource": DS,
         "gridPos": {"x": x, "y": y, "w": w, "h": h},
         "fieldConfig": {"defaults": defaults, "overrides": []}, "options": opcoes, "targets": alvos}
    if descricao:
        p["description"] = descricao
    return p


def serie(titulo, x, y, w, h, alvos, unidade, limiares, cor, descricao, minimo=None, maximo=None):
    defaults = {"unit": unidade, "color": {"mode": "fixed", "fixedColor": cor},
                "thresholds": {"mode": "absolute", "steps": limiares},
                "custom": {"lineWidth": 2, "showPoints": "never", "thresholdsStyle": {"mode": "dashed+area"}}}
    if minimo is not None:
        defaults["min"] = minimo
    if maximo is not None:
        defaults["max"] = maximo
    return {"id": proximo_id(), "title": titulo, "type": "timeseries", "datasource": DS,
            "description": descricao, "gridPos": {"x": x, "y": y, "w": w, "h": h},
            "fieldConfig": {"defaults": defaults, "overrides": []},
            "options": {"legend": {"showLegend": False}, "tooltip": {"mode": "single"}}, "targets": alvos}


painel = []

# --- Pergunta 1 -------------------------------------------------------------------
painel.append(linha("1 · A estufa está bem agora?  —  para o operador da estufa", 0))
painel += [
    stat("Temperatura do ar", 0, 1, 4, 6, [alvo(agora("temperature", "temperatura"))], "celsius", 1,
         [{"color": "blue", "value": None}, {"color": "green", "value": 24}, {"color": "red", "value": 28}],
         descricao="Última medida do DHT22. Azul abaixo de 24 °C, verde na faixa, vermelho a partir de 28 °C "
                   "(os limites do ventilador na AgriGreenhouse)."),
    stat("Umidade do solo", 4, 1, 4, 6, [alvo(agora("soilMoisture", "solo"))], "percent", 1,
         [{"color": "red", "value": None}, {"color": "green", "value": 30}, {"color": "blue", "value": 45}],
         descricao="Última medida do sensor capacitivo. Vermelho abaixo de 30 % (a bomba deve ligar), "
                   "verde na faixa, azul a partir de 45 % (a bomba deve desligar)."),
    stat("Umidade do ar", 8, 1, 4, 6, [alvo(agora("relativeHumidity", "umidade do ar"))], "percentunit", 0,
         descricao="relativeHumidity de 0 a 1, mostrada em %. Sem limiar de cor: o grupo ainda não definiu "
                   "uma faixa para a cultura."),
    stat("Luz (LDR)", 12, 1, 4, 6, [alvo(agora("lightLevel", "luz"))], "percent", 0,
         descricao="% da escala do ADC do LDR: nível relativo, não lux."),
    stat("Ventilador", 16, 1, 4, 6, [alvo(estado_agora("fanState", "ventilador"), formato="table")],
         mapas=LIGADO, campos="/^ventilador$/", texto="value",
         descricao="Estado que a ESP32 informa (fanState). É o estado observado, não o comando pedido."),
    stat("Bomba", 20, 1, 4, 6, [alvo(estado_agora("pumpState", "bomba"), formato="table")],
         mapas=LIGADO, campos="/^bomba$/", texto="value",
         descricao="Estado que a ESP32 informa (pumpState)."),
]

# --- Pergunta 2 -------------------------------------------------------------------
painel.append(linha("2 · O controle mantém a estufa nas faixas?  —  para o grupo, que avalia a regra de histerese", 7))
painel += [
    serie("Temperatura do ar e os limites do ventilador (24 °C e 28 °C)", 0, 8, 12, 8,
          [alvo(historico("temperature", "temperatura"))], "celsius",
          [{"color": "blue", "value": None}, {"color": "transparent", "value": 24}, {"color": "red", "value": 28}],
          "green", "A curva deve oscilar entre as linhas: o ventilador liga ao cruzar 28 °C e desliga ao "
                   "cruzar 24 °C. Ficar acima da linha vermelha por muito tempo indica ventilação insuficiente.",
          20, 32),
    serie("Umidade do solo e os limites da bomba (30 % e 45 %)", 12, 8, 12, 8,
          [alvo(historico("soilMoisture", "solo"))], "percent",
          [{"color": "red", "value": None}, {"color": "transparent", "value": 30}, {"color": "blue", "value": 45}],
          "orange", "Dente de serra: o solo seca devagar e a bomba o molha depressa entre 30 % e 45 %.",
          20, 55),
    {"id": proximo_id(), "title": "Ventilador e bomba ao longo do tempo", "type": "state-timeline",
     "datasource": DS, "gridPos": {"x": 0, "y": 16, "w": 24, "h": 5},
     "description": "Quando cada relé esteve ligado. Compare com as curvas acima: cada faixa verde do ventilador "
                    "deve começar em 28 °C e terminar em 24 °C.",
     "fieldConfig": {"defaults": {"color": {"mode": "thresholds"}, "mappings": LIGADO}, "overrides": []},
     "options": {"showValue": "auto", "mergeValues": True, "rowHeight": 0.8, "legend": {"showLegend": False}},
     "targets": [alvo(historico("fanState", "ventilador", cast=False), "A"),
                 alvo(historico("pumpState", "bomba", cast=False), "B")]},
]

# --- Pergunta 3 -------------------------------------------------------------------
JANELAS = f"""
SELECT
  $__unixEpochGroupAlias(recvTimeTs / 1000, '5m'),
  100 * AVG(CASE WHEN attrName = 'fanState'  THEN attrValue = 'ON' END) AS "ventilador",
  100 * AVG(CASE WHEN attrName = 'pumpState' THEN attrValue = 'ON' END) AS "bomba"
FROM {TABELA}
WHERE attrName IN ('fanState', 'pumpState')
  AND $__unixEpochFilter(recvTimeTs / 1000)
GROUP BY 1
ORDER BY 1"""

PERIODO = f"""
SELECT
  100 * AVG(CASE WHEN attrName = 'fanState'  THEN attrValue = 'ON' END) AS "ventilador",
  100 * AVG(CASE WHEN attrName = 'pumpState' THEN attrValue = 'ON' END) AS "bomba"
FROM {TABELA}
WHERE attrName IN ('fanState', 'pumpState')
  AND $__unixEpochFilter(recvTimeTs / 1000)"""

ACIONAMENTOS = f"""
SELECT
  SUM(attrName = 'fanState')  AS "ventilador",
  SUM(attrName = 'pumpState') AS "bomba"
FROM (
  SELECT attrName, attrValue,
         LAG(attrValue) OVER (PARTITION BY attrName ORDER BY recvTimeTs) AS anterior
  FROM {TABELA}
  WHERE attrName IN ('fanState', 'pumpState')
    AND $__unixEpochFilter(recvTimeTs / 1000)
) AS mudancas
WHERE attrValue = 'ON' AND anterior = 'OFF'"""

painel.append(linha("3 · Quanto tempo os atuadores ficam ligados?  —  para quem paga a energia e a água", 21))
painel += [
    {"id": proximo_id(), "title": "Tempo ligado em cada janela de 5 minutos", "type": "barchart",
     "datasource": DS, "gridPos": {"x": 0, "y": 22, "w": 14, "h": 8},
     "description": "Fração do tempo com o relé ligado (ciclo de trabalho), por janela de 5 min. "
                    "Ventilador: energia; bomba: energia e água.",
     "fieldConfig": {"defaults": {"unit": "percent", "decimals": 0, "min": 0, "max": 100},
                     "overrides": [
                         {"matcher": {"id": "byName", "options": "ventilador"},
                          "properties": [{"id": "color", "value": {"mode": "fixed", "fixedColor": "green"}}]},
                         {"matcher": {"id": "byName", "options": "bomba"},
                          "properties": [{"id": "color", "value": {"mode": "fixed", "fixedColor": "blue"}}]}]},
     "options": {"xTickLabelRotation": 0, "showValue": "auto", "groupWidth": 0.7,
                 "legend": {"showLegend": True, "displayMode": "list", "placement": "bottom"}},
     "targets": [alvo(JANELAS)]},
    stat("Tempo ligado no período", 14, 22, 5, 8, [alvo(PERIODO, formato="table")], "percent", 0,
         campos="", texto="value_and_name",
         descricao="Ciclo de trabalho no período do seletor: média das amostras ligadas (uma a cada 5 s)."),
    stat("Acionamentos no período", 19, 22, 5, 8, [alvo(ACIONAMENTOS, formato="table")], None, 0,
         campos="", texto="value_and_name",
         descricao="Quantas vezes cada relé passou de OFF para ON: desgaste do relé e picos de partida do motor."),
]

dashboard = {
    "uid": "pel220-estufa",
    "title": "Estufa 001 — painel do grupo",
    "description": "PEL220 · projeto estufa agrícola inteligente · marco da Aula 8. Histórico gravado pelo Cygnus "
                   "no MySQL (banco estufa) a partir da subscrição 'Historico da estufa para o Cygnus'.",
    "tags": ["pel220", "estufa", "aula08"],
    "editable": True,
    "schemaVersion": 39,
    "version": 1,
    "refresh": "5s",
    "time": {"from": "now-30m", "to": "now"},
    "templating": {"list": []},
    "annotations": {"list": []},
    "panels": painel,
}

SAIDA.write_text(json.dumps(dashboard, indent=2, ensure_ascii=False) + "\n")
print(f"gravado: {SAIDA} ({len(painel)} itens)")
