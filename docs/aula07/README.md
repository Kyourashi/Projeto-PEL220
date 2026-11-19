# Aula 7 — FIWARE II: Orion avançado e visualização no Grafana

**PEL 220 — Internet das Coisas e Gêmeos Digitais** · Centro Universitário FEI · Prof. Rafael Gomes Alves

Na Aula 6 você subiu as Etapas 1 a 4 da plataforma: o Orion guarda o **presente** da sala K501 e da ESP32. Hoje
você aprende a **organizar, consultar, atualizar e avisar** com o Orion em escala (tenants, caminhos, linguagem de
consulta, operadores atômicos, registros e subscrições) e leva o **passado** até a tela: o Cygnus grava o
histórico no MySQL e você monta, passo a passo, um painel no Grafana.

```
                    clima-externo:3010 (Etapa 5) ◀── registro ──┐
                                                                │
 ESP32 ─▶ mosquitto:1883 ─▶ iot-agent:4041 ─▶  orion:1026  ◀──┴──▶ mongo-db:27017
                                                   │
                                     subscrição    │  POST http://cygnus:5050/notify
                                                   ▼
                              cygnus:5050 (Etapa 6) ─▶ mysql-db:3306 ─▶ grafana:3000 (Etapa 7)
                                                                              ▲
                                                               você, no navegador (localhost:3000)
```

| Momento da aula | O que você faz | Onde |
|---|---|---|
| Retomada | **Reentrada**: Etapas 1 a 3 de volta ao ar | PowerShell + coleção da Base |
| Seção 1 | **C1 e C2**: tenants, caminhos, embutidos, caracteres proibidos | coleção desta aula |
| Seção 2 | **C3**: a linguagem de consulta, por inteiro | coleção desta aula |
| Seção 3 | **C4**: verbos e operadores atômicos; `concorrencia.py` | coleção desta aula + PowerShell |
| Seção 4 | **Etapa 5**: o clima do campus por um provedor; **C5**: subscrições | coleção da Base + desta aula + MQTTX |
| Seção 5 | **Etapa 6**: Cygnus + MySQL guardam o histórico | PowerShell + coleção da Base |
| Seção 6 | **Etapa 7**: o painel no Grafana, em seis passos | navegador + coleção da Base |
| Fim | **C6**: limpeza do tenant `pel220` | coleção desta aula |

Tudo o que aparece aqui foi executado em **16/11/2026** e conferido de novo em **18/11/2026**, a partir deste
pacote, com volumes vazios (Windows 11, Docker Desktop, Postman CLI 1.75). Identificadores, horários,
temperaturas e o clima mudam de uma máquina e de um dia para outro.

---

## Estrutura

```
aula07-orion-grafana.zip
├── fiware/                                             a plataforma (a mesma da Aula 6) → C:\pel220\fiware
│     ├── docker-compose.yml                            os dez serviços (Etapas 1 a 9) + 2 versões prontas
│     ├── mosquitto/  esp32_simulada/  clima/           broker, dispositivo, provedor de clima (Etapa 5)
│     ├── controlador/  controlador_pronto/             aplicação de controle (Aula 9): esqueleto e pronta
│     ├── grafana/                                      Grafana pronto (porta 3001), para comparar
│     ├── queries.txt                                   as consultas SQL dos painéis
│     └── CCM130 - Aula 10 - …postman_collection.json   coleção da Base: uma pasta por etapa
├── README.md                                           este roteiro
├── Material complementar - Orion avançado, Cygnus e Grafana.md (e .pdf)
│                                                       referência das APIs, do Cygnus, do Grafana e dos testes
├── PEL220 - Aula 07 - Orion avançado.postman_collection.json
│     ├── C1 a C5   tenants, embutidos, consultas, atualizações, subscrições (tenant pel220)
│     └── C6        limpeza do tenant pel220
└── ferramentas/
      ├── concorrencia.py                               ler-somar-gravar × $inc (seção 3)
      └── gerar_colecao.py                              gera a coleção da aula (para quem quiser alterá-la)
```

**A pasta `fiware/` é a mesma da Aula 6.** Se você já tem `C:\pel220\fiware` funcionando, não precisa copiá-la
de novo. Se precisar (pasta apagada, outro computador), copie para **`C:\pel220\fiware`**: é o nome da pasta que
liga você aos volumes (`fiware_mongo-db`, `fiware_mysql-db`, `fiware_grafana-data`). Copiar os arquivos por cima
não apaga dados; quem apaga é `docker compose down -v`.

---

## Onde executar

| O quê | Onde |
|---|---|
| `docker compose …`, `docker logs …`, `docker exec …` | **PowerShell** em `C:\pel220\fiware` |
| Reentrada e Etapas 5 a 7 | **Postman**, coleção da Base (pasta da etapa) |
| Pastas C1 a C6 | **Postman**, coleção desta aula |
| Assinar as notificações MQTT | **MQTTX**: Host `localhost`, Port `1883`, assinatura `pel220/#` |
| Grafana | **navegador**: `http://localhost:3000` |
| `concorrencia.py` | **PowerShell**, na pasta `ferramentas` (só Python, nada a instalar) |

A coleção da Base usa o tenant **`ccm130`** (a sala e a ESP32). A coleção desta aula usa o tenant **`pel220`**:
uma não mexe nos dados da outra.

---

## Antes de começar

1. **Docker Desktop aberto**: `docker version` mostra **Client** e **Server**.
2. **Imagens novas de hoje** (≈ 1,9 GB; baixe antes, se a rede for lenta):

    ```powershell
    docker pull quay.io/fiware/cygnus-ngsi:3.11.0
    docker pull mysql:8.0
    docker pull grafana/grafana:10.4.0
    docker pull python:3.12-slim
    ```

    O provedor de clima é **construído** na Etapa 5 (base `python:3.12-slim`, só biblioteca padrão). Ele consulta
    a API pública Open-Meteo; **sem internet**, responde valores simulados (`source = simulado`) e a aula segue.

3. **Postman**: **Import** da coleção desta aula (`PEL220 - Aula 07 - Orion avançado.postman_collection.json`).
   A da Base você já tem desde a Aula 6.
4. **MQTTX**: conexão `localhost:1883`; acrescente a assinatura **`pel220/#`** (é por ela que chegam as
   notificações da pasta C5).
5. **Portas livres**: 1026, 4041, 1883, 3010 (clima), 5050 e 5080 (Cygnus), 3306 (MySQL), 3000 (Grafana).

> **Nunca `docker compose up -d` sem nomes.** A ESP32 subiria antes do provisionamento e nasceria a entidade
> `Thing:esp32001`. Suba sempre pelo nome do serviço, na ordem das etapas.

---

## Reentrada — a pilha da Aula 6 de volta ao ar

```powershell
cd C:\pel220\fiware
docker compose up -d --wait orion          # ≈ 13 s: db-mongo e fiware-orion Healthy
docker compose up -d --wait iot-agent      # ≈ 8 s: mosquitto e fiware-iot-agent Healthy
```

**Postman › coleção da Base:** pasta **Etapa 1** e pasta **Etapa 2**. Se os volumes foram preservados, o grupo e
o dispositivo devolvem `409` (já existem) — os testes aceitam. Depois:

```powershell
docker compose up -d --build esp32-simulada
```

e a pasta **Etapa 3**. **Confira antes de seguir:** `docker compose ps` com orion e iot-agent `healthy`; no MQTTX,
uma mensagem a cada 5 s em `/json/ccm130/esp32001/attrs`.

---

## Seção 1 — Organizar o contexto (pastas C1 e C2)

**Postman › coleção desta aula › C1 - Tenants e caminhos.** Cria quatro entidades no tenant `pel220`: três no
andar 5 do prédio K e uma no andar 4. Elas são usadas até a pasta C5.

| id | type | `fiware-servicepath` | floor | capacity | color | temperature |
|---|---|---|---|---|---|---|
| `urn:ngsi-ld:Room:K501` | Room | `/predioK/andar5` | 5 | 40 | blue | 27,5 (± 0,5) |
| `urn:ngsi-ld:Room:K502` | Room | `/predioK/andar5` | 5 | 30 | yellow | 22 (± 2) |
| `urn:ngsi-ld:Room:K401` | Room | `/predioK/andar4` | 4 | 60 | black | — |
| `urn:ngsi-ld:Lab:K503` | Lab | `/predioK/andar5` | 5 | 25 | — | 31 (± 0,5) |

O que a C1 mostra, requisição a requisição:

| Requisição | Resposta |
|---|---|
| `GET /v2/entities` com `fiware-servicepath: /predioK` | `200 []` — caminho **exato** |
| … com `/predioK/#` | as 4 entidades — `#` inclui os subcaminhos |
| … com `/predioK/andar4,/predioK/andar5` | as 4 — lista de até 10 caminhos |
| … **sem** `fiware-servicepath` | as 4 — ler sem o cabeçalho equivale a `/#` |
| … com `/` | `[]` — só a raiz |
| … com `fiware-service: PEL220` | as 4 — o tenant não diferencia maiúsculas |
| … com um tenant que não existe | `200 []` — sem erro |
| `PATCH` na K502 **sem** `fiware-servicepath` | `404` — gravar sem o cabeçalho equivale a `/` |
| `POST` com `/predioK/#` | `400` — o curinga só vale em consultas |
| a mesma K501 criada também no andar 4 | `201`; depois, o `GET` por id devolve `409 TooManyResults` |

**C2 - Embutidos, expiração e caracteres proibidos.** `dateCreated` e `dateModified` só vêm quando pedidos pelo
nome (`attrs=dateCreated,dateModified,*`). Um alerta é criado com `dateExpires` 20 s à frente; a requisição
seguinte **espera 85 s** e confere que ele sumiu (o MongoDB remove pelo índice TTL, que roda a cada 60 s). Por
fim, os caracteres proibidos: `< > " ' = ; ( )` dão `400` em valores, descrições e ids.

**Compare e anote:** (1) por que `/predioK` devolve lista vazia, se as salas estão no prédio K? (2) o que o
`PATCH` sem cabeçalho devolve, e por quê? (3) em que banco do MongoDB essas entidades estão
(`docker exec db-mongo mongosh --quiet --eval "db.getMongo().getDBNames()"`)?

---

## Seção 2 — Consultar (pasta C3)

Todas as consultas levam `fiware-service: pel220` e `fiware-servicepath: /predioK/#`. Cada requisição confere o
conjunto exato de entidades devolvido.

| Consulta | Devolve |
|---|---|
| `q=floor==5;capacity>=30` | K501, K502 |
| `q=capacity==25..40` | K501, K502, K503 |
| `q=color==blue,black` | K501, K401 |
| `q=color!=blue,black` | só K502 (K503 não tem `color`) |
| `q=name~=^Lab` · `q=name~=lab` | K501, K503 · nada (diferencia maiúsculas) |
| `q=!temperature` | K401 |
| `q=tags==iot` | K501 |
| `mq=temperature.accuracy<1` | K501, K503 |
| `q=capacity>30\|floor==4` | `400`: não há OU entre condições diferentes |
| `orderBy=floor,!capacity` | K401, K501, K502, K503 |
| `limit=2&offset=1&options=count&orderBy=capacity` | K502, K501; `Fiware-Total-Count: 4` |
| `georel=near;maxDistance:1000&geometry=point&coords=-23.7245,-46.5793` | K501 (`coords` = latitude,longitude) |

---

## Seção 3 — Atualizar (pasta C4 e `concorrencia.py`)

**C4 - Atualizações** cria a porta `Door:K5` com um contador e passa pelos dez operadores atômicos
(`$inc`, `$mul`, `$max`, `$min`, `$push`, `$addToSet`, `$pull`, `$pullAll`, `$set`, `$unset`), conferindo o valor
depois de cada um. O operador vai no lugar do `value`:

```json
{ "count": { "type": "Number", "value": { "$inc": 1 } } }
```

Também estão lá, de propósito, as respostas de erro: `422` para `$inc` em atributo que não existe, `500` para
`{"$inc": "1"}`, o `PATCH` que preserva os metadados e o lote (`/v2/op/update`) que grava a parte válida mesmo
devolvendo `422 PartialUpdate`.

**O problema das duas portas**, com dois processos gravando ao mesmo tempo:

```powershell
cd <pasta do zip>\ferramentas
python concorrencia.py
```

```
ler-somar-gravar   esperado 400  contador 235  perdidas 165  (5.8 s)
$inc               esperado 400  contador 400  perdidas 0  (4.0 s)
```

O número de perdidas muda a cada execução (176 e 165 na preparação); a perda, não.

---

## Seção 4 — Buscar e avisar (Etapa 5 e pasta C5)

### Etapa 5 — o clima do campus entra no contexto

```powershell
docker compose up -d --build clima-externo
curl.exe http://localhost:3010/health
```

**Postman › Base › Etapa 5 - Dados externos:** cria o **registro** (o Orion passa a perguntar ao provedor pelos
atributos de `urn:ngsi-ld:WeatherObserved:FEI`), lê o clima pelo Orion e tenta uma subscrição sobre ele.

```powershell
docker logs clima-externo
# [clima] Orion perguntou: ['temperature', 'relativeHumidity', 'windSpeed', 'source', 'dateObserved']
#         de ['urn:ngsi-ld:WeatherObserved:FEI']
```

**Compare e anote:** (1) onde está o valor da temperatura: no MongoDB ou no provedor? (2) por que a subscrição
sobre o clima termina com `timesSent` zero? (3) o que seria preciso para o clima entrar no histórico?

### C5 — subscrições

**Antes:** MQTTX assinando `pel220/#`. A pasta cria a subscrição *Sala quente via MQTT* (salas `Room`, dispara
em `temperature`, condição `temperature>28`, notifica em `pel220/quente`) e altera a K501 passo a passo:

| Passo | Notifica? |
|---|---|
| subscrição criada (sala a 25 °C) | não: não há notificação inicial |
| 25 → 26 °C | não: 26 > 28 é falso |
| 26 → 29 °C | **sim** |
| 29 → 29 °C | não: o valor não mudou |
| `capacity` muda | não: fora de `condition.attrs` |
| `Lab:K503` a 32 °C | não: a subscrição pede `type: Room` |
| 29 → 30 °C | **sim** |
| 30 → 30 °C com `?options=forcedUpdate` | **sim** |

No MQTTX, cada **sim** chega como:

```json
{"subscriptionId":"…","data":[{"id":"urn:ngsi-ld:Room:K501","type":"Room","temperature":29,"name":"Laboratório K5-01"}]}
```

Depois, uma subscrição **HTTP com `localhost` na URL**: o status mostra `failsCounter` e
`lastFailureReason: Couldn't connect to server` — `localhost`, para o Orion, é o contêiner dele.

---

## Seção 5 — Guardar o passado (Etapa 6)

```powershell
docker compose up -d --wait cygnus         # ≈ 28 s: sobe também o MySQL
```

**Postman › Base › Etapa 6 - Histórico:** cria a subscrição para `http://cygnus:5050/notify` (`normalized`,
`throttling: 1`) e confere `timesSent` subindo e `lastSuccessCode` 200. Depois, olhe o que foi gravado:

```powershell
docker exec -it db-mysql mysql -uroot -p123
```

```sql
SHOW TABLES FROM ccm130;
SELECT recvTimeTs, recvTime, attrName, attrValue
  FROM ccm130.`urn_ngsi-ld_ClimateStation_ESP32001_ClimateStation`
  ORDER BY recvTimeTs DESC LIMIT 6;
```

Um banco por `fiware-service`, uma tabela por entidade, **uma linha por atributo e tudo em texto**:
`recvTimeTs` está em milissegundos e `attrValue` é texto. Daí o `/ 1000` e o `CAST` nas consultas do Grafana.
**Deixe a pilha publicando:** o painel precisa de alguns minutos de histórico.

---

## Seção 6 — O painel no Grafana (Etapa 7)

**Passo 1 — subir e entrar.**

```powershell
docker compose up -d grafana
```

Navegador: `http://localhost:3000`, usuário `admin`, senha `admin`, e **Skip** na troca de senha (se trocar,
ajuste a variável `grafanaPass` da coleção da Base).

**Passo 2 — a fonte de dados.** *Connections › Data sources › Add new data source › MySQL*:

| Campo | Valor | Por quê |
|---|---|---|
| Host URL | `mysql-db:3306` | quem acessa o banco é o contêiner do Grafana: nome do serviço, não `localhost` |
| Database name | `ccm130` | o banco é o `fiware-service` |
| Username / Password | `root` / `123` | do `docker-compose.yml` (senha de laboratório) |

**Save & test**, no fim da página: *Database Connection OK*.

**Passo 3 — histórico da temperatura.** *Dashboards › New › New dashboard › Add visualization*, fonte `mysql`.
Na tela de edição: editor **Code** (não *Builder*), *Format* **Time series**, cole a consulta do painel 1 de
`queries.txt`, **Run query**; à direita, tipo **Time series**, título e *Standard options › Unit › Celsius*;
**Apply**.

```sql
SELECT
  recvTimeTs / 1000 AS "time",                       -- milissegundos → segundos
  CAST(attrValue AS DECIMAL(6,1)) AS "temperatura"   -- texto → número
FROM `urn_ngsi-ld_ClimateStation_ESP32001_ClimateStation`
WHERE attrName = 'temperature'                       -- uma linha por atributo: escolha um
  AND $__unixEpochFilter(recvTimeTs / 1000)          -- só o período do seletor de tempo
ORDER BY recvTimeTs ASC
```

Sem o `CAST`, a coluna chega ao Grafana como texto e o painel mostra *Data is missing a number field*.

**Passo 4 — o presente e o relé.** *Add › Visualization*, duas vezes, com as consultas 2 e 3 de `queries.txt`:
**Stat** (o `LIMIT 1` dá o valor de agora; *Thresholds* 24 verde e 28 vermelho) e **State timeline** (sem
`CAST`: o valor é `ON` ou `OFF`; *Value mappings* ON → Ligado, OFF → Desligado). Mande um `on` e um `off` pela
pasta **Etapa 4** e veja os dois painéis mudarem juntos.

**Passo 5 — a média por minuto.** Mais uma visualização, **Bar chart**, com a consulta de análise de
`queries.txt` (`$__unixEpochGroupAlias(recvTimeTs / 1000, '1m')` agrupa em janelas de 1 minuto). Troque `'1m'`
por `'5m'` e compare.

**Passo 6 — terminar.** Período *Last 15 minutes*, atualização *5s*; engrenagem › *General* › *Tags*: **`aula10`**
(é a etiqueta que a coleção da Base procura); título e **Save**. Depois, **Postman › Base › Etapa 7 - Painéis no
Grafana**.

| Pergunta | Visualização |
|---|---|
| Como está agora? | Stat |
| Como evoluiu? | Time series |
| Quando esteve em cada estado? | State timeline |
| Qual o resumo por período? | Bar chart |

**Para comparar:** `docker compose up -d grafana-pronto` abre um painel já configurado em `http://localhost:3001`.

---

## Limpeza do tenant `pel220` (pasta C6)

Remove as subscrições e as entidades criadas pelas pastas C1 a C5. **Não toca no tenant `ccm130`**: a sala, a
ESP32, o histórico e o painel continuam.

---

## Para aprofundar (antes da Aula 8)

**Exercício:** acrescente ao painel a **umidade** (Time series) e um **Stat com a máxima do período**; crie uma
subscrição MQTT que avise em `pel220/umida` quando `humidity>70` (tenant `ccm130`, caminho `/`).

**Questão de pesquisa:** o Cygnus guarda uma linha por atributo, em texto. Quanto isso custa, em espaço e em
tempo de consulta, diante de um banco de séries temporais? Um parágrafo, com uma fonte.

**Marco do projeto (Aula 8):** o painel do grupo — três perguntas que ele responde, a visualização e a consulta
SQL de cada uma, sobre dados gravados pelo Cygnus a partir de uma subscrição que o grupo criou.

---

## Parar sem perder o histórico

```powershell
docker compose stop          # para tudo; contexto, histórico, fonte de dados e painel ficam nos volumes
docker compose down          # remove contêineres e rede; os volumes ficam
docker compose down -v       # APAGA os volumes: contexto, histórico e painel
```

**Reentrada na Aula 8:** suba até a Etapa 6 (`orion`, `iot-agent`, `esp32-simulada`, `cygnus`) e `grafana`;
confira a subscrição do Cygnus (pasta **Etapa 6**, último teste) e o painel salvo.

---

## Problemas comuns

| Sintoma | Causa | Solução |
|---|---|---|
| Lista vazia, sem erro | tenant ou caminho errado | confira `fiware-service` e `fiware-servicepath` |
| `PATCH` responde `404` | gravação sem `fiware-servicepath` vai para `/` | mande o caminho da entidade |
| `400 … wildcard # is not allowed` | `#` em criação, atualização ou DELETE | `#` só em consultas |
| `409 TooManyResults` | o mesmo id em dois caminhos | restrinja o caminho ou use `?type=` |
| `400 Invalid characters` / `forbidden characters` | `< > " ' = ; ( )` em valor, id ou descrição | troque o texto, ou use `TextUnrestricted` |
| `422` num `PATCH` | o atributo não existe | `POST …/attrs` para criar |
| `500` com mensagem do MongoDB | operador com argumento de tipo errado (`"$inc": "1"`) | número sem aspas |
| A subscrição nunca notifica | condição não satisfeita, atributo fora de `condition.attrs`, valor igual | leia o slide e o status (`timesSent`) |
| `failsCounter` subindo | consumidor fora do ar ou URL com `localhost` | `docker compose ps`; use `cygnus:5050` |
| `400 invalid attrsFormat` | `legacy`, de tutoriais antigos | use `normalized` |
| Nada chega no MQTTX | assinatura errada | assine `pel220/#` (sem barra inicial) |
| `source: simulado` | o contêiner do clima não alcança a internet | normal em rede bloqueada; a aula segue |
| `Table doesn't exist` | a tabela nasce com a primeira notificação | confira a subscrição; `SHOW TABLES FROM ccm130;` |
| *Save & test* falha | Host `localhost`, ou MySQL ainda subindo | `mysql-db:3306`; espere `healthy` |
| *Data is missing a number field* | faltou o `CAST`, ou editor em *Builder* | editor **Code** e `CAST(… AS DECIMAL(6,1))` |
| Painel vazio (*No data*) | período fora dos dados | *Last 15 minutes* |
| Datas em 1970 ou no futuro | faltou o `/ 1000` | `recvTimeTs / 1000 AS "time"` |
| Postman: `401` no Grafana | a senha do admin foi trocada | ajuste `grafanaPass` na coleção da Base |
| A requisição da C2 demora | ela espera 85 s de propósito | aguarde (é a expiração do alerta) |
