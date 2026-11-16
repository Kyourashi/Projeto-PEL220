"""PEL 220 · Aula 6 — mede quanto tempo leva um comando (Etapa 4 da Base).

Manda N comandos alternados (on/off) ao Orion e mede o tempo até o 204 do PATCH e até o
<comando>_status = OK, consultando o Orion a cada 5 ms (o fim é detectado pela mudança do
metadado dateModified de <comando>_status). Só biblioteca padrão do Python.

Requisitos: Etapas 1 a 3 da Base no ar (a ESP32 simulada precisa responder).
Uso:        python ferramentas/latencia_comando.py
Em 11/11/2026: 204 em 50 ms e OK em 64 ms (medianas de 12); outra rodada: 56 e 77 ms.
"""
import json
import statistics
import time
import urllib.request

O = "http://127.0.0.1:1026"
ENT = "urn:ngsi-ld:ClimateStation:ESP32001"
H = {"fiware-service": "ccm130", "fiware-servicepath": "/"}
N = 12


def req(metodo, url, corpo=None):
    h = dict(H)
    dados = None
    if corpo is not None:
        dados = json.dumps(corpo).encode()
        h["Content-Type"] = "application/json"
    r = urllib.request.Request(url, data=dados, method=metodo, headers=h)
    with urllib.request.urlopen(r, timeout=10) as resp:
        corpo = resp.read()
        return resp.status, (json.loads(corpo) if corpo else None)


tempos_ok, tempos_204 = [], []
for i in range(N):
    cmd = "on" if i % 2 == 0 else "off"
    _, a = req("GET", f"{O}/v2/entities/{ENT}?attrs={cmd}_status&metadata=dateModified")
    antes = a.get(f"{cmd}_status", {}).get("metadata", {}).get("dateModified", {}).get("value")
    t0 = time.perf_counter()
    st, _ = req("PATCH", f"{O}/v2/entities/{ENT}/attrs?type=ClimateStation",
                {cmd: {"type": "command", "value": ""}})
    t1 = time.perf_counter()
    pendente_visto = False
    while True:
        _, e = req("GET", f"{O}/v2/entities/{ENT}?attrs={cmd}_status&metadata=dateModified")
        at = e.get(f"{cmd}_status", {})
        s = at.get("value")
        mod = at.get("metadata", {}).get("dateModified", {}).get("value")
        if s == "PENDING":
            pendente_visto = True
        if s == "OK" and mod != antes:
            break
        if time.perf_counter() - t0 > 10:
            raise SystemExit("tempo esgotado")
        time.sleep(0.005)
    t2 = time.perf_counter()
    tempos_204.append((t1 - t0) * 1000)
    tempos_ok.append((t2 - t0) * 1000)
    print(f"{cmd:3s}  PENDING visto={pendente_visto!s:5}  204 em {tempos_204[-1]:6.1f} ms   OK em {tempos_ok[-1]:6.1f} ms")
    time.sleep(1.5)

print(f"mediana 204: {statistics.median(tempos_204):.1f} ms | mediana PATCH->OK: {statistics.median(tempos_ok):.1f} ms "
      f"(min {min(tempos_ok):.1f}, max {max(tempos_ok):.1f}, n={N})")
