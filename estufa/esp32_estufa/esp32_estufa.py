"""
============================================================================
 PEL220 - Projeto do grupo: estufa agrícola inteligente (cultura: alface)
----------------------------------------------------------------------------
 ESP32 SIMULADA DA ESTUFA (nó urn:ngsi-ld:Device:ESP32-001).

 Faz em software o que o nó da estufa faz em hardware, no mesmo contrato
 MQTT do provisionamento (modelo-dados/provisionamento/dispositivo.json):

   medidas    publica  /json/<chave>/<device_id>/attrs
                       {"t": 23.4, "h": 0.72, "v": 0.81, "m": 38.5, "l": 21500, "e": 31600,
                        "a": 492.3, "q": 0.0, "f": "OFF", "p": "OFF", "i": "OFF", "n": "OFF"}
   comandos   assina   /<chave>/<device_id>/cmd
                       {"fanOn": ""} · {"pumpOn": ""} · {"lampOn": ""} · {"mistOn": ""} (e os ...Off)
   resultado  publica  /json/<chave>/<device_id>/cmdexe
                       {"fanOn": "OK - ventilador ligado"}

   t  temperatura do ar (°C, DHT22)            m  umidade do solo (%, capacitivo)
   h  umidade relativa do ar (0 a 1, DHT22)    l  luz dentro, na altura das plantas (lx, BH1750 em 0x23)
   v  déficit de pressão de vapor (kPa),       e  luz lá fora, no teto (lx, BH1750 em 0x5C)
      calculado na placa a partir de t e h     a  água na caixa (L): ultrassom na tampa,
   f  relé do ventilador (ON/OFF)                 convertido em litros na placa
   p  relé da bomba da aspersão (ON/OFF)       q  vazão depois da bomba (L/min):
   i  relé das lâmpadas LED (ON/OFF)              medidor de vazão de pulsos (efeito Hall)
   n  relé da bomba da nebulização (ON/OFF)

 Dois BH1750 no mesmo barramento I2C: o pino ADDR escolhe o endereço
 (0x23 ou 0x5C). O de dentro mede o que a planta recebe (sol + lâmpadas,
 para o DLI); o do teto mede só o sol e decide as lâmpadas. Se a regra
 usasse o sensor de dentro, as lâmpadas acesas o fariam desligá-las.

 Caixa d'água (cilíndrica, premissa): o ultrassom mede a distância d até a
 água; com H = distância do sensor ao fundo e A = área da seção,
   a = 1000 · A · (H - d)       litros (A em m², H e d em m)
 Medidor de vazão: K pulsos por litro (folha de dados do sensor); com n pulsos
 no intervalo Δt (s),
   q = 60 · n / (K · Δt)        L/min

 O DHT22 entrega a umidade em %; o firmware divide por 100, porque o modelo
 de dados usa relativeHumidity de 0 a 1 (como o Smart Data Model).

 VPD pela equação de Tetens (a mesma da FAO-56), com t e h já arredondados,
 para quem lê o histórico poder refazer a conta:
   e_s = 0,6108 · exp(17,27 · t / (t + 237,3))     pressão de saturação, kPa
   v   = e_s · (1 - h)

 Regra local (na borda), com histerese — os limites da AgriGreenhouse:
   ventilador  liga com t >= LIGA_VENT     e desliga com t <= DESLIGA_VENT
   bomba       liga com m <= LIGA_BOMBA    e desliga com m >= DESLIGA_BOMBA
   lâmpadas    ligam com e <= LIGA_LUZ     e desligam com e >= DESLIGA_LUZ;
               de noite (e < NOITE_LUX), desligadas: só completam o dia
   nebulização liga com v >= LIGA_NEBLINA  e desliga com v <= DESLIGA_NEBLINA
   proteção    bomba bloqueada com a < CAIXA_MINIMA, até a >= CAIXA_RETOMA,
               para não rodar a seco; vale também para o comando manual
 Fora da faixa, a regra manda no relé a cada leitura. Entre os dois limites,
 ela não mexe: ali, um comando manual vale.

 Física simplificada e acelerada, para o painel de 30 minutos mostrar vários
 dias e vários ciclos:
   - um "dia" dura PERIODO_LUZ segundos: metade com sol, metade de noite;
     ao meio-dia, lá fora, a luz chega a PICO_LUX, menos as nuvens (ruído);
     dentro chega TRANSMISSAO dessa luz, mais LAMPADA_LUX com as lâmpadas;
     o BH1750 satura em 65 535 lx;
   - sem ventilação, o ar tende a 19 °C à noite e a 32 °C ao meio-dia;
     com o ventilador, a 21 °C; a névoa evapora e tira 2,5 °C;
   - a umidade do ar muda devagar: cai com o calor, o sol e a ventilação,
     e sobe com o solo úmido, com a água da aspersão e com a névoa;
   - o solo seca devagar e a aspersão, no alto, o molha depressa, se houver água;
   - a bomba tira VAZAO_LPM da caixa e a névoa, NEBLINA_LPM; a boia repõe
     BOIA_LPM até encher.

 Variáveis de ambiente (padrão entre parênteses):
   DEVICE_ID (estufa001)  APIKEY (estufa)  MQTT_HOST (mosquitto)  MQTT_PORT (1883)
   INTERVALO (5) s · LIGA_VENT (24) · DESLIGA_VENT (22) · LIGA_BOMBA (30)
   DESLIGA_BOMBA (45) · LIGA_LUZ (15000) lx · DESLIGA_LUZ (20000) lx · NOITE_LUX (500) lx
   LIGA_NEBLINA (1.25) kPa · DESLIGA_NEBLINA (0.95) kPa
   PERIODO_LUZ (600) s · PICO_LUX (50000) lx · TRANSMISSAO (0.68) · LAMPADA_LUX (5400) lx
   CAIXA_LITROS (500) · VAZAO_LPM (18) · BOIA_LPM (3) · NEBLINA_LPM (1)
   CAIXA_MINIMA (100) · CAIXA_RETOMA (150) · CAIXA_INICIAL (vazio: sorteada entre 92 e 98 %)
============================================================================
"""

import json
import math
import os
import random
import time

import paho.mqtt.client as mqtt

# ---------------------------------------------------------------------------
# 1. Configuração
# ---------------------------------------------------------------------------
DEVICE_ID = os.getenv("DEVICE_ID", "estufa001")
CHAVE = os.getenv("APIKEY", "estufa")
BROKER = os.getenv("MQTT_HOST", "mosquitto")
PORTA = int(os.getenv("MQTT_PORT", "1883"))
INTERVALO = float(os.getenv("INTERVALO", "5"))          # o DHT22 real exige no mínimo 2 s
LIGA_VENT = float(os.getenv("LIGA_VENT", "24"))
DESLIGA_VENT = float(os.getenv("DESLIGA_VENT", "22"))
LIGA_BOMBA = float(os.getenv("LIGA_BOMBA", "30"))
DESLIGA_BOMBA = float(os.getenv("DESLIGA_BOMBA", "45"))
LIGA_LUZ = float(os.getenv("LIGA_LUZ", "15000"))         # luz lá fora, no teto
DESLIGA_LUZ = float(os.getenv("DESLIGA_LUZ", "20000"))
NOITE_LUX = float(os.getenv("NOITE_LUX", "500"))         # abaixo disso é noite (premissa)
LIGA_NEBLINA = float(os.getenv("LIGA_NEBLINA", "1.25"))  # VPD, kPa
DESLIGA_NEBLINA = float(os.getenv("DESLIGA_NEBLINA", "0.95"))
PERIODO_LUZ = float(os.getenv("PERIODO_LUZ", "600"))
PICO_LUX = float(os.getenv("PICO_LUX", "50000"))         # sol ao meio-dia, lá fora (premissa)
TRANSMISSAO = float(os.getenv("TRANSMISSAO", "0.68"))    # fração da luz de fora que chega dentro (premissa)
LAMPADA_LUX = float(os.getenv("LAMPADA_LUX", "5400"))    # luz das lâmpadas no sensor de dentro (premissa)
FIM_DE_ESCALA_BH1750 = 65535                            # 16 bits, 1 lx por contagem
CAIXA_LITROS = float(os.getenv("CAIXA_LITROS", "500"))   # capacidade da caixa d'água
CAIXA_MINIMA = float(os.getenv("CAIXA_MINIMA", "100"))   # bomba bloqueada daqui para baixo (irrigationMinTankVolume)
CAIXA_RETOMA = float(os.getenv("CAIXA_RETOMA", "150"))   # ...até a caixa voltar a este nível (premissa)
CAIXA_INICIAL = os.getenv("CAIXA_INICIAL", "")           # litros no começo; vazio = sorteado
VAZAO_LPM = float(os.getenv("VAZAO_LPM", "18"))          # aspersão: 12 aspersores × 90 L/h (premissa)
BOIA_LPM = float(os.getenv("BOIA_LPM", "3"))             # reposição pela boia, da rede (premissa)
NEBLINA_LPM = float(os.getenv("NEBLINA_LPM", "1"))       # 10 nebulizadores × 6 L/h (premissa)

TOPICO_MEDIDAS = f"/json/{CHAVE}/{DEVICE_ID}/attrs"
TOPICO_COMANDOS = f"/{CHAVE}/{DEVICE_ID}/cmd"
TOPICO_RESULTADO = f"/json/{CHAVE}/{DEVICE_ID}/cmdexe"

# ---------------------------------------------------------------------------
# 2. "Hardware" simulado
# ---------------------------------------------------------------------------
inicio = time.time()
temperatura = random.uniform(20.5, 22.5)
umidade = random.uniform(0.76, 0.82)                     # umidade relativa do ar, de 0 a 1
solo = random.uniform(36.0, 42.0)
caixa = float(CAIXA_INICIAL) if CAIXA_INICIAL else CAIXA_LITROS * random.uniform(0.92, 0.98)   # litros na caixa
vazao = 0.0                                              # L/min no cano depois da bomba
ventilador = False                                      # estado seguro: tudo começa desligado
bomba = False
bomba_bloqueada = False                                 # proteção: caixa no mínimo
lampadas = False
neblina = False


def luz_de_fora():
    """Luz no teto, em lux: sol na primeira metade do 'dia', noite na segunda."""
    fase = 2 * math.pi * (time.time() - inicio) / PERIODO_LUZ
    sol = max(math.sin(fase), 0.0)                      # seno negativo = noite
    return PICO_LUX * sol * random.uniform(0.85, 1.0)     # nuvens


def bh1750(lux):
    """O que o sensor entrega: lux inteiro, de 0 ao fim de escala."""
    return int(min(max(lux, 0.0), FIM_DE_ESCALA_BH1750))


def passo_fisico(fora):
    """Avança a física da estufa em um intervalo de medida."""
    global temperatura, umidade, solo, caixa, vazao
    luz = fora / PICO_LUX                               # 0 à noite, ~1 ao meio-dia
    alvo = (21.0 if ventilador else 19.0 + 13.0 * luz) - (2.5 if neblina else 0.0)
    temperatura += 0.05 * (alvo - temperatura) + random.uniform(-0.12, 0.12)
    alvo_ur = (74 - 1.8 * (temperatura - 25) + 0.5 * (solo - 37.5) - 20 * luz
               - (8 if ventilador else 0) + 8 * vazao / VAZAO_LPM + (18 if neblina else 0)) / 100
    umidade += 0.15 * (alvo_ur - umidade)               # o ar muda devagar
    secagem = 0.18 + 0.004 * max(temperatura - 20, 0)    # mais calor, mais evaporação
    minutos = INTERVALO / 60
    disponivel = caixa / minutos + BOIA_LPM               # L/min que a caixa e a boia dão neste passo
    vazao = min(VAZAO_LPM * random.uniform(0.97, 1.03), disponivel) if bomba else 0.0   # caixa vazia: só o que a boia repõe
    nevoa = min(NEBLINA_LPM, disponivel - vazao) if neblina else 0.0
    caixa = min(max(caixa - (vazao + nevoa) * minutos + BOIA_LPM * minutos, 0.0), CAIXA_LITROS)
    solo += 1.6 * vazao / VAZAO_LPM - (0 if vazao else secagem)   # molha na proporção da vazão; sem água, seca
    solo = min(max(solo + random.uniform(-0.05, 0.05), 5.0), 80.0)


def ler_umidade_ar():
    """Umidade relativa de 0 a 1 (o DHT22 dá %, o firmware divide por 100)."""
    return min(max(umidade + random.uniform(-0.01, 0.01), 0.30), 0.95)


def calcular_vpd(t, ur):
    """Déficit de pressão de vapor em kPa (Tetens/FAO-56). t em °C, ur de 0 a 1."""
    e_s = 0.6108 * math.exp(17.27 * t / (t + 237.3))
    return e_s * (1 - ur)


def regra_local(fora, vpd):
    """Histerese na borda: fora da faixa, manda no relé; entre os limites, não mexe."""
    global ventilador, bomba, bomba_bloqueada, lampadas, neblina
    if temperatura >= LIGA_VENT and not ventilador:
        ventilador = True
        print(f"regra   -> ventilador ON  (t = {temperatura:.1f} °C)", flush=True)
    elif temperatura <= DESLIGA_VENT and ventilador:
        ventilador = False
        print(f"regra   -> ventilador OFF (t = {temperatura:.1f} °C)", flush=True)
    if caixa < CAIXA_MINIMA and not bomba_bloqueada:
        bomba_bloqueada = True
        print(f"proteção -> bomba bloqueada (caixa = {caixa:.0f} L)", flush=True)
    elif caixa >= CAIXA_RETOMA and bomba_bloqueada:
        bomba_bloqueada = False
        print(f"proteção -> bomba liberada (caixa = {caixa:.0f} L)", flush=True)
    if bomba_bloqueada:
        if bomba:
            bomba = False
            print(f"regra   -> bomba OFF (caixa abaixo do mínimo, {caixa:.0f} L)", flush=True)
    elif solo <= LIGA_BOMBA and not bomba:
        bomba = True
        print(f"regra   -> bomba ON  (m = {solo:.1f} %)", flush=True)
    elif solo >= DESLIGA_BOMBA and bomba:
        bomba = False
        print(f"regra   -> bomba OFF (m = {solo:.1f} %)", flush=True)
    noite = fora < NOITE_LUX
    if lampadas and (noite or fora >= DESLIGA_LUZ):
        lampadas = False
        print(f"regra   -> lâmpadas OFF (e = {fora:.0f} lx)", flush=True)
    elif not lampadas and not noite and fora <= LIGA_LUZ:
        lampadas = True
        print(f"regra   -> lâmpadas ON  (e = {fora:.0f} lx)", flush=True)
    if vpd >= LIGA_NEBLINA and not neblina:
        neblina = True
        print(f"regra   -> nebulização ON  (v = {vpd:.2f} kPa)", flush=True)
    elif vpd <= DESLIGA_NEBLINA and neblina:
        neblina = False
        print(f"regra   -> nebulização OFF (v = {vpd:.2f} kPa)", flush=True)


def estados():
    liga = lambda x: "ON" if x else "OFF"
    return {"f": liga(ventilador), "p": liga(bomba), "i": liga(lampadas), "n": liga(neblina)}


RELES = {"fan": ("ventilador", "ventilador ligado", "ventilador desligado"),
         "pump": ("bomba", "bomba ligada", "bomba desligada"),
         "lamp": ("lampadas", "lâmpadas ligadas", "lâmpadas desligadas"),
         "mist": ("neblina", "nebulização ligada", "nebulização desligada")}


def executar(comando):
    """Aciona um relé e devolve o texto do resultado (vai para <comando>_info).

    O Orion recusa < > " ' = ; ( ) nos valores: o texto não pode tê-los.
    """
    if comando == "pumpOn" and bomba_bloqueada:
        return "ERRO - caixa abaixo do mínimo, bomba bloqueada"
    for prefixo, (variavel, ligado, desligado) in RELES.items():
        if comando in (prefixo + "On", prefixo + "Off"):
            liga = comando.endswith("On")
            globals()[variavel] = liga
            return "OK - " + (ligado if liga else desligado)
    return "ERRO - comando desconhecido"


# ---------------------------------------------------------------------------
# 3. MQTT
# ---------------------------------------------------------------------------
def publicar(cliente, medida):
    cliente.publish(TOPICO_MEDIDAS, json.dumps(medida))   # números SEM aspas
    print("medida  ->", TOPICO_MEDIDAS, medida, flush=True)


def ao_conectar(cliente, userdata, flags, reason_code, properties):
    print(f"Conectada a {BROKER}:{PORTA} ({reason_code})", flush=True)
    cliente.subscribe(TOPICO_COMANDOS)
    print("Escutando", TOPICO_COMANDOS, flush=True)


def ao_receber(cliente, userdata, msg):
    try:
        comandos = json.loads(msg.payload)
    except ValueError:
        print("Mensagem ignorada (não é JSON):", msg.payload, flush=True)
        return
    print("comando <-", TOPICO_COMANDOS, comandos, flush=True)
    for comando in comandos:
        resultado = {comando: executar(comando)}
        cliente.publish(TOPICO_RESULTADO, json.dumps(resultado))
        print("cmdexe  ->", TOPICO_RESULTADO, resultado, flush=True)
    publicar(cliente, estados())                          # o novo estado é uma medida comum


# ---------------------------------------------------------------------------
# 4. Laço principal
# ---------------------------------------------------------------------------
cliente = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"{DEVICE_ID}-{os.getpid()}")
cliente.on_connect = ao_conectar
cliente.on_message = ao_receber

while True:                                             # o broker pode subir depois da placa
    try:
        cliente.connect(BROKER, PORTA, keepalive=60)
        break
    except OSError as erro:
        print("Broker indisponível, nova tentativa em 3 s:", erro, flush=True)
        time.sleep(3)

cliente.loop_start()                                    # a rede roda à parte; o laço só mede
try:
    while True:
        fora = luz_de_fora()
        passo_fisico(fora)
        t = round(temperatura, 1)
        h = round(ler_umidade_ar(), 2)
        v = round(calcular_vpd(t, h), 2)
        regra_local(fora, v)
        dentro = TRANSMISSAO * fora + (LAMPADA_LUX if lampadas else 0.0)
        medida = {"t": t, "h": h, "v": v, "m": round(solo, 1), "l": bh1750(dentro), "e": bh1750(fora),
                  "a": round(min(max(caixa + random.uniform(-1.5, 1.5), 0.0), CAIXA_LITROS), 1), "q": round(vazao, 1)}
        medida.update(estados())
        publicar(cliente, medida)
        time.sleep(INTERVALO)
except KeyboardInterrupt:
    print("Encerrando a ESP32 simulada da estufa.", flush=True)
finally:
    cliente.loop_stop()
    cliente.disconnect()
