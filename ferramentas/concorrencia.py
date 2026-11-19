"""Aula 7, seção 3: ler-somar-gravar perde atualizações; o operador $inc não.

Duas "portas" contam visitantes no mesmo atributo, ao mesmo tempo.
Precisa só do Python (sem bibliotecas) e do Orion em localhost:1026.

    python concorrencia.py            # 200 visitas por porta
    python concorrencia.py 500        # 500 visitas por porta
"""
import json
import sys
import threading
import time
import urllib.error
import urllib.request

ORION = "http://localhost:1026"
CAB = {"fiware-service": "pel220", "fiware-servicepath": "/predioK/andar5"}
ID = "urn:ngsi-ld:Door:Concorrencia"
VISITAS = int(sys.argv[1]) if len(sys.argv) > 1 else 200


def chamar(metodo, caminho, corpo=None, tipo="application/json"):
    cab = dict(CAB)
    dados = None
    if corpo is not None:
        dados = corpo.encode() if isinstance(corpo, str) else json.dumps(corpo).encode()
        cab["Content-Type"] = tipo
    req = urllib.request.Request(ORION + caminho, data=dados, method=metodo, headers=cab)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            texto = r.read().decode()
            return r.status, (json.loads(texto) if texto else None)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def ler():
    return chamar("GET", f"/v2/entities/{ID}/attrs/count/value")[1]


def porta_ler_somar_gravar():
    for _ in range(VISITAS):
        atual = ler()                                                    # 1: lê
        chamar("PUT", f"/v2/entities/{ID}/attrs/count/value", str(int(atual) + 1), "text/plain")  # 2: grava


def porta_inc():
    for _ in range(VISITAS):
        chamar("PATCH", f"/v2/entities/{ID}/attrs", {"count": {"type": "Number", "value": {"$inc": 1}}})


def rodada(nome, porta):
    chamar("PUT", f"/v2/entities/{ID}/attrs/count/value", "0", "text/plain")
    inicio = time.time()
    portas = [threading.Thread(target=porta) for _ in range(2)]
    for p in portas:
        p.start()
    for p in portas:
        p.join()
    contador = int(ler())
    esperado = 2 * VISITAS
    print(f"{nome:18s} esperado {esperado}  contador {contador}  perdidas {esperado - contador}"
          f"  ({time.time() - inicio:.1f} s)")


if __name__ == "__main__":
    chamar("DELETE", f"/v2/entities/{ID}")
    codigo, _ = chamar("POST", "/v2/entities", {"id": ID, "type": "Door", "count": {"type": "Number", "value": 0}})
    if codigo != 201:
        sys.exit(f"Não consegui criar a entidade de teste (HTTP {codigo}). O Orion está no ar?")
    rodada("ler-somar-gravar", porta_ler_somar_gravar)
    rodada("$inc", porta_inc)
    chamar("DELETE", f"/v2/entities/{ID}")
