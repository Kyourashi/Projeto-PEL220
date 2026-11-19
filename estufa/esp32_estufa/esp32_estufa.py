"""
============================================================================
 PEL220 - Projeto do grupo: estufa agrícola inteligente
----------------------------------------------------------------------------
 ESP32 SIMULADA DA ESTUFA (nó urn:ngsi-ld:Device:ESP32-001).

 Faz em software o que o nó da estufa faz em hardware, no mesmo contrato
 MQTT do provisionamento (modelo-dados/provisionamento/dispositivo.json):

   medidas    publica  /json/<chave>/<device_id>/attrs
                       {"t": 26.4, "h": 0.62, "m": 38.5, "l": 71.0,
                        "f": "OFF", "p": "OFF"}
   comandos   assina   /<chave>/<device_id>/cmd
                       {"fanOn": ""} · {"fanOff": ""} · {"pumpOn": ""} · {"pumpOff": ""}
   resultado  publica  /json/<chave>/<device_id>/cmdexe
                       {"fanOn": "OK - ventilador ligado"}

   t  temperatura do ar (°C, DHT22)       f  relé do ventilador (ON/OFF)
   h  umidade relativa do ar (0 a 1)      p  relé da bomba (ON/OFF)
   m  umidade do solo (%, capacitivo)     l  luminosidade (% da escala do LDR)

 O DHT22 entrega a umidade em %; o firmware divide por 100, porque o modelo
 de dados usa relativeHumidity de 0 a 1 (como o Smart Data Model).

 Regra local (na borda), com histerese — os limites da AgriGreenhouse:
   ventilador liga com t >= LIGA_VENT e desliga com t <= DESLIGA_VENT
   bomba      liga com m <= LIGA_BOMBA e desliga com m >= DESLIGA_BOMBA
 A regra só age quando um limite é cruzado; um comando manual vale até o
 próximo cruzamento.

 Física simplificada e acelerada (um ciclo do ventilador leva poucos
 minutos), para o painel de 30 minutos mostrar vários ciclos:
   - a luz segue um "dia" de PERIODO_LUZ segundos;
   - sem ventilação, o ar tende a 29 °C + 4 °C × luz; com o ventilador, a 21 °C;
   - o solo seca devagar e a bomba o molha depressa;
   - a umidade do ar cai com o calor e com a ventilação e sobe com a rega.

 Variáveis de ambiente (padrão entre parênteses):
   DEVICE_ID (estufa001)  APIKEY (estufa)  MQTT_HOST (mosquitto)  MQTT_PORT (1883)
   INTERVALO (5) s · LIGA_VENT (28) · DESLIGA_VENT (24) · LIGA_BOMBA (30)
   DESLIGA_BOMBA (45) · PERIODO_LUZ (1200) s
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
LIGA_VENT = float(os.getenv("LIGA_VENT", "28"))
DESLIGA_VENT = float(os.getenv("DESLIGA_VENT", "24"))
LIGA_BOMBA = float(os.getenv("LIGA_BOMBA", "30"))
DESLIGA_BOMBA = float(os.getenv("DESLIGA_BOMBA", "45"))
PERIODO_LUZ = float(os.getenv("PERIODO_LUZ", "1200"))

TOPICO_MEDIDAS = f"/json/{CHAVE}/{DEVICE_ID}/attrs"
TOPICO_COMANDOS = f"/{CHAVE}/{DEVICE_ID}/cmd"
TOPICO_RESULTADO = f"/json/{CHAVE}/{DEVICE_ID}/cmdexe"

# ---------------------------------------------------------------------------
# 2. "Hardware" simulado
# ---------------------------------------------------------------------------
inicio = time.time()
temperatura = random.uniform(24.5, 26.5)
solo = random.uniform(36.0, 42.0)
ventilador = False                                      # estado seguro: começa desligado
bomba = False


def ler_ldr():
    """Luz em % da escala do ADC: um 'dia' acelerado, com nuvens (ruído)."""
    fase = 2 * math.pi * (time.time() - inicio) / PERIODO_LUZ
    luz = 55 + 40 * math.sin(fase) + random.uniform(-3, 3)
    return min(max(luz, 0.0), 100.0)


def passo_fisico(luz):
    """Avança a física da estufa em um intervalo de medida."""
    global temperatura, solo
    alvo = 21.0 if ventilador else 29.0 + 4.0 * luz / 100
    temperatura += 0.05 * (alvo - temperatura) + random.uniform(-0.12, 0.12)
    secagem = 0.18 + 0.004 * max(temperatura - 20, 0)    # mais calor, mais evaporação
    solo += 1.6 if bomba else -secagem
    solo = min(max(solo + random.uniform(-0.05, 0.05), 5.0), 80.0)


def ler_umidade_ar():
    """Umidade relativa de 0 a 1 (o DHT22 dá %, o firmware divide por 100)."""
    ur = 75 - 1.8 * (temperatura - 25) + 0.5 * (solo - 37.5) - (6 if ventilador else 0)
    ur += random.uniform(-1.0, 1.0)
    return min(max(ur, 30.0), 95.0) / 100


def regra_local():
    """Histerese na borda: só muda o relé quando um limite é cruzado."""
    global ventilador, bomba
    if temperatura >= LIGA_VENT and not ventilador:
        ventilador = True
        print(f"regra   -> ventilador ON  (t = {temperatura:.1f} °C)", flush=True)
    elif temperatura <= DESLIGA_VENT and ventilador:
        ventilador = False
        print(f"regra   -> ventilador OFF (t = {temperatura:.1f} °C)", flush=True)
    if solo <= LIGA_BOMBA and not bomba:
        bomba = True
        print(f"regra   -> bomba ON  (m = {solo:.1f} %)", flush=True)
    elif solo >= DESLIGA_BOMBA and bomba:
        bomba = False
        print(f"regra   -> bomba OFF (m = {solo:.1f} %)", flush=True)


def estados():
    return {"f": "ON" if ventilador else "OFF", "p": "ON" if bomba else "OFF"}


def executar(comando):
    """Aciona um relé e devolve o texto do resultado (vai para <comando>_info).

    O Orion recusa < > " ' = ; ( ) nos valores: o texto não pode tê-los.
    """
    global ventilador, bomba
    if comando == "fanOn":
        ventilador = True
        return "OK - ventilador ligado"
    if comando == "fanOff":
        ventilador = False
        return "OK - ventilador desligado"
    if comando == "pumpOn":
        bomba = True
        return "OK - bomba ligada"
    if comando == "pumpOff":
        bomba = False
        return "OK - bomba desligada"
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
        luz = ler_ldr()
        passo_fisico(luz)
        regra_local()
        medida = {"t": round(temperatura, 1), "h": round(ler_umidade_ar(), 2),
                  "m": round(solo, 1), "l": round(luz, 1)}
        medida.update(estados())
        publicar(cliente, medida)
        time.sleep(INTERVALO)
except KeyboardInterrupt:
    print("Encerrando a ESP32 simulada da estufa.", flush=True)
finally:
    cliente.loop_stop()
    cliente.disconnect()
