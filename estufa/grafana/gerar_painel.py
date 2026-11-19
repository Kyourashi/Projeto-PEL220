"""
Gera estufa/grafana/paineis/painel_estufa.json (o painel do grupo, marco da Aula 8).

O JSON é o que o Grafana carrega por provisionamento; este script só existe para
deixar as consultas SQL legíveis e fáceis de revisar. Os limites, as potências e a
vazão vêm do modelo de dados (modelo-dados/), então rode de novo quando eles mudarem:

    python3 estufa/grafana/gerar_painel.py
    cd fiware && docker compose restart grafana-estufa
"""

import json
import pathlib

DS = {"type": "mysql", "uid": "mysql-estufa"}
TABELA = "`urn_ngsi-ld_Device_ESP32-001_Device`"     # Cygnus: <id>_<type>, ':' trocado por '_'
TABELA_CLIMA = "`urn_ngsi-ld_WeatherObserved_FEI_WeatherObserved`"
AQUI = pathlib.Path(__file__).resolve().parent
SAIDA = AQUI / "paineis" / "painel_estufa.json"
MODELO = AQUI.parent.parent / "modelo-dados"

# Os números do painel vêm do modelo de dados, não são digitados aqui:
#   limites de controle  → exemplos/AgriGreenhouse.json
#   potências e vazão    → provisionamento/dispositivo.json (atributos estáticos da ESP32)
ESTUFA = json.loads((MODELO / "exemplos" / "AgriGreenhouse.json").read_text())
NO = json.loads((MODELO / "provisionamento" / "dispositivo.json").read_text())["devices"][0]
NOMINAL = {a["name"]: a["value"] for a in NO["static_attributes"] if a["type"] == "Number"}
LIGA_VENT, DESLIGA_VENT = ESTUFA["fanOnTemperature"]["value"], ESTUFA["fanOffTemperature"]["value"]
LIGA_BOMBA, DESLIGA_BOMBA = ESTUFA["irrigationOnSoilMoisture"]["value"], ESTUFA["irrigationOffSoilMoisture"]["value"]
P_VENT, P_BOMBA, Q_BOMBA = NOMINAL["fanRatedPower"], NOMINAL["pumpRatedPower"], NOMINAL["pumpFlowRate"]
DT = 5                       # s entre amostras (INTERVALO da ESP32): cada amostra ON vale 5 s ligado
FRIO_ALFACE = 18             # °C, limite inferior da faixa da alface (18 a 23 °C)
DLI_MIN, DLI_MAX = 14, 18    # mol/m²/dia para alface
VPD = (0.45, 1.25, 1.5)      # kPa: úmido demais | faixa | atenção | estresse
LUX_PARA_PPFD = 0.0185       # µmol/m²/s por lx, luz do sol

LIGADO = [{"type": "value", "options": {
    "ON": {"color": "green", "index": 0, "text": "Ligado"},
    "OFF": {"color": "gray", "index": 1, "text": "Desligado"}}}]

_id = 0


def proximo_id():
    global _id
    _id += 1
    return _id


def br(x):
    """Número com vírgula decimal, para os textos do painel."""
    return f"{x:g}".replace(".", ",")


def alvo(sql, ref="A", formato="time_series"):
    return {"refId": ref, "datasource": DS, "editorMode": "code", "format": formato,
            "rawQuery": True, "rawSql": sql.strip()}


def linha(titulo, y):
    return {"id": proximo_id(), "type": "row", "title": titulo, "collapsed": False,
            "gridPos": {"x": 0, "y": y, "w": 24, "h": 1}, "panels": []}


def agora(atributo, apelido, valor="CAST(attrValue AS DECIMAL(10,2))"):
    return f"""
SELECT
  recvTimeTs / 1000 AS "time",
  {valor} AS "{apelido}"
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


def cor(nome, valor):
    return {"color": nome, "value": valor}


def campo(nome, **propriedades):
    """Override do Grafana: propriedades de uma coluna, pelo nome."""
    return {"matcher": {"id": "byName", "options": nome},
            "properties": [{"id": k.replace("__", "."), "value": v} for k, v in propriedades.items()]}


def stat(titulo, x, y, w, h, alvos, unidade=None, decimais=None, limiares=None, mapas=None,
         campos="", modo_cor="background", texto=None, descricao=None, tempo=None, sobreposicoes=None,
         orientacao=None):
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
         "fieldConfig": {"defaults": defaults, "overrides": sobreposicoes or []}, "options": opcoes,
         "targets": alvos}
    if descricao:
        p["description"] = descricao
    if tempo:
        p["timeFrom"] = tempo                          # janela própria, independente do seletor
        p["hideTimeOverride"] = True                   # o título já diz a janela
    if orientacao:
        opcoes["orientation"] = orientacao
    return p


def serie(titulo, x, y, w, h, alvos, unidade, limiares, cor_linha, descricao, minimo=None, maximo=None,
          sobreposicoes=None, legenda=False):
    custom = {"lineWidth": 2, "showPoints": "never", "thresholdsStyle": {"mode": "dashed+area"}}
    if minimo is not None:
        custom["axisSoftMin"] = minimo                 # limites "macios": o eixo cresce se o dado passar
    if maximo is not None:
        custom["axisSoftMax"] = maximo
    defaults = {"unit": unidade, "color": {"mode": "fixed", "fixedColor": cor_linha},
                "thresholds": {"mode": "absolute", "steps": limiares}, "custom": custom}
    return {"id": proximo_id(), "title": titulo, "type": "timeseries", "datasource": DS,
            "description": descricao, "gridPos": {"x": x, "y": y, "w": w, "h": h},
            "fieldConfig": {"defaults": defaults, "overrides": sobreposicoes or []},
            "options": {"legend": {"showLegend": legenda, "displayMode": "list", "placement": "bottom"},
                        "tooltip": {"mode": "multi" if legenda else "single"}},
            "targets": alvos}


painel = []

# --- Pergunta 1 -------------------------------------------------------------------
DLI_SQL = f"""
SELECT
  AVG(CAST(attrValue AS DECIMAL(10,1))) * {LUX_PARA_PPFD} * 86400 / 1000000 AS "DLI"
FROM {TABELA}
WHERE attrName = 'illuminance'
  AND $__unixEpochFilter(recvTimeTs / 1000)"""

painel.append(linha("1 · A estufa está bem agora?  —  para o operador da estufa", 0))
painel += [
    stat("Temperatura", 0, 1, 3, 6, [alvo(agora("temperature", "temperatura"))], "celsius", 1,
         [cor("blue", None), cor("green", FRIO_ALFACE), cor("red", LIGA_VENT)],
         descricao=f"Última medida do DHT22. Alface: azul abaixo de {FRIO_ALFACE} °C, verde na faixa, vermelho a "
                   f"partir de {LIGA_VENT} °C, quando o ventilador deve estar ligado (fanOnTemperature)."),
    stat("Umidade do solo", 3, 1, 3, 6, [alvo(agora("soilMoisture", "solo"))], "percent", 1,
         [cor("red", None), cor("green", LIGA_BOMBA), cor("blue", DESLIGA_BOMBA)],
         descricao=f"Última medida do sensor capacitivo. Vermelho abaixo de {LIGA_BOMBA} % (a bomba deve ligar), "
                   f"verde na faixa, azul a partir de {DESLIGA_BOMBA} % (a bomba deve desligar)."),
    stat("Umidade do ar", 6, 1, 3, 6, [alvo(agora("relativeHumidity", "umidade do ar"))], "percentunit", 0,
         descricao="relativeHumidity de 0 a 1, mostrada em %. Sem cor: quem diz se o ar está úmido ou seco "
                   "demais é o VPD, ao lado, que junta umidade e temperatura."),
    stat("VPD", 9, 1, 3, 6, [alvo(agora("vaporPressureDeficit", "VPD"))], "pressurekpa", 2,
         [cor("blue", None), cor("green", VPD[0]), cor("orange", VPD[1]), cor("red", VPD[2])],
         descricao=f"Déficit de pressão de vapor, calculado na ESP32 com a temperatura e a umidade (Tetens/FAO-56). "
                   f"Azul abaixo de {br(VPD[0])} kPa: ar úmido demais, risco de doença. Verde até {br(VPD[1])}. "
                   f"Laranja até {br(VPD[2])}. Vermelho acima: estresse hídrico."),
    stat("Luz agora", 12, 1, 3, 6,
         [alvo(agora("illuminance", "luz", "CAST(attrValue AS DECIMAL(10,1)) / 1000"))], "suffix: klx", 1,
         descricao="Iluminância do BH1750, em klx. Sem cor: o que conta para a planta é a luz do dia inteiro "
                   "(o DLI, ao lado)."),
    stat("DLI (24 h)", 15, 1, 3, 6, [alvo(DLI_SQL, formato="table")], "suffix: mol/m²/d", 1,
         [cor("orange", None), cor("green", DLI_MIN), cor("orange", DLI_MAX)], campos="/^DLI$/", tempo="24h",
         descricao=f"Luz diária integrada das últimas 24 h: média da iluminância × {br(LUX_PARA_PPFD)} (lx → "
                   f"µmol/m²/s, luz do sol) × 86 400 s ÷ 10⁶. Alface: {DLI_MIN} a {DLI_MAX} mol/m²/dia (verde)."),
    stat("Ventilador", 18, 1, 3, 6, [alvo(estado_agora("fanState", "ventilador"), formato="table")],
         mapas=LIGADO, campos="/^ventilador$/", texto="value",
         descricao="Estado que a ESP32 informa (fanState). É o estado observado, não o comando pedido."),
    stat("Bomba", 21, 1, 3, 6, [alvo(estado_agora("pumpState", "bomba"), formato="table")],
         mapas=LIGADO, campos="/^bomba$/", texto="value",
         descricao="Estado que a ESP32 informa (pumpState)."),
]

# --- Pergunta 2 -------------------------------------------------------------------
# Lá fora: uma leitura a cada 15 min. A consulta junta a última leitura antes da janela,
# as leituras da janela e a última leitura repetida no fim da janela, para a linha em
# degraus cobrir o gráfico inteiro (cada leitura vale até a próxima).
LA_FORA = f"""
SELECT t_s AS "time", externa AS "lá fora"
FROM (
  (SELECT recvTimeTs / 1000 AS t_s, CAST(attrValue AS DECIMAL(6,1)) AS externa
   FROM {TABELA_CLIMA}
   WHERE attrName = 'temperature' AND recvTimeTs < $__unixEpochFrom() * 1000
   ORDER BY recvTimeTs DESC LIMIT 1)
  UNION ALL
  (SELECT recvTimeTs / 1000, CAST(attrValue AS DECIMAL(6,1))
   FROM {TABELA_CLIMA}
   WHERE attrName = 'temperature' AND $__unixEpochFilter(recvTimeTs / 1000))
  UNION ALL
  (SELECT $__unixEpochTo(), CAST(attrValue AS DECIMAL(6,1))
   FROM {TABELA_CLIMA}
   WHERE attrName = 'temperature' AND recvTimeTs <= $__unixEpochTo() * 1000
   ORDER BY recvTimeTs DESC LIMIT 1)
) AS leituras
ORDER BY t_s"""

painel.append(linha("2 · O controle mantém a estufa nas faixas?  —  para o grupo, que avalia a regra de histerese", 7))
painel += [
    serie(f"Temperatura do ar dentro e lá fora, e os limites do ventilador ({DESLIGA_VENT} °C e {LIGA_VENT} °C)",
          0, 8, 12, 8, [alvo(historico("temperature", "dentro"), "A"), alvo(LA_FORA, "B")], "celsius",
          [cor("blue", None), cor("transparent", FRIO_ALFACE), cor("green", DESLIGA_VENT), cor("red", LIGA_VENT)],
          "orange",
          f"Dentro (DHT22): a curva deve oscilar entre as linhas; o ventilador liga ao cruzar {LIGA_VENT} °C e "
          f"desliga ao cruzar {DESLIGA_VENT} °C. Lá fora (clima-externo, uma leitura a cada 15 min, em degraus): "
          f"na estufa real, o ventilador só resfria até perto dela; com lá fora acima de {DESLIGA_VENT} °C, ele não "
          f"consegue desligar. A simulação não usa o clima de fora.",
          15, 30, legenda=True,
          sobreposicoes=[campo("lá fora", color={"mode": "fixed", "fixedColor": "purple"},
                               custom__lineInterpolation="stepAfter",
                               custom__lineStyle={"fill": "dash", "dash": [10, 10]})]),
    serie(f"Umidade do solo e os limites da bomba ({LIGA_BOMBA} % e {DESLIGA_BOMBA} %)", 12, 8, 12, 8,
          [alvo(historico("soilMoisture", "solo"))], "percent",
          [cor("red", None), cor("transparent", LIGA_BOMBA), cor("blue", DESLIGA_BOMBA)],
          "orange", f"Dente de serra: o solo seca devagar e a bomba o molha depressa entre {LIGA_BOMBA} % e "
                    f"{DESLIGA_BOMBA} %.",
          20, 55),
    {"id": proximo_id(), "title": "Ventilador e bomba ao longo do tempo", "type": "state-timeline",
     "datasource": DS, "gridPos": {"x": 0, "y": 16, "w": 24, "h": 5},
     "description": f"Quando cada relé esteve ligado. Compare com as curvas acima: cada faixa verde do ventilador "
                    f"deve começar em {LIGA_VENT} °C e terminar em {DESLIGA_VENT} °C. À noite (luz zero) o "
                    f"ventilador fica desligado.",
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

# E = P · Δt · Σ s_i  (Wh = W · s / 3600)   ·   V = Q · Δt · Σ s_i  (L = L/h · s / 3600)
CONSUMO = f"""
SELECT
  {P_VENT}  * {DT} * SUM(attrName = 'fanState'  AND attrValue = 'ON') / 3600 AS "ventilador",
  {P_BOMBA} * {DT} * SUM(attrName = 'pumpState' AND attrValue = 'ON') / 3600 AS "bomba",
  {Q_BOMBA} * {DT} * SUM(attrName = 'pumpState' AND attrValue = 'ON') / 3600 AS "água"
FROM {TABELA}
WHERE attrName IN ('fanState', 'pumpState')
  AND $__unixEpochFilter(recvTimeTs / 1000)"""

painel.append(linha("3 · Quanto tempo os atuadores ficam ligados?  —  para quem paga a energia e a água", 21))
painel += [
    {"id": proximo_id(), "title": "Tempo ligado em cada janela de 5 minutos", "type": "barchart",
     "datasource": DS, "gridPos": {"x": 0, "y": 22, "w": 10, "h": 8},
     "description": "Fração do tempo com o relé ligado (ciclo de trabalho), por janela de 5 min. "
                    "Ventilador: energia; bomba: energia e água.",
     "fieldConfig": {"defaults": {"unit": "percent", "decimals": 0, "min": 0, "max": 100},
                     "overrides": [
                         campo("ventilador", color={"mode": "fixed", "fixedColor": "green"}),
                         campo("bomba", color={"mode": "fixed", "fixedColor": "blue"})]},
     "options": {"xTickLabelRotation": 0, "showValue": "auto", "groupWidth": 0.7,
                 "legend": {"showLegend": True, "displayMode": "list", "placement": "bottom"}},
     "targets": [alvo(JANELAS)]},
    stat("Tempo ligado no período", 10, 22, 4, 8, [alvo(PERIODO, formato="table")], "percent", 0,
         campos="", texto="value_and_name",
         descricao="Ciclo de trabalho no período do seletor: média das amostras ligadas (uma a cada 5 s)."),
    stat("Acionamentos no período", 14, 22, 4, 8, [alvo(ACIONAMENTOS, formato="table")], None, 0,
         campos="", texto="value_and_name",
         descricao="Quantas vezes cada relé passou de OFF para ON: desgaste do relé e picos de partida do motor."),
    stat("Energia e água no período", 18, 22, 6, 8, [alvo(CONSUMO, formato="table")], None, 1,
         campos="", texto="value_and_name", orientacao="horizontal",
         sobreposicoes=[campo("ventilador", unit="watth"), campo("bomba", unit="watth"),
                        campo("água", unit="litre", decimals=0)],
         descricao=f"Energia = potência nominal × tempo ligado; água = vazão nominal × tempo ligado; cada amostra "
                   f"ON vale {DT} s. Valores nominais (atributos estáticos da ESP32): ventilador {P_VENT} W, bomba "
                   f"{P_BOMBA} W e {br(Q_BOMBA)} L/h. A física da simulação é acelerada: o número mostra o cálculo, "
                   f"não o consumo de um dia real."),
]

dashboard = {
    "uid": "pel220-estufa",
    "title": "Estufa 001 — painel do grupo",
    "description": "PEL220 · projeto estufa agrícola inteligente (alface) · marco da Aula 8. Histórico gravado pelo "
                   "Cygnus no MySQL (banco estufa) a partir das subscrições 'Historico da estufa para o Cygnus' e "
                   "'Clima externo para o Cygnus'.",
    "tags": ["pel220", "estufa", "aula08"],
    "editable": True,
    "schemaVersion": 39,
    "version": 2,
    "refresh": "5s",
    "time": {"from": "now-30m", "to": "now"},
    "templating": {"list": []},
    "annotations": {"list": []},
    "panels": painel,
}

SAIDA.write_text(json.dumps(dashboard, indent=2, ensure_ascii=False) + "\n")
print(f"gravado: {SAIDA} ({len(painel)} itens)")
