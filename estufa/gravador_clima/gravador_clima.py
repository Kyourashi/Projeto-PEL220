"""
============================================================================
 PEL220 - Projeto do grupo: estufa agrícola inteligente
----------------------------------------------------------------------------
 GRAVADOR DO CLIMA EXTERNO (urn:ngsi-ld:WeatherObserved:FEI, tenant estufa).

 Por que existe: com um REGISTRO (Aula 7), o Orion não guarda o clima; ele
 pergunta ao provedor a cada leitura. Sem gravação no Orion não há
 notificação, e sem notificação o Cygnus não grava. Este programa troca o
 registro por uma cópia periódica:

   a cada INTERVALO segundos
     POST <PROVEDOR>/op/query    pergunta ao clima-externo da Base (Open-Meteo),
                                 o mesmo pedido que o Orion faria no registro
     POST <ORION>/v2/op/update   append: cria ou atualiza a WeatherObserved:FEI
   e a subscrição "Clima externo para o Cygnus" (configurar.py) leva ao MySQL.

 Por que 15 min: o "current" da Open-Meteo vem da previsão de 15 em 15 min;
 ler mais rápido não traz informação nova. Se nada mudou, o Orion não
 notifica, e o histórico não ganha linha repetida.

 Um ou outro: no tenant estufa, o clima não pode ter registro. Com registro e
 gravação juntos, o Orion mistura as fontes: o atributo gravado sai do Orion
 e o que faltar vem do provedor na hora, cada um com uma idade (testado no
 Orion 4.1.0).

 Variáveis de ambiente (padrão entre parênteses):
   PROVEDOR (http://clima-externo:3010/v2)  ORION (http://orion:1026)
   FIWARE_SERVICE (estufa)  FIWARE_SERVICEPATH (/)  INTERVALO (900) s
   LATITUDE (-23.7245)  LONGITUDE (-46.5793)
============================================================================
"""

import json
import os
import time
import urllib.error
import urllib.request

PROVEDOR = os.getenv("PROVEDOR", "http://clima-externo:3010/v2")
ORION = os.getenv("ORION", "http://orion:1026")
TENANT = {"fiware-service": os.getenv("FIWARE_SERVICE", "estufa"),
          "fiware-servicepath": os.getenv("FIWARE_SERVICEPATH", "/")}
INTERVALO = float(os.getenv("INTERVALO", "900"))
LATITUDE = float(os.getenv("LATITUDE", "-23.7245"))
LONGITUDE = float(os.getenv("LONGITUDE", "-46.5793"))

ID = "urn:ngsi-ld:WeatherObserved:FEI"
TIPO = "WeatherObserved"
UNIDADES = {"temperature": "CEL", "relativeHumidity": "C62", "windSpeed": "MTS"}   # como no modelo de dados


def log(*args):
    print("[gravador]", *args, flush=True)


def post(url, corpo, cabecalhos=None):
    pedido = urllib.request.Request(url, data=json.dumps(corpo).encode(), method="POST",
                                    headers={"Content-Type": "application/json", **(cabecalhos or {})})
    with urllib.request.urlopen(pedido, timeout=10) as resposta:
        texto = resposta.read().decode()
        return resposta.status, (json.loads(texto) if texto else None)


def ler_provedor():
    """O clima atual, já em NGSI-v2 (o provedor traduz a Open-Meteo)."""
    _, entidades = post(f"{PROVEDOR}/op/query", {"entities": [{"id": ID, "type": TIPO}]})
    return entidades[0]


def gravar(entidade):
    """Acrescenta as unidades e a posição e grava no Orion (cria ou atualiza)."""
    for nome, codigo in UNIDADES.items():
        if nome in entidade:
            entidade[nome]["metadata"] = {"unitCode": {"type": "Text", "value": codigo}}
    entidade["location"] = {"type": "geo:json",
                            "value": {"type": "Point", "coordinates": [LONGITUDE, LATITUDE]}}   # [lon, lat]
    status, _ = post(f"{ORION}/v2/op/update", {"actionType": "append", "entities": [entidade]}, TENANT)
    return status


log(f"provedor {PROVEDOR} → Orion {ORION} (tenant {TENANT['fiware-service']}), a cada {INTERVALO:.0f} s")
while True:
    try:
        clima = ler_provedor()
        status = gravar(clima)
        log(f"gravado ({status}):", {k: v["value"] for k, v in clima.items() if k not in ("id", "type", "location")})
        espera = INTERVALO
    except urllib.error.HTTPError as erro:
        log(f"recusado ({erro.code}), nova tentativa em 30 s:", erro.read().decode()[:300])
        espera = 30
    except (OSError, ValueError, KeyError, IndexError) as erro:          # provedor ou Orion fora do ar
        log("falhou, nova tentativa em 30 s:", erro)
        espera = 30
    time.sleep(espera)
