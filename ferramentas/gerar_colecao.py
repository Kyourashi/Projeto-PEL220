"""Gera a coleção do Postman da Aula 7 (pastas C1 a C6) a partir de uma lista de requisições.

    python gerar_colecao.py

Cada requisição é: (nome, método, caminho, opções). Opções:
  sp      valor de fiware-servicepath (None = sem o cabeçalho)
  svc     valor de fiware-service (padrão: {{service}}; None = sem o cabeçalho)
  body    corpo JSON (dict/list) ou texto (str, enviado como text/plain)
  status  código HTTP esperado (ou lista de códigos aceitos)
  ids     lista esperada dos finais de id (ex.: ["K501", "K502"]), em qualquer ordem
  ordem   idem, mas na ordem exata
  igual   o corpo JSON da resposta deve ser igual a este valor
  js      linhas extras de teste em JavaScript
  pre     linhas de script de pré-requisição (ex.: espera)
  desc    descrição mostrada no Postman
"""
import json
import os
import uuid

AQUI = os.path.dirname(os.path.abspath(__file__))
E = "/v2/entities"
S = "/v2/subscriptions"
A5, A4, TUDO = "/predioK/andar5", "/predioK/andar4", "/predioK/#"
K501, K502, K401, K503 = ("urn:ngsi-ld:Room:K501", "urn:ngsi-ld:Room:K502", "urn:ngsi-ld:Room:K401",
                          "urn:ngsi-ld:Lab:K503")
DOOR = "urn:ngsi-ld:Door:K5"


def sala(ident, tipo, nome, andar, cap, cor=None, temp=None, exat=None, extra=None):
    e = {"id": ident, "type": tipo, "name": {"type": "Text", "value": nome},
         "floor": {"type": "Number", "value": andar}, "capacity": {"type": "Number", "value": cap}}
    if cor:
        e["color"] = {"type": "Text", "value": cor}
    if temp is not None:
        e["temperature"] = {"type": "Number", "value": temp, "metadata": {
            "unitCode": {"type": "Text", "value": "CEL"}, "accuracy": {"type": "Number", "value": exat}}}
    if extra:
        e.update(extra)
    return e


def num(v):
    return {"type": "Number", "value": v}


def q(nome, consulta, ids=None, ordem=None, status=200, desc=""):
    return (nome, "GET", f"{E}?{consulta}&options=keyValues&attrs=name", dict(sp=TUDO, ids=ids, ordem=ordem,
                                                                              status=status, desc=desc))


def op(nome, attr, valor, tipo="Number", status=204):
    return (nome, "PATCH", f"{E}/{DOOR}/attrs", dict(sp=A5, body={attr: {"type": tipo, "value": valor}}, status=status))


def valor(nome, attr, esperado, ident=DOOR):
    return (nome, "GET", f"{E}/{ident}/attrs/{attr}/value", dict(sp=A5, igual=esperado))


def temp(nome, v, opt=""):
    return (nome, "PATCH", f"{E}/{K501}/attrs{opt}", dict(sp=A5, body={"temperature": num(v)}, status=204))


ESPERA = lambda s: [f"// espera {s} s antes de enviar", f"return new Promise(r => setTimeout(r, {int(s * 1000)}));"]
SUB_QUENTE = {"description": "Sala quente via MQTT",
              "subject": {"entities": [{"idPattern": ".*", "type": "Room"}],
                          "condition": {"attrs": ["temperature"], "expression": {"q": "temperature>28"}}},
              "notification": {"mqtt": {"url": "mqtt://mosquitto:1883", "topic": "pel220/quente"},
                               "attrs": ["temperature", "name"], "attrsFormat": "keyValues"}}

PASTAS = [
    ("C1 - Tenants e caminhos", "Seção 1. Cria as quatro entidades do laboratório no tenant pel220 e mostra o que cada "
     "fiware-servicepath enxerga.", [
        ("Cria Room:K501 no andar 5", "POST", E, dict(sp=A5, status=201, body=sala(
            K501, "Room", "Laboratório K5-01", 5, 40, "blue", 27.5, 0.5,
            {"tags": {"type": "StructuredValue", "value": ["lab", "iot"]},
             "location": {"type": "geo:json", "value": {"type": "Point", "coordinates": [-46.5793, -23.7245]}}}))),
        ("Cria Room:K502 no andar 5", "POST", E, dict(sp=A5, status=201, body=sala(K502, "Room", "Sala K5-02", 5, 30, "yellow", 22, 2))),
        ("Cria Lab:K503 no andar 5", "POST", E, dict(sp=A5, status=201, body=sala(K503, "Lab", "Laboratório K5-03", 5, 25, None, 31, 0.5))),
        ("Cria Room:K401 no andar 4", "POST", E, dict(sp=A4, status=201, body=sala(K401, "Room", "Sala K4-01", 4, 60, "black"))),
        ("Caminho exato - predioK não inclui os andares", "GET", E + "?options=keyValues&attrs=name", dict(sp="/predioK", ids=[])),
        ("Com curinga - predioK e subcaminhos", "GET", E + "?options=keyValues&attrs=name", dict(sp=TUDO, ids=["K501", "K502", "K503", "K401"])),
        ("Lista de caminhos", "GET", E + "?options=keyValues&attrs=name", dict(sp=A4 + "," + A5, ids=["K501", "K502", "K503", "K401"])),
        ("Sem fiware-servicepath - equivale a barra cerquilha", "GET", E + "?options=keyValues&attrs=name", dict(sp=None, ids=["K501", "K502", "K503", "K401"])),
        ("Raiz - só o que está exatamente em barra", "GET", E + "?options=keyValues&attrs=name", dict(sp="/", ids=[])),
        ("Tenant em maiúsculas - é o mesmo tenant", "GET", E + "?options=keyValues&attrs=name", dict(sp=TUDO, svc="PEL220", ids=["K501", "K502", "K503", "K401"])),
        ("Tenant que não existe - lista vazia, sem erro", "GET", E + "?options=keyValues&attrs=name", dict(sp=TUDO, svc="naoexiste", ids=[])),
        ("PATCH sem fiware-servicepath - 404", "PATCH", f"{E}/{K502}/attrs", dict(sp=None, status=404, body={"capacity": num(31)},
            desc="Gravação sem o cabeçalho vale para a raiz; a sala está em /predioK/andar5.")),
        ("Criação com curinga - 400", "POST", E, dict(sp=TUDO, status=400, body={"id": "urn:ngsi-ld:Room:X1", "type": "Room"})),
        ("Caminho sem a barra inicial - 400", "POST", E, dict(sp="predioK", status=400, body={"id": "urn:ngsi-ld:Room:X2", "type": "Room"})),
        ("Mesmo id em outro caminho - 201", "POST", E, dict(sp=A4, status=201, body={"id": K501, "type": "Room", "name": {"type": "Text", "value": "homonima no andar 4"}})),
        ("GET por id com dois candidatos - 409", "GET", f"{E}/{K501}?options=keyValues&attrs=name", dict(sp=None, status=409)),
        ("Remove a homônima do andar 4", "DELETE", f"{E}/{K501}", dict(sp=A4, status=204)),
    ]),
    ("C2 - Embutidos, expiração e caracteres proibidos", "Seção 1. dateCreated, dateModified, dateExpires e os oito caracteres proibidos.", [
        ("Embutidos não vêm sem pedir", "GET", f"{E}/{K502}?options=keyValues", dict(sp=A5, js=[
            'pm.test("Sem dateCreated", () => pm.expect(pm.response.json()).to.not.have.property("dateCreated"));'])),
        ("Embutidos pedidos pelo nome", "GET", f"{E}/{K502}?options=keyValues&attrs=dateCreated,dateModified,*", dict(sp=A5, js=[
            'pm.test("Vieram dateCreated e dateModified", () => pm.expect(pm.response.json()).to.include.keys("dateCreated", "dateModified", "temperature"));'])),
        ("Datas de um atributo - são metadados", "GET", f"{E}/{K502}?attrs=temperature&metadata=dateCreated,dateModified,*", dict(sp=A5, js=[
            'pm.test("Metadados embutidos e de usuário", () => pm.expect(pm.response.json().temperature.metadata).to.include.keys("dateCreated", "dateModified", "unitCode", "accuracy"));'])),
        ("Alerta com prazo de 20 s", "POST", E, dict(sp=A5, status=201,
            pre=['pm.collectionVariables.set("expira", new Date(Date.now() + 20000).toISOString());'],
            body={"id": "urn:ngsi-ld:Alert:001", "type": "Alert", "dateExpires": {"type": "DateTime", "value": "{{expira}}"}})),
        ("O alerta existe", "GET", f"{E}/urn:ngsi-ld:Alert:001?options=keyValues&attrs=dateExpires", dict(sp=A5, js=[
            'pm.test("Tem dateExpires", () => pm.expect(pm.response.json()).to.have.property("dateExpires"));'])),
        ("O alerta sumiu - espera 85 s", "GET", f"{E}/urn:ngsi-ld:Alert:001", dict(sp=A5, status=404, pre=ESPERA(85),
            desc="O MongoDB remove pelo índice TTL, que roda a cada 60 s. Esta requisição espera 85 s antes de enviar.")),
        ("Valor com parênteses - 400", "POST", f"{E}/{K502}/attrs", dict(sp=A5, status=400, body={"obs": {"type": "Text", "value": "Sala quente (HTTP)"}})),
        ("Valor com outros símbolos - aceito", "POST", f"{E}/{K502}/attrs", dict(sp=A5, status=204, body={"obs": {"type": "Text", "value": "ok: 100% - sala/5 + [x] {y} @ # & ?"}})),
        ("TextUnrestricted aceita os proibidos", "POST", f"{E}/{K502}/attrs", dict(sp=A5, status=204, body={"obs": {"type": "TextUnrestricted", "value": "Sala quente (HTTP); a=b"}})),
        ("Remove o atributo obs", "DELETE", f"{E}/{K502}/attrs/obs", dict(sp=A5, status=204)),
        ("Id com espaço - 400", "POST", E, dict(sp=A5, status=400, body={"id": "urn:ngsi-ld:Room:K 9", "type": "Room"})),
    ]),
    ("C3 - Consultas", "Seção 2. A linguagem de consulta simples sobre as quatro entidades. Cabeçalho fiware-servicepath: /predioK/#.", [
        q("Igualdade", "q=floor==5", ["K501", "K502", "K503"]),
        q("E lógico", "q=floor==5;capacity>=30", ["K501", "K502"]),
        q("Intervalo inclusivo", "q=capacity==25..40", ["K501", "K502", "K503"]),
        q("Lista - OU entre valores", "q=color==blue,black", ["K501", "K401"]),
        q("Diferente de todos", "q=color!=blue,black", ["K502"], desc="K503 não tem color e não aparece."),
        q("Comparação", "q=temperature>25", ["K501", "K503"]),
        q("Expressão regular", "q=name~=^Lab", ["K501", "K503"]),
        q("Expressão regular diferencia maiúsculas", "q=name~=lab", []),
        q("Unária - não tem o atributo", "q=!temperature", ["K401"]),
        q("Unária - tem o atributo", "q=temperature", ["K501", "K502", "K503"]),
        q("Valor dentro de uma lista", "q=tags==iot", ["K501"]),
        q("Filtro sobre metadado", "mq=temperature.accuracy<1", ["K501", "K503"]),
        q("Aspas forçam texto", "q=floor=='5'", []),
        q("Não há OU entre condições - 400", "q=capacity>30|floor==4", status=400),
        q("Com type - só as salas", "type=Room&q=temperature>25", ["K501"]),
        q("Lista de tipos", "type=Room,Lab", ["K501", "K502", "K503", "K401"]),
        q("typePattern", "typePattern=^L", ["K503"]),
        q("idPattern", "idPattern=K50[12]$", ["K501", "K502"]),
        q("Ordenação por dois critérios", "orderBy=floor,!capacity", ordem=["K401", "K501", "K502", "K503"]),
        ("Paginação com total", "GET", E + "?limit=2&offset=1&options=count,keyValues&attrs=name&orderBy=capacity", dict(sp=TUDO, ordem=["K502", "K501"], js=[
            'pm.test("Total no cabeçalho", () => pm.expect(pm.response.headers.get("Fiware-Total-Count")).to.eql("4"));'])),
        ("Só os valores", "GET", E + "?type=Room&attrs=name,capacity&options=values&orderBy=!capacity", dict(sp=TUDO, igual=[["Sala K4-01", 60], ["Laboratório K5-01", 40], ["Sala K5-02", 30]])),
        q("Geográfica - coords em latitude,longitude", "georel=near;maxDistance:1000&geometry=point&coords=-23.7245,-46.5793", ["K501"]),
        q("Geográfica com a ordem trocada - vazio, sem erro", "georel=near;maxDistance:1000&geometry=point&coords=-46.5793,-23.7245", []),
        q("Filtro sobre atributo embutido", "q=dateModified>2026-01-01T00:00:00Z", ["K501", "K502", "K503", "K401"]),
        ("Consulta no corpo - op/query", "POST", "/v2/op/query?options=keyValues", dict(sp=TUDO, ids=["K501", "K401"], body={
            "entities": [{"idPattern": ".*", "type": "Room"}], "attrs": ["name", "capacity"], "expression": {"q": "capacity>=40"}})),
        ("Limite máximo é 1000 - 400", "GET", E + "?limit=1001", dict(sp=TUDO, status=400)),
    ]),
    ("C4 - Atualizações", "Seção 3. Verbos, metadados e operadores atômicos, sobre a porta Door:K5 e a sala K502.", [
        ("Cria a porta Door:K5", "POST", E, dict(sp=A5, status=201, body={"id": DOOR, "type": "Door", "count": num(10), "peak": num(10), "low": num(10),
            "tags": {"type": "StructuredValue", "value": ["a"]}, "cfg": {"type": "StructuredValue", "value": {"x": 1, "y": 2}}})),
        op("inc 1", "count", {"$inc": 1}), valor("count vale 11", "count", 11),
        op("inc -3", "count", {"$inc": -3}), op("mul 2", "count", {"$mul": 2}), valor("count vale 16", "count", 16),
        op("max 7 - não muda", "peak", {"$max": 7}), valor("peak continua 10", "peak", 10),
        op("max 15", "peak", {"$max": 15}), valor("peak vale 15", "peak", 15),
        op("min 4", "low", {"$min": 4}), valor("low vale 4", "low", 4),
        op("push b", "tags", {"$push": "b"}, "StructuredValue"), op("push b de novo - repete", "tags", {"$push": "b"}, "StructuredValue"),
        op("addToSet b - já existe", "tags", {"$addToSet": "b"}, "StructuredValue"), op("addToSet c", "tags", {"$addToSet": "c"}, "StructuredValue"),
        valor("tags vale a, b, b, c", "tags", ["a", "b", "b", "c"]),
        op("pull b - remove todas", "tags", {"$pull": "b"}, "StructuredValue"), valor("tags vale a, c", "tags", ["a", "c"]),
        op("pullAll a, c", "tags", {"$pullAll": ["a", "c"]}, "StructuredValue"), valor("tags vazia", "tags", []),
        op("set z e x", "cfg", {"$set": {"z": 3, "x": 9}}, "StructuredValue"), op("unset y", "cfg", {"$unset": {"y": 1}}, "StructuredValue"),
        valor("cfg vale x 9, z 3", "cfg", {"x": 9, "z": 3}),
        op("inc em atributo que não existe - 422", "novo", {"$inc": 5}, status=422),
        ("POST attrs cria com o valor do incremento", "POST", f"{E}/{DOOR}/attrs", dict(sp=A5, status=204, body={"novo": num({"$inc": 5})})),
        valor("novo vale 5", "novo", 5),
        op("Dois operadores - só o primeiro vale", "count", {"$inc": 1, "$mul": 2}), valor("count vale 17, e não 34", "count", 17),
        op("inc com texto - 500", "count", {"$inc": "1"}, status=500),
        ("PUT só do valor - text/plain", "PUT", f"{E}/{DOOR}/attrs/count/value", dict(sp=A5, status=204, body="0")),
        valor("count vale 0", "count", 0),
        ("PATCH só com o valor", "PATCH", f"{E}/{K502}/attrs", dict(sp=A5, status=204, body={"temperature": num(23)})),
        ("Os metadados foram preservados", "GET", f"{E}/{K502}/attrs/temperature", dict(sp=A5, js=[
            'pm.test("unitCode e accuracy continuam", () => pm.expect(pm.response.json().metadata).to.have.keys("unitCode", "accuracy"));'])),
        ("PATCH com overrideMetadata", "PATCH", f"{E}/{K502}/attrs?options=overrideMetadata", dict(sp=A5, status=204, body={"temperature": num(23.5)})),
        ("Os metadados sumiram", "GET", f"{E}/{K502}/attrs/temperature", dict(sp=A5, js=[
            'pm.test("metadata vazio", () => pm.expect(pm.response.json().metadata).to.eql({}));'])),
        ("Restaura a temperatura da K502", "PATCH", f"{E}/{K502}/attrs", dict(sp=A5, status=204, body={"temperature": {
            "type": "Number", "value": 22, "metadata": {"unitCode": {"type": "Text", "value": "CEL"}, "accuracy": num(2)}}})),
        ("PATCH em atributo novo - 422", "PATCH", f"{E}/{K502}/attrs", dict(sp=A5, status=422, body={"hasProjector": {"type": "Boolean", "value": False}})),
        ("POST com options=append em atributo existente - 422", "POST", f"{E}/{K502}/attrs?options=append", dict(sp=A5, status=422, body={"capacity": num(99)})),
        ("Cria a entidade de teste com a e b", "POST", E, dict(sp=A5, status=201, body={"id": "urn:ngsi-ld:Teste:P1", "type": "Teste", "a": num(1), "b": num(2)})),
        ("PUT attrs substitui todos", "PUT", f"{E}/urn:ngsi-ld:Teste:P1/attrs", dict(sp=A5, status=204, body={"c": num(3)})),
        ("Só restou c", "GET", f"{E}/urn:ngsi-ld:Teste:P1?options=keyValues", dict(sp=A5, igual={"id": "urn:ngsi-ld:Teste:P1", "type": "Teste", "c": 3})),
        ("Remove a entidade de teste", "DELETE", f"{E}/urn:ngsi-ld:Teste:P1", dict(sp=A5, status=204)),
        ("Lote com uma entidade inexistente - 422 PartialUpdate", "POST", "/v2/op/update", dict(sp=A5, status=422, body={"actionType": "update", "entities": [
            {"id": K501, "type": "Room", "capacity": num(44)}, {"id": "urn:ngsi-ld:Room:NAOEXISTE", "type": "Room", "capacity": num(1)}]})),
        valor("Mas a parte válida foi gravada - 44", "capacity", 44, K501),
        ("Restaura a capacidade da K501", "PUT", f"{E}/{K501}/attrs/capacity/value", dict(sp=A5, status=204, body="40")),
    ]),
    ("C5 - Subscrições", "Seção 4. Subscrição por MQTT: assine pel220/# no MQTTX antes de começar (localhost:1883). Precisa do Mosquitto no ar (Etapa 2).", [
        ("Descrição com parênteses - 400", "POST", S, dict(sp=TUDO, status=400, body=dict(SUB_QUENTE, description="Sala quente (MQTT)"))),
        ("Formato legacy - 400", "POST", S, dict(sp=TUDO, status=400, body={"description": "Formato legado", "subject": {"entities": [{"id": K501, "type": "Room"}]},
            "notification": {"http": {"url": "http://cygnus:5050/notify"}, "attrsFormat": "legacy"}})),
        temp("Sala K501 a 25 graus", 25),
        ("Cria a subscrição sala quente", "POST", S, dict(sp=TUDO, status=201, body=SUB_QUENTE, js=[
            'pm.collectionVariables.set("subQuente", pm.response.headers.get("Location").split("/").pop());'])),
        ("Sem notificação inicial", "GET", S + "/{{subQuente}}", dict(sp=None, pre=ESPERA(2), js=[
            'pm.test("timesSent ausente", () => pm.expect(pm.response.json().notification).to.not.have.property("timesSent"));'])),
        temp("26 graus - mudou, mas não passa de 28", 26),
        temp("29 graus - notifica", 29),
        temp("29 graus de novo - não notifica", 29),
        ("Muda capacity com a sala quente - não notifica", "PATCH", f"{E}/{K501}/attrs", dict(sp=A5, status=204, body={"capacity": num(41)})),
        ("Lab K503 a 32 graus - não notifica", "PATCH", f"{E}/{K503}/attrs", dict(sp=A5, status=204, body={"temperature": num(32)})),
        temp("30 graus - notifica", 30),
        ("Duas notificações até aqui", "GET", S + "/{{subQuente}}", dict(sp=None, pre=ESPERA(2), js=[
            'pm.test("timesSent 2", () => pm.expect(pm.response.json().notification.timesSent).to.eql(2));'])),
        temp("30 graus com forcedUpdate - notifica", 30, "?options=forcedUpdate"),
        ("Três notificações", "GET", S + "/{{subQuente}}", dict(sp=None, pre=ESPERA(2), js=[
            'pm.test("timesSent 3", () => pm.expect(pm.response.json().notification.timesSent).to.eql(3));'])),
        ("Subscrição HTTP com localhost na URL", "POST", S, dict(sp=TUDO, status=201, body={"description": "URL com localhost",
            "subject": {"entities": [{"id": K501, "type": "Room"}], "condition": {"attrs": ["capacity"]}},
            "notification": {"http": {"url": "http://localhost:5050/notify"}, "attrsFormat": "keyValues"}}, js=[
            'pm.collectionVariables.set("subLocal", pm.response.headers.get("Location").split("/").pop());'])),
        ("Muda capacity - dispara a subscrição do localhost", "PATCH", f"{E}/{K501}/attrs", dict(sp=A5, status=204, body={"capacity": num(40)})),
        ("A falha aparece no status", "GET", S + "/{{subLocal}}", dict(sp=None, pre=ESPERA(4), js=[
            'const n = pm.response.json().notification;',
            'pm.test("failsCounter contou", () => pm.expect(n.failsCounter).to.be.at.least(1));',
            'pm.test("Motivo registrado", () => pm.expect(n.lastFailureReason).to.be.a("string"));',
            'pm.test("O status continua active", () => pm.expect(pm.response.json().status).to.eql("active"));'])),
        ("A listagem filtra pelo cabeçalho", "GET", S, dict(sp="/", js=[
            'pm.test("Nenhuma subscrição na raiz", () => pm.expect(pm.response.json()).to.eql([]));'])),
        ("DELETE com curinga - 400", "DELETE", S + "/{{subLocal}}", dict(sp=TUDO, status=400)),
        ("Volta as temperaturas", "POST", "/v2/op/update", dict(sp=A5, status=204, body={"actionType": "update", "entities": [
            {"id": K501, "type": "Room", "temperature": num(27.5)}, {"id": K503, "type": "Lab", "temperature": num(31)}]})),
    ]),
    ("C6 - Limpeza", "Remove tudo o que a coleção criou no tenant pel220. Não toca no tenant ccm130 da Base.", [
        ("Remove todas as subscrições do tenant pel220", "GET", S + "?limit=100", dict(sp=None, js=[
            'const subs = pm.response.json();',
            'subs.forEach(s => pm.sendRequest({url: pm.variables.replaceIn("http://{{orion}}/v2/subscriptions/") + s.id,',
            '  method: "DELETE", header: {"fiware-service": pm.variables.get("service")}}, () => {}));',
            'pm.test("Subscrições encontradas: " + subs.length, () => pm.expect(subs).to.be.an("array"));'],
            desc="Lista as subscrições do tenant (sem fiware-servicepath: todas) e remove uma a uma.")),
        ("Não sobrou subscrição", "GET", S, dict(sp=None, igual=[], pre=ESPERA(1))),
        ("Remove Room:K501", "DELETE", f"{E}/{K501}", dict(sp=A5, status=[204, 404])),
        ("Remove Room:K502", "DELETE", f"{E}/{K502}", dict(sp=A5, status=[204, 404])),
        ("Remove Lab:K503", "DELETE", f"{E}/{K503}", dict(sp=A5, status=[204, 404])),
        ("Remove Room:K401", "DELETE", f"{E}/{K401}", dict(sp=A4, status=[204, 404])),
        ("Remove Door:K5", "DELETE", f"{E}/{DOOR}", dict(sp=A5, status=[204, 404])),
        ("O tenant ficou vazio", "GET", E + "?options=keyValues&attrs=name", dict(sp=None, ids=[])),
    ]),
]


def codificar(caminho):
    """Codifica só o que o Postman não codifica sozinho na query."""
    if "?" not in caminho:
        return caminho
    base, query = caminho.split("?", 1)
    for a, b in (("#", "%23"), ("^", "%5E"), ("|", "%7C"), ("<", "%3C"), (">", "%3E"), ("$", "%24"), ("'", "%27")):
        query = query.replace(a, b)
    return base + "?" + query


def item(nome, metodo, caminho, o):
    hdr = []
    svc = o.get("svc", "{{service}}")
    if svc:
        hdr.append({"key": "fiware-service", "value": svc})
    if o.get("sp") is not None:
        hdr.append({"key": "fiware-servicepath", "value": o["sp"]})
    req = {"method": metodo, "header": hdr, "url": "http://{{orion}}" + codificar(caminho)}
    if o.get("desc"):
        req["description"] = o["desc"]
    body = o.get("body")
    if body is not None:
        if isinstance(body, str):
            hdr.append({"key": "Content-Type", "value": "text/plain"})
            req["body"] = {"mode": "raw", "raw": body}
        else:
            hdr.append({"key": "Content-Type", "value": "application/json"})
            req["body"] = {"mode": "raw", "raw": json.dumps(body, ensure_ascii=False, indent=2),
                           "options": {"raw": {"language": "json"}}}
    st = o.get("status", 200)
    tests = []
    if isinstance(st, list):
        tests.append(f'pm.test("Status {" ou ".join(map(str, st))}", () => pm.expect(pm.response.code).to.be.oneOf({st}));')
    else:
        tests.append(f'pm.test("Status {st}", () => pm.response.to.have.status({st}));')
    curto = 'pm.response.json().map(e => e.id.split(":").pop())'
    if o.get("ids") is not None:
        tests.append(f'pm.test("Entidades: {", ".join(o["ids"]) or "nenhuma"}", () => pm.expect({curto}.sort()).to.eql({json.dumps(sorted(o["ids"]))}));')
    if o.get("ordem") is not None:
        tests.append(f'pm.test("Nesta ordem: {", ".join(o["ordem"])}", () => pm.expect({curto}).to.eql({json.dumps(o["ordem"])}));')
    if "igual" in o:
        tests.append(f'pm.test("Resposta esperada", () => pm.expect(pm.response.json()).to.eql({json.dumps(o["igual"], ensure_ascii=False)}));')
    tests += o.get("js", [])
    ev = [{"listen": "test", "script": {"type": "text/javascript", "exec": tests}}]
    if o.get("pre"):
        ev.append({"listen": "prerequest", "script": {"type": "text/javascript", "exec": o["pre"]}})
    return {"name": nome, "request": req, "response": [], "event": ev}


def main():
    col = {"info": {"_postman_id": str(uuid.uuid5(uuid.NAMESPACE_URL, "pel220-aula07")),
                    "name": "PEL220 - Aula 07 - Orion avançado",
                    "description": "PEL 220 — Internet das Coisas e Gêmeos Digitais · Aula 7 — FIWARE II: Orion avançado e "
                                   "visualização no Grafana. Prof. Rafael Gomes Alves (FEI).\n\nPastas C1 a C6, no tenant pel220 "
                                   "(não interferem no tenant ccm130 da Base). Execute na ordem. As Etapas 5 a 7 da plataforma "
                                   "ficam na coleção da Base.",
                    "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"},
           "variable": [{"key": "orion", "value": "localhost:1026"}, {"key": "service", "value": "pel220"},
                        {"key": "subQuente", "value": ""}, {"key": "subLocal", "value": ""}, {"key": "expira", "value": ""}],
           "item": [{"name": n, "description": d, "item": [item(*r) for r in reqs]} for n, d, reqs in PASTAS]}
    destino = os.path.join(AQUI, "..", "PEL220 - Aula 07 - Orion avançado.postman_collection.json")
    with open(destino, "w", encoding="utf-8") as f:
        json.dump(col, f, ensure_ascii=False, indent=1)
    print(sum(len(r) for _, _, r in PASTAS), "requisições em", len(PASTAS), "pastas ->", os.path.normpath(destino))


if __name__ == "__main__":
    main()
