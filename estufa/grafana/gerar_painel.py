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

# Uma cor por grandeza, a mesma em todo o painel.
COR = {
    "temperatura": "#FF9830",   # laranja
    "fora": "#B877D9",          # roxo: o clima externo
    "agua": "#8AB8FF",          # azul-claro: umidade do ar, do solo e água
    "luz": "#FADE2A",           # amarelo
    "ventilador": "#73BF69",    # verde
    "bomba": "#5794F2",         # azul
    "desligado": "#8E8E8E",     # texto "Desligado"
    "desligado_faixa": "#3A3E45",   # faixa desligada na linha do tempo
    "verde": "#73BF69", "azul": "#5794F2", "azul_escuro": "#1F60C4",
    "laranja": "#FF9830", "vermelho": "#F2495C",
}

_id = 0


def proximo_id():
    global _id
    _id += 1
    return _id


def br(x):
    """Número com vírgula decimal, para os textos do painel."""
    return f"{x:g}".replace(".", ",")


def cor(nome, valor):
    return {"color": COR.get(nome, nome), "value": valor}


def fixa(nome):
    return {"mode": "fixed", "fixedColor": COR.get(nome, nome)}


def campo(nome, **propriedades):
    """Override do Grafana: propriedades de uma coluna, pelo nome (custom__x vira custom.x)."""
    return {"matcher": {"id": "byName", "options": nome},
            "properties": [{"id": k.replace("__", "."), "value": v} for k, v in propriedades.items()]}


def ligado(cor_ligado, cor_desligado="desligado"):
    return [{"type": "value", "options": {
        "ON": {"color": COR[cor_ligado], "index": 0, "text": "Ligado"},
        "OFF": {"color": COR[cor_desligado], "index": 1, "text": "Desligado"}}}]


def alvo(sql, ref="A", formato="time_series"):
    return {"refId": ref, "datasource": DS, "editorMode": "code", "format": formato,
            "rawQuery": True, "rawSql": sql.strip()}


def base(tipo, titulo, x, y, w, h, alvos, descricao=None, defaults=None, overrides=None, opcoes=None, **extra):
    p = {"id": proximo_id(), "type": tipo, "title": titulo, "datasource": DS,
         "gridPos": {"x": x, "y": y, "w": w, "h": h},
         "fieldConfig": {"defaults": defaults or {}, "overrides": overrides or []},
         "options": opcoes or {}, "targets": alvos}
    if descricao:
        p["description"] = descricao
    p.update(extra)
    return p


def linha(titulo, y):
    return {"id": proximo_id(), "type": "row", "title": titulo, "collapsed": False,
            "gridPos": {"x": 0, "y": y, "w": 24, "h": 1}, "panels": []}


# --- consultas ------------------------------------------------------------------
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


def historico(atributo, apelido, valor="CAST(attrValue AS DECIMAL(6,1))"):
    return f"""
SELECT
  recvTimeTs / 1000 AS "time",
  {valor} AS "{apelido}"
FROM {TABELA}
WHERE attrName = '{atributo}'
  AND $__unixEpochFilter(recvTimeTs / 1000)
ORDER BY recvTimeTs ASC"""


DLI_SQL = f"""
SELECT
  AVG(CAST(attrValue AS DECIMAL(10,1))) * {LUX_PARA_PPFD} * 86400 / 1000000 AS "DLI"
FROM {TABELA}
WHERE attrName = 'illuminance'
  AND $__unixEpochFilter(recvTimeTs / 1000)"""

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


# --- tipos de painel ----------------------------------------------------------------
def medidor(titulo, x, y, w, h, alvos, unidade, decimais, minimo, maximo, limiares, descricao, **extra):
    """Gauge: o valor de agora sobre o arco das faixas."""
    return base("gauge", titulo, x, y, w, h, alvos, descricao,
                defaults={"unit": unidade, "decimals": decimais, "min": minimo, "max": maximo,
                          "color": {"mode": "thresholds"},
                          "thresholds": {"mode": "absolute", "steps": limiares}},
                opcoes={"reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
                        "orientation": "auto", "showThresholdMarkers": True, "showThresholdLabels": False,
                        "sizing": "auto", "minVizWidth": 75, "minVizHeight": 75},
                **extra)


def tendencia(titulo, x, y, w, h, alvos, unidade, decimais, nome_cor, descricao):
    """Stat com o valor de agora e a curva do período ao fundo."""
    return base("stat", titulo, x, y, w, h, alvos, descricao,
                defaults={"unit": unidade, "decimals": decimais, "color": fixa(nome_cor)},
                opcoes={"reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
                        "colorMode": "none", "graphMode": "area", "justifyMode": "center",
                        "textMode": "value", "orientation": "auto"})


def estado(titulo, x, y, w, h, atributo, apelido, nome_cor, descricao):
    """Stat do relé: Ligado na cor do atuador, Desligado em cinza."""
    return base("stat", titulo, x, y, w, h, [alvo(estado_agora(atributo, apelido), formato="table")], descricao,
                defaults={"color": {"mode": "thresholds"}, "mappings": ligado(nome_cor),
                          "thresholds": {"mode": "absolute", "steps": [cor("desligado", None)]}},
                opcoes={"reduceOptions": {"calcs": ["lastNotNull"], "fields": f"/^{apelido}$/", "values": False},
                        "colorMode": "value", "graphMode": "none", "justifyMode": "center",
                        "textMode": "value", "orientation": "auto"})


def numeros(titulo, x, y, w, h, alvos, descricao, sobreposicoes, orientacao="auto", decimais=None, unidade=None):
    """Stat de vários valores com nome (cada coluna da consulta vira um número)."""
    defaults = {"color": fixa("text")}
    if decimais is not None:
        defaults["decimals"] = decimais
    if unidade:
        defaults["unit"] = unidade
    return base("stat", titulo, x, y, w, h, alvos, descricao, defaults=defaults, overrides=sobreposicoes,
                opcoes={"reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
                        "colorMode": "value", "graphMode": "none", "justifyMode": "center",
                        "textMode": "value_and_name", "orientation": orientacao})


def serie(titulo, x, y, w, h, alvos, unidade, nome_cor, limiares, descricao, minimo, maximo,
          sobreposicoes=None, legenda=False):
    """Time series: linha suave com preenchimento leve; os limites como linhas tracejadas."""
    return base("timeseries", titulo, x, y, w, h, alvos, descricao,
                defaults={"unit": unidade, "color": fixa(nome_cor),
                          "thresholds": {"mode": "absolute", "steps": limiares},
                          "custom": {"lineWidth": 2, "lineInterpolation": "smooth", "showPoints": "never",
                                     "fillOpacity": 18, "gradientMode": "opacity",
                                     "axisSoftMin": minimo, "axisSoftMax": maximo,
                                     "thresholdsStyle": {"mode": "dashed"}}},
                overrides=sobreposicoes,
                opcoes={"legend": {"showLegend": legenda, "displayMode": "list", "placement": "bottom"},
                        "tooltip": {"mode": "multi" if legenda else "single", "sort": "none"}})


painel = []

# --- cabeçalho ------------------------------------------------------------------------
painel.append({
    "id": proximo_id(), "type": "text", "title": "", "transparent": True,
    "gridPos": {"x": 0, "y": 0, "w": 24, "h": 2},
    "options": {"mode": "markdown", "content":
                f"#### Estufa 001 · alface &nbsp;·&nbsp; FEI, São Bernardo do Campo\n"
                f"Faixas da alface: **ar {FRIO_ALFACE} a {LIGA_VENT} °C** · **solo {LIGA_BOMBA} a {DESLIGA_BOMBA} %** · "
                f"**VPD {br(VPD[0])} a {br(VPD[1])} kPa** · **luz {DLI_MIN} a {DLI_MAX} mol/m²/dia** &nbsp;—&nbsp; "
                f"histórico do Cygnus no MySQL, atualizado a cada 5 s"}})

# --- Pergunta 1 -------------------------------------------------------------------
painel.append(linha("1 · A estufa está bem agora?  —  para o operador da estufa", 2))
painel += [
    medidor("Temperatura do ar", 0, 3, 4, 6, [alvo(agora("temperature", "temperatura"))], "celsius", 1, 10, 35,
            [cor("azul", None), cor("verde", FRIO_ALFACE), cor("vermelho", LIGA_VENT)],
            f"Última medida do DHT22. Alface: azul abaixo de {FRIO_ALFACE} °C, verde na faixa, vermelho a partir "
            f"de {LIGA_VENT} °C, quando o ventilador deve estar ligado (fanOnTemperature)."),
    medidor("Umidade do solo", 4, 3, 4, 6, [alvo(agora("soilMoisture", "solo"))], "percent", 1, 10, 70,
            [cor("vermelho", None), cor("verde", LIGA_BOMBA), cor("azul", DESLIGA_BOMBA)],
            f"Última medida do sensor capacitivo. Vermelho abaixo de {LIGA_BOMBA} % (a bomba deve ligar), verde na "
            f"faixa, azul a partir de {DESLIGA_BOMBA} % (a bomba deve desligar)."),
    medidor("VPD (umidade do ar)", 8, 3, 4, 6, [alvo(agora("vaporPressureDeficit", "VPD"))], "pressurekpa", 2, 0, 2.5,
            [cor("azul", None), cor("verde", VPD[0]), cor("laranja", VPD[1]), cor("vermelho", VPD[2])],
            f"Déficit de pressão de vapor, calculado na ESP32 com a temperatura e a umidade (Tetens/FAO-56). "
            f"Azul abaixo de {br(VPD[0])} kPa: ar úmido demais, risco de doença. Verde até {br(VPD[1])}. Laranja até "
            f"{br(VPD[2])}. Vermelho acima: estresse hídrico."),
    medidor("Luz do dia (DLI, 24 h)", 12, 3, 4, 6, [alvo(DLI_SQL, formato="table")], "suffix: mol/m²/d", 1, 0, 30,
            [cor("laranja", None), cor("verde", DLI_MIN), cor("laranja", DLI_MAX)],
            f"Luz diária integrada das últimas 24 h: média da iluminância × {br(LUX_PARA_PPFD)} (lx → µmol/m²/s, "
            f"luz do sol) × 86 400 s ÷ 10⁶. Alface: {DLI_MIN} a {DLI_MAX} mol/m²/dia (verde).",
            timeFrom="24h", hideTimeOverride=True),
    tendencia("Umidade do ar", 16, 3, 4, 3,
              [alvo(historico("relativeHumidity", "umidade do ar", "CAST(attrValue AS DECIMAL(6,2))"))],
              "percentunit", 0, "agua",
              "relativeHumidity de 0 a 1, mostrada em %, com a curva do período. Quem diz se o ar está úmido ou "
              "seco demais é o VPD, que junta umidade e temperatura."),
    tendencia("Luz agora", 16, 6, 4, 3,
              [alvo(historico("illuminance", "luz", "CAST(attrValue AS DECIMAL(10,1)) / 1000"))],
              "suffix: klx", 1, "luz",
              "Iluminância do BH1750, em klx, com a curva do período (o dia e a noite). O que conta para a planta "
              "é a luz do dia inteiro: o DLI."),
    estado("Ventilador", 20, 3, 4, 3, "fanState", "ventilador", "ventilador",
           "Estado que a ESP32 informa (fanState). É o estado observado, não o comando pedido."),
    estado("Bomba", 20, 6, 4, 3, "pumpState", "bomba", "bomba",
           "Estado que a ESP32 informa (pumpState)."),
]

# --- Pergunta 2 -------------------------------------------------------------------
painel.append(linha("2 · O controle mantém a estufa nas faixas?  —  para o grupo, que avalia a regra de histerese", 9))
painel += [
    serie(f"Temperatura do ar: dentro, lá fora e os limites do ventilador ({DESLIGA_VENT} e {LIGA_VENT} °C)",
          0, 10, 12, 8, [alvo(historico("temperature", "dentro"), "A"), alvo(LA_FORA, "B")], "celsius",
          "temperatura", [cor("transparent", None), cor("verde", DESLIGA_VENT), cor("vermelho", LIGA_VENT)],
          f"Dentro (DHT22): a curva deve oscilar entre as linhas; o ventilador liga ao cruzar {LIGA_VENT} °C (linha "
          f"vermelha) e desliga ao cruzar {DESLIGA_VENT} °C (linha verde). Lá fora (clima-externo, uma leitura a "
          f"cada 15 min, em degraus): na estufa real, o ventilador só resfria até perto dela; com lá fora acima de "
          f"{DESLIGA_VENT} °C, ele não consegue desligar. A simulação não usa o clima de fora.",
          16, 28, legenda=True,
          sobreposicoes=[campo("lá fora", color=fixa("fora"), custom__lineInterpolation="stepAfter",
                               custom__fillOpacity=0, custom__lineStyle={"fill": "dash", "dash": [10, 6]})]),
    serie(f"Umidade do solo e os limites da bomba ({LIGA_BOMBA} e {DESLIGA_BOMBA} %)", 12, 10, 12, 8,
          [alvo(historico("soilMoisture", "solo"))], "percent", "agua",
          [cor("transparent", None), cor("vermelho", LIGA_BOMBA), cor("azul_escuro", DESLIGA_BOMBA)],
          f"Dente de serra: o solo seca devagar e a bomba o molha depressa. A bomba liga ao cruzar {LIGA_BOMBA} % "
          f"(linha vermelha) e desliga ao cruzar {DESLIGA_BOMBA} % (linha azul).",
          20, 55),
    base("state-timeline", "Quando cada relé esteve ligado", 0, 18, 24, 4,
         [alvo(historico("fanState", "ventilador", "attrValue"), "A"),
          alvo(historico("pumpState", "bomba", "attrValue"), "B")],
         f"Faixa colorida = relé ligado (ventilador em verde, bomba em azul). Cada faixa verde deve começar em "
         f"{LIGA_VENT} °C e terminar em {DESLIGA_VENT} °C. À noite (luz zero) o ventilador fica desligado.",
         defaults={"color": {"mode": "thresholds"}, "mappings": ligado("ventilador", "desligado_faixa"),
                   "custom": {"fillOpacity": 85, "lineWidth": 0}},
         overrides=[campo("bomba", mappings=ligado("bomba", "desligado_faixa"))],
         opcoes={"showValue": "never", "mergeValues": True, "rowHeight": 0.7, "alignValue": "center",
                 "legend": {"showLegend": False}, "tooltip": {"mode": "single"}}),
]

# --- Pergunta 3 -------------------------------------------------------------------
painel.append(linha("3 · Quanto tempo os atuadores ficam ligados?  —  para quem paga a energia e a água", 22))
painel += [
    base("barchart", "Tempo ligado em cada janela de 5 minutos", 0, 23, 12, 8, [alvo(JANELAS)],
         "Fração do tempo com o relé ligado (ciclo de trabalho), por janela de 5 min. Ventilador: energia; "
         "bomba: energia e água.",
         defaults={"unit": "percent", "decimals": 0, "min": 0, "max": 100,
                   "custom": {"fillOpacity": 85, "lineWidth": 0, "gradientMode": "none"}},
         overrides=[campo("ventilador", color=fixa("ventilador")), campo("bomba", color=fixa("bomba"))],
         opcoes={"xTickLabelRotation": 0, "xTickLabelSpacing": 100, "showValue": "always", "groupWidth": 0.75,
                 "barWidth": 0.9, "barRadius": 0.15, "text": {"valueSize": 12},
                 "legend": {"showLegend": True, "displayMode": "list", "placement": "bottom"},
                 "tooltip": {"mode": "multi"}}),
    base("bargauge", "Tempo ligado no período", 12, 23, 6, 4, [alvo(PERIODO, formato="table")],
         "Ciclo de trabalho no período do seletor: média das amostras ligadas (uma a cada 5 s).",
         defaults={"unit": "percent", "decimals": 0, "min": 0, "max": 100, "color": fixa("ventilador")},
         overrides=[campo("bomba", color=fixa("bomba"))],
         opcoes={"reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
                 "displayMode": "gradient", "orientation": "horizontal", "showUnfilled": True, "valueMode": "color",
                 "namePlacement": "auto", "sizing": "auto", "minVizHeight": 16, "minVizWidth": 8,
                 "maxVizHeight": 300}),
    numeros("Acionamentos no período", 12, 27, 6, 4, [alvo(ACIONAMENTOS, formato="table")],
            "Quantas vezes cada relé passou de OFF para ON: desgaste do relé e picos de partida do motor.",
            [campo("ventilador", color=fixa("ventilador")), campo("bomba", color=fixa("bomba"))], decimais=0),
    numeros("Energia e água no período", 18, 23, 6, 8, [alvo(CONSUMO, formato="table")],
            f"Energia = potência nominal × tempo ligado; água = vazão nominal × tempo ligado; cada amostra ON vale "
            f"{DT} s. Valores nominais (atributos estáticos da ESP32): ventilador {P_VENT} W, bomba {P_BOMBA} W e "
            f"{br(Q_BOMBA)} L/h. A física da simulação é acelerada: o número mostra o cálculo, não o consumo de um "
            f"dia real.",
            [campo("ventilador", color=fixa("ventilador"), unit="watth", decimals=1),
             campo("bomba", color=fixa("bomba"), unit="watth", decimals=1),
             campo("água", color=fixa("agua"), unit="litre", decimals=0)],
            orientacao="horizontal"),
]

dashboard = {
    "uid": "pel220-estufa",
    "title": "Estufa 001 — painel do grupo",
    "description": "PEL220 · projeto estufa agrícola inteligente (alface) · marco da Aula 8. Histórico gravado pelo "
                   "Cygnus no MySQL (banco estufa) a partir das subscrições 'Historico da estufa para o Cygnus' e "
                   "'Clima externo para o Cygnus'.",
    "tags": ["pel220", "estufa", "aula08"],
    "editable": True,
    "graphTooltip": 1,                                 # cursor compartilhado entre os gráficos
    "schemaVersion": 39,
    "version": 3,
    "refresh": "5s",
    "time": {"from": "now-30m", "to": "now"},
    "templating": {"list": []},
    "annotations": {"list": []},
    "panels": painel,
}

SAIDA.write_text(json.dumps(dashboard, indent=2, ensure_ascii=False) + "\n")
print(f"gravado: {SAIDA} ({len(painel)} itens)")
