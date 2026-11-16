# Aula 6 — Introdução ao FIWARE: contexto e dispositivos

**PEL 220 — Internet das Coisas e Gêmeos Digitais** · Centro Universitário FEI · Prof. Rafael Gomes Alves

Nesta aula você sobe, **uma peça de cada vez**, as Etapas 1 a 4 da plataforma FIWARE da disciplina (pasta
`Base/`): o **Orion** guarda o contexto no **MongoDB**; o **IoT Agent JSON** traduz as mensagens MQTT da **ESP32
simulada** (DHT22 + relé) para NGSI-v2; e a aplicação comanda o relé **pelo Orion**. No meio do caminho, você
explora a API do Orion com o exemplo das lojas e reproduz, de propósito, os erros mais comuns.

```
 Postman ──── API NGSI-v2 ────────────────────────▶ orion:1026 ◀──▶ mongo-db:27017
    │                                                   ▲  │
    └── provisionamento ──▶ iot-agent-json:4041 ── upsert  │ registro (comandos)
                                   ▲  │
                     /json/ccm130/esp32001/attrs           │
                                   │  ▼  /ccm130/esp32001/cmd
 MQTTX (você) ──▶ mosquitto:1883 ◀──▶ esp32-simulada (Etapa 3)
```

| Momento da aula | O que você faz | Onde |
|---|---|---|
| Seção 2 | **Etapa 1**: Orion + MongoDB; cria e lê a sala K501 | PowerShell + coleção da Base |
| Seção 3 | **Pastas A e X**: a API do Orion (lojas) e os experimentos | coleção desta aula |
| Seção 4 | **Etapa 2**: IoT Agent + Mosquitto; grupo e dispositivo | PowerShell + coleção da Base |
| Seção 4 | **Publicação manual**: a primeira medida, à mão | MQTTX (ou PowerShell) |
| Seção 4 | **Etapa 3**: a ESP32 simulada publica a cada 5 s | PowerShell + coleção da Base |
| Seção 5 | **Etapa 4**: comandos `on` e `off`; experimento X7 | coleção da Base + MQTTX |

Tudo o que aparece aqui foi executado em **11/11/2026** (Windows 11, Docker Desktop com Engine 29.9.2, WSL 2,
PowerShell 7.6, Postman CLI 1.75), a partir de volumes vazios: **81 requisições e 131 testes, zero falhas**.
Identificadores, horários e temperaturas mudam de uma máquina para outra.

---

## Estrutura

```
aula06-fiware-contexto.zip
├── fiware/                                                  a plataforma (Base sem gabarito) → C:\pel220\fiware
└── aula06-fiware-contexto/
aula06-fiware-contexto/
├── README.md                                                este roteiro
├── Material complementar - Orion e IoT Agent JSON.md (e .pdf)
│                                                            a plataforma, as duas APIs e o catálogo dos testes
├── fiware/                                                  a plataforma pronta para subir (→ C:\pel220\fiware)
│     ├── docker-compose.yml                                 os dez serviços (Etapas 1 a 9) + 2 versões prontas
│     ├── mosquitto/  esp32_simulada/  clima/                arquivos de apoio
│     ├── controlador/                                       esqueleto, para os alunos (porta 5001)
│     ├── controlador_pronto/                                versão pronta e automática (porta 5002, perfil "pronto")
│     ├── grafana/                                           Grafana pronto: provisionamento + painel (porta 3001)
│     ├── queries.txt                                        consultas SQL de exemplo para os painéis
│     └── CCM130 - Aula 10 - …postman_collection.json, README.md
├── PEL220 - Aula 06 - Introdução ao FIWARE.postman_collection.json
│     ├── A1 a A5   a API do Orion com o exemplo das lojas (tenant padrão, sem cabeçalhos)
│     ├── X1 a X7   experimentos: o que o Orion e o IoT Agent fazem de verdade
│     └── A6        limpeza das lojas
└── ferramentas/latencia_comando.py                         mede o tempo de um comando (seção 5)
```

A plataforma em si vem na pasta **`fiware/`** do zip da aula (`aula06-fiware-contexto.zip`): é a pasta `Base/`
do Material de Apoio **sem** o gabarito — `docker-compose.yml`, `mosquitto/`, `esp32_simulada/`, `clima/`,
`controlador/` (esqueleto), `queries.txt` e a coleção `CCM130 - Aula 10 - Fluxo de dados completo`, com as pastas
**Etapa 1 a Etapa 9** (as Etapas 5 a 9 ficam para as Aulas 7 a 9). As pastas A da coleção desta aula vêm da CCM130
(Aula 7, pastas 01 a 06).

> **Professor:** distribua só o zip. A pasta `Base/` tem `Atividade GABARITO/` **e** `Atividade GABARITO.zip`
> (controlador e painéis resolvidos).

---

## Onde executar

| O quê | Onde |
|---|---|
| `docker compose …`, `docker logs …`, `docker exec …` | **PowerShell** em `C:\pel220\fiware` |
| Etapas 1 a 4 | **Postman**, coleção da Base (pasta da etapa) |
| Pastas A e X | **Postman**, coleção desta aula |
| Publicar e assinar MQTT | **MQTTX**: Host `localhost`, Port `1883`, `mqtt://` |

**Uma pasta só, `C:\pel220\fiware`, da Aula 6 à Aula 9.** O nome da pasta vira o prefixo do projeto Compose
(rede `fiware_default`, volume `fiware_mongo-db`). Se cada aula usar uma pasta diferente, os volumes também são
outros e o contexto "some".

**Git Bash?** Tópicos que começam com `/` viram caminhos do Windows (na preparação, `/json/…` virou
`C:/Program Files/Git/json/…`). Use `MSYS_NO_PATHCONV=1` antes do comando, ou o PowerShell.

---

## Antes de começar

1. **Docker Desktop aberto**: `docker version` mostra **Client** e **Server**.
2. **Limpeza da Aula 5** (os nomes voltam hoje), na pasta do experimento:

    ```powershell
    docker compose down -v
    docker rm -f mosquitto esp32001 esp32002 registrador
    ```

3. **A plataforma em `C:\pel220\fiware`**: descompacte `aula06-fiware-contexto.zip` e copie a pasta `fiware\`
   para `C:\pel220\fiware` (é o nome da pasta que importa). Abra o PowerShell nela.
4. **Imagens** (≈ 1,9 GB; baixe antes, se a rede for lenta):

    ```powershell
    docker pull quay.io/fiware/orion:4.1.0
    docker pull quay.io/fiware/iotagent-json:3.7.0-distroless
    docker pull mongo:6.0
    docker pull eclipse-mosquitto:2.0.18
    docker pull python:3.12-slim
    ```

    A ESP32 simulada é **construída** na Etapa 3, e o build baixa o `paho-mqtt` do PyPI. Sem internet no
    laboratório, use o plano B da Aula 5: construa a imagem antes e leve-a num arquivo.

    ```powershell
    docker compose build esp32-simulada                       # em casa, com internet
    docker save ccm130/esp32-simulada -o esp32-simulada.tar   # leve o .tar
    docker load -i esp32-simulada.tar                         # no laboratório
    ```

5. **Postman** (o aplicativo): **Import** das duas coleções — a da Base e a desta aula.
6. **MQTTX**: nova conexão `localhost:1883`.

> **Nunca `docker compose up -d` sem nomes.** A ESP32 subiria antes do provisionamento (Etapa 2) e nasceria a
> entidade `Thing:esp32001`.

---

## Etapa 1 — O Orion guarda o contexto

📍 **Onde:** PowerShell em `C:\pel220\fiware`, depois Postman.

```powershell
docker compose up -d --wait orion
```

```
 Container db-mongo Healthy
 Container fiware-orion Healthy
```

Com as imagens já baixadas, levou **12,3 s** (o Orion espera o MongoDB ficar saudável).

**Postman › coleção da Base › Etapa 1 - Contexto:** confere a versão, cria a sala `urn:ngsi-ld:Room:K501`
(`POST /v2/op/update`) e a lê de volta — **3 requisições, 5 testes**.

**Verifique:** o banco do tenant nasceu.

```powershell
docker exec db-mongo mongosh --quiet --eval "db.getMongo().getDBNames()"
```

```
[ 'admin', 'config', 'local', 'orion-ccm130' ]
```

---

## Pastas A e X — a API do Orion na mão

📍 **Onde:** Postman, coleção desta aula, com a Etapa 1 no ar.

Rode **A1 a A5**, uma requisição por vez (leia a resposta antes do *Test Results*), depois **X1 a X6** e, por
último, **A6** (limpeza). As pastas A usam o **tenant padrão** (sem `fiware-service`): não mexem na Base.
Resultado esperado: **59 requisições, 90 testes**.

| Pasta | O que observar |
|---|---|
| A1 Primeiras requisições | `201 Created` e o cabeçalho `Location` |
| A2 Consultas | `attrs`, `q` (inclusive em subatributo), `georel`, `limit`/`offset` e `Fiware-Total-Count` |
| A3 Relações | 1:N (`refStore`) e N:N (`InventoryItem`); pai → filhos com `q` |
| A4 CRUD | `422` do id repetido e do `PATCH` em atributo novo; o `PUT …/attrs` substitui tudo |
| A5 Operações em lote | `appendStrict` (422 se já existe) × `append`; `replace` |
| X1 Entidade sem type | o Orion usa `Thing` e infere `Number` para o atributo |
| X2 Content-Type em GET | `400`: GET e DELETE não aceitam o cabeçalho |
| X3 Número entre aspas | `"25"` com type Number é texto: `q=capacity>20` não acha |
| X4 Datas sob demanda | `dateCreated`/`dateModified` só vêm quando pedidos |
| X5 Unário | `q=address` = quem **tem**; `q=!address` = quem **não tem** |
| X6 Caractere proibido | `"OK: rele=ON"` → `400 Invalid characters` |
| X7 Comando | **depois da Etapa 2** (ver Etapa 4) |
| A6 Limpeza | remove as lojas |

---

## Etapa 2 — O IoT Agent conhece a ESP32

📍 **Onde:** PowerShell em `C:\pel220\fiware`, depois Postman.

```powershell
docker compose up -d --wait iot-agent
```

```
 Container mosquitto Healthy
 Container fiware-iot-agent Healthy
```

**Postman › Base › Etapa 2 - IoT Agent** (**6 requisições, 10 testes**): cria o grupo de serviço (chave `ccm130`,
`resource` `/iot/json`, `cbroker` `http://orion:1026`) e provisiona `esp32001`:

| Medida (`object_id` → atributo) | Comando | Estático |
|---|---|---|
| `t` → `temperature` (Number) | `on` | `refRoom` → `urn:ngsi-ld:Room:K501` |
| `h` → `humidity` (Number) | `off` | |
| `s` → `state` (Text) | | |

**Verifique — provisionar não cria a entidade.** O `GET` da ESP32 responde `200` com `on` e `off`, mas ela não
está no banco: o Orion **encaminha** a consulta ao IoT Agent, pelo registro de provedor dos comandos.

```powershell
docker exec db-mongo mongosh --quiet --eval "db.getSiblingDB('orion-ccm130').entities.find({}, {'_id.id': 1}).toArray()"
docker logs fiware-orion 2>&1 | Select-String "Request forwarded" | Select-Object -Last 1
```

```
[ { _id: { id: 'urn:ngsi-ld:Room:K501' } } ]
… Request forwarded (regId: 6af45fcd…): POST http://iot-agent-json:4041/op/query …
```

> A chave (`apikey`) **só roteia** a mensagem para o grupo: não autentica nada. Segurança fica para a Aula 10.

---

## Publicação manual — você é o dispositivo

📍 **Onde:** MQTTX (ou PowerShell).

No MQTTX, assine `/json/ccm130/#` e `/ccm130/#` e publique **uma** medida, com os números **sem aspas**:

| Tópico | Mensagem |
|---|---|
| `/json/ccm130/esp32001/attrs` | `{"t": 24.5, "h": 61, "s": "OFF"}` |

Sem MQTTX, pelo PowerShell (o JSON entra pela entrada padrão):

```powershell
'{"t": 24.5, "h": 61, "s": "OFF"}' | docker exec -i mosquitto mosquitto_pub -t /json/ccm130/esp32001/attrs -s
```

**Verifique:** a entidade agora está no banco, com `refRoom` e `TimeInstant` (cabeçalhos `fiware-service: ccm130`
e `fiware-servicepath: /`):

```
GET http://localhost:1026/v2/entities/urn:ngsi-ld:ClimateStation:ESP32001?options=keyValues
{"id":"urn:ngsi-ld:ClimateStation:ESP32001","type":"ClimateStation","TimeInstant":"2026-11-11T12:30:08.453Z",
 "humidity":61,"refRoom":"urn:ngsi-ld:Room:K501","state":"OFF","temperature":24.5,"on":"","off":""}
```

O log do IoT Agent registra `Multiple measures for device esp32001 with apiKey ccm130 successfully updated`.
A carga MQTT tem **32 B**; o corpo NGSI que o IoT Agent manda ao Orion, **654 B** (≈ 20×).

---

## Etapa 3 — A ESP32 simulada publica

📍 **Onde:** PowerShell em `C:\pel220\fiware`, depois Postman.

```powershell
docker compose up -d --build esp32-simulada
docker logs -f esp32-simulada
```

```
Conectada a mosquitto:1883 (Success)
Escutando /ccm130/esp32001/cmd
medida  -> /json/ccm130/esp32001/attrs {'t': 26.2, 'h': 54.8, 's': 'OFF'}
medida  -> /json/ccm130/esp32001/attrs {'t': 26.3, 'h': 55.1, 's': 'OFF'}
```

(As duas primeiras linhas podem sair intercaladas: a rede roda numa *thread* à parte.)

**Postman › Base › Etapa 3** (**3 requisições, 10 testes**): tipos numéricos, relé desligado, sala K501, medida
recente, `TimeInstant` do tipo `DateTime` e `404` em `Thing:esp32001`.

**Verifique no MQTTX:** uma mensagem a cada 5 s; a temperatura sobe devagar (a sala tende a 29 °C com o relé
desligado).

---

## Etapa 4 — A aplicação comanda o relé

📍 **Onde:** Postman e MQTTX. Nada novo para subir.

**Postman › Base › Etapa 4 - Comandos** (**4 requisições, 10 testes**): `on` e `off` vão ao **Orion**, nunca à
ESP32, sempre com `?type=`:

```
PATCH http://localhost:1026/v2/entities/urn:ngsi-ld:ClimateStation:ESP32001/attrs?type=ClimateStation
{"on": {"type": "command", "value": ""}}
```

**Verifique no MQTTX** (horários UTC):

```
12:30:38  /ccm130/esp32001/cmd           {"on":""}
12:30:38  /json/ccm130/esp32001/cmdexe   {"on": "OK - rele ligado"}
12:30:38  /json/ccm130/esp32001/attrs    {"s": "ON"}
12:30:41  /ccm130/esp32001/cmd           {"off":""}
12:30:41  /json/ccm130/esp32001/cmdexe   {"off": "OK - rele desligado"}
12:30:41  /json/ccm130/esp32001/attrs    {"s": "OFF"}
```

**Três confirmações diferentes:**

| Mensagem | O que significa |
|---|---|
| `204` do `PATCH` | o Orion **encaminhou** ao IoT Agent; nada mais |
| `cmdexe` → `on_status = OK` | o dispositivo **respondeu** — com qualquer texto: `{"off": "ERRO - rele travado"}` também vira `OK` (o erro fica em `off_info`) |
| `attrs` → `state` | o estado que o dispositivo diz ter |

**Coleção desta aula › X7** (**6 requisições, 6 testes**): numa lâmpada provisionada sem dispositivo, o `PATCH`
sem `?type` dá `404`; com `?type=Lamp`, `204` e `on_status = PENDING` para sempre. A pasta se desfaz no fim.

**E com a ESP32 desligada?** (`docker compose stop esp32-simulada`): o `PATCH` continua dando `204`, o
`on_status` fica `PENDING` e **continua `PENDING` depois que ela volta** — o IoT Agent publica o comando com
**QoS 0** e a ESP32 assina com sessão limpa. O `on_info` continua mostrando o resultado do comando **anterior**.

### Medir você mesmo

`ferramentas/latencia_comando.py` manda 12 comandos alternados e mede o tempo até o `204` e até o
`on_status = OK` (só biblioteca padrão do Python; a ESP32 simulada precisa estar no ar):

```powershell
python ferramentas/latencia_comando.py
```

Na preparação: **204 em 50 ms** e **OK em 64 ms** (medianas de 12; uma segunda rodada deu 56 e 77 ms).

---

## Para aprofundar (antes da Aula 7)

**Exercício:** crie a sala `urn:ngsi-ld:Room:K502`, provisione `esp32002` (entidade
`urn:ngsi-ld:ClimateStation:ESP32002`, mesmas medidas e comandos, `refRoom` → K502) e suba uma segunda ESP32:

```powershell
docker run -d --name esp32002 --network fiware_default -e DEVICE_ID=esp32002 ccm130/esp32-simulada
```

Verifique com `GET /v2/entities?q=refRoom==urn:ngsi-ld:Room:K502&options=keyValues` (com os cabeçalhos do tenant).
Para desfazer: `docker rm -f esp32002`, `DELETE /iot/devices/esp32002` e o `DELETE` das duas entidades.

**Questão de pesquisa:** o que um comando deve garantir — prazo, repetição segura, correlação com a resposta —
e onde isso mora (dispositivo, IoT Agent, aplicação)? Um parágrafo, com uma fonte.

**Marco do projeto (Aula 7):** o esboço do modelo de dados do grupo — entidades, atributos (tipo, unidade e
origem), relacionamentos, ids em URN e um JSON de exemplo por tipo, **aceito pelo Orion e lido de volta**.

---

## Parar sem perder o contexto

```powershell
docker compose stop          # para tudo; entidades, grupo e dispositivo ficam no volume
docker compose down          # remove contêineres e rede; o volume fica
docker compose down -v       # APAGA o volume: na Aula 7 seria preciso refazer tudo
```

**Reentrada na Aula 7:** `docker compose up -d --wait orion`, `docker compose up -d --wait iot-agent`, a pasta
**Etapa 2** (o grupo devolve `409` se já existir — o teste aceita), depois `docker compose up -d esp32-simulada`
e a pasta **Etapa 3**.

---

## Problemas comuns

| Sintoma | Causa | Solução |
|---|---|---|
| `Container name already in use` | sobra da Aula 5 ou de outra pasta com a Base | `docker rm -f <nome>`; uma Base por vez |
| `port is already allocated` (1883) | outro broker no Windows | pare o outro broker |
| `400` num GET ao Orion | cabeçalho `Content-Type` em GET ou DELETE (X2) | remova o cabeçalho |
| Lista vazia ou `404` nas entidades da ESP32 | consulta sem `fiware-service`/`fiware-servicepath` | use os cabeçalhos do tenant (`ccm130`, `/`) |
| A medida não chega ao Orion | tópico errado (chave, barra inicial, maiúsculas) | log do IoT Agent: `MEASURES-004` = chave/dispositivo desconhecido |
| Surge `Thing:esp32001` | a ESP32 publicou antes do provisionamento | provisione primeiro; remova a entidade e o dispositivo `Thing` |
| Atributo com nome curto (`t`, `x`) | campo publicado que não está no provisionamento | confira os `object_id` e o JSON publicado |
| `temperature` com aspas | número publicado entre aspas | publique `{"t": 24.5}`, sem aspas |
| Comando responde `404` | `PATCH` sem `?type=ClimateStation` | mantenha o `?type` na URL |
| Comando fica `PENDING` | a ESP32 não estava no ar (QoS 0, sem reenvio) | `docker compose start esp32-simulada` e mande de novo |
| `on_status = OK`, mas o relé não mudou | o dispositivo respondeu com erro | leia `on_info` e o `state` |
| Tópico vira `C:/Program Files/Git/…` | Git Bash convertendo a barra | `MSYS_NO_PATHCONV=1` ou PowerShell |
| O contexto "sumiu" na aula seguinte | outra pasta (outro volume) ou `down -v` | sempre `C:\pel220\fiware`; pare com `stop` |
