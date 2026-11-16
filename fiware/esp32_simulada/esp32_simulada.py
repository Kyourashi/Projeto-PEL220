"""
============================================================================
 CCM130 - Conectividade e IoT | Aula 10 - Fluxo de dados completo
 Centro Universitário FEI - Prof. Rafael Gomes Alves
----------------------------------------------------------------------------
 ESP32 SIMULADA: o único dispositivo da aula.

 Faz em software o que a placa faz em hardware: um DHT22 mede a sala e um
 módulo relé liga um ventilador. Conversa com a plataforma só por MQTT, nos
 mesmos tópicos e com as mesmas mensagens do firmware da Aula 9
 (esp32/estacao_esp32.py). Por isso a placa real pode entrar no lugar dela
 sem mudar nada na plataforma.

   medidas    publica  /json/<chave>/<device_id>/attrs
                       {"t": 26.4, "h": 58.1, "s": "OFF"}
   comandos   assina   /<chave>/<device_id>/cmd
                       {"on": ""}  ou  {"off": ""}
   resultado  publica  /json/<chave>/<device_id>/cmdexe
                       {"on": "OK - rele ligado"}

 Com o relé desligado a sala esquenta (até perto de 29 °C); com o relé
 ligado, o ventilador a esfria (até perto de 22 °C).

 Variáveis de ambiente (padrão entre parênteses):
   DEVICE_ID (esp32001)  APIKEY (ccm130)  MQTT_HOST (mosquitto)
   MQTT_PORT (1883)      INTERVALO (5) segundos entre medidas
============================================================================
"""

import json
import os
import random
import time

import paho.mqtt.client as mqtt

# ---------------------------------------------------------------------------
# 1. Configuração
# ---------------------------------------------------------------------------
DEVICE_ID = os.getenv("DEVICE_ID", "esp32001")
CHAVE = os.getenv("APIKEY", "ccm130")
BROKER = os.getenv("MQTT_HOST", "mosquitto")
PORTA = int(os.getenv("MQTT_PORT", "1883"))
INTERVALO = float(os.getenv("INTERVALO", "5"))    # o DHT22 real exige no mínimo 2 s

TOPICO_MEDIDAS = f"/json/{CHAVE}/{DEVICE_ID}/attrs"
TOPICO_COMANDOS = f"/{CHAVE}/{DEVICE_ID}/cmd"
TOPICO_RESULTADO = f"/json/{CHAVE}/{DEVICE_ID}/cmdexe"

# ---------------------------------------------------------------------------
# 2. "Hardware" simulado
# ---------------------------------------------------------------------------
temperatura = random.uniform(24.0, 27.0)
umidade = random.uniform(50.0, 65.0)
rele_ligado = False                               # estado seguro: começa desligado


def ler_dht22():
    """Uma leitura do sensor: a sala tende a 29 °C, ou a 22 °C com o ventilador."""
    global temperatura, umidade
    alvo = 22.0 if rele_ligado else 29.0
    temperatura += 0.1 * (alvo - temperatura) + random.uniform(-0.2, 0.2)
    umidade = min(max(umidade + random.uniform(-0.8, 0.8), 20.0), 95.0)
    return round(temperatura, 1), round(umidade, 1)


def acionar_rele(ligado):
    global rele_ligado
    rele_ligado = ligado


def estado():
    return "ON" if rele_ligado else "OFF"


def executar(comando):
    """Aciona o relé e devolve o texto do resultado (vai para <comando>_info).

    Atenção: o Orion recusa < > " ' = ; ( ) nos valores: um texto como
    "OK: rele=ON" é rejeitado e o comando fica PENDING.
    """
    if comando == "on":
        acionar_rele(True)
        return "OK - rele ligado"
    if comando == "off":
        acionar_rele(False)
        return "OK - rele desligado"
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
    publicar(cliente, {"s": estado()})                    # o novo estado é uma medida comum


# ---------------------------------------------------------------------------
# 4. Laço principal
# ---------------------------------------------------------------------------
cliente = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"{DEVICE_ID}-{os.getpid()}")
cliente.on_connect = ao_conectar
cliente.on_message = ao_receber

while True:                                       # o broker pode subir depois da placa
    try:
        cliente.connect(BROKER, PORTA, keepalive=60)
        break
    except OSError as erro:
        print("Broker indisponível, nova tentativa em 3 s:", erro, flush=True)
        time.sleep(3)

cliente.loop_start()                              # a rede roda à parte; o laço só mede
try:
    while True:
        t, h = ler_dht22()
        publicar(cliente, {"t": t, "h": h, "s": estado()})
        time.sleep(INTERVALO)
except KeyboardInterrupt:
    print("Encerrando a ESP32 simulada.", flush=True)
finally:
    cliente.loop_stop()
    cliente.disconnect()
