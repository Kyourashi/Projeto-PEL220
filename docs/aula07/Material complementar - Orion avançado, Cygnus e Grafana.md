# Material complementar — Orion avançado, Cygnus e Grafana

**PEL 220 — Internet das Coisas e Gêmeos Digitais · Aula 7 — FIWARE II: Orion avançado e visualização no Grafana**
Centro Universitário FEI · Prof. Rafael Gomes Alves

> **O que é.** A referência da Aula 7, escrita para o caso da disciplina (sala K501, ESP32 com DHT22 e relé,
> tenant `ccm130`) e para o laboratório da aula (prédio K, tenant `pel220`): as **funcionalidades avançadas do
> Orion** — tenants e caminhos, atributos embutidos, linguagem de consulta, verbos e operadores de atualização,
> registros e subscrições —, o **histórico com o Cygnus e o MySQL**, o **Grafana** passo a passo e o **catálogo
> dos testes** da coleção da aula. O roteiro continua no `README.md`; este material é para consultar durante a
> prática, revisar depois e reutilizar no projeto.

> **Tudo aqui foi executado.** Orion 4.1.0, IoT Agent JSON 3.7.0, Cygnus 3.11.0, MySQL 8.0 e Grafana 10.4.0, no
> Windows 11 com Docker Engine 29.6.2 e Postman CLI 1.75, em 16/11/2026, e de novo a partir deste pacote, com
> volumes vazios, em 18/11/2026. As respostas são reais; identificadores, horários, temperaturas e o clima mudam
> de uma máquina e de um dia para outro.

## Sumário

1. [A plataforma da Aula 7](#1-a-plataforma-da-aula-7) — os serviços novos (Etapas 5 a 7) e seus blocos no Compose
2. [Organizar o contexto](#2-organizar-o-contexto) — tenants, `fiware-servicepath`, embutidos, expiração, caracteres proibidos
3. [Consultar](#3-consultar) — a linguagem `q` e `mq`, ordenação, paginação, formatos, geografia, `op/query`
4. [Atualizar](#4-atualizar) — verbos, metadados, lote, operadores atômicos
5. [Registros: o Orion busca](#5-registros-o-orion-busca) — o provedor de clima
6. [Subscrições: o Orion avisa](#6-subscrições-o-orion-avisa) — campos, comportamentos, status, MQTT, armadilhas
7. [O histórico: Cygnus e MySQL](#7-o-histórico-cygnus-e-mysql)
8. [O Grafana passo a passo](#8-o-grafana-passo-a-passo) — fonte de dados, consultas, macros, visualizações
9. [Os testes da aula](#9-os-testes-da-aula) — as coleções, como rodar, catálogo requisição a requisição
10. [Cola de comandos (PowerShell)](#10-cola-de-comandos-powershell)
11. [Diagnóstico: do sintoma à causa](#11-diagnóstico-do-sintoma-à-causa)
12. [Glossário](#12-glossário)
13. [Referências](#13-referências)
- [Apêndice A — O provedor de clima, comentado](#apêndice-a--o-provedor-de-clima-comentado)

---

## 1. A plataforma da Aula 7

A plataforma é a mesma da Aula 6 (`fiware/`, em `C:\pel220\fiware`). Hoje sobem as Etapas 5, 6 e 7:

| Etapa | Serviço (contêiner) | Imagem | Porta no Windows | Nome na rede Docker | Papel |
|---|---|---|---|---|---|
| 5 | `clima-externo` | construída de `clima/` (python:3.12-slim) | 3010 | `clima-externo:3010` | provedor de contexto: clima do campus pela Open-Meteo |
| 6 | `cygnus` (`fiware-cygnus`) | quay.io/fiware/cygnus-ngsi:3.11.0 | 5050, 5080 | `cygnus:5050` | recebe as notificações do Orion e grava no MySQL |
| 6 | `mysql-db` (`db-mysql`) | mysql:8.0 | 3306 | `mysql-db:3306` | o banco do histórico (um banco por `fiware-service`) |
| 7 | `grafana` | grafana/grafana:10.4.0 | 3000 | `grafana:3000` | painéis sobre o MySQL |
| — | `grafana-pronto` (perfil `pronto`) | grafana/grafana:10.4.0 | 3001 | — | painel já configurado, para comparar |

**A regra de endereços** (Aula 5) aparece três vezes hoje: o Orion notifica `http://cygnus:5050/notify`; o
Cygnus grava em `mysql-db:3306`; o Grafana lê de `mysql-db:3306`. Só você, do Windows, usa `localhost`
(`localhost:3000` para o Grafana, `localhost:3306` para um cliente MySQL). `localhost` dentro de um contêiner é
o próprio contêiner.

### 1.1 Os blocos do Compose das Etapas 5 a 7

```yaml
  clima-externo:
    build: ./clima
    image: ccm130/clima-externo
    hostname: clima-externo
    container_name: clima-externo
    ports:
      - "3010:3010"
    environment:
      - PORTA=3010
      - LATITUDE=-23.7245
      - LONGITUDE=-46.5793
      - CACHE=60
      - MODO=api # "simulado" para não depender da internet

  cygnus:
    image: quay.io/fiware/cygnus-ngsi:3.11.0
    hostname: cygnus
    container_name: fiware-cygnus
    depends_on:
      mysql-db:
        condition: service_healthy
    ports:
      - "5050:5050" # notificações do Orion
      - "5080:5080" # API de gerenciamento (GET /v1/version)
    environment:
      - CYGNUS_MYSQL_SERVICE_PORT=5050
      - CYGNUS_MYSQL_HOST=mysql-db
      - CYGNUS_MYSQL_PORT=3306
      - CYGNUS_MYSQL_USER=root
      - CYGNUS_MYSQL_PASS=123
      - CYGNUS_SERVICE_PORT=5050
      - CYGNUS_API_PORT=5080
      - CYGNUS_LOG_LEVEL=DEBUG
    healthcheck:
      test: curl --fail -s http://localhost:5080/v1/version || exit 1
      interval: 10s

  mysql-db:
    image: mysql:8.0
    hostname: mysql-db
    container_name: db-mysql
    ports:
      - "3306:3306"
    environment:
      - MYSQL_ROOT_PASSWORD=123
      - MYSQL_ROOT_HOST=%
    volumes:
      - mysql-db:/var/lib/mysql
    healthcheck:
      test: ["CMD", "mysqladmin", "ping", "-h", "localhost", "-u", "root", "-p123"]
      interval: 5s
      timeout: 5s
      retries: 10

  grafana:
    image: grafana/grafana:10.4.0
    hostname: grafana
    container_name: grafana
    depends_on:
      mysql-db:
        condition: service_healthy
    ports:
      - "3000:3000"
    volumes:
      - grafana-data:/var/lib/grafana
```

| Bloco | O que observar |
|---|---|
| `clima-externo` | `MODO=simulado` força valores simulados; `CACHE=60` evita consultar a API a cada leitura do Orion |
| `cygnus` | sobe só depois de o MySQL ficar saudável; o *healthcheck* usa `localhost` porque roda **dentro** do contêiner do Cygnus |
| `mysql-db` | `MYSQL_ROOT_HOST=%` permite o root vindo de outros contêineres (o Cygnus e o Grafana); senha de laboratório |
| `grafana` | sem configuração: fonte de dados e painéis você cria pela interface; tudo fica no volume `grafana-data` |

### 1.2 Tempos e memória medidos

| Comando | Tempo (imagens já baixadas) |
|---|---|
| `docker compose up -d --wait orion` | ≈ 13 s |
| `docker compose up -d --wait iot-agent` | ≈ 8 s |
| `docker compose up -d --build clima-externo` | ≈ 2 s (com cache do build) |
| `docker compose up -d --wait cygnus` | ≈ 28 s (inclui o MySQL) |
| `docker compose up -d grafana` | ≈ 2 s |

Com as Etapas 1 a 7 no ar, `docker stats` somou **≈ 1,1 GiB**: MySQL 455 MiB, Cygnus 268, MongoDB 188, IoT Agent
112, Grafana 64, Orion 23, clima 17, ESP32 15, Mosquitto 3. Na Aula 6, com as Etapas 1 a 4, eram ≈ 192 MiB:
guardar e mostrar o passado custa muito mais memória do que manter o presente.

---

## 2. Organizar o contexto

### 2.1 Tenant: um banco por `fiware-service`

Cada valor de `fiware-service` é um **tenant** (inquilino) e vira um banco próprio no MongoDB, `orion-<nome>`.
Sem o cabeçalho, a requisição vai ao **tenant padrão** (banco `orion`). O IoT Agent guarda grupos e dispositivos
no banco `iotagentjson`.

```powershell
docker exec db-mongo mongosh --quiet --eval "db.getMongo().getDBNames()"
# [ 'admin', 'config', 'iotagentjson', 'local', 'orion-ccm130', 'orion-pel220' ]
```

| Fato (medido) | Consequência |
|---|---|
| Nenhuma consulta atravessa tenants | o mesmo `id` em dois tenants são duas entidades |
| O nome não diferencia maiúsculas | `PEL220` e `pel220` são o mesmo tenant |
| Tenant inexistente devolve `200 []` | erro de digitação no cabeçalho não dá erro: dá lista vazia |
| O Cygnus cria no MySQL um banco com o nome do tenant | o banco do histórico é `ccm130` |
| Tenant não é segurança | quem conhece o nome lê e grava os dados (Aula 10) |

**Regra de nomes:** até 50 caracteres, letras minúsculas, números e sublinhado (o Orion converte para
minúsculas).

### 2.2 `fiware-servicepath`: uma hierarquia dentro do tenant

O caminho organiza as entidades de um tenant em ramos, como pastas: `/predioK/andar5`. No MongoDB ele faz parte
da chave da entidade (`_id: {id, type, servicePath}`), por isso o mesmo `id` pode existir em dois caminhos.

O laboratório da aula (tenant `pel220`):

```
/                      (raiz: criação sem o cabeçalho)
└── /predioK
    ├── /predioK/andar4      Room:K401
    └── /predioK/andar5      Room:K501  Room:K502  Lab:K503
```

| Situação | Cabeçalho | Resultado medido |
|---|---|---|
| Consulta no caminho exato | `/predioK` | `200 []` (não inclui os andares) |
| Consulta com subcaminhos | `/predioK/#` | as 4 entidades |
| Consulta em lista (até 10 caminhos) | `/predioK/andar4,/predioK/andar5` | as 4 entidades |
| Consulta sem o cabeçalho | (nenhum) = `/#` | as 4 entidades |
| Consulta na raiz | `/` | `200 []` |
| Criação sem o cabeçalho | (nenhum) = `/` | `201`, entidade na raiz |
| `PATCH` sem o cabeçalho | (nenhum) = `/` | `404`: a sala está em `/predioK/andar5` |
| Curinga ao criar, atualizar ou apagar | `/predioK/#` | `400 … wildcard # is not allowed` |
| Lista ao criar | `/a,/b` | `400 more than one service path in context update request` |
| Mesmo `id` em dois caminhos | `/predioK/andar4` e `…/andar5` | `201`; depois, `GET` por id que enxergue os dois: `409 TooManyResults` |
| Caminho sem barra inicial | `predioK` | `400 Only /absolute/ Service Paths allowed` |
| 11 caminhos na lista | `/p0,…,/p10` | **HTTP 200** com corpo `orionError … maximum of ten service paths` |
| 11 níveis | `/a/b/…/k` | `400 too many components in ServicePath` |
| Nível com mais de 50 caracteres | `/aaaa…` | `400 component-name too long in ServicePath` |

> **A assimetria que derruba.** Ler sem o cabeçalho enxerga o tenant inteiro; gravar sem o cabeçalho só enxerga
> a raiz. Na Base (tenant `ccm130`), tudo está em `/`, por isso a coleção da Base manda sempre
> `fiware-servicepath: /`.

O caminho também vale para **subscrições e registros**: uma subscrição criada com `/predioK` não recebe as
mudanças de `/predioK/andar5`; a criada com `/predioK/#`, recebe (seção 6.5).

### 2.3 Atributos embutidos

| Embutido | Quem escreve | Significado |
|---|---|---|
| `dateCreated` | Orion | criação da entidade (ISO 8601) |
| `dateModified` | Orion | última modificação |
| `dateExpires` | cliente | quando a entidade será removida |

Ficam **ocultos**: só vêm quando pedidos pelo nome em `attrs` (o `*` pede também os demais atributos).

```http
GET /v2/entities/urn:ngsi-ld:Room:K502?options=keyValues&attrs=dateCreated,dateModified,*
fiware-service: pel220
fiware-servicepath: /predioK/andar5
```

```json
{ "id": "urn:ngsi-ld:Room:K502", "type": "Room", "capacity": 30, "color": "yellow", "floor": 5,
  "name": "Sala K5-02", "temperature": 22,
  "dateCreated": "2026-11-16T11:11:41.574Z", "dateModified": "2026-11-16T11:11:41.574Z" }
```

Por atributo, as mesmas datas existem como **metadados**, pedidos em `metadata`:

```http
GET /v2/entities/urn:ngsi-ld:Room:K502?attrs=temperature&metadata=dateCreated,dateModified,*
```

```json
"temperature": { "type": "Number", "value": 22, "metadata": {
  "accuracy": {"type": "Number", "value": 2}, "unitCode": {"type": "Text", "value": "CEL"},
  "dateCreated": {"type": "DateTime", "value": "2026-11-16T11:11:41.574Z"},
  "dateModified": {"type": "DateTime", "value": "2026-11-16T11:11:41.574Z"} } }
```

Servem para ordenar (`orderBy=!dateModified`) e filtrar (`q=dateModified>2026-01-01T00:00:00Z`).

**Armadilha conferida:** o Orion aceita um atributo comum chamado `dateCreated` (`"type": "Text"`) — e ele esconde
o embutido na resposta.

### 2.4 Entidades que expiram: `dateExpires`

```json
{ "id": "urn:ngsi-ld:Alert:001", "type": "Alert",
  "dateExpires": { "type": "DateTime", "value": "2026-11-16T11:12:31Z" } }
```

| Medida | Resultado |
|---|---|
| Prazo de 20 s | a entidade sumiu **33,8 s** depois de criada |
| Prazo de 5 s (segunda medição) | sumiu 30,4 s depois de criada |
| Notificação de `entityDelete` na expiração | **não houve** (uma remoção pela API, sim) |

O MongoDB remove pelo índice TTL, que roda a cada **60 s**: a entidade some entre 0 e ~60 s depois do prazo.
Bom para alertas, reservas e sessões; inadequado para o que precisa de precisão no tempo, ou de aviso quando some.

### 2.5 Caracteres proibidos: `< > " ' = ; ( )`

O Orion recusa esses oito caracteres em identificadores, nomes de atributos, descrições e valores de texto
(proteção contra injeção). Medido:

| Onde | Exemplo | Resposta |
|---|---|---|
| Valor de atributo | `"Sala quente (HTTP)"`, `"a=b"`, `"x;y"`, `"<b>"`, `"diz 'oi'"` | `400 Invalid characters in attribute value` |
| Descrição de subscrição ou registro | `"Clima externo do campus (Open-Meteo)"` | `400 forbidden characters in description` |
| Identificador | `"urn:ngsi-ld:Room:K 9"`, `"urn:ngsi-ld:Room:K(9)"` | `400 Invalid characters in entity id` |
| Valor com `: % - / + [ ] { } @ # & ?` | `"ok: 100% - sala/5 + [x] {y} @ # & ?"` | `204`: aceito |
| Valor com `"type": "TextUnrestricted"` | `"Sala quente (HTTP); a=b"` | `204`: aceito, sem verificação |

`TextUnrestricted` desliga a verificação daquele atributo: a responsabilidade de sanitizar passa a ser de quem
exibe o valor. Na Aula 6, o mesmo filtro deixou um comando `PENDING`: a resposta `"OK: red=200"` foi recusada
pelo Orion. A exceção é a consulta `q`, que tem sintaxe própria (seção 3).

---

## 3. Consultar

### 3.1 Os dados do laboratório

Todas as consultas desta seção: `fiware-service: pel220`, `fiware-servicepath: /predioK/#`.

| id | type | floor | capacity | color | temperature (accuracy) | outros |
|---|---|---|---|---|---|---|
| K501 | Room | 5 | 40 | blue | 27,5 (0,5) | `tags` [lab, iot], `location` |
| K502 | Room | 5 | 30 | yellow | 22 (2) | |
| K401 | Room | 4 | 60 | black | — | |
| K503 | Lab | 5 | 25 | — | 31 (0,5) | |

`location` da K501: `{"type": "geo:json", "value": {"type": "Point", "coordinates": [-46.5793, -23.7245]}}`.

### 3.2 A linguagem de consulta simples

Uma condição tem três formas: **binária** (`atributo` `operador` `valor`), **unária** (`atributo` = tem;
`!atributo` = não tem) e **combinação** com `;` (E lógico). `mq` aplica a mesma sintaxe aos metadados
(`atributo.metadado`).

| Operador | Exemplo | Resultado medido |
|---|---|---|
| `==` igualdade | `q=floor==5` | K501, K502, K503 |
| `;` E lógico | `q=floor==5;capacity>=30` | K501, K502 |
| `..` intervalo inclusivo | `q=capacity==25..40` | K501, K502, K503 |
| `,` lista: OU entre valores | `q=color==blue,black` | K501, K401 |
| `!=` diferente de todos | `q=color!=blue,black` | só K502 |
| `>` `<` `>=` `<=` | `q=temperature>25` | K501, K503 |
| `~=` expressão regular | `q=name~=^Lab` | K501, K503 |
| unária: tem | `q=temperature` | K501, K502, K503 |
| unária: não tem | `q=!temperature` | K401 |
| valor dentro de uma lista | `q=tags==iot` | K501 |
| subatributo (objeto) | `q=address.addressLocality=='Kreuzberg'` | (Aula 6, lojas) |
| embutido | `q=dateModified>2026-01-01T00:00:00Z` | as quatro |
| metadado | `mq=temperature.accuracy<1` | K501, K503 |
| metadado | `mq=temperature.unitCode==CEL` | K501, K502, K503 |
| `:` como igualdade | `q=floor:5` | K501, K502, K503 |

### 3.3 Seis sutilezas, todas medidas

| # | Sutileza | Evidência |
|---|---|---|
| 1 | `!=` só considera quem **tem** o atributo | K503 (sem `color`) não aparece em `color!=blue,black` |
| 2 | `~=` diferencia maiúsculas | `name~=lab` → `[]`; `name~=(?i)lab` → `400` (parênteses são proibidos) |
| 3 | Aspas simples forçam texto | `floor=='5'` → `[]`, porque `floor` é número |
| 4 | Não há OU entre condições diferentes | `capacity>30\|floor==4` → `400`; faça duas consultas |
| 5 | Sem `type`, a consulta vale para todos os tipos | `temperature>25` traz a Room K501 e o Lab K503; com `type=Room`, só a K501 |
| 6 | `coords` é **latitude,longitude** (o GeoJSON guarda longitude, latitude) | com a ordem trocada, `[]`, sem erro |

### 3.4 Parâmetros complementares

| Parâmetro | Exemplo | Resultado medido |
|---|---|---|
| `type` (aceita lista) | `type=Room,Lab` | as quatro |
| `typePattern` | `typePattern=^L` | K503 |
| `idPattern` | `idPattern=K50[12]$` | K501, K502 |
| `attrs` | `attrs=name,capacity` | só esses atributos |
| `orderBy` (`!` = decrescente) | `orderBy=floor,!capacity` | K401, K501, K502, K503 |
| `limit`, `offset` | `limit=2&offset=1&orderBy=capacity` | K502, K501 |
| `options=count` | (com qualquer consulta) | total no cabeçalho `Fiware-Total-Count` (4) |
| `options=keyValues` | | `{"id":…, "name": "Sala K5-02"}` |
| `options=values` | `type=Room&attrs=name,capacity&options=values&orderBy=!capacity` | `[["Sala K4-01", 60], ["Laboratório K5-01", 40], ["Sala K5-02", 30]]` |
| `options=unique` | `attrs=color&options=unique` | `[["blue"], ["yellow"], ["black"], []]` |
| `georel`, `geometry`, `coords` | `georel=near;maxDistance:1000&geometry=point&coords=-23.7245,-46.5793` | K501 |

**Limites:** 20 entidades por resposta, se `limit` não for informado; no máximo 1000 (`limit=1001` →
`400 Bad pagination limit: /1001/ [max: 1000]`). Esquecer a paginação é o erro clássico com muitas entidades: a
21ª simplesmente não aparece.

### 3.5 A consulta no corpo: `POST /v2/op/query`

Faz o mesmo que o `GET`, com a consulta num JSON (útil quando a URL fica longa ou tem caracteres difíceis):

```http
POST /v2/op/query?options=keyValues
Content-Type: application/json
fiware-service: pel220
fiware-servicepath: /predioK/#

{ "entities": [{"idPattern": ".*", "type": "Room"}],
  "attrs": ["name", "capacity"],
  "expression": {"q": "capacity>=40"} }
```

```json
[ {"id": "urn:ngsi-ld:Room:K501", "type": "Room", "name": "Laboratório K5-01", "capacity": 40},
  {"id": "urn:ngsi-ld:Room:K401", "type": "Room", "name": "Sala K4-01", "capacity": 60} ]
```

### 3.6 Uma leitura de atributo ou de valor

```http
GET /v2/entities/urn:ngsi-ld:Room:K501/attrs/temperature         → {"type":"Number","value":27.5,"metadata":{…}}
GET /v2/entities/urn:ngsi-ld:Room:K501/attrs/temperature/value   → 27.5
```

---

## 4. Atualizar

### 4.1 Cada verbo, o que faz e o que preserva

| Requisição | O que faz | Medido |
|---|---|---|
| `PATCH …/{id}/attrs` | atualiza atributos que existem | atributo novo: `422`; **metadados não enviados são preservados** |
| `PATCH …/attrs?options=overrideMetadata` | atualiza e substitui os metadados | `metadata: {}` depois de um PATCH sem metadados |
| `PATCH …/attrs?options=forcedUpdate` | atualiza e dispara as subscrições mesmo sem mudança | seção 6.3 |
| `POST …/{id}/attrs` | cria ou atualiza atributos | `204` |
| `POST …/attrs?options=append` | só cria | atributo existente: `422` |
| `PUT …/{id}/attrs` | substitui **todos** os atributos | `{a, b}` virou só `{c}` |
| `PUT …/attrs/{a}/value` | troca só o valor (`Content-Type: text/plain`) | `30` → número; `"30"` → texto |
| `POST /v2/entities?options=upsert` | cria a entidade ou atualiza | `204`; os outros atributos ficam |
| `POST /v2/op/update` | lote: `append`, `appendStrict`, `update`, `replace`, `delete` | ver 4.2 |
| `DELETE …/attrs/{a}` · `DELETE …/{id}` | remove atributo · entidade | `204` |

### 4.2 O lote não é uma transação

```json
POST /v2/op/update
{ "actionType": "update", "entities": [
  {"id": "urn:ngsi-ld:Room:K501", "type": "Room", "capacity": {"type": "Number", "value": 44}},
  {"id": "urn:ngsi-ld:Room:NAOEXISTE", "type": "Room", "capacity": {"type": "Number", "value": 1}} ] }
```

Resposta: `422 PartialUpdate … do not exist: urn:ngsi-ld:Room:NAOEXISTE/Room - [entity itself]`. E a capacidade
da K501 **foi gravada** (44). Não há transação: a parte válida é aplicada.

### 4.3 O problema da atualização concorrente

Duas portas contam visitantes no mesmo atributo `count`. Se cada uma **lê, soma 1 e grava**, as duas podem ler
10 antes de qualquer uma gravar; as duas gravam 11 e uma visita se perde.

```
Porta A: GET count → 10                       Porta B: GET count → 10
Porta A: PUT count = 11                       Porta B: PUT count = 11     → contador 11, eram 12
```

Medido com `ferramentas/concorrencia.py` (dois processos, 200 visitas cada):

| Estratégia | Esperado | Contador | Perdidas | Tempo |
|---|---|---|---|---|
| ler-somar-gravar | 400 | 224 · 235 | **176 · 165** | 7,4 s · 5,8 s |
| `{"$inc": 1}` | 400 | 400 · 400 | **0** | 4,0 s · 4,0 s |

Com o operador, a soma é feita dentro do MongoDB, uma de cada vez, numa única requisição.

### 4.4 Os dez operadores atômicos

O operador vai **no lugar do `value`**, num `PATCH …/attrs` comum:

```json
{ "count": { "type": "Number", "value": { "$inc": 1 } } }
```

| Operador | Para quê | Antes | Depois (medido) |
|---|---|---|---|
| `{"$inc": 1}` · `{"$inc": -3}` | somar (ou subtrair) | 10 | 11 · 8 |
| `{"$mul": 2}` | multiplicar | 8 | 16 |
| `{"$max": 7}` · `{"$max": 15}` | guardar o maior | 10 | 10 · 15 |
| `{"$min": 12}` · `{"$min": 4}` | guardar o menor | 10 | 10 · 4 |
| `{"$push": "b"}` (duas vezes) | acrescentar à lista | `[a]` | `[a, b]` · `[a, b, b]` |
| `{"$addToSet": "b"}` · `{"$addToSet": "c"}` | acrescentar sem repetir | `[a, b, b]` | `[a, b, b]` · `[a, b, b, c]` |
| `{"$pull": "b"}` | remover todas as ocorrências | `[a, b, b, c]` | `[a, c]` |
| `{"$pullAll": ["a", "c"]}` | remover vários | `[a, c]` | `[]` |
| `{"$set": {"z": 3, "x": 9}}` | acrescentar ou alterar chaves | `{x: 1, y: 2}` | `{x: 9, y: 2, z: 3}` |
| `{"$unset": {"y": 1}}` | remover chaves | `{x: 9, y: 2, z: 3}` | `{x: 9, z: 3}` |

`$max` e `$min` registram extremos sem histórico (o pico de temperatura do dia); `$addToSet` monta listas sem
repetir; `$set` e `$unset` alteram partes de um objeto sem reenviá-lo inteiro.

### 4.5 O que os operadores não fazem

| Limite | Medido |
|---|---|
| O `PATCH` não cria | `$inc` em atributo inexistente: `422`. Com `POST …/attrs`, o atributo nasce com o valor do incremento (5); numa criação de entidade, `{"$inc": 1}` virou 1 |
| Um operador por valor | `{"$inc": 1, "$mul": 2}` sobre 16 deu **17**: o segundo foi ignorado, sem erro |
| Argumento de tipo errado | `{"$inc": "1"}` devolve **500**, com a mensagem do MongoDB no corpo (`Cannot increment with non-numeric argument`) |
| `$addToSet` não limpa o passado | numa lista `[a, b, b]`, acrescentar `b` mantém as duas cópias |
| Atômico não é transacional | vale para um atributo; dois atributos, duas entidades ou um lote continuam sem transação |

---

## 5. Registros: o Orion busca

Um **registro** diz ao Orion: *os atributos X da entidade Y não estão no meu banco — pergunte ao provedor P*. A
cada leitura, o Orion faz `POST <url>/op/query`, junta a resposta com o que tem no banco e devolve uma resposta
única. É o mesmo mecanismo dos comandos do IoT Agent (Aula 6).

### 5.1 O provedor de clima (Etapa 5)

```http
POST /v2/registrations
Content-Type: application/json
fiware-service: ccm130
fiware-servicepath: /

{ "description": "Clima atual do campus pela Open-Meteo",
  "dataProvided": {
    "entities": [{"id": "urn:ngsi-ld:WeatherObserved:FEI", "type": "WeatherObserved"}],
    "attrs": ["temperature", "relativeHumidity", "windSpeed", "dateObserved", "source"] },
  "provider": {"http": {"url": "http://clima-externo:3010/v2"}} }
```

→ `201 Created`, cabeçalho `Location: /v2/registrations/<id>`.

| Campo | Significado |
|---|---|
| `dataProvided.entities` | quais entidades (por `id` ou `idPattern`, e `type`) |
| `dataProvided.attrs` | quais atributos moram no provedor |
| `provider.http.url` | onde perguntar; o Orion acrescenta `/op/query` (nome do contêiner, não `localhost`) |
| `description` | texto livre — **sem** os caracteres proibidos |

Lendo pelo Orion:

```http
GET /v2/entities/urn:ngsi-ld:WeatherObserved:FEI?type=WeatherObserved&options=keyValues
```

```json
{ "id": "urn:ngsi-ld:WeatherObserved:FEI", "type": "WeatherObserved", "temperature": 19.4,
  "relativeHumidity": 0.91, "windSpeed": 2.6, "source": "open-meteo",
  "dateObserved": "2026-11-16T11:15:00.000Z" }
```

```powershell
docker logs clima-externo
# [clima] Orion perguntou: ['temperature', 'relativeHumidity', 'windSpeed', 'source', 'dateObserved']
#         de ['urn:ngsi-ld:WeatherObserved:FEI']
```

| O que o laboratório mostra (medido) | |
|---|---|
| Leitura pelo Orion | 22 a 33 ms (o provedor guarda a resposta da API por 60 s) |
| No MongoDB (`orion-ccm130`) | só `Room:K501` e `ClimateStation:ESP32001`: o clima **não** é guardado |
| `GET /v2/entities?type=WeatherObserved` | devolve o clima: o Orion repassa a consulta ao provedor |
| `q=temperature>0` sem `type` | traz a ESP32 **e** o clima |
| Subscrição sobre o clima | `timesSent` ausente depois de várias leituras: o Orion não vê mudança no que não guarda |

> **Presente, não histórico.** Para o clima entrar no histórico, alguém precisaria gravá-lo **no Orion**
> periodicamente (um coletor fazendo `upsert`); aí a subscrição do Cygnus o levaria ao MySQL.

### 5.2 Ler e remover registros

```http
GET    /v2/registrations          (com os cabeçalhos do tenant)
DELETE /v2/registrations/<id>
```

Na Base há dois: o do IoT Agent (`on` e `off` da ESP32, provedor `http://iot-agent-json:4041`) e o do clima.
**Nunca apague à mão o registro do IoT Agent**: os comandos param de funcionar.

---

## 6. Subscrições: o Orion avisa

Uma **subscrição** pede ao Orion: *quando estas entidades mudarem desta forma, avise este endereço*. É o
mecanismo do Cygnus (histórico, Etapa 6) e do controlador (Aula 9).

### 6.1 Anatomia

```http
POST /v2/subscriptions
Content-Type: application/json
fiware-service: pel220
fiware-servicepath: /predioK/#

{ "description": "Sala quente via MQTT",
  "subject": {
    "entities": [{"idPattern": ".*", "type": "Room"}],
    "condition": {
      "attrs": ["temperature"],
      "expression": {"q": "temperature>28"} } },
  "notification": {
    "mqtt": {"url": "mqtt://mosquitto:1883", "topic": "pel220/quente"},
    "attrs": ["temperature", "name"],
    "attrsFormat": "keyValues" },
  "throttling": 5 }
```

→ `201 Created`, `Location: /v2/subscriptions/<id>`.

| Campo | Responde a | Valores |
|---|---|---|
| `subject.entities` | quais entidades observar | `id` ou `idPattern`, `type` ou `typePattern` |
| `subject.condition.attrs` | que atributo dispara | vazio = qualquer um |
| `subject.condition.expression` | em que situação avisar | `q`, `mq`, `georel`… sobre o estado **depois** da mudança |
| `subject.condition.alterationTypes` | que tipo de alteração | `entityChange` (padrão), `entityUpdate`, `entityCreate`, `entityDelete` |
| `notification.http` / `mqtt` | para onde enviar | `url`; no MQTT, `topic`, `qos` (padrão 0), `retain` (padrão false) |
| `notification.attrs` / `exceptAttrs` | o que enviar | lista de atributos; `alterationType` é um atributo especial |
| `notification.attrsFormat` | formato | `normalized`, `keyValues`, `values`, `simplifiedNormalized`, `simplifiedKeyValues` |
| `notification.metadata` | metadados extras | `previousValue`, `actionType`, os embutidos |
| `throttling` | intervalo mínimo entre notificações, em segundos | |
| `expires`, `status` | validade; `active` ou `inactive` | |

`"attrsFormat": "legacy"`, de tutoriais antigos, foi removido no Orion 4: `400 invalid attrsFormat, accepted
values: normalized, simplifiedNormalized, keyValues, simplifiedkeyValues, values`.

### 6.2 O que chega ao consumidor

Em `keyValues` (MQTTX assinando `pel220/#`):

```json
pel220/quente
{ "subscriptionId": "6afae5f1fcd1c6d58401ecc5",
  "data": [{ "id": "urn:ngsi-ld:Room:K501", "type": "Room",
             "temperature": 29, "name": "Laboratório K5-01" }] }
```

Com `"metadata": ["previousValue", "actionType"]`, em `normalized`:

```json
"temperature": { "type": "Number", "value": 27.5, "metadata": {
  "previousValue": { "type": "Number", "value": 30 },
  "actionType":    { "type": "Text",   "value": "update" } } }
```

Por HTTP, o mesmo corpo chega num `POST` ao endereço de `notification.http.url`; o consumidor deve responder
`2xx`.

### 6.3 Comportamentos medidos

Subscrição *Sala quente via MQTT* (Room, `condition.attrs: [temperature]`, `q: temperature>28`):

| Situação | Notifica? | Detalhe |
|---|---|---|
| Subscrição recém-criada, sala a 25 °C | não | não há notificação inicial |
| Subscrição criada com a sala **já** a 29 °C | não | mesmo assim, nenhuma notificação inicial |
| 25 → 26 °C | não | `expression.q` não satisfeita |
| 26 → 29 °C | **sim** | `{"temperature": 29, "name": …}` |
| 29 → 29 °C (mesmo valor) | não | o padrão (`entityChange`) exige mudança de valor |
| 29 → 29 °C com `?options=forcedUpdate` | **sim** | |
| `capacity` muda, sala a 29 °C | não | fora de `condition.attrs` |
| `Lab:K503` vai a 32 °C | não | `entities` pede `type: Room` |

Outras subscrições, medidas no mesmo laboratório:

| Configuração | O que aconteceu |
|---|---|
| `alterationTypes: [entityCreate, entityDelete]` | avisou a criação e a remoção (pela API) de um alerta; a alteração, não; a expiração por `dateExpires`, não |
| `alterationTypes: [entityUpdate]` | avisou **toda** gravação, mesmo sem mudança de valor |
| `metadata: [previousValue, actionType]` | o valor anterior veio junto (27,5, antes 30) |
| `throttling: 10` e quatro mudanças em 2,5 s | **uma** notificação; as outras três foram **descartadas**, não adiadas |

### 6.4 O status: o primeiro lugar onde olhar

```http
GET /v2/subscriptions/<id>
```

```json
"notification": { "timesSent": 18, "lastNotification": "2026-11-16T11:16:23.000Z",
  "lastSuccess": "2026-11-16T11:16:23.000Z", "lastSuccessCode": 200, … }
```

| Campo | O que diz |
|---|---|
| `timesSent` | tentativas de envio (ausente = nenhuma) |
| `lastSuccess`, `lastSuccessCode` | última entrega (o código só existe no HTTP) |
| `lastFailure`, `lastFailureReason` | última falha e o motivo |
| `failsCounter` | falhas seguidas; zera na primeira entrega que dá certo |

Os três motivos de falha medidos:

| Causa | `lastFailureReason` |
|---|---|
| URL com `localhost` (é o contêiner do Orion) | `Couldn't connect to server` |
| host que não existe (`http://naoexiste:8080`) | `Timeout was reached` |
| Cygnus parado (`docker stop fiware-cygnus`) | `Couldn't resolve host name` |

O `status` continua `active` mesmo falhando.

### 6.5 Três armadilhas

1. **`localhost` na URL.** Quem envia é o Orion, de dentro do contêiner. Use o nome do serviço: `cygnus:5050`,
   `mosquitto:1883`, `controlador:5001`.
2. **O caminho da subscrição.** Criada com `fiware-servicepath: /predioK`, não recebeu a mudança de uma sala de
   `/predioK/andar5`; criada com `/predioK/#`, recebeu. A **listagem** também filtra pelo cabeçalho: com
   `/predioK/#`, só as criadas com `/predioK/#`; sem cabeçalho, todas. `DELETE` com `#` dá `400`; sem
   cabeçalho, funciona.
3. **Não há fila.** Com o Cygnus parado por 23 s e a ESP32 publicando a cada 5 s, o Orion tentou, registrou
   `failsCounter: 3` e seguiu; quando o Cygnus voltou, nada foi reenviado. No fim, a subscrição marcava **152**
   notificações enviadas e o MySQL tinha **147** medidas: um buraco de 30 s no histórico. Garantia de entrega
   exige um broker com persistência entre o Orion e o consumidor (MQTT com QoS 1 e sessão persistente, Kafka).

Uma quarta, que separa *notificar* de *entregar*: numa notificação MQTT (QoS 0, sem `retain`), o Orion publica no
broker e conta um sucesso — mesmo que ninguém esteja assinando o tópico.

### 6.6 Registro × subscrição

| | Registro | Subscrição |
|---|---|---|
| Direção | o Orion **busca** (pull) | o Orion **avisa** (push) |
| Quando | a cada leitura de uma aplicação | a cada mudança que satisfaz a condição |
| Sistema externo | provedor de contexto | consumidor de contexto |
| Onde fica o dado | na fonte | no Orion; o consumidor recebe cópia |
| Na Base | comandos do IoT Agent; clima (Etapa 5) | Cygnus (Etapa 6); controlador (Aula 9) |
| Limite | o Orion não guarda nem notifica esses atributos | sem fila: consumidor fora do ar perde o aviso |

---

## 7. O histórico: Cygnus e MySQL

### 7.1 A subscrição do Cygnus (Etapa 6)

```json
POST /v2/subscriptions          (fiware-service: ccm130, fiware-servicepath: /)
{ "description": "Historico da ESP32 para o Cygnus",
  "subject": {
    "entities": [{"idPattern": ".*", "type": "ClimateStation"}],
    "condition": {"attrs": ["temperature", "humidity", "state"]} },
  "notification": {
    "http": {"url": "http://cygnus:5050/notify"},
    "attrs": ["temperature", "humidity", "state"],
    "attrsFormat": "normalized" },
  "throttling": 1 }
```

O Cygnus precisa do formato **`normalized`** (tipo e metadados de cada atributo). Uma medida a cada 5 s dá cerca
de 12 notificações por minuto: depois de um minuto e meio, `timesSent: 18`, `lastSuccessCode: 200`.

### 7.2 O esquema que o Cygnus cria

| Nível | Regra | Na Base |
|---|---|---|
| Banco | um por `fiware-service` | `ccm130` |
| Tabela | uma por entidade: `<id>_<type>`, com caracteres especiais trocados por `_` | `` `urn_ngsi-ld_ClimateStation_ESP32001_ClimateStation` `` |
| Linha | uma por **atributo** notificado | uma medida = 3 linhas (temperature, humidity, state) |
| Colunas | nove, **todas do tipo `text`** | abaixo |

| Coluna | Conteúdo | Exemplo |
|---|---|---|
| `recvTimeTs` | instante em que o Cygnus recebeu, em **milissegundos** desde 1970 | `1794827798294` |
| `recvTime` | o mesmo instante, legível (UTC) | `2026-11-16 11:16:38.294` |
| `fiwareServicePath` | o caminho | `/` |
| `entityId`, `entityType` | a entidade | `urn:ngsi-ld:ClimateStation:ESP32001`, `ClimateStation` |
| `attrName`, `attrType` | o atributo | `temperature`, `Number` |
| `attrValue` | o valor, **em texto** | `28.9` |
| `attrMd` | os metadados, em JSON | `[{"name":"TimeInstant","type":"DateTime","value":"2026-11-16T11:16:38.263Z"}]` |

```powershell
docker exec -it db-mysql mysql -uroot -p123
```

```sql
SHOW TABLES FROM ccm130;
SELECT recvTimeTs, recvTime, attrName, attrValue
  FROM ccm130.`urn_ngsi-ld_ClimateStation_ESP32001_ClimateStation`
  ORDER BY recvTimeTs DESC LIMIT 3;
-- 1794827798294  2026-11-16 11:16:38.294  state        OFF
-- 1794827798294  2026-11-16 11:16:38.294  humidity     61.9
-- 1794827798294  2026-11-16 11:16:38.294  temperature  28.9
```

| Medida | Valor |
|---|---|
| Linhas por hora, por dispositivo | 2.160 (3 atributos × 720 medidas) |
| Em 12 minutos de preparação | 441 linhas (147 medidas) |
| Atraso entre o `TimeInstant` do IoT Agent e o `recvTime` do Cygnus | dezenas de milissegundos (31 ms no exemplo) |

O esquema é simples e genérico, mas caro: tudo em texto obriga a converter em cada consulta, e "uma linha por
atributo" multiplica as linhas. As alternativas (TimescaleDB, QuantumLeap com CrateDB) são assunto da Aula 8.

---

## 8. O Grafana passo a passo

### 8.1 Entrar e criar a fonte de dados

1. `docker compose up -d grafana`; navegador em `http://localhost:3000`; `admin` / `admin`; **Skip** na troca de
   senha (se trocar, ajuste a variável `grafanaPass` da coleção da Base).
2. *Connections › Data sources › Add new data source*, filtre por `mysql`, escolha **MySQL**:

| Campo | Valor | Por quê |
|---|---|---|
| Host URL | `mysql-db:3306` | quem acessa o banco é o contêiner do Grafana |
| Database name | `ccm130` | o banco é o `fiware-service` |
| Username | `root` | do `docker-compose.yml` |
| Password | `123` | senha de laboratório |

3. **Save & test**, no fim da página: *Database Connection OK*. Com `localhost:3306`, o teste falha.

A própria tela do Grafana recomenda um usuário só com `SELECT`; em produção, crie-o (Aula 10).

### 8.2 As consultas, linha a linha

Editor **Code** (o *Builder* monta a consulta por menus e não converte o texto do Cygnus), *Format*
**Time series**. Painel 1, o modelo de todos:

```sql
SELECT
  recvTimeTs / 1000 AS "time",
  CAST(attrValue AS DECIMAL(6,1)) AS "temperatura"
FROM `urn_ngsi-ld_ClimateStation_ESP32001_ClimateStation`
WHERE attrName = 'temperature'
  AND $__unixEpochFilter(recvTimeTs / 1000)
ORDER BY recvTimeTs ASC
```

| Trecho | Para quê |
|---|---|
| `recvTimeTs / 1000 AS "time"` | o Grafana espera a coluna `time` em segundos; o Cygnus grava milissegundos |
| `CAST(attrValue AS DECIMAL(6,1))` | texto → número |
| `attrName = 'temperature'` | a tabela mistura os três atributos, uma linha cada |
| `$__unixEpochFilter(…)` | macro: vira `… BETWEEN início AND fim` com o período do painel; sem ela, a consulta varre a tabela inteira a cada atualização |
| `ORDER BY recvTimeTs ASC` | séries temporais em ordem crescente |

**Sem o `CAST`**, a API do Grafana devolve a coluna como `string` e o painel mostra *Data is missing a number
field*. (No cliente `mysql`, `AVG(attrValue)` funciona, porque o MySQL converte texto em número numa conta; é o
Grafana que exige o tipo certo na coluna.)

Todas as consultas estão em `fiware/queries.txt`:

| Painel | Visualização | Consulta |
|---|---|---|
| 1 — histórico | Time series | a de cima |
| 2 — presente | Stat | a mesma, sem `$__unixEpochFilter`, com `ORDER BY recvTimeTs DESC LIMIT 1` |
| 3 — relé | State timeline | `attrValue AS "relé"`, **sem** `CAST` (`ON`/`OFF`), `attrName = 'state'` |
| análise — média por minuto | Bar chart | `$__unixEpochGroupAlias(recvTimeTs / 1000, '1m')`, `AVG(CAST(…))`, `GROUP BY 1 ORDER BY 1` |

### 8.3 As macros do Grafana para MySQL

| Macro | Vira |
|---|---|
| `$__unixEpochFilter(col)` | `col >= <início> AND col <= <fim>` (em segundos) |
| `$__unixEpochGroupAlias(col, '1m')` | o tempo arredondado para janelas de 1 minuto, já com o nome `time` |
| `$__timeFilter(col)` | o mesmo filtro, para colunas `DATETIME` |
| `$__timeGroupAlias(col, '5m')` | o mesmo agrupamento, para colunas `DATETIME` |

O Cygnus grava o tempo como número (texto com milissegundos), por isso a disciplina usa as macros `unixEpoch`.

### 8.4 Ajustes de cada visualização

| Visualização | Ajuste |
|---|---|
| Time series | *Standard options › Unit › Celsius* |
| Stat | *Thresholds*: base azul, 24 verde, 28 vermelho (os limites do controlador da Aula 9) |
| State timeline | *Value mappings*: `ON` → Ligado (verde), `OFF` → Desligado (cinza) |
| Bar chart | troque `'1m'` por `'5m'`: janela maior, menos barras, curva mais lisa |

No painel: período *Last 15 minutes*, atualização *5s*; engrenagem › *General* › *Tags*: `aula10` (a etiqueta que
a pasta Etapa 7 da Base procura); título e **Save**.

### 8.5 Que visualização para que pergunta?

| Pergunta | Visualização | Cuidado |
|---|---|---|
| Como está agora? | Stat | limiares de cor com significado |
| Como evoluiu? | Time series | unidade explícita |
| Quando esteve em cada estado? | State timeline | mapear valores para rótulos |
| Qual o resumo por período? | Bar chart | janela coerente com a pergunta |

Um painel responde a uma pergunta de quem decide: a pergunta escolhe a visualização, e não o contrário.

### 8.6 O Grafana pronto

`docker compose up -d grafana-pronto` sobe um segundo Grafana em `http://localhost:3001`, com a fonte de dados e
um painel completo carregados por provisionamento (`fiware/grafana/`). Serve para comparar com o seu; não
substitui fazer o seu.

---

## 9. Os testes da aula

### 9.1 As duas coleções

| Coleção | Pastas usadas hoje | Tenant |
|---|---|---|
| `fiware/CCM130 - Aula 10 - Fluxo de dados completo.postman_collection.json` (Base) | Etapa 1 a 3 (reentrada), Etapa 4, Etapa 5, Etapa 6, Etapa 7 | `ccm130` |
| `PEL220 - Aula 07 - Orion avançado.postman_collection.json` (esta aula) | C1 a C6 | `pel220` |

### 9.2 Como executar

No aplicativo Postman, uma pasta por vez (**Run folder**), na ordem. Pelo Postman CLI:

```powershell
postman collection run "PEL220 - Aula 07 - Orion avançado.postman_collection.json"
postman collection run "fiware\CCM130 - Aula 10 - Fluxo de dados completo.postman_collection.json" -i "Etapa 6 - Histórico"
```

A coleção da aula foi gerada por `ferramentas/gerar_colecao.py`: para alterar uma requisição, edite a lista no
script e rode `python gerar_colecao.py`.

### 9.3 Resultados

| Execução | Requisições | Testes | Falhas |
|---|---|---|---|
| Coleção da aula, C1 a C6 (18/11/2026) | 128 | 190 | 0 |
| Base, Etapas 1 a 7, a partir deste pacote, volumes vazios (18/11/2026) | 31 | 61 | 0 |

### 9.4 Catálogo — coleção da Aula 7

Cada linha é uma requisição, na ordem em que roda. *Confere* lista o que os testes verificam além do código HTTP.

**C1 - Tenants e caminhos** — Seção 1. Cria as quatro entidades do laboratório no tenant pel220 e mostra o que cada fiware-servicepath enxerga.

| # | Requisição | Método e caminho | Cabeçalho `fiware-servicepath` | Espera | Confere |
|---|---|---|---|---|---|
| 1 | Cria Room:K501 no andar 5 | `POST /v2/entities` | `/predioK/andar5` | 201 |  |
| 2 | Cria Room:K502 no andar 5 | `POST /v2/entities` | `/predioK/andar5` | 201 |  |
| 3 | Cria Lab:K503 no andar 5 | `POST /v2/entities` | `/predioK/andar5` | 201 |  |
| 4 | Cria Room:K401 no andar 4 | `POST /v2/entities` | `/predioK/andar4` | 201 |  |
| 5 | Caminho exato - predioK não inclui os andares | `GET /v2/entities?options=keyValues&attrs=name` | `/predioK` | 200 | entidades: nenhuma |
| 6 | Com curinga - predioK e subcaminhos | `GET /v2/entities?options=keyValues&attrs=name` | `/predioK/#` | 200 | entidades: K501, K502, K503, K401 |
| 7 | Lista de caminhos | `GET /v2/entities?options=keyValues&attrs=name` | `/predioK/andar4,/predioK/andar5` | 200 | entidades: K501, K502, K503, K401 |
| 8 | Sem fiware-servicepath - equivale a barra cerquilha | `GET /v2/entities?options=keyValues&attrs=name` | (nenhum) | 200 | entidades: K501, K502, K503, K401 |
| 9 | Raiz - só o que está exatamente em barra | `GET /v2/entities?options=keyValues&attrs=name` | `/` | 200 | entidades: nenhuma |
| 10 | Tenant em maiúsculas - é o mesmo tenant | `GET /v2/entities?options=keyValues&attrs=name` | `/predioK/#` · tenant `PEL220` | 200 | entidades: K501, K502, K503, K401 |
| 11 | Tenant que não existe - lista vazia, sem erro | `GET /v2/entities?options=keyValues&attrs=name` | `/predioK/#` · tenant `naoexiste` | 200 | entidades: nenhuma |
| 12 | PATCH sem fiware-servicepath - 404 | `PATCH /v2/entities/urn:ngsi-ld:Room:K502/attrs` | (nenhum) | 404 |  |
| 13 | Criação com curinga - 400 | `POST /v2/entities` | `/predioK/#` | 400 |  |
| 14 | Caminho sem a barra inicial - 400 | `POST /v2/entities` | `predioK` | 400 |  |
| 15 | Mesmo id em outro caminho - 201 | `POST /v2/entities` | `/predioK/andar4` | 201 |  |
| 16 | GET por id com dois candidatos - 409 | `GET /v2/entities/urn:ngsi-ld:Room:K501?options=keyValues&attrs=name` | (nenhum) | 409 |  |
| 17 | Remove a homônima do andar 4 | `DELETE /v2/entities/urn:ngsi-ld:Room:K501` | `/predioK/andar4` | 204 |  |

**C2 - Embutidos, expiração e caracteres proibidos** — Seção 1. dateCreated, dateModified, dateExpires e os oito caracteres proibidos.

| # | Requisição | Método e caminho | Cabeçalho `fiware-servicepath` | Espera | Confere |
|---|---|---|---|---|---|
| 18 | Embutidos não vêm sem pedir | `GET /v2/entities/urn:ngsi-ld:Room:K502?options=keyValues` | `/predioK/andar5` | 200 | Sem dateCreated |
| 19 | Embutidos pedidos pelo nome | `GET /v2/entities/urn:ngsi-ld:Room:K502?options=keyValues&attrs=dateCrea…` | `/predioK/andar5` | 200 | Vieram dateCreated e dateModified |
| 20 | Datas de um atributo - são metadados | `GET /v2/entities/urn:ngsi-ld:Room:K502?attrs=temperature&metadata=dateC…` | `/predioK/andar5` | 200 | Metadados embutidos e de usuário |
| 21 | Alerta com prazo de 20 s | `POST /v2/entities` | `/predioK/andar5` | 201 |  |
| 22 | O alerta existe | `GET /v2/entities/urn:ngsi-ld:Alert:001?options=keyValues&attrs=dateExpires` | `/predioK/andar5` | 200 | Tem dateExpires |
| 23 | O alerta sumiu - espera 85 s | `GET /v2/entities/urn:ngsi-ld:Alert:001` | `/predioK/andar5` | 404 | espera antes de enviar |
| 24 | Valor com parênteses - 400 | `POST /v2/entities/urn:ngsi-ld:Room:K502/attrs` | `/predioK/andar5` | 400 |  |
| 25 | Valor com outros símbolos - aceito | `POST /v2/entities/urn:ngsi-ld:Room:K502/attrs` | `/predioK/andar5` | 204 |  |
| 26 | TextUnrestricted aceita os proibidos | `POST /v2/entities/urn:ngsi-ld:Room:K502/attrs` | `/predioK/andar5` | 204 |  |
| 27 | Remove o atributo obs | `DELETE /v2/entities/urn:ngsi-ld:Room:K502/attrs/obs` | `/predioK/andar5` | 204 |  |
| 28 | Id com espaço - 400 | `POST /v2/entities` | `/predioK/andar5` | 400 |  |

**C3 - Consultas** — Seção 2. A linguagem de consulta simples sobre as quatro entidades. Cabeçalho fiware-servicepath: /predioK/#.

| # | Requisição | Método e caminho | Cabeçalho `fiware-servicepath` | Espera | Confere |
|---|---|---|---|---|---|
| 29 | Igualdade | `GET /v2/entities?q=floor==5&options=keyValues&attrs=name` | `/predioK/#` | 200 | entidades: K501, K502, K503 |
| 30 | E lógico | `GET /v2/entities?q=floor==5;capacity>=30&options=keyValues&attrs=name` | `/predioK/#` | 200 | entidades: K501, K502 |
| 31 | Intervalo inclusivo | `GET /v2/entities?q=capacity==25..40&options=keyValues&attrs=name` | `/predioK/#` | 200 | entidades: K501, K502, K503 |
| 32 | Lista - OU entre valores | `GET /v2/entities?q=color==blue,black&options=keyValues&attrs=name` | `/predioK/#` | 200 | entidades: K501, K401 |
| 33 | Diferente de todos | `GET /v2/entities?q=color!=blue,black&options=keyValues&attrs=name` | `/predioK/#` | 200 | entidades: K502 |
| 34 | Comparação | `GET /v2/entities?q=temperature>25&options=keyValues&attrs=name` | `/predioK/#` | 200 | entidades: K501, K503 |
| 35 | Expressão regular | `GET /v2/entities?q=name~=^Lab&options=keyValues&attrs=name` | `/predioK/#` | 200 | entidades: K501, K503 |
| 36 | Expressão regular diferencia maiúsculas | `GET /v2/entities?q=name~=lab&options=keyValues&attrs=name` | `/predioK/#` | 200 | entidades: nenhuma |
| 37 | Unária - não tem o atributo | `GET /v2/entities?q=!temperature&options=keyValues&attrs=name` | `/predioK/#` | 200 | entidades: K401 |
| 38 | Unária - tem o atributo | `GET /v2/entities?q=temperature&options=keyValues&attrs=name` | `/predioK/#` | 200 | entidades: K501, K502, K503 |
| 39 | Valor dentro de uma lista | `GET /v2/entities?q=tags==iot&options=keyValues&attrs=name` | `/predioK/#` | 200 | entidades: K501 |
| 40 | Filtro sobre metadado | `GET /v2/entities?mq=temperature.accuracy<1&options=keyValues&attrs=name` | `/predioK/#` | 200 | entidades: K501, K503 |
| 41 | Aspas forçam texto | `GET /v2/entities?q=floor=='5'&options=keyValues&attrs=name` | `/predioK/#` | 200 | entidades: nenhuma |
| 42 | Não há OU entre condições - 400 | `GET /v2/entities?q=capacity>30\|floor==4&options=keyValues&attrs=name` | `/predioK/#` | 400 |  |
| 43 | Com type - só as salas | `GET /v2/entities?type=Room&q=temperature>25&options=keyValues&attrs=name` | `/predioK/#` | 200 | entidades: K501 |
| 44 | Lista de tipos | `GET /v2/entities?type=Room,Lab&options=keyValues&attrs=name` | `/predioK/#` | 200 | entidades: K501, K502, K503, K401 |
| 45 | typePattern | `GET /v2/entities?typePattern=^L&options=keyValues&attrs=name` | `/predioK/#` | 200 | entidades: K503 |
| 46 | idPattern | `GET /v2/entities?idPattern=K50[12]$&options=keyValues&attrs=name` | `/predioK/#` | 200 | entidades: K501, K502 |
| 47 | Ordenação por dois critérios | `GET /v2/entities?orderBy=floor,!capacity&options=keyValues&attrs=name` | `/predioK/#` | 200 | ordem: K401, K501, K502, K503 |
| 48 | Paginação com total | `GET /v2/entities?limit=2&offset=1&options=count,keyValues&attrs=name&or…` | `/predioK/#` | 200 | ordem: K502, K501; Total no cabeçalho |
| 49 | Só os valores | `GET /v2/entities?type=Room&attrs=name,capacity&options=values&orderBy=!…` | `/predioK/#` | 200 | valor: `[["Sala K4-01", 60], ["Laboratório K5-01", 40], ["Sala K5-02", 30]]` |
| 50 | Geográfica - coords em latitude,longitude | `GET /v2/entities?georel=near;maxDistance:1000&geometry=point&coords=-23…` | `/predioK/#` | 200 | entidades: K501 |
| 51 | Geográfica com a ordem trocada - vazio, sem erro | `GET /v2/entities?georel=near;maxDistance:1000&geometry=point&coords=-46…` | `/predioK/#` | 200 | entidades: nenhuma |
| 52 | Filtro sobre atributo embutido | `GET /v2/entities?q=dateModified>2026-01-01T00:00:00Z&options=keyValues&…` | `/predioK/#` | 200 | entidades: K501, K502, K503, K401 |
| 53 | Consulta no corpo - op/query | `POST /v2/op/query?options=keyValues` | `/predioK/#` | 200 | entidades: K501, K401 |
| 54 | Limite máximo é 1000 - 400 | `GET /v2/entities?limit=1001` | `/predioK/#` | 400 |  |

**C4 - Atualizações** — Seção 3. Verbos, metadados e operadores atômicos, sobre a porta Door:K5 e a sala K502.

| # | Requisição | Método e caminho | Cabeçalho `fiware-servicepath` | Espera | Confere |
|---|---|---|---|---|---|
| 55 | Cria a porta Door:K5 | `POST /v2/entities` | `/predioK/andar5` | 201 |  |
| 56 | inc 1 | `PATCH /v2/entities/urn:ngsi-ld:Door:K5/attrs` | `/predioK/andar5` | 204 |  |
| 57 | count vale 11 | `GET /v2/entities/urn:ngsi-ld:Door:K5/attrs/count/value` | `/predioK/andar5` | 200 | valor: `11` |
| 58 | inc -3 | `PATCH /v2/entities/urn:ngsi-ld:Door:K5/attrs` | `/predioK/andar5` | 204 |  |
| 59 | mul 2 | `PATCH /v2/entities/urn:ngsi-ld:Door:K5/attrs` | `/predioK/andar5` | 204 |  |
| 60 | count vale 16 | `GET /v2/entities/urn:ngsi-ld:Door:K5/attrs/count/value` | `/predioK/andar5` | 200 | valor: `16` |
| 61 | max 7 - não muda | `PATCH /v2/entities/urn:ngsi-ld:Door:K5/attrs` | `/predioK/andar5` | 204 |  |
| 62 | peak continua 10 | `GET /v2/entities/urn:ngsi-ld:Door:K5/attrs/peak/value` | `/predioK/andar5` | 200 | valor: `10` |
| 63 | max 15 | `PATCH /v2/entities/urn:ngsi-ld:Door:K5/attrs` | `/predioK/andar5` | 204 |  |
| 64 | peak vale 15 | `GET /v2/entities/urn:ngsi-ld:Door:K5/attrs/peak/value` | `/predioK/andar5` | 200 | valor: `15` |
| 65 | min 4 | `PATCH /v2/entities/urn:ngsi-ld:Door:K5/attrs` | `/predioK/andar5` | 204 |  |
| 66 | low vale 4 | `GET /v2/entities/urn:ngsi-ld:Door:K5/attrs/low/value` | `/predioK/andar5` | 200 | valor: `4` |
| 67 | push b | `PATCH /v2/entities/urn:ngsi-ld:Door:K5/attrs` | `/predioK/andar5` | 204 |  |
| 68 | push b de novo - repete | `PATCH /v2/entities/urn:ngsi-ld:Door:K5/attrs` | `/predioK/andar5` | 204 |  |
| 69 | addToSet b - já existe | `PATCH /v2/entities/urn:ngsi-ld:Door:K5/attrs` | `/predioK/andar5` | 204 |  |
| 70 | addToSet c | `PATCH /v2/entities/urn:ngsi-ld:Door:K5/attrs` | `/predioK/andar5` | 204 |  |
| 71 | tags vale a, b, b, c | `GET /v2/entities/urn:ngsi-ld:Door:K5/attrs/tags/value` | `/predioK/andar5` | 200 | valor: `["a", "b", "b", "c"]` |
| 72 | pull b - remove todas | `PATCH /v2/entities/urn:ngsi-ld:Door:K5/attrs` | `/predioK/andar5` | 204 |  |
| 73 | tags vale a, c | `GET /v2/entities/urn:ngsi-ld:Door:K5/attrs/tags/value` | `/predioK/andar5` | 200 | valor: `["a", "c"]` |
| 74 | pullAll a, c | `PATCH /v2/entities/urn:ngsi-ld:Door:K5/attrs` | `/predioK/andar5` | 204 |  |
| 75 | tags vazia | `GET /v2/entities/urn:ngsi-ld:Door:K5/attrs/tags/value` | `/predioK/andar5` | 200 | valor: `[]` |
| 76 | set z e x | `PATCH /v2/entities/urn:ngsi-ld:Door:K5/attrs` | `/predioK/andar5` | 204 |  |
| 77 | unset y | `PATCH /v2/entities/urn:ngsi-ld:Door:K5/attrs` | `/predioK/andar5` | 204 |  |
| 78 | cfg vale x 9, z 3 | `GET /v2/entities/urn:ngsi-ld:Door:K5/attrs/cfg/value` | `/predioK/andar5` | 200 | valor: `{"x": 9, "z": 3}` |
| 79 | inc em atributo que não existe - 422 | `PATCH /v2/entities/urn:ngsi-ld:Door:K5/attrs` | `/predioK/andar5` | 422 |  |
| 80 | POST attrs cria com o valor do incremento | `POST /v2/entities/urn:ngsi-ld:Door:K5/attrs` | `/predioK/andar5` | 204 |  |
| 81 | novo vale 5 | `GET /v2/entities/urn:ngsi-ld:Door:K5/attrs/novo/value` | `/predioK/andar5` | 200 | valor: `5` |
| 82 | Dois operadores - só o primeiro vale | `PATCH /v2/entities/urn:ngsi-ld:Door:K5/attrs` | `/predioK/andar5` | 204 |  |
| 83 | count vale 17, e não 34 | `GET /v2/entities/urn:ngsi-ld:Door:K5/attrs/count/value` | `/predioK/andar5` | 200 | valor: `17` |
| 84 | inc com texto - 500 | `PATCH /v2/entities/urn:ngsi-ld:Door:K5/attrs` | `/predioK/andar5` | 500 |  |
| 85 | PUT só do valor - text/plain | `PUT /v2/entities/urn:ngsi-ld:Door:K5/attrs/count/value` | `/predioK/andar5` | 204 |  |
| 86 | count vale 0 | `GET /v2/entities/urn:ngsi-ld:Door:K5/attrs/count/value` | `/predioK/andar5` | 200 | valor: `0` |
| 87 | PATCH só com o valor | `PATCH /v2/entities/urn:ngsi-ld:Room:K502/attrs` | `/predioK/andar5` | 204 |  |
| 88 | Os metadados foram preservados | `GET /v2/entities/urn:ngsi-ld:Room:K502/attrs/temperature` | `/predioK/andar5` | 200 | unitCode e accuracy continuam |
| 89 | PATCH com overrideMetadata | `PATCH /v2/entities/urn:ngsi-ld:Room:K502/attrs?options=overrideMetadata` | `/predioK/andar5` | 204 |  |
| 90 | Os metadados sumiram | `GET /v2/entities/urn:ngsi-ld:Room:K502/attrs/temperature` | `/predioK/andar5` | 200 | metadata vazio |
| 91 | Restaura a temperatura da K502 | `PATCH /v2/entities/urn:ngsi-ld:Room:K502/attrs` | `/predioK/andar5` | 204 |  |
| 92 | PATCH em atributo novo - 422 | `PATCH /v2/entities/urn:ngsi-ld:Room:K502/attrs` | `/predioK/andar5` | 422 |  |
| 93 | POST com options=append em atributo existente - 422 | `POST /v2/entities/urn:ngsi-ld:Room:K502/attrs?options=append` | `/predioK/andar5` | 422 |  |
| 94 | Cria a entidade de teste com a e b | `POST /v2/entities` | `/predioK/andar5` | 201 |  |
| 95 | PUT attrs substitui todos | `PUT /v2/entities/urn:ngsi-ld:Teste:P1/attrs` | `/predioK/andar5` | 204 |  |
| 96 | Só restou c | `GET /v2/entities/urn:ngsi-ld:Teste:P1?options=keyValues` | `/predioK/andar5` | 200 | valor: `{"id": "urn:ngsi-ld:Teste:P1", "type": "Teste", "c": 3}` |
| 97 | Remove a entidade de teste | `DELETE /v2/entities/urn:ngsi-ld:Teste:P1` | `/predioK/andar5` | 204 |  |
| 98 | Lote com uma entidade inexistente - 422 PartialUpdate | `POST /v2/op/update` | `/predioK/andar5` | 422 |  |
| 99 | Mas a parte válida foi gravada - 44 | `GET /v2/entities/urn:ngsi-ld:Room:K501/attrs/capacity/value` | `/predioK/andar5` | 200 | valor: `44` |
| 100 | Restaura a capacidade da K501 | `PUT /v2/entities/urn:ngsi-ld:Room:K501/attrs/capacity/value` | `/predioK/andar5` | 204 |  |

**C5 - Subscrições** — Seção 4. Subscrição por MQTT: assine pel220/# no MQTTX antes de começar (localhost:1883). Precisa do Mosquitto no ar (Etapa 2).

| # | Requisição | Método e caminho | Cabeçalho `fiware-servicepath` | Espera | Confere |
|---|---|---|---|---|---|
| 101 | Descrição com parênteses - 400 | `POST /v2/subscriptions` | `/predioK/#` | 400 |  |
| 102 | Formato legacy - 400 | `POST /v2/subscriptions` | `/predioK/#` | 400 |  |
| 103 | Sala K501 a 25 graus | `PATCH /v2/entities/urn:ngsi-ld:Room:K501/attrs` | `/predioK/andar5` | 204 |  |
| 104 | Cria a subscrição sala quente | `POST /v2/subscriptions` | `/predioK/#` | 201 |  |
| 105 | Sem notificação inicial | `GET /v2/subscriptions/{{subQuente}}` | (nenhum) | 200 | timesSent ausente; espera antes de enviar |
| 106 | 26 graus - mudou, mas não passa de 28 | `PATCH /v2/entities/urn:ngsi-ld:Room:K501/attrs` | `/predioK/andar5` | 204 |  |
| 107 | 29 graus - notifica | `PATCH /v2/entities/urn:ngsi-ld:Room:K501/attrs` | `/predioK/andar5` | 204 |  |
| 108 | 29 graus de novo - não notifica | `PATCH /v2/entities/urn:ngsi-ld:Room:K501/attrs` | `/predioK/andar5` | 204 |  |
| 109 | Muda capacity com a sala quente - não notifica | `PATCH /v2/entities/urn:ngsi-ld:Room:K501/attrs` | `/predioK/andar5` | 204 |  |
| 110 | Lab K503 a 32 graus - não notifica | `PATCH /v2/entities/urn:ngsi-ld:Lab:K503/attrs` | `/predioK/andar5` | 204 |  |
| 111 | 30 graus - notifica | `PATCH /v2/entities/urn:ngsi-ld:Room:K501/attrs` | `/predioK/andar5` | 204 |  |
| 112 | Duas notificações até aqui | `GET /v2/subscriptions/{{subQuente}}` | (nenhum) | 200 | timesSent 2; espera antes de enviar |
| 113 | 30 graus com forcedUpdate - notifica | `PATCH /v2/entities/urn:ngsi-ld:Room:K501/attrs?options=forcedUpdate` | `/predioK/andar5` | 204 |  |
| 114 | Três notificações | `GET /v2/subscriptions/{{subQuente}}` | (nenhum) | 200 | timesSent 3; espera antes de enviar |
| 115 | Subscrição HTTP com localhost na URL | `POST /v2/subscriptions` | `/predioK/#` | 201 |  |
| 116 | Muda capacity - dispara a subscrição do localhost | `PATCH /v2/entities/urn:ngsi-ld:Room:K501/attrs` | `/predioK/andar5` | 204 |  |
| 117 | A falha aparece no status | `GET /v2/subscriptions/{{subLocal}}` | (nenhum) | 200 | failsCounter contou; Motivo registrado; O status continua active; espera antes de enviar |
| 118 | A listagem filtra pelo cabeçalho | `GET /v2/subscriptions` | `/` | 200 | Nenhuma subscrição na raiz |
| 119 | DELETE com curinga - 400 | `DELETE /v2/subscriptions/{{subLocal}}` | `/predioK/#` | 400 |  |
| 120 | Volta as temperaturas | `POST /v2/op/update` | `/predioK/andar5` | 204 |  |

**C6 - Limpeza** — Remove tudo o que a coleção criou no tenant pel220. Não toca no tenant ccm130 da Base.

| # | Requisição | Método e caminho | Cabeçalho `fiware-servicepath` | Espera | Confere |
|---|---|---|---|---|---|
| 121 | Remove todas as subscrições do tenant pel220 | `GET /v2/subscriptions?limit=100` | (nenhum) | 200 | Subscrições encontradas:  |
| 122 | Não sobrou subscrição | `GET /v2/subscriptions` | (nenhum) | 200 | valor: `[]`; espera antes de enviar |
| 123 | Remove Room:K501 | `DELETE /v2/entities/urn:ngsi-ld:Room:K501` | `/predioK/andar5` | 204 ou 404 |  |
| 124 | Remove Room:K502 | `DELETE /v2/entities/urn:ngsi-ld:Room:K502` | `/predioK/andar5` | 204 ou 404 |  |
| 125 | Remove Lab:K503 | `DELETE /v2/entities/urn:ngsi-ld:Lab:K503` | `/predioK/andar5` | 204 ou 404 |  |
| 126 | Remove Room:K401 | `DELETE /v2/entities/urn:ngsi-ld:Room:K401` | `/predioK/andar4` | 204 ou 404 |  |
| 127 | Remove Door:K5 | `DELETE /v2/entities/urn:ngsi-ld:Door:K5` | `/predioK/andar5` | 204 ou 404 |  |
| 128 | O tenant ficou vazio | `GET /v2/entities?options=keyValues&attrs=name` | (nenhum) | 200 | entidades: nenhuma |


### 9.5 Anatomia de um teste da coleção

```javascript
pm.test("Status 200", () => pm.response.to.have.status(200));
pm.test("Entidades: K501, K502", () =>
  pm.expect(pm.response.json().map(e => e.id.split(":").pop()).sort()).to.eql(["K501", "K502"]));
```

O primeiro confere o código; o segundo, o **conjunto exato** de entidades devolvidas, em qualquer ordem (nas
consultas com `orderBy`, a ordem também é conferida). As requisições que precisam esperar (expiração,
notificações) têm um *pre-request script* com `return new Promise(r => setTimeout(r, …))`.

### 9.6 O que os testes não garantem

- Que a notificação MQTT **chegou** a alguém: o Orion conta como sucesso a publicação no broker. Confira no MQTTX.
- Que o painel está **certo**: a pasta Etapa 7 confere a fonte de dados, que há histórico e que existem as três
  visualizações, não o conteúdo das consultas.
- Tempos: os números de tempo e de memória deste material são de uma máquina; os seus vão variar.

---

## 10. Cola de comandos (PowerShell)

```powershell
# subir, na ordem
docker compose up -d --wait orion
docker compose up -d --wait iot-agent
docker compose up -d --build esp32-simulada
docker compose up -d --build clima-externo
docker compose up -d --wait cygnus
docker compose up -d grafana

# o que está no ar
docker compose ps

# tenants no MongoDB
docker exec db-mongo mongosh --quiet --eval "db.getMongo().getDBNames()"

# consulta com tenant e caminho
curl.exe -s "http://localhost:1026/v2/entities?q=floor==5&options=keyValues&attrs=name" `
  -H "fiware-service: pel220" -H "fiware-servicepath: /predioK/#"

# as subscrições do tenant da Base e o status
curl.exe -s "http://localhost:1026/v2/subscriptions" -H "fiware-service: ccm130"

# o clima pelo Orion e o log do provedor
curl.exe -s "http://localhost:1026/v2/entities/urn:ngsi-ld:WeatherObserved:FEI?type=WeatherObserved&options=keyValues" `
  -H "fiware-service: ccm130" -H "fiware-servicepath: /"
docker logs clima-externo --tail 5

# Cygnus no ar e o que ele gravou
curl.exe -s http://localhost:5080/v1/version
docker logs fiware-cygnus 2>&1 | Select-String "INSERT INTO" | Select-Object -Last 1
docker exec db-mysql mysql -uroot -p123 -e "SHOW TABLES FROM ccm130"

# quantas linhas de histórico
docker exec db-mysql mysql -uroot -p123 -e "SELECT attrName, COUNT(*) FROM ccm130.``urn_ngsi-ld_ClimateStation_ESP32001_ClimateStation`` GROUP BY attrName"

# Grafana no ar
curl.exe -s http://localhost:3000/api/health

# escutar as notificações MQTT sem o MQTTX
docker exec mosquitto mosquitto_sub -t "pel220/#" -v

# concorrência
python ferramentas\concorrencia.py
```

No PowerShell, a crase (`` ` ``) é o caractere de escape: o nome da tabela entre crases do MySQL precisa de duas
crases (` `` `) dentro de uma cadeia com aspas duplas.

---

## 11. Diagnóstico: do sintoma à causa

| Sintoma | Pergunta | Como verificar | Causa provável |
|---|---|---|---|
| Lista vazia, sem erro | o tenant e o caminho estão certos? | repita sem `fiware-servicepath` | cabeçalho errado (seção 2) |
| `404` num `PATCH` | a entidade está na raiz? | `GET` com `/#` e `attrs=` | gravação sem caminho vai para `/` |
| `409 TooManyResults` | o id existe em dois caminhos? | `GET /v2/entities?id=…` com `/#` | mesmo id em dois ramos |
| `400` com texto | algum `< > " ' = ; ( )`? | leia o corpo do erro | caracteres proibidos |
| A consulta não acha o que deveria | o atributo existe nessa entidade? tipo número ou texto? | `GET` sem `keyValues` | `!=` ignora ausentes; `"25"` é texto |
| Contador "perdendo" visitas | há ler-somar-gravar? | revise o código | use `$inc` |
| A subscrição não notifica | o valor mudou? o atributo está em `condition.attrs`? o tipo bate? | `GET /v2/subscriptions/<id>` | seção 6.3 |
| `failsCounter` subindo | o consumidor está no ar? a URL tem `localhost`? | `lastFailureReason` | seção 6.4 |
| A subscrição do clima não dispara | o atributo vem de um registro? | `GET /v2/registrations` | o Orion não notifica atributo de provedor |
| `source: simulado` | o contêiner alcança a internet? | `curl.exe http://localhost:3010/health` | rede bloqueada; normal |
| `Table doesn't exist` | já houve notificação? | status da subscrição do Cygnus | a tabela nasce com a 1ª notificação |
| Buraco no histórico | o Cygnus ficou fora do ar? | `recvTime` das linhas | não há fila (seção 6.5) |
| *Save & test* falha | o Host é `mysql-db:3306`? o MySQL está `healthy`? | `docker compose ps` | `localhost`, ou MySQL subindo |
| *Data is missing a number field* | há `CAST`? o editor está em *Code*? | *Query inspector* | texto no lugar de número |
| *No data* | o período cobre os dados? | *Last 15 minutes* | período antigo; histórico novo depois de `down -v` |
| Datas em 1970 ou no futuro | há `/ 1000`? | *Table view* | milissegundos tratados como segundos |

---

## 12. Glossário

| Termo | Significado |
|---|---|
| Tenant (inquilino) | espaço de dados isolado no Orion, escolhido por `fiware-service`; um banco no MongoDB |
| `fiware-servicepath` | caminho hierárquico dentro de um tenant (`/predioK/andar5`); `#` inclui os subcaminhos |
| Atributo embutido | mantido pelo Orion (`dateCreated`, `dateModified`) ou com efeito especial (`dateExpires`) |
| TTL | *time to live*: índice do MongoDB que remove documentos vencidos, a cada 60 s |
| Linguagem de consulta simples | a sintaxe de `q` e `mq` (`==`, `!=`, `..`, `~=`, `;`, unários) |
| Operador atômico | `$inc`, `$max`, `$push`…: a alteração é feita no banco, numa única operação |
| Atualização perdida (*lost update*) | duas gravações concorrentes baseadas na mesma leitura: uma se perde |
| Registro | aviso ao Orion de que certos atributos moram num provedor de contexto |
| Provedor de contexto | serviço que responde `POST /op/query` em NGSI-v2 (o clima, o IoT Agent) |
| Subscrição | pedido de notificação quando o contexto muda de certa forma |
| Consumidor de contexto | quem recebe as notificações (Cygnus, controlador, MQTTX) |
| `throttling` | intervalo mínimo entre notificações; as do meio são descartadas |
| Cygnus | conector do FIWARE que grava as notificações em bancos (aqui, MySQL) |
| Sumidouro (*sink*) | o destino de um conector: no Cygnus, o MySQL |
| Macro do Grafana | trecho como `$__unixEpochFilter` que o Grafana troca por SQL antes de consultar |
| Fonte de dados (*data source*) | a conexão do Grafana com um banco |

---

## 13. Referências

- FIWARE. *Orion Context Broker — documentation*: multitenancy, service paths, builtin attributes, update
  operators, subscriptions, registrations, forbidden characters. <https://fiware-orion.readthedocs.io/>
- FIWARE. *FIWARE NGSI v2 Specification* (Simple Query Language, attribute types).
  <https://fiware.github.io/specifications/ngsiv2/stable/>
- FIWARE. *Cygnus — NGSIMySQLSink*. <https://fiware-cygnus.readthedocs.io/>
- FIWARE. *Step-by-step tutorials*: Subscriptions, Context Providers, Historic Context (Cygnus).
  <https://fiware-tutorials.readthedocs.io/>
- Grafana Labs. *MySQL data source* (macros) e *Visualizations*, versão 10.4. <https://grafana.com/docs/grafana/v10.4/>
- MongoDB. *TTL Indexes*. <https://www.mongodb.com/docs/manual/core/index-ttl/>
- Open-Meteo. *Weather Forecast API*. <https://open-meteo.com/en/docs>
- ZIEGLER, S. et al. (org.). *Springer Handbook of Internet of Things*. Springer, 2024 (capítulos de plataformas e
  de dados).

---

## Apêndice A — O provedor de clima, comentado

`fiware/clima/provedor.py` é o modelo de qualquer integração com uma API externa: só a função `buscar_clima()`
muda. Ele usa só a biblioteca padrão do Python.

| Parte | O que faz |
|---|---|
| Configuração | `PORTA`, `LATITUDE`, `LONGITUDE`, `CACHE` (60 s) e `MODO` (`api` ou `simulado`), por variável de ambiente |
| `buscar_clima()` | consulta a Open-Meteo; converte a umidade para 0 a 1 e o vento de km/h para m/s; sem internet, devolve valores simulados com `source = simulado` |
| Tradução para NGSI-v2 | monta, para cada atributo pedido, `{"type": …, "value": …}` |
| Servidor HTTP | `POST /v2/op/query` (o que o Orion chama) e `GET /health` (para você) |

O que o Orion manda e o que o provedor responde:

```json
POST http://clima-externo:3010/v2/op/query
{ "entities": [{"id": "urn:ngsi-ld:WeatherObserved:FEI", "type": "WeatherObserved"}],
  "attrs": ["temperature", "relativeHumidity", "windSpeed", "source", "dateObserved"] }
```

```json
[ { "id": "urn:ngsi-ld:WeatherObserved:FEI", "type": "WeatherObserved",
    "temperature": {"type": "Number", "value": 19.4},
    "relativeHumidity": {"type": "Number", "value": 0.91},
    "windSpeed": {"type": "Number", "value": 2.6},
    "source": {"type": "Text", "value": "open-meteo"},
    "dateObserved": {"type": "DateTime", "value": "2026-11-16T11:15:00Z"} } ]
```

**Para o projeto do grupo:** troque `buscar_clima()` pela API que o grupo precisa; mantenha a tradução e o
servidor. Chave de API vai em variável de ambiente no `docker-compose.yml` (ou num `.env`), nunca no código nem no
GitHub.

O código completo:

```python
"""
============================================================================
 CCM130 - Conectividade e IoT | Aula 10 - Fluxo de dados completo
 Centro Universitário FEI - Prof. Rafael Gomes Alves
----------------------------------------------------------------------------
 PROVEDOR DE CONTEXTO (proxy NGSI v2) com o clima real do campus da FEI.

 O Orion não guarda estes dados: um REGISTRO (Aula 8) diz a ele que os
 atributos da entidade urn:ngsi-ld:WeatherObserved:FEI estão neste provedor.
 A cada leitura de uma aplicação, o Orion faz

     POST <url do registro>/op/query
     {"entities": [{"id": "...", "type": "WeatherObserved"}], "attrs": [...]}

 e este programa busca o clima atual na API pública Open-Meteo (sem chave),
 traduz para NGSI v2 e responde. É o padrão de qualquer integração com uma
 API externa: só a função buscar_clima() muda.

   temperature        Number   °C           (temperature_2m)
   relativeHumidity   Number   0 a 1        (relative_humidity_2m / 100)
   windSpeed          Number   m/s          (wind_speed_10m em km/h / 3,6)
   dateObserved       DateTime              (hora da observação)
   source             Text     open-meteo | simulado

 Sem internet (rede da sala bloqueada), responde com valores SIMULADOS e
 source = "simulado" -- a aula continua funcionando.

 Variáveis de ambiente (padrão entre parênteses):
   PORTA (3010)  LATITUDE (-23.7245)  LONGITUDE (-46.5793)  CACHE (60) s
   MODO (api)    "simulado" força os valores simulados
============================================================================
"""

import json
import os
import random
import time
import urllib.request
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

PORTA = int(os.getenv("PORTA", "3010"))
LATITUDE = float(os.getenv("LATITUDE", "-23.7245"))       # FEI, São Bernardo do Campo
LONGITUDE = float(os.getenv("LONGITUDE", "-46.5793"))
CACHE = float(os.getenv("CACHE", "60"))                   # não consulte a API a cada leitura
MODO = os.getenv("MODO", "api")

URL_API = ("https://api.open-meteo.com/v1/forecast"
           f"?latitude={LATITUDE}&longitude={LONGITUDE}"
           "&current=temperature_2m,relative_humidity_2m,wind_speed_10m&timezone=UTC")

_cache = {"quando": 0.0, "dados": None}


def log(*args):
    print("[clima]", *args, flush=True)


# ---------------------------------------------------------------------------
# 1. A API externa -- a única parte que muda de uma integração para outra
# ---------------------------------------------------------------------------
def buscar_clima():
    """Devolve um dicionário com as grandezas já nas unidades do modelo de dados."""
    if MODO != "simulado":
        try:
            with urllib.request.urlopen(URL_API, timeout=5) as resposta:
                atual = json.load(resposta)["current"]
            return {
                "temperature": atual["temperature_2m"],
                "relativeHumidity": round(atual["relative_humidity_2m"] / 100, 2),
                "windSpeed": round(atual["wind_speed_10m"] / 3.6, 1),
                "dateObserved": atual["time"] + ":00Z",
                "source": "open-meteo",
            }
        except Exception as erro:                     # sem internet, API fora do ar, limite de uso
            log("API indisponível, usando valores simulados:", erro)
    return {
        "temperature": round(random.uniform(16, 30), 1),
        "relativeHumidity": round(random.uniform(0.4, 0.9), 2),
        "windSpeed": round(random.uniform(0, 6), 1),
        "dateObserved": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": "simulado",
    }


def clima_atual():
    if _cache["dados"] is None or time.time() - _cache["quando"] > CACHE:
        _cache["dados"], _cache["quando"] = buscar_clima(), time.time()
        log("clima atualizado:", _cache["dados"])
    return _cache["dados"]


# ---------------------------------------------------------------------------
# 2. Tradução para NGSI v2
# ---------------------------------------------------------------------------
TIPOS = {"temperature": "Number", "relativeHumidity": "Number", "windSpeed": "Number",
         "dateObserved": "DateTime", "source": "Text"}


def responder_consulta(consulta):
    """Recebe o corpo do /op/query do Orion e devolve a lista de entidades."""
    dados = clima_atual()
    pedidos = consulta.get("attrs") or list(TIPOS)          # sem attrs = todos
    resposta = []
    for entidade in consulta.get("entities", []):
        e = {"id": entidade["id"], "type": entidade.get("type", "WeatherObserved")}
        for atributo in pedidos:
            if atributo in dados:
                e[atributo] = {"type": TIPOS[atributo], "value": dados[atributo], "metadata": {}}
        resposta.append(e)
    return resposta


class Provedor(BaseHTTPRequestHandler):
    def _json(self, status, corpo):
        bruto = json.dumps(corpo).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(bruto)))
        self.end_headers()
        self.wfile.write(bruto)

    def do_POST(self):
        if not urlsplit(self.path).path.endswith("/op/query"):      # o Orion acrescenta ?options=...
            self._json(404, {"error": "NotFound", "description": "use <base>/op/query"})
            return
        tamanho = int(self.headers.get("Content-Length", 0))
        consulta = json.loads(self.rfile.read(tamanho) or b"{}")
        log("Orion perguntou:", consulta.get("attrs"), "de", [e["id"] for e in consulta.get("entities", [])])
        self._json(200, responder_consulta(consulta))

    def do_GET(self):                                        # GET /health: o provedor está no ar?
        self._json(200, {"status": "ok", "modo": MODO, "clima": clima_atual()})

    def log_message(self, formato, *args):
        pass


if __name__ == "__main__":
    log(f"Provedor de clima em :{PORTA} | lat {LATITUDE} lon {LONGITUDE} | modo {MODO}")
    ThreadingHTTPServer(("0.0.0.0", PORTA), Provedor).serve_forever()
```
