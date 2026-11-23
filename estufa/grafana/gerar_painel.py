"""
Gera estufa/grafana/paineis/painel_estufa.json (o painel do grupo, marco da Aula 8).

O JSON é o que o Grafana carrega por provisionamento; este script só existe para
deixar as consultas SQL legíveis e fáceis de revisar. Os limites, as potências, as
vazões e a caixa vêm do modelo de dados (modelo-dados/), então rode de novo quando eles mudarem:

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
LIGA_LUZ, DESLIGA_LUZ = ESTUFA["lampOnOutdoorIlluminance"]["value"], ESTUFA["lampOffOutdoorIlluminance"]["value"]
LIGA_NEBLINA, DESLIGA_NEBLINA = (ESTUFA["mistOnVaporPressureDeficit"]["value"],
                                 ESTUFA["mistOffVaporPressureDeficit"]["value"])
P_VENT, P_BOMBA = NOMINAL["fanRatedPower"], NOMINAL["pumpRatedPower"]
P_LAMPADAS, P_NEBLINA, Q_NEBLINA = NOMINAL["lampRatedPower"], NOMINAL["mistRatedPower"], NOMINAL["mistFlowRate"]
CAIXA = NOMINAL["tankCapacity"]                       # L
CAIXA_MIN = ESTUFA["irrigationMinTankVolume"]["value"]   # L: abaixo disso, a ESP32 bloqueia a bomba
CAIXA_RETOMA = 150                                    # L: e libera daqui para cima (CAIXA_RETOMA no compose)
RESERVA = 0.4                                         # fração da caixa: laranja abaixo de 40 %
DT = 5                       # s entre amostras (INTERVALO da ESP32): cada amostra ON vale 5 s ligado
FRIO_ALFACE = 18             # °C, limite inferior da faixa da alface (18 a 23 °C)
QUENTE_ALFACE = 23           # °C, limite superior da faixa da alface
DLI_MIN, DLI_MAX = 14, 18    # mol/m²/dia para alface
VPD = (0.45, 1.25, 1.5)      # kPa: úmido demais | faixa | atenção | estresse
LUX_PARA_PPFD = 0.0185       # µmol/m²/s por lx, luz do sol

# Uma cor por grandeza, a mesma em todo o painel.
COR = {
    "temperatura": "#FF9830",   # laranja
    "fora": "#B877D9",          # roxo: o que vem de fora (o clima e a luz no teto)
    "agua": "#8AB8FF",          # azul-claro: umidade do ar, do solo e água
    "luz": "#FADE2A",           # amarelo
    "ventilador": "#73BF69",    # verde
    "bomba": "#5794F2",         # azul
    "lampadas": "#F2CC0C",      # amarelo-ouro
    "nevoa": "#3FB8AF",         # verde-água
    "desligado": "#8E8E8E",     # texto "Desligado"
    "desligado_faixa": "#3A3E45",   # faixa desligada na linha do tempo
    "verde": "#73BF69", "azul": "#5794F2", "azul_escuro": "#1F60C4",
    "laranja": "#FF9830", "vermelho": "#F2495C",
}

# Os quatro relés: atributo de estado, nome no painel, cor e potência nominal (W).
RELES = [("fanState", "ventilador", "ventilador", P_VENT), ("pumpState", "bomba", "bomba", P_BOMBA),
         ("lampState", "lâmpadas", "lampadas", P_LAMPADAS), ("mistState", "nebulização", "nevoa", P_NEBLINA)]
LISTA_RELES = ", ".join(f"'{a}'" for a, *_ in RELES)

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

def _coluna(atributo):
    return f"'{atributo}'".ljust(12)


def _fracao_ligado():
    return ",\n".join(f"  100 * AVG(CASE WHEN attrName = {_coluna(a)}THEN attrValue = 'ON' END) AS \"{n}\""
                      for a, n, *_ in RELES)


JANELAS = f"""
SELECT
  $__unixEpochGroupAlias(recvTimeTs / 1000, '5m'),
{_fracao_ligado()}
FROM {TABELA}
WHERE attrName IN ({LISTA_RELES})
  AND $__unixEpochFilter(recvTimeTs / 1000)
GROUP BY 1
ORDER BY 1"""

PERIODO = f"""
SELECT
{_fracao_ligado()}
FROM {TABELA}
WHERE attrName IN ({LISTA_RELES})
  AND $__unixEpochFilter(recvTimeTs / 1000)"""

_acionou = ",\n".join(f"  SUM(attrName = {(repr(a) + ')').ljust(12)} AS \"{n}\"" for a, n, *_ in RELES)
ACIONAMENTOS = f"""
SELECT
{_acionou}
FROM (
  SELECT attrName, attrValue,
         LAG(attrValue) OVER (PARTITION BY attrName ORDER BY recvTimeTs) AS anterior
  FROM {TABELA}
  WHERE attrName IN ({LISTA_RELES})
    AND $__unixEpochFilter(recvTimeTs / 1000)
) AS mudancas
WHERE attrValue = 'ON' AND anterior = 'OFF'"""

# Energia: E = P · Δt · Σ s_i / 3600 (Wh), com a potência nominal de cada relé.
# Água da aspersão: V = Δt · Σ q_i / 60 (L), com a vazão MEDIDA.
# Água da névoa: V = Q · Δt · Σ s_i / 3600 (L), com a vazão NOMINAL (o medidor fica no cano da aspersão).
_energia = "".join(f"  {p:<4} * {DT} * SUM(attrName = {_coluna(a)}AND attrValue = 'ON') / 3600 AS \"{n}\",\n"
                   for a, n, _, p in RELES)
CONSUMO = f"""
SELECT
{_energia}  {DT} * SUM(CASE WHEN attrName = 'waterFlow' THEN CAST(attrValue AS DECIMAL(6,1)) ELSE 0 END) / 60 AS "água da aspersão",
  {Q_NEBLINA} * {DT} * SUM(attrName = 'mistState' AND attrValue = 'ON') / 3600 AS "água da névoa"
FROM {TABELA}
WHERE attrName IN ({LISTA_RELES}, 'waterFlow')
  AND $__unixEpochFilter(recvTimeTs / 1000)"""

_ultimo = ",\n".join(f"  (SELECT attrValue FROM {TABELA} WHERE attrName = {_coluna(a)}"
                     f"ORDER BY recvTimeTs DESC LIMIT 1) AS \"{n}\"" for a, n, *_ in RELES)
RELES_AGORA = f"""
SELECT
{_ultimo}"""


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


def reles_agora(titulo, x, y, w, h, descricao):
    """Stat com os quatro relés: Ligado na cor de cada atuador, Desligado em cinza."""
    return base("stat", titulo, x, y, w, h, [alvo(RELES_AGORA, formato="table")], descricao,
                defaults={"color": {"mode": "thresholds"}, "mappings": ligado("ventilador"),
                          "thresholds": {"mode": "absolute", "steps": [cor("desligado", None)]}},
                overrides=[campo(nome, mappings=ligado(cor_rele)) for _, nome, cor_rele, _ in RELES],
                opcoes={"reduceOptions": {"calcs": ["lastNotNull"], "fields": "/.*/", "values": False},
                        "colorMode": "value", "graphMode": "none", "justifyMode": "auto",
                        "textMode": "value_and_name", "orientation": "horizontal",
                        "text": {"titleSize": 13, "valueSize": 22}})


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
                          "custom": {k: val for k, val in {
                              "lineWidth": 2, "lineInterpolation": "smooth", "showPoints": "never",
                              "fillOpacity": 18, "gradientMode": "opacity",
                              "axisSoftMin": minimo, "axisSoftMax": maximo,
                              "thresholdsStyle": {"mode": "dashed"}}.items() if val is not None}},
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
                f"Faixas da alface: **ar {FRIO_ALFACE} a {QUENTE_ALFACE} °C** · **solo {LIGA_BOMBA} a {DESLIGA_BOMBA} %** · "
                f"**VPD {br(VPD[0])} a {br(VPD[1])} kPa** · **luz {DLI_MIN} a {DLI_MAX} mol/m²/dia** &nbsp;—&nbsp; "
                f"histórico do Cygnus no MySQL, painel atualizado a cada 10 s"}})

# --- Pergunta 1 -------------------------------------------------------------------
painel.append(linha("1 · A estufa está bem agora?  —  para o operador da estufa", 2))
painel += [
    medidor("Temperatura do ar", 0, 3, 4, 6, [alvo(agora("temperature", "temperatura"))], "celsius", 1, 10, 35,
            [cor("azul", None), cor("verde", FRIO_ALFACE), cor("vermelho", LIGA_VENT)],
            f"Última medida do DHT22. Alface: azul abaixo de {FRIO_ALFACE} °C, verde na faixa, vermelho a partir "
            f"de {LIGA_VENT} °C, quando o ventilador deve estar ligado (fanOnTemperature)."),
    medidor("Umidade do solo", 4, 3, 4, 6, [alvo(agora("soilMoisture", "solo"))], "percent", 1, 10, 70,
            [cor("vermelho", None), cor("verde", LIGA_BOMBA), cor("azul", DESLIGA_BOMBA)],
            f"Última medida do sensor capacitivo. Vermelho abaixo de {LIGA_BOMBA} % (a aspersão deve ligar), verde "
            f"na faixa, azul a partir de {DESLIGA_BOMBA} % (a aspersão deve desligar)."),
    medidor("VPD (umidade do ar)", 8, 3, 4, 6, [alvo(agora("vaporPressureDeficit", "VPD"))], "pressurekpa", 2, 0, 2.5,
            [cor("azul", None), cor("verde", VPD[0]), cor("laranja", VPD[1]), cor("vermelho", VPD[2])],
            f"Déficit de pressão de vapor, calculado na ESP32 com a temperatura e a umidade (Tetens/FAO-56). "
            f"Azul abaixo de {br(VPD[0])} kPa: ar úmido demais, risco de doença. Verde até {br(VPD[1])}. Laranja até "
            f"{br(VPD[2])}. Vermelho acima: estresse hídrico. A nebulização liga em {br(LIGA_NEBLINA)} kPa."),
    medidor("Luz do dia (DLI, 24 h)", 12, 3, 4, 6, [alvo(DLI_SQL, formato="table")], "suffix: mol/m²/d", 1, 0, 30,
            [cor("laranja", None), cor("verde", DLI_MIN), cor("laranja", DLI_MAX)],
            f"Luz diária integrada das últimas 24 h, no BH1750 de dentro (sol + lâmpadas): média da iluminância × "
            f"{br(LUX_PARA_PPFD)} (lx → µmol/m²/s, luz do sol) × 86 400 s ÷ 10⁶. Alface: {DLI_MIN} a {DLI_MAX} "
            f"mol/m²/dia (verde).",
            timeFrom="24h", hideTimeOverride=True),
    medidor("Caixa d'água", 16, 3, 4, 6, [alvo(agora("tankWaterVolume", "caixa", "CAST(attrValue AS DECIMAL(10,1))"))],
            "litre", 0, 0, CAIXA,
            [cor("vermelho", None), cor("laranja", CAIXA_MIN), cor("verde", RESERVA * CAIXA)],
            f"Água na caixa de {CAIXA} L: ultrassom na tampa, convertido em litros na ESP32. Vermelho abaixo "
            f"de {CAIXA_MIN} L (irrigationMinTankVolume): a ESP32 bloqueia a bomba, para ela não rodar a seco, "
            f"e só libera com {CAIXA_RETOMA} L. Laranja abaixo de {RESERVA:.0%} da caixa. A aspersão e a névoa "
            f"tiram água; a boia repõe."),
    reles_agora("Relés agora", 20, 3, 4, 6,
                "Estado que a ESP32 informa (fanState, pumpState, lampState, mistState). É o estado observado, não o "
                "comando pedido."),
    tendencia("Umidade do ar", 0, 9, 6, 3,
              [alvo(historico("relativeHumidity", "umidade do ar", "CAST(attrValue AS DECIMAL(6,2))"))],
              "percentunit", 0, "agua",
              "relativeHumidity de 0 a 1, mostrada em %, com a curva do período. Quem diz se o ar está úmido ou "
              "seco demais é o VPD, que junta umidade e temperatura."),
    tendencia("Luz dentro", 6, 9, 6, 3,
              [alvo(historico("illuminance", "dentro", "CAST(attrValue AS DECIMAL(10,1)) / 1000"))],
              "suffix: klx", 1, "luz",
              "BH1750 na altura das plantas: o sol que passa pelo filme mais as lâmpadas. É a luz que a planta recebe "
              "e a que entra no DLI."),
    tendencia("Luz no teto (lá fora)", 12, 9, 6, 3,
              [alvo(historico("outdoorIlluminance", "no teto", "CAST(attrValue AS DECIMAL(10,1)) / 1000"))],
              "suffix: klx", 1, "fora",
              f"BH1750 no teto, olhando para o céu: só o sol. É ele que decide as lâmpadas (ligam abaixo de "
              f"{LIGA_LUZ / 1000:g} klx, desligam acima de {DESLIGA_LUZ / 1000:g} klx, desligadas à noite), porque o "
              f"sensor de dentro também vê as lâmpadas."),
    tendencia("Vazão da aspersão", 18, 9, 6, 3,
              [alvo(historico("waterFlow", "vazão"))], "suffix: L/min", 1, "bomba",
              "Medidor de vazão de pulsos (efeito Hall) no cano depois da bomba da aspersão. Zero com a bomba "
              "desligada. Bomba ligada com vazão perto de zero = caixa vazia ou cano entupido."),
]

# --- Pergunta 2 -------------------------------------------------------------------
painel.append(linha("2 · O controle mantém a estufa nas faixas?  —  para o grupo, que avalia a regra de histerese", 12))
painel += [
    serie(f"Temperatura do ar: dentro, lá fora e os limites do ventilador ({DESLIGA_VENT} e {LIGA_VENT} °C)",
          0, 13, 12, 8, [alvo(historico("temperature", "dentro"), "A"), alvo(LA_FORA, "B")], "celsius",
          "temperatura", [cor("transparent", None), cor("verde", DESLIGA_VENT), cor("vermelho", LIGA_VENT)],
          f"Dentro (DHT22): a curva deve oscilar entre as linhas; o ventilador liga ao cruzar {LIGA_VENT} °C (linha "
          f"vermelha) e desliga ao cruzar {DESLIGA_VENT} °C (linha verde). Lá fora (clima-externo, uma leitura a "
          f"cada 15 min, em degraus): na estufa real, o ventilador só resfria até perto dela; com lá fora acima de "
          f"{DESLIGA_VENT} °C, ele não consegue desligar. A simulação não usa o clima de fora.",
          16, 28, legenda=True,
          sobreposicoes=[campo("lá fora", color=fixa("fora"), custom__lineInterpolation="stepAfter",
                               custom__fillOpacity=0, custom__lineStyle={"fill": "dash", "dash": [10, 6]})]),
    serie(f"Umidade do solo e os limites da aspersão ({LIGA_BOMBA} e {DESLIGA_BOMBA} %)", 12, 13, 12, 8,
          [alvo(historico("soilMoisture", "solo"))], "percent", "agua",
          [cor("transparent", None), cor("vermelho", LIGA_BOMBA), cor("azul_escuro", DESLIGA_BOMBA)],
          f"Dente de serra: o solo seca devagar e a aspersão o molha depressa. A bomba liga ao cruzar "
          f"{LIGA_BOMBA} % (linha vermelha) e desliga ao cruzar {DESLIGA_BOMBA} % (linha azul).",
          20, 55),
    serie(f"Luz: no teto, dentro e os limites das lâmpadas ({LIGA_LUZ / 1000:g} e {DESLIGA_LUZ / 1000:g} klx)",
          0, 21, 12, 8,
          [alvo(historico("outdoorIlluminance", "no teto", "CAST(attrValue AS DECIMAL(10,1)) / 1000"), "A"),
           alvo(historico("illuminance", "dentro", "CAST(attrValue AS DECIMAL(10,1)) / 1000"), "B")],
          "suffix: klx", "luz",
          [cor("transparent", None), cor("lampadas", LIGA_LUZ / 1000), cor("verde", DESLIGA_LUZ / 1000)],
          f"No teto (roxo, tracejado): só o sol; as lâmpadas ligam quando ele cai abaixo de {LIGA_LUZ / 1000:g} klx "
          f"(linha amarela) e desligam acima de {DESLIGA_LUZ / 1000:g} klx (linha verde) ou à noite. Dentro "
          f"(amarelo): o sol que passa pelo filme mais as lâmpadas; o degrau no começo e no fim do dia é a luz "
          f"delas.",
          0, None, legenda=True,
          sobreposicoes=[campo("no teto", color=fixa("fora"), custom__fillOpacity=0,
                               custom__lineStyle={"fill": "dash", "dash": [10, 6]})]),
    serie(f"VPD e os limites da nebulização ({br(DESLIGA_NEBLINA)} e {br(LIGA_NEBLINA)} kPa)", 12, 21, 12, 8,
          [alvo(historico("vaporPressureDeficit", "VPD", "CAST(attrValue AS DECIMAL(6,2))"))], "pressurekpa", "nevoa",
          [cor("transparent", None), cor("verde", DESLIGA_NEBLINA), cor("laranja", LIGA_NEBLINA)],
          f"Com sol e ventilação, o ar seca e o VPD sobe. A névoa liga ao cruzar {br(LIGA_NEBLINA)} kPa (linha "
          f"laranja, o fim da faixa verde da alface) e desliga ao voltar a {br(DESLIGA_NEBLINA)} kPa (linha verde). "
          f"À noite, o ar úmido deixa o VPD baixo.",
          0, 1.6),
    base("state-timeline", "Quando cada relé esteve ligado", 0, 29, 24, 5,
         [alvo(historico(atributo, nome, "attrValue"), ref) for (atributo, nome, *_), ref in zip(RELES, "ABCD")],
         f"Faixa colorida = relé ligado. Ventilador (verde): de {LIGA_VENT} a {DESLIGA_VENT} °C. Aspersão (azul): "
         f"de {LIGA_BOMBA} a {DESLIGA_BOMBA} % no solo. Lâmpadas (amarelo): no começo e no fim do dia, com pouco "
         f"sol. Névoa (verde-água): perto do meio-dia, com o ar seco.",
         defaults={"color": {"mode": "thresholds"}, "mappings": ligado("ventilador", "desligado_faixa"),
                   "custom": {"fillOpacity": 85, "lineWidth": 0}},
         overrides=[campo(nome, mappings=ligado(cor_rele, "desligado_faixa")) for _, nome, cor_rele, _ in RELES],
         opcoes={"showValue": "never", "mergeValues": True, "rowHeight": 0.7, "alignValue": "center",
                 "legend": {"showLegend": False}, "tooltip": {"mode": "single"}}),
]

# --- Pergunta 3 -------------------------------------------------------------------
cores_reles = [campo(nome, color=fixa(cor_rele)) for _, nome, cor_rele, _ in RELES]
painel.append(linha("3 · Quanto tempo os atuadores ficam ligados?  —  para quem paga a energia e a água", 34))
painel += [
    base("barchart", "Tempo ligado em cada janela de 5 minutos", 0, 35, 12, 8, [alvo(JANELAS)],
         "Fração do tempo com o relé ligado (ciclo de trabalho), por janela de 5 min. Todos gastam energia; o "
         "aspersão e a névoa também gastam água.",
         defaults={"unit": "percent", "decimals": 0, "min": 0, "max": 100,
                   "custom": {"fillOpacity": 85, "lineWidth": 0, "gradientMode": "none"}},
         overrides=cores_reles,
         opcoes={"xTickLabelRotation": 0, "xTickLabelSpacing": 100, "showValue": "always", "groupWidth": 0.8,
                 "barWidth": 0.9, "barRadius": 0.15, "text": {"valueSize": 11},
                 "legend": {"showLegend": True, "displayMode": "list", "placement": "bottom"},
                 "tooltip": {"mode": "multi"}}),
    base("bargauge", "Tempo ligado no período", 12, 35, 6, 4, [alvo(PERIODO, formato="table")],
         "Ciclo de trabalho no período do seletor: média das amostras ligadas (uma a cada 5 s).",
         defaults={"unit": "percent", "decimals": 0, "min": 0, "max": 100, "color": fixa("ventilador")},
         overrides=cores_reles,
         opcoes={"reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
                 "displayMode": "gradient", "orientation": "horizontal", "showUnfilled": True, "valueMode": "color",
                 "namePlacement": "left", "sizing": "auto", "minVizHeight": 10, "minVizWidth": 8,
                 "maxVizHeight": 300}),
    numeros("Acionamentos no período", 12, 39, 6, 4, [alvo(ACIONAMENTOS, formato="table")],
            "Quantas vezes cada relé passou de OFF para ON: desgaste do relé e picos de partida dos motores.",
            cores_reles, decimais=0),
    numeros("Energia e água no período", 18, 35, 6, 8, [alvo(CONSUMO, formato="table")],
            f"Energia = potência nominal × tempo ligado (cada amostra ON vale {DT} s): ventilador {P_VENT} W, bomba "
            f"{P_BOMBA} W, lâmpadas {P_LAMPADAS} W, nebulização {P_NEBLINA} W (atributos estáticos da ESP32). Água da "
            f"aspersão = soma da vazão MEDIDA × {DT} s ÷ 60. Água da névoa = vazão nominal ({Q_NEBLINA} L/h) × "
            f"tempo ligado. A física da simulação é acelerada: o número mostra o cálculo, não o consumo de um dia "
            f"real.",
            [campo(nome, color=fixa(cor_rele), unit="watth", decimals=1) for _, nome, cor_rele, _ in RELES]
            + [campo("água da aspersão", color=fixa("agua"), unit="litre", decimals=0),
               campo("água da névoa", color=fixa("nevoa"), unit="litre", decimals=1)],
            orientacao="horizontal"),
    serie(f"Caixa d'água ({CAIXA} L) e vazão: o nível cai quando a aspersão liga, e a boia repõe", 0, 43, 24, 7,
          [alvo(historico("tankWaterVolume", "caixa", "CAST(attrValue AS DECIMAL(10,1))"), "A"),
           alvo(historico("waterFlow", "vazão"), "B")], "litre", "agua",
          [cor("transparent", None), cor("vermelho", CAIXA_MIN), cor("laranja", RESERVA * CAIXA)],
          f"Litros na caixa (eixo da esquerda) e vazão medida da aspersão (eixo da direita, em degraus). Linha "
          f"vermelha: {CAIXA_MIN} L, o mínimo; abaixo dela, a bomba fica bloqueada até a caixa voltar a "
          f"{CAIXA_RETOMA} L. "
          f"A névoa também tira água da caixa ({Q_NEBLINA} L/h), mas não passa pelo medidor. A água da aspersão "
          f"no período é a área sob a vazão.",
          None, None, legenda=True,
          sobreposicoes=[campo("caixa", custom__fillOpacity=0, custom__lineWidth=2),
                         campo("vazão", color=fixa("bomba"), unit="suffix: L/min", custom__axisPlacement="right",
                               custom__lineInterpolation="stepAfter", custom__fillOpacity=35, custom__lineWidth=1,
                               custom__gradientMode="none", custom__thresholdsStyle={"mode": "off"})]),
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
    "version": 5,
    "refresh": "10s",                                  # 5 s pesa no túnel de portas do Codespace
    "time": {"from": "now-30m", "to": "now"},
    "templating": {"list": []},
    "annotations": {"list": []},
    "panels": painel,
}

SAIDA.write_text(json.dumps(dashboard, indent=2, ensure_ascii=False) + "\n")
print(f"gravado: {SAIDA} ({len(painel)} itens)")
