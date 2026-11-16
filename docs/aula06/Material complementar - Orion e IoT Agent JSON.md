# Material complementar — Orion e IoT Agent JSON na prática

**PEL 220 — Internet das Coisas e Gêmeos Digitais · Aula 6 — Introdução ao FIWARE: contexto e dispositivos**
Centro Universitário FEI · Prof. Rafael Gomes Alves

> **O que é.** Três coisas, escritas para o caso da aula (sala K501, ESP32 com DHT22 e relé, tenant `ccm130`):
> a **definição completa da plataforma** — os dez serviços do `docker-compose.yml`, os arquivos de apoio e como
> montá-la do zero; a referência das duas APIs da Aula 6 — a **API NGSI-v2 do Orion** e a **API de
> provisionamento e os tópicos MQTT do IoT Agent JSON**; e o **catálogo dos testes** que acompanham a aula: o que
> cada requisição das duas coleções faz, o que cada teste confere e por que ele existe. O roteiro passo a passo
> continua no `README.md` desta pasta; este material é para consultar durante a prática, revisar depois e
> reutilizar no projeto.

> **Tudo aqui foi executado.** Reexecução de **11/11/2026**, a partir de volumes vazios, com a pilha do
> `aula06-fiware-contexto.zip` (Orion 4.1.0; IoT Agent JSON 3.7.0 sobre a iotagent-node-lib 4.7.0; MongoDB 6.0;
> Mosquitto 2.0.18) num Windows 11 com Docker Engine 29.6.2, PowerShell 7.7 e Postman CLI 1.75.0:
> **81 requisições e 131 testes das duas coleções, zero falhas**, mais de **cem chamadas avulsas** às APIs e
> dezenas de passos de MQTT e Docker para os exemplos e os casos de erro deste material. A plataforma da seção 2 foi
> montada do zero a partir do texto deste documento (seção 2.7). As respostas são reais; identificadores (`_id`),
> horários e temperaturas mudam de uma máquina para outra.

## Sumário

1. [Como usar este material](#1-como-usar-este-material)
2. [A plataforma: definição e montagem](#2-a-plataforma-definição-e-montagem) — os dez serviços, o
   `docker-compose.yml` completo e comentado, os arquivos de apoio, montagem do zero, verificação, adaptação,
   versões prontas do controlador e do Grafana
3. [O caso da aula em uma página](#3-o-caso-da-aula-em-uma-página) — pilha, identificadores, modelo de dados
4. [A API NGSI-v2 do Orion](#4-a-api-ngsi-v2-do-orion) — convenções, entidades, consultas, atributos, lote,
   tipos, registros, erros
5. [O IoT Agent JSON: provisionamento e MQTT](#5-o-iot-agent-json-provisionamento-e-mqtt) — configuração,
   grupos, dispositivos, tópicos, comandos, erros e logs
6. [Os testes desenvolvidos](#6-os-testes-desenvolvidos) — as duas coleções, como rodar, catálogo teste a teste,
   testes complementares, como escrever os seus, limitações
7. [Cola de comandos (PowerShell)](#7-cola-de-comandos-powershell)
8. [Diagnóstico: do sintoma à causa](#8-diagnóstico-do-sintoma-à-causa)
9. [Glossário](#9-glossário)
10. [Referências](#10-referências)
- [Apêndice A — O código dos serviços construídos](#apêndice-a--o-código-dos-serviços-construídos)

---

## 1. Como usar este material

| Se você quer… | Vá para |
|---|---|
| montar a plataforma do zero e entender cada serviço e cada linha do Compose | seção 2 e Apêndice A |
| entender o caminho da medida e de onde vem cada atributo da ESP32 | seção 3 |
| escrever uma requisição ao Orion (consulta, atualização, lote) | seção 4 e a cola da seção 7 |
| provisionar um dispositivo novo ou entender por que a medida não chegou | seção 5 e a seção 8 |
| saber o que a coleção testa e rodar tudo pela linha de comando | seção 6 |
| testar o modelo de dados do seu projeto | seção 6.7 |

**Convenções.** Nas coleções do Postman, `{{orion}}` é `localhost:1026` e `{{iota}}` é `localhost:4041`; o tenant é
`fiware-service: ccm130` com `fiware-servicepath: /`. Os exemplos abaixo usam os mesmos nomes. Quando um exemplo
diz **"com tenant"**, ele leva esses dois cabeçalhos; quando diz **"tenant padrão"**, não leva nenhum (é o caso do
exemplo das lojas, pastas A da coleção da aula, que assim não interfere na Base).

**Onde executar.** `docker …` no **PowerShell**, na pasta `C:\pel220\fiware`; requisições HTTP no **Postman** (ou
com `Invoke-RestMethod`, seção 7); MQTT no **MQTTX** (`localhost:1883`). No **Git Bash**, tópicos que começam com
`/` viram caminhos do Windows — aconteceu de novo nesta reexecução (`/ccm130/#` virou
`C:/Program Files/Git/ccm130/#` e o assinante ficou mudo). Use `MSYS_NO_PATHCONV=1` antes do comando, ou o
PowerShell.

---

## 2. A plataforma: definição e montagem

A plataforma da disciplina é **um único `docker-compose.yml` com dez serviços**, montado em **nove etapas** ao longo
das Aulas 6 a 9: a cada aula sobem as peças novas, sem desmontar as anteriores. O mesmo arquivo traz ainda **duas
versões prontas**, opcionais: um controlador que comanda o relé sozinho e um Grafana com o painel já configurado
(seção 2.10). Esta seção é a definição completa —
o que cada serviço é, cada bloco do Compose, os arquivos de apoio — e o roteiro para **montar tudo do zero numa
pasta vazia**. Os arquivos vêm prontos na pasta `fiware/`, ao lado deste material: basta copiá-la para
`C:\pel220\fiware`. Também estão aqui (seções 2.3, 2.5 e 2.10 e Apêndice A), para quem quiser montar à mão e
entender cada linha.

> **Por que `ccm130` e "Aula 10" nos arquivos?** A plataforma nasceu como a Aula 10 da disciplina CCM130
> (Conectividade e IoT). Os nomes ficaram — tenant `ccm130`, imagens `ccm130/…`, coleção
> `CCM130 - Aula 10 - Fluxo de dados completo` —, e os comentários dos arquivos citam aulas daquela numeração. Na
> PEL 220, valem as etapas e as aulas da tabela abaixo.

### 2.1 Os dez serviços, as nove etapas e as quatro aulas

```
               Etapa 3                 Etapa 2              Etapa 2
            esp32-simulada ◀──MQTT──▶ mosquitto ◀──MQTT──▶ iot-agent
                                                               ▲
                                                               │ NGSI-v2 (medidas ↓, comandos ↑)
                                                               ▼
 clima-externo ◀── consulta encaminhada (registro) ───────── orion ◀──────▶ mongo-db
    Etapa 5                                                 Etapa 1         Etapa 1
                                                              │ ▲
                                  notificações  ┌─────────────┘ │
                              ┌─────────────────┤               │ PATCH de comando
                              ▼                 ▼               │
                            cygnus         controlador ─────────┘
                           Etapa 6           Etapa 8
                              │ SQL
                              ▼
                          mysql-db ◀──── SQL ──── grafana
                          Etapa 6                 Etapa 7
```

A ESP32 só fala MQTT; o IoT Agent é o único que traduz; o **Orion é o centro**: guarda o presente (no MongoDB),
pergunta ao provedor de clima quando alguém lê o clima, e avisa por subscrição quem precisa saber das mudanças — o
Cygnus, que grava o passado no MySQL para o Grafana, e o controlador, que decide e devolve comandos **pelo Orion**.

| Etapa | Aula | Serviço | Contêiner | Imagem | Porta no PC | Depende de | Pronto quando |
|---|---|---|---|---|---|---|---|
| 1 | 6 | `orion` | `fiware-orion` | `quay.io/fiware/orion:4.1.0` | 1026 | `mongo-db` saudável | `curl /version` responde |
| 1 | 6 | `mongo-db` | `db-mongo` | `mongo:6.0` | 27017 | — | `mongosh` responde ao ping |
| 2 | 6 | `iot-agent` | `fiware-iot-agent` | `quay.io/fiware/iotagent-json:3.7.0-distroless` | 4041 | `orion` e `mongo-db` saudáveis; `mosquitto` iniciado | healthcheck da própria imagem |
| 2 | 6 | `mosquitto` | `mosquitto` | `eclipse-mosquitto:2.0.18` | 1883 | — | (sem healthcheck) |
| 3 | 6 | `esp32-simulada` | `esp32-simulada` | `ccm130/esp32-simulada`, construída de `esp32_simulada/` | — | `mosquitto` | (sem healthcheck) |
| 4 | 6 | — | — | nada novo: comandos pelo Orion | — | — | — |
| 5 | 7 | `clima-externo` | `clima-externo` | `ccm130/clima-externo`, construída de `clima/` | 3010 | — | (sem healthcheck) |
| 6 | 7 | `cygnus` | `fiware-cygnus` | `quay.io/fiware/cygnus-ngsi:3.11.0` | 5050, 5080 | `mysql-db` saudável | `curl /v1/version` responde |
| 6 | 7 | `mysql-db` | `db-mysql` | `mysql:8.0` | 3306 | — | `mysqladmin ping` responde |
| 7 | 8 | `grafana` | `grafana` | `grafana/grafana:10.4.0` | 3000 | `mysql-db` saudável | (sem healthcheck) |
| 8 | 9 | `controlador` | `controlador` | `ccm130/controlador`, construída de `controlador/` | 5001 | `orion` | (sem healthcheck) |
| 9 | 8 e 9 | — | — | nada novo: indicadores no Grafana | — | — | — |
| 8 | 9 | `controlador-pronto` *(perfil `pronto`)* | `controlador-pronto` | `ccm130/controlador-pronto`, construída de `controlador_pronto/` | 5002 | `orion` | (sem healthcheck) |
| 7 e 9 | 8 e 9 | `grafana-pronto` *(perfil `pronto`)* | `grafana-pronto` | `grafana/grafana:10.4.0` | 3001 | `mysql-db` saudável | (sem healthcheck) |

As duas últimas linhas são as **versões prontas** (seção 2.10): pertencem ao perfil `pronto` e só sobem quando
chamadas pelo nome — `docker compose config --services` continua listando dez serviços.

**Imagens a baixar** (tamanho em disco, `docker images`) — baixe **antes** da aula, numa rede boa:

| Para | Imagens | Total |
|---|---|---|
| Etapas 1 a 4 (Aula 6) | `orion:4.1.0` 389 MB · `iotagent-json:3.7.0-distroless` 245 MB · `mongo:6.0` 1,1 GB · `eclipse-mosquitto:2.0.18` 21,5 MB · `python:3.12-slim` 180 MB (base das três imagens construídas) | ≈ 1,9 GB |
| Etapas 6 e 7 (Aulas 7 e 8) | `quay.io/fiware/cygnus-ngsi:3.11.0` · `mysql:8.0` · `grafana/grafana:10.4.0` | baixe antes da Aula 7 |

```powershell
docker compose pull --ignore-buildable     # na pasta da plataforma: baixa todas as imagens prontas
```

O `--ignore-buildable` pula as três imagens construídas (`ccm130/…`), que não existem em registro nenhum: são
geradas na sua máquina pelo `--build`, e a primeira construção da ESP32 baixa o `paho-mqtt` do PyPI. Sem internet
no laboratório, construa-as em casa e leve-as num arquivo (`docker save` / `docker load`, Aula 5).

### 2.2 A pasta da plataforma

```
C:\pel220\fiware\                        o nome "fiware" importa: vira o prefixo do projeto Compose
├── docker-compose.yml                   os dez serviços (seção 2.3)
├── mosquitto\mosquitto.conf             configuração do broker (seção 2.5)
├── esp32_simulada\
│   ├── Dockerfile                       imagem da ESP32 simulada (seção 2.5)
│   └── esp32_simulada.py                DHT22 + relé em software (Apêndice A.1)
├── clima\
│   ├── Dockerfile                       imagem do provedor de clima (seção 2.5)
│   └── provedor.py                      provedor de contexto NGSI-v2 (Apêndice A.2)
├── controlador\
│   ├── Dockerfile                       imagem da aplicação de controle (seção 2.5)
│   └── controlador.py                   esqueleto: a regra é completada na Aula 9 (Apêndice A.3)
├── controlador_pronto\
│   ├── Dockerfile                       imagem do controlador pronto (seção 2.10)
│   └── controlador.py                   regra pronta + subscrição automática (Apêndice A.4)
├── grafana\
│   ├── provisioning\datasources\mysql.yml    a fonte de dados MySQL (seção 2.10)
│   ├── provisioning\dashboards\paineis.yml   onde o Grafana procura os painéis (seção 2.10)
│   ├── paineis\painel_pronto.json      o painel pronto: sete visualizações (seção 2.10)
│   └── painel_pronto.png                como ele aparece (seção 2.10)
├── queries.txt                          consultas SQL de exemplo para os painéis (seção 2.5)
└── CCM130 - Aula 10 - Fluxo de dados completo.postman_collection.json   pastas Etapa 1 a Etapa 9
```

O Compose deriva tudo do nome da pasta: projeto `fiware`, rede `fiware_default`, volumes `fiware_mongo-db`,
`fiware_mosquitto-data`, `fiware_mysql-db` e `fiware_grafana-data`. **Mesma pasta da Aula 6 à Aula 9**: numa pasta
com outro nome, os volumes são outros e o contexto "some".

### 2.3 O `docker-compose.yml` completo

Este é o arquivo da pasta `fiware/`, inteiro. Os comentários (`#`) fazem parte dele e explicam as escolhas; a
seção 2.4 detalha cada uma. Os dois últimos serviços (perfil `pronto`) são as versões prontas da seção 2.10.

```yaml
# WARNING: Não faça deploy deste arquivo em produção; ele é apenas um exemplo para fins de aprendizado.
# CCM130 - Conectividade e IoT | Aula 10 - Fluxo de dados completo
#
# A solução é construída aos poucos: cada etapa da aula sobe só o que ela precisa.
#
#   Etapa 1  docker compose up -d orion                      Orion + MongoDB
#   Etapa 2  docker compose up -d iot-agent                  IoT Agent + Mosquitto
#   Etapa 3  docker compose up -d --build esp32-simulada     o dispositivo
#   Etapa 4  (nada novo: comandos pelo Orion)
#   Etapa 5  docker compose up -d --build clima-externo      provedor de contexto
#   Etapa 6  docker compose up -d cygnus                     Cygnus + MySQL
#   Etapa 7  docker compose up -d grafana                    painéis
#   Etapa 8  docker compose up -d --build controlador        aplicação de controle
#   Etapa 9  (nada novo: indicadores no Grafana)
#
# Versões prontas (perfil "pronto", para o professor ou para conferir):
#   docker compose up -d --build controlador-pronto      controle automático, porta 5002
#   docker compose up -d grafana-pronto                  painel configurado, porta 3001
# Para parar ou remover também as versões prontas, inclua o perfil:
#   docker compose --profile pronto stop     ·     docker compose --profile pronto down
#
# Não use "docker compose up -d" sem nomes no começo da aula: a ESP32 subiria antes do
# provisionamento (etapa 2), e a medida de um dispositivo desconhecido vira Thing:esp32001.
#
# Endereços: do seu computador use localhost:<porta>; entre contêineres use <nome do serviço>:<porta>.
#
# Antes de subir este ambiente, pare o da aula anterior (docker compose down na pasta da Aula 9):
# os contêineres têm os mesmos nomes e usam as mesmas portas.

services:

  # --- Etapa 1: gestão de contexto --------------------------------------------------
  orion:
    image: quay.io/fiware/orion:4.1.0
    hostname: orion
    container_name: fiware-orion
    depends_on:
      mongo-db:
        condition: service_healthy
    ports:
      - "1026:1026" # API NGSI v2
    command: -dbURI mongodb://mongo-db -logLevel DEBUG
    healthcheck:
      test: curl --fail -s http://orion:1026/version || exit 1
      interval: 5s
      timeout: 5s
      retries: 3

  mongo-db:
    image: mongo:6.0
    hostname: mongo-db
    container_name: db-mongo
    ports:
      - "27017:27017"
    volumes:
      - mongo-db:/data/db
    healthcheck:
      test: ["CMD", "mongosh", "--eval", "db.adminCommand('ping')"]
      interval: 5s
      timeout: 5s
      retries: 3
      start_period: 5s

  # --- Etapa 2: comunicação com o dispositivo ---------------------------------------
  iot-agent:
    image: quay.io/fiware/iotagent-json:3.7.0-distroless
    hostname: iot-agent-json
    container_name: fiware-iot-agent
    depends_on:
      orion:
        condition: service_healthy
      mongo-db:
        condition: service_healthy
      mosquitto:
        condition: service_started
    ports:
      - "4041:4041" # API de provisionamento
    environment:
      - IOTA_CB_HOST=orion
      - IOTA_CB_PORT=1026
      - IOTA_NORTH_PORT=4041
      - IOTA_REGISTRY_TYPE=mongodb
      - IOTA_LOG_LEVEL=DEBUG
      - IOTA_MONGO_HOST=mongo-db
      - IOTA_MONGO_PORT=27017
      - IOTA_MONGO_DB=iotagentjson
      - IOTA_MQTT_HOST=mosquitto
      - IOTA_MQTT_PORT=1883
      - IOTA_DEFAULT_TRANSPORT=MQTT
      - IOTA_PROVIDER_URL=http://iot-agent-json:4041
      - IOTA_DEFAULT_RESOURCE=/iot/json
      - IOTA_TIMESTAMP=true
      - IOTA_CB_NGSI_VERSION=v2
      - IOTA_AUTOCAST=true
    # Sem healthcheck aqui: a imagem já traz o seu. Um "curl" não funciona (a imagem distroless não tem curl).

  mosquitto:
    image: eclipse-mosquitto:2.0.18
    hostname: mosquitto
    container_name: mosquitto
    ports:
      - "1883:1883" # MQTT: IoT Agent, ESP32 e MQTTX
    volumes:
      - ./mosquitto/mosquitto.conf:/mosquitto/config/mosquitto.conf
      - mosquitto-data:/mosquitto/data

  # --- Etapa 3: o dispositivo -------------------------------------------------------
  esp32-simulada:
    # ESP32 com DHT22 e relé, em software. Acompanhe com: docker logs -f esp32-simulada
    # Para usar a placa real no lugar dela: docker compose stop esp32-simulada
    build: ./esp32_simulada
    image: ccm130/esp32-simulada
    container_name: esp32-simulada
    depends_on:
      - mosquitto
    environment:
      - DEVICE_ID=esp32001
      - APIKEY=ccm130
      - MQTT_HOST=mosquitto
      - MQTT_PORT=1883
      - INTERVALO=5

  # --- Etapa 5: dados externos ------------------------------------------------------
  clima-externo:
    # Provedor de contexto (proxy NGSI v2): clima atual do campus pela API Open-Meteo.
    # Sem internet, responde valores simulados (source = simulado). Teste: http://localhost:3010/health
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

  # --- Etapa 6: histórico -----------------------------------------------------------
  cygnus:
    # O Orion notifica http://cygnus:5050/notify e o Cygnus grava no MySQL:
    # um banco por fiware-service (ccm130) e uma tabela por entidade.
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
      - "3306:3306" # acesso direto: docker exec -it db-mysql mysql -uroot -p123
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

  # --- Etapa 7: painéis -------------------------------------------------------------
  grafana:
    # http://localhost:3000 (admin/admin). A fonte de dados e os painéis você cria pela interface.
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

  # --- Etapa 8: decisão -------------------------------------------------------------
  controlador:
    # Aplicação de controle: recebe notificações do Orion e comanda o relé (histerese).
    # ESQUELETO para os alunos: a regra (decidir) e a subscrição (pasta Etapa 8) são feitas na aula.
    # Depois de editar controlador/controlador.py: docker compose up -d --build controlador
    # Acompanhe: docker logs -f controlador  ·  status: http://localhost:5001/status
    build: ./controlador
    image: ccm130/controlador
    hostname: controlador
    container_name: controlador
    depends_on:
      - orion
    ports:
      - "5001:5001"
    environment:
      - ORION=http://orion:1026
      - SERVICE=ccm130
      - SERVICEPATH=/
      - LIGA=28
      - DESLIGA=24
      - ESPERA=10
      - PORTA=5001

  # --- Versões prontas (perfil "pronto") --------------------------------------------
  # Só sobem quando chamadas pelo nome; "docker compose up -d" sem nomes não as inclui.

  controlador-pronto:
    # Controlador PRONTO: a regra já implementada e a subscrição criada sozinha na partida.
    # Comanda o relé automaticamente a partir das medidas da ESP32 (ou de qualquer ClimateStation).
    #   docker compose up -d --build controlador-pronto
    # Acompanhe: docker logs -f controlador-pronto  ·  status: http://localhost:5002/status
    # Não deixe o esqueleto (já completado) e a versão pronta decidindo ao mesmo tempo.
    profiles: ["pronto"]
    build: ./controlador_pronto
    image: ccm130/controlador-pronto
    hostname: controlador-pronto
    container_name: controlador-pronto
    depends_on:
      - orion
    ports:
      - "5002:5002"
    environment:
      - ORION=http://orion:1026
      - SERVICE=ccm130
      - SERVICEPATH=/
      - LIGA=28
      - DESLIGA=24
      - ESPERA=10
      - PORTA=5002
      - NOTIFICAR_EM=http://controlador-pronto:5002/notify

  grafana-pronto:
    # Grafana PRONTO: fonte de dados MySQL e o painel da sala K501 já configurados (provisionamento).
    #   docker compose up -d grafana-pronto  ·  http://localhost:3001 (abre direto no painel, sem login;
    #   admin/admin para editar). Precisa do histórico: Etapa 6 (cygnus + subscrição) no ar.
    profiles: ["pronto"]
    image: grafana/grafana:10.4.0
    hostname: grafana-pronto
    container_name: grafana-pronto
    depends_on:
      mysql-db:
        condition: service_healthy
    ports:
      - "3001:3000"
    environment:
      - GF_AUTH_ANONYMOUS_ENABLED=true          # visitante só lê (Viewer)
      - GF_AUTH_ANONYMOUS_ORG_ROLE=Viewer
      - GF_DASHBOARDS_DEFAULT_HOME_DASHBOARD_PATH=/etc/grafana/paineis/painel_pronto.json
    volumes:
      - ./grafana/provisioning:/etc/grafana/provisioning:ro   # fonte de dados e provedor de painéis
      - ./grafana/paineis:/etc/grafana/paineis:ro             # o painel pronto (JSON)

volumes:
  mongo-db:
  mosquitto-data:
  mysql-db:
  grafana-data:
```

### 2.4 O que cada bloco do Compose faz

**Decisões que valem para todos os serviços**

| No arquivo | O que faz | Por quê |
|---|---|---|
| `image: quay.io/fiware/orion:4.1.0` | fixa a versão da imagem | a mesma plataforma em todas as máquinas e daqui a um ano; os comportamentos deste material são dessas versões (Aula 5: tag ainda é rótulo; digest é a identidade) |
| `hostname: orion` | nome do contêiner **dentro** da rede Docker | é por ele que os outros acham o serviço: `orion:1026`, `mongo-db`, `iot-agent-json:4041`, `mysql-db:3306`, `cygnus:5050` |
| `container_name: fiware-orion` | nome fixo do contêiner | para `docker logs fiware-orion`, `docker exec db-mongo …`; impede duas cópias da plataforma ao mesmo tempo |
| `ports: - "1026:1026"` | publica a porta no PC (`PC:contêiner`) | para o Postman, o MQTTX e o navegador; entre contêineres não precisa. Porta ocupada no PC? Mude só o número da esquerda |
| `depends_on:` com `condition: service_healthy` | ordem de partida **com prontidão** | o Orion só sobe quando o MongoDB responde; o IoT Agent, quando o Orion responde. Sem a condição, "subiu" não quer dizer "pronto" |
| `healthcheck:` | o teste que define "pronto" | é o que `docker compose up -d --wait <serviço>` espera e o que `docker compose ps` mostra como `(healthy)` |
| `volumes:` nomeados (fim do arquivo) | dados fora do contêiner | sobrevivem a `docker compose down` e ao `rm` do contêiner; só `down -v` os apaga |
| `build: ./esp32_simulada` + `image: ccm130/esp32-simulada` | constrói a imagem a partir da pasta e dá nome a ela | o código da ESP32 é seu; `--build` reconstrói depois de editar |
| `environment:` | configuração por variável | muda-se o comportamento sem mudar a imagem (Aula 5) |

**Etapa 1 — `orion` e `mongo-db`**

| Linha | Explicação |
|---|---|
| `command: -dbURI mongodb://mongo-db -logLevel DEBUG` | argumentos acrescentados ao ponto de entrada da imagem (`/usr/bin/contextBroker -fg -multiservice …`; o `-multiservice` é o que habilita os tenants): onde está o MongoDB — pelo nome do serviço — e log detalhado, que mostra o `Request forwarded` dos comandos |
| `healthcheck: curl --fail -s http://orion:1026/version` a cada 5 s | substitui o da imagem (a cada 60 s): `up --wait orion` termina em segundos |
| `mongo-db` › `ports: 27017:27017` | só para inspecionar o banco do PC; a plataforma não precisa dela |
| `mongo-db` › `volumes: mongo-db:/data/db` | entidades, grupos e dispositivos ficam no volume: é o que permite parar na Aula 6 e continuar na Aula 7 |
| `mongo-db` › `healthcheck: mongosh --eval "db.adminCommand('ping')"` | `start_period: 5s` dá tempo ao banco de iniciar antes de contar falhas |

**Etapa 2 — `iot-agent` e `mosquitto`**

| Linha | Explicação |
|---|---|
| `depends_on:` `orion` e `mongo-db` saudáveis; `mosquitto` só iniciado | o IoT Agent precisa do Orion e do banco prontos para registrar e guardar cadastros; o broker não tem healthcheck |
| `environment:` `IOTA_…` | uma variável por decisão — tabela completa na seção 5.1 (Orion, banco, broker, `IOTA_PROVIDER_URL`, `TimeInstant`) |
| sem `healthcheck:` | a imagem *distroless* não tem `curl`; vale o healthcheck da própria imagem (`node ./bin/healthcheck`), e `up --wait iot-agent` o respeita |
| `mosquitto` › `volumes: ./mosquitto/mosquitto.conf:/mosquitto/config/mosquitto.conf` | o único arquivo da pasta montado no contêiner (*bind mount*): editar o `.conf` e reiniciar o broker basta |
| `mosquitto` › `volumes: mosquitto-data:/mosquitto/data` | persistência do broker (mensagens retidas e sessões) |

**Etapa 3 — `esp32-simulada`**

| Linha | Explicação |
|---|---|
| `build: ./esp32_simulada` | usa o `Dockerfile` da pasta (seção 2.5); a primeira construção baixa o `paho-mqtt` do PyPI |
| `DEVICE_ID=esp32001`, `APIKEY=ccm130` | formam os tópicos `/json/ccm130/esp32001/attrs` e `/ccm130/esp32001/cmd`: **têm de bater** com o grupo e o dispositivo provisionados na Etapa 2 |
| `MQTT_HOST=mosquitto`, `MQTT_PORT=1883` | o broker pelo nome do serviço (de dentro da rede) |
| `INTERVALO=5` | uma medida a cada 5 s (o DHT22 real exige pelo menos 2 s) |

**Etapas 5 a 8 — o que entra nas próximas aulas**

| Serviço | Variáveis e portas | Papel |
|---|---|---|
| `clima-externo` (Etapa 5) | `PORTA=3010`, `LATITUDE`/`LONGITUDE` do campus, `CACHE=60` s, `MODO=api` (ou `simulado`, sem internet) | provedor de contexto: o Orion encaminha a ele as leituras de `WeatherObserved:FEI`, e ele responde com a Open-Meteo |
| `cygnus` (Etapa 6) | `5050` recebe as notificações do Orion; `5080` é a API de gestão; `CYGNUS_MYSQL_*` aponta para `mysql-db` | grava o histórico: um banco por `fiware-service` (`ccm130`), uma tabela por entidade |
| `mysql-db` (Etapa 6) | `MYSQL_ROOT_PASSWORD=123`, `MYSQL_ROOT_HOST=%`; volume `mysql-db` | o banco do histórico |
| `grafana` (Etapa 7) | `3000`; `admin`/`admin`; volume `grafana-data` | painéis; a fonte de dados e os painéis são criados pela interface (Aula 8) |
| `controlador` (Etapa 8) | `ORION`, `SERVICE`, `SERVICEPATH`, `LIGA=28`, `DESLIGA=24`, `ESPERA=10`, `PORTA=5001` | recebe notificações e comanda o relé pelo Orion (regra completada na Aula 9) |

**Versões prontas — `controlador-pronto` e `grafana-pronto`** (detalhes na seção 2.10)

| Linha | Explicação |
|---|---|
| `profiles: ["pronto"]` | o serviço só sobe quando chamado pelo nome (`up -d controlador-pronto`) ou com `--profile pronto`; não entra no `up` sem nomes nem na contagem de serviços |
| `controlador-pronto` › `ports: 5002:5002`, `PORTA=5002` | porta própria: convive com o esqueleto (5001) sem conflito de nome ou de porta |
| `controlador-pronto` › `NOTIFICAR_EM=http://controlador-pronto:5002/notify` | o endereço que ele mesmo registra na subscrição do Orion, pelo `hostname` |
| `grafana-pronto` › `ports: 3001:3000` | o Grafana pronto em http://localhost:3001; o dos alunos continua em 3000 |
| `grafana-pronto` › `GF_AUTH_ANONYMOUS_*` | quem abre a página vê o painel sem login, só leitura; `admin`/`admin` para editar |
| `grafana-pronto` › `GF_DASHBOARDS_DEFAULT_HOME_DASHBOARD_PATH` | o painel pronto é a página inicial |
| `grafana-pronto` › `volumes: ./grafana/provisioning` e `./grafana/paineis` (`:ro`) | provisionamento: na partida, o Grafana lê a fonte de dados e o painel desses arquivos — nada a configurar na interface |
| `grafana-pronto` sem volume de dados | cada recriação parte do zero e volta igual: a configuração está nos arquivos, não no banco do Grafana |

> **Só para laboratório.** O próprio arquivo avisa: *não faça deploy em produção*. MQTT anônimo, MySQL com
> `root`/`123`, Grafana com `admin`/`admin`, logs em DEBUG, todas as portas publicadas e nenhuma autenticação no
> Orion. Como proteger cada uma dessas portas é assunto da Aula 10.

**A regra de ouro: nunca `docker compose up -d` sem nomes.** Sem nomes, sobem os dez serviços de uma vez, e a ESP32
começa a publicar antes do provisionamento da Etapa 2: o IoT Agent autoprovisiona e nasce a entidade
`Thing:esp32001`. Suba sempre **por serviço** (`up -d --wait orion`, `up -d --wait iot-agent`, …), na ordem das
etapas.

### 2.5 Os arquivos de apoio

**`mosquitto/mosquitto.conf`**

```
persistence true
persistence_location /mosquitto/data/
log_dest stdout

# Broker local da plataforma: usado pelo IoT Agent e pelos clientes (MQTTX, ESP32).
# Na versão 2.x, sem "listener", o Mosquitto só aceita conexões de localhost.
listener 1883
allow_anonymous true
```

`persistence` guarda sessões e mensagens retidas no volume; `log_dest stdout` manda o log para `docker logs
mosquitto`; `listener 1883` abre a porta para fora do próprio contêiner (no Mosquitto 2.x, sem `listener`, só
`localhost` conecta — nem o IoT Agent conseguiria); `allow_anonymous true` dispensa usuário e senha (Aula 10).

**`esp32_simulada/Dockerfile`**

```dockerfile
# CCM130 - Conectividade e IoT | Aula 10 - ESP32 simulada (DHT22 + relé, por MQTT)
FROM python:3.12-slim

WORKDIR /app
RUN pip install --no-cache-dir paho-mqtt==2.1.0

COPY esp32_simulada.py .

# -u: sem buffer de saída, para o "docker logs -f" mostrar cada mensagem na hora
CMD ["python", "-u", "esp32_simulada.py"]
```

**`esp32_simulada/esp32_simulada.py`** — o código completo está no Apêndice A.1. O que importa para a plataforma é o
**contrato** que ele cumpre (e que uma ESP32 real precisa cumprir igual):

| O quê | Como |
|---|---|
| Medidas | publica `{"t": 26.4, "h": 58.1, "s": "OFF"}` em `/json/<APIKEY>/<DEVICE_ID>/attrs` a cada `INTERVALO` s, números sem aspas |
| Comandos | assina `/<APIKEY>/<DEVICE_ID>/cmd`; para cada chave do JSON recebido (`{"on": ""}`), executa |
| Resultado | publica `{"on": "OK - rele ligado"}` em `/json/<APIKEY>/<DEVICE_ID>/cmdexe` — texto sem `< > " ' = ; ( )` |
| Novo estado | publica `{"s": "ON"}` como medida comum, logo depois do comando |
| Física da sala | relé desligado: a temperatura tende a 29 °C; ligado (ventilador), a 22 °C |
| Conexão | `client_id` único (`esp32001-<pid>`); tenta de novo a cada 3 s se o broker ainda não subiu |

**`clima/Dockerfile`** e **`controlador/Dockerfile`** — só a biblioteca padrão do Python, nada a instalar:

```dockerfile
# CCM130 - Conectividade e IoT | Aula 10 - Provedor de contexto do clima (Open-Meteo)
# Só a biblioteca padrão do Python: nada a instalar.
FROM python:3.12-slim

WORKDIR /app
COPY provedor.py .

CMD ["python", "-u", "provedor.py"]
```

```dockerfile
# CCM130 - Conectividade e IoT | Aula 10 - Aplicação de controle (regra com histerese)
# Só a biblioteca padrão do Python. Depois de editar controlador.py:
#   docker compose up -d --build controlador
FROM python:3.12-slim

WORKDIR /app
COPY controlador.py .

CMD ["python", "-u", "controlador.py"]
```

**`queries.txt`** — consultas SQL de exemplo para os painéis do Grafana (Aulas 8 e 9). O Cygnus grava uma tabela por
entidade e tudo como texto, daí o `CAST` e o `/ 1000`; as macros `$__unixEpochFilter` e `$__unixEpochGroupAlias`
são do Grafana. As quatro primeiras visualizações do painel pronto (seção 2.10) usam exatamente estas consultas.

```sql
-- ============================================================================
-- CCM130 - Conectividade e IoT | Aula 10 - Consultas para os painéis do Grafana
-- ----------------------------------------------------------------------------
-- Fonte de dados: a sua, criada na etapa 7 (MySQL, banco ccm130). Editor em modo Code.
-- O Cygnus cria uma tabela por entidade e grava tudo como texto, por isso:
--   recvTimeTs / 1000                    milissegundos -> segundos
--   CAST(attrValue AS DECIMAL(6,1))      texto -> número
--
-- $__unixEpochFilter(x)                  x dentro do período escolhido no painel
-- $__unixEpochGroupAlias(x, '1m')        agrupa em janelas de 1 minuto (coluna time)
-- ============================================================================

-- ETAPA 7, painel 1 - HISTÓRICO: temperatura (Time series)
SELECT
  recvTimeTs / 1000 AS "time",
  CAST(attrValue AS DECIMAL(6,1)) AS "temperatura"
FROM `urn_ngsi-ld_ClimateStation_ESP32001_ClimateStation`
WHERE attrName = 'temperature'
  AND $__unixEpochFilter(recvTimeTs / 1000)
ORDER BY recvTimeTs ASC;

-- ETAPA 7, painel 2 - PRESENTE: última temperatura (Stat)
SELECT
  recvTimeTs / 1000 AS "time",
  CAST(attrValue AS DECIMAL(6,1)) AS "agora"
FROM `urn_ngsi-ld_ClimateStation_ESP32001_ClimateStation`
WHERE attrName = 'temperature'
ORDER BY recvTimeTs DESC
LIMIT 1;

-- ETAPA 7, painel 3 - HISTÓRICO: estado do relé (State timeline)
SELECT
  recvTimeTs / 1000 AS "time",
  attrValue AS "relé"
FROM `urn_ngsi-ld_ClimateStation_ESP32001_ClimateStation`
WHERE attrName = 'state'
  AND $__unixEpochFilter(recvTimeTs / 1000)
ORDER BY recvTimeTs ASC;

-- ETAPA 9 - ANÁLISE: média da temperatura por minuto (Bar chart)
SELECT
  $__unixEpochGroupAlias(recvTimeTs / 1000, '1m'),
  AVG(CAST(attrValue AS DECIMAL(6,1))) AS "média"
FROM `urn_ngsi-ld_ClimateStation_ESP32001_ClimateStation`
WHERE attrName = 'temperature'
  AND $__unixEpochFilter(recvTimeTs / 1000)
GROUP BY 1
ORDER BY 1;
```

O `provedor.py` (Apêndice A.2) responde a `POST …/op/query` — a consulta que o Orion encaminha pelo registro, o
mesmo mecanismo dos comandos da seção 4.8 — e a `GET /health`. O `controlador.py` (Apêndice A.3) é um **esqueleto**:
recebe as notificações e já sabe mandar o `PATCH` de comando, mas a função `decidir()` devolve sempre `None` até a
Aula 9.

### 2.6 Montar do zero, etapa a etapa

Tudo no **PowerShell**. Com a pasta `fiware\` em mãos, os passos 1 e 2 se resumem a copiá-la para
`C:\pel220\fiware`.

**1. Criar a pasta e as subpastas**

```powershell
New-Item -ItemType Directory -Force C:\pel220\fiware\mosquitto, C:\pel220\fiware\esp32_simulada, `
    C:\pel220\fiware\clima, C:\pel220\fiware\controlador | Out-Null
Set-Location C:\pel220\fiware
```

**2. Criar os arquivos** com o conteúdo das seções 2.3 e 2.5 e do Apêndice A, nos caminhos da seção 2.2 (no VS Code
ou no Bloco de Notas, salvando em UTF-8). Confira a definição antes de subir qualquer coisa:

```powershell
docker compose config --services
```

```
mysql-db
cygnus
mosquitto
esp32-simulada
mongo-db
orion
iot-agent
controlador
grafana
clima-externo
```

Dez nomes (a ordem muda de uma execução para outra), sem erro: o YAML está bem formado. Um erro de indentação aparece
aqui, com a linha (`L`) e a coluna (`C`). Com `container_name` do Orion recuado um espaço a menos:

```
go-yaml load error in parser (while parsing a block mapping) at L27.C3-L30.C4: did not find expected key
```

YAML só aceita **espaços** (nunca tabulação), e cada nível tem 2 espaços a mais que o de cima.

**3. Etapa 1 — o contexto**

```powershell
docker compose up -d --wait orion
Invoke-RestMethod http://localhost:1026/version | Select-Object -ExpandProperty orion | Select-Object version
```

**4. Etapa 2 — o IoT Agent e o broker**

```powershell
docker compose up -d --wait iot-agent
Invoke-RestMethod http://localhost:4041/iot/about
```

**5. Provisionar — a sala, o grupo e a ESP32** (o que as pastas Etapa 1 e Etapa 2 da coleção da Base fazem; pelo
Postman ou, sem ele, com este bloco):

```powershell
$T = @{ 'fiware-service' = 'ccm130'; 'fiware-servicepath' = '/' }
$J = 'application/json'

# a sala K501 (append: pode repetir)
$sala = '{"actionType": "append", "entities": [{"id": "urn:ngsi-ld:Room:K501", "type": "Room",
  "name": {"type": "Text", "value": "Laboratório K5-01"}, "capacity": {"type": "Number", "value": 40}}]}'
Invoke-RestMethod -Method Post http://localhost:1026/v2/op/update -Headers $T -ContentType $J -Body $sala

# o grupo de serviço (409 se já existir)
$grupo = '{"services": [{"apikey": "ccm130", "cbroker": "http://orion:1026",
  "entity_type": "Thing", "resource": "/iot/json"}]}'
Invoke-RestMethod -Method Post http://localhost:4041/iot/services -Headers $T -ContentType $J -Body $grupo

# a ESP32 (409 se já existir)
$esp = '{"devices": [{"device_id": "esp32001", "apikey": "ccm130",
  "entity_name": "urn:ngsi-ld:ClimateStation:ESP32001", "entity_type": "ClimateStation", "transport": "MQTT",
  "attributes": [{"object_id": "t", "name": "temperature", "type": "Number"},
                 {"object_id": "h", "name": "humidity", "type": "Number"},
                 {"object_id": "s", "name": "state", "type": "Text"}],
  "commands": [{"name": "on", "type": "command"}, {"name": "off", "type": "command"}],
  "static_attributes": [{"name": "refRoom", "type": "Relationship", "value": "urn:ngsi-ld:Room:K501"}]}]}'
Invoke-RestMethod -Method Post http://localhost:4041/iot/devices -Headers $T -ContentType $J -Body $esp
```

O PowerShell 7 envia o corpo em UTF-8 (o "ó" de "Laboratório" chega certo). Um `409` no grupo ou na ESP32 numa
segunda execução só quer dizer que o cadastro já existe.

**6. Etapa 3 — a ESP32 simulada**

```powershell
docker compose up -d --build esp32-simulada
docker logs --tail 3 esp32-simulada
Invoke-RestMethod "http://localhost:1026/v2/entities/urn:ngsi-ld:ClimateStation:ESP32001?options=keyValues&attrs=temperature,humidity,state,refRoom" -Headers $T
```

**7. Etapa 4 — um comando** (cola da seção 7) e, por fim, as pastas **Etapa 1 a Etapa 4** da coleção da Base: o
critério de "plataforma montada" é **16 requisições e 35 testes sem falha**.

**8. Etapas 5 a 9 — nas próximas aulas**, sempre na mesma pasta:

| Aula | Etapa | Comando | Depois, no Postman |
|---|---|---|---|
| 7 | 5 | `docker compose up -d --build clima-externo` | pasta Etapa 5 |
| 7 | 6 | `docker compose up -d --wait cygnus` (sobe o MySQL junto) | pasta Etapa 6 |
| 8 | 7 | `docker compose up -d grafana` → http://localhost:3000 | pasta Etapa 7 (depois de criar fonte de dados e painel) |
| 9 | 8 | `docker compose up -d --build controlador` | pasta Etapa 8 |
| — | prontos | `docker compose up -d --build controlador-pronto` e `docker compose up -d grafana-pronto` | nada: tudo automático (seção 2.10) |

### 2.7 Verificar a plataforma, serviço a serviço

| Serviço | Comando (PowerShell) | Resposta esperada |
|---|---|---|
| todos | `docker compose ps` | os serviços no ar; `orion`, `mongo-db`, `iot-agent`, `mysql-db` e `cygnus` com `(healthy)` |
| `orion` | `Invoke-RestMethod http://localhost:1026/version` | `version: 4.1.0` |
| `mongo-db` | `docker exec db-mongo mongosh --quiet --eval "db.adminCommand('ping')"` | `{ ok: 1 }` |
| `iot-agent` | `Invoke-RestMethod http://localhost:4041/iot/about` | `version: 3.7.0`, `libVersion: 4.7.0` |
| `mosquitto` + `esp32-simulada` | `docker exec mosquitto mosquitto_sub -v -t '/json/ccm130/#' -C 1` | uma medida em até 5 s |
| `clima-externo` | `Invoke-RestMethod http://localhost:3010/health` | `status: ok`, `source` `open-meteo` ou `simulado` |
| `mysql-db` | `docker exec db-mysql mysqladmin ping -h localhost -uroot -p123` | `mysqld is alive` |
| `cygnus` | `Invoke-RestMethod http://localhost:5080/v1/version` | `success: true` e a versão |
| `grafana` | `Invoke-RestMethod http://localhost:3000/api/health` | `database: ok` |
| `controlador` | `Invoke-RestMethod http://localhost:5001/status` | `limites: liga 28, desliga 24` |
| `controlador-pronto` | `Invoke-RestMethod http://localhost:5002/status` | `subscricao: criada` (ou `já existia`) e contadores `on`/`off` subindo |
| `grafana-pronto` | abrir http://localhost:3001 | o painel pronto, sem login |

> **Como esta seção foi conferida (11/11/2026).** Os oito arquivos da plataforma foram **extraídos deste
> documento** (seções 2.3 e 2.5 e Apêndice A), salvos com fim de linha CRLF — como o Bloco de Notas salva — e
> comparados um a um com os originais: idênticos (as versões prontas, acrescentadas depois, têm verificação
> própria na seção 2.10). Com eles, numa pasta vazia, os passos 2 a 7 da seção 2.6 foram
> seguidos ao pé da letra: `config --services` listou os dez serviços; `orion` ficou saudável em 12,9 s; o
> `iot-agent` também; o bloco de provisionamento em PowerShell criou sala, grupo e ESP32 (com o "ó" certo, e `409`
> na repetição); o Mosquitto carregou o `.conf` com CRLF sem reclamar; a ESP32 foi construída e publicou. Na
> coleção da Base: **Etapas 3 e 4, 7 requisições e 20 testes**, **Etapa 5, 6 e 11** e **Etapa 8.1, 4 e 8**, sem
> falhas. Os serviços `cygnus`, `mysql-db` e `grafana` (Etapas 6 e 7) **não** foram subidos nesta verificação:
> estão definidos no Compose acima e entram em uso nas Aulas 7 e 8.

### 2.8 Parar, voltar e recomeçar

| Comando | O que acontece | Quando usar |
|---|---|---|
| `docker compose stop` | para os contêineres; tudo fica | fim de cada aula |
| `docker compose start` | volta de onde parou | começo da aula seguinte (a ESP32 volta junto: o provisionamento já existe) |
| `docker compose down` | remove contêineres e rede; **os volumes ficam** | liberar portas para outra pilha |
| `docker compose down -v` | remove também os volumes: entidades, grupo, dispositivo, histórico e painéis **somem** | recomeçar do zero, de propósito |
| `docker compose up -d --build <serviço>` | reconstrói a imagem e recria o contêiner | depois de editar `esp32_simulada.py`, `provedor.py` ou `controlador.py` |
| `docker compose logs -f <serviço>` | acompanha o log | depurar (seção 8) |
| `docker compose --profile pronto stop` (ou `down`, `down -v`) | o mesmo, **incluindo** as versões prontas | sem `--profile pronto`, `stop` e `down` não tocam em `controlador-pronto` e `grafana-pronto` (conferido: continuaram rodando, e o `down` não conseguiu remover a rede) |

**Reentrada na Aula 7** (volume preservado): `docker compose up -d --wait orion`, `docker compose up -d --wait
iot-agent`, `docker compose up -d esp32-simulada`, e confira com as pastas Etapa 2 e Etapa 3 — na Etapa 2, dois
testes falham **de propósito** (`409` do dispositivo e "Ainda sem medidas"), porque tudo já está lá (seção 6.8).

### 2.9 Adaptar a plataforma ao projeto do grupo

Os identificadores aparecem em vários lugares; mudar um exige mudar os outros **juntos**:

| Se mudar… | Mude também |
|---|---|
| o tenant (`ccm130`) | os cabeçalhos de toda requisição e as variáveis `service` das coleções; `SERVICE` do controlador; o nome do banco no MySQL (o Cygnus cria um banco por tenant) |
| a chave (`apikey`) | o grupo, o dispositivo, `APIKEY` da ESP32 e os tópicos |
| o `device_id` | o dispositivo, `DEVICE_ID` da ESP32 e os tópicos |
| o id da entidade | `entity_name` do dispositivo, as consultas e as subscrições; o nome da tabela no MySQL (`queries.txt`) |
| uma porta ocupada no PC | só o número da **esquerda** em `ports:` e o endereço nas coleções; entre contêineres nada muda |
| o nome da pasta | nada no arquivo, mas a rede e os volumes passam a ter outro prefixo |

**Mais um dispositivo** não exige mexer no Compose: provisione-o (como no passo 5, com outros ids) e suba outra
instância da mesma imagem na rede da plataforma —
`docker run -d --name esp32002 --network fiware_default -e DEVICE_ID=esp32002 ccm130/esp32-simulada`.
**A ESP32 real** entra no lugar da simulada cumprindo o mesmo contrato (seção 2.5), com o broker no IP do
computador (`ipconfig`) e a porta 1883 liberada no firewall do Windows; pare a simulada antes, para não haver dois
`esp32001` escrevendo na mesma entidade.

### 2.10 As versões prontas: controlador automático e Grafana configurado

Duas peças das Aulas 8 e 9 têm uma **versão para os alunos desenvolverem** e uma **versão pronta**, no mesmo
`docker-compose.yml`:

| Peça | Para os alunos | Pronta |
|---|---|---|
| Controlador (Etapa 8) | `controlador` (porta 5001): esqueleto; a regra `decidir()` e a subscrição (pasta Etapa 8) são feitas na aula | `controlador-pronto` (porta 5002): regra implementada e subscrição criada **sozinha**: comanda o relé automaticamente a partir das medidas |
| Grafana (Etapas 7 e 9) | `grafana` (porta 3000): vazio; fonte de dados e painéis criados pela interface | `grafana-pronto` (porta 3001): fonte de dados e painel **já configurados** por provisionamento |

As versões prontas servem para o professor demonstrar o laço fechado, para os alunos compararem com o que
construíram e para recuperar uma aula que atrasou. **São o gabarito** da regra (Aula 9) e dos indicadores do desafio
(Etapa 9): distribua quando quiser que os alunos as vejam.

**Subir** (na pasta da plataforma, com as Etapas 1 a 3 no ar; o Grafana precisa também do histórico — Etapa 6, com
a subscrição do Cygnus):

```powershell
docker compose up -d --build controlador-pronto
docker logs -f controlador-pronto            # Ctrl+C para sair do log
docker compose up -d grafana-pronto          # e abra http://localhost:3001
```

#### O controlador pronto

O código completo está no Apêndice A.4; a imagem, em `controlador_pronto/Dockerfile`:

```dockerfile
# PEL 220 | Plataforma FIWARE, Etapa 8 - Controlador PRONTO (regra com histerese + subscrição automática)
# Só a biblioteca padrão do Python. Depois de editar controlador.py:
#   docker compose up -d --build controlador-pronto
FROM python:3.12-slim

WORKDIR /app
COPY controlador.py .

CMD ["python", "-u", "controlador.py"]
```

O que muda em relação ao esqueleto:

| | Esqueleto (`controlador/`) | Pronto (`controlador_pronto/`) |
|---|---|---|
| Regra `decidir()` | devolve sempre `None` (TODO da Aula 9) | histerese: `on` com ≥ 28 °C e relé não ligado; `off` com ≤ 24 °C e relé não desligado |
| Subscrição no Orion | criada pelo Postman (pasta Etapa 8) | criada **na partida**, se ainda não houver uma que notifique o seu endereço; tenta de novo a cada 5 s enquanto o Orion não responde |
| Quais dispositivos | os da subscrição | todas as `ClimateStation` do tenant (`idPattern: .*`): uma ESP32 nova é controlada sem mudar nada |
| Temperatura como texto (`"24.7"`) | — | convertida para número; sem valor válido, não decide |
| `GET /status` | limites, contadores, últimas decisões | o mesmo, mais o id e a situação da subscrição |
| Porta | 5001 | 5002 |

A subscrição que ele cria é a mesma da pasta Etapa 8 (formato `keyValues`, com `temperature` e `state`), mas
apontando para `http://controlador-pronto:5002/notify`. **Não deixe o esqueleto já completado e a versão pronta
decidindo ao mesmo tempo**: os dois mandariam comandos ao mesmo relé.

O log real, do zero (ESP32 publicando havia alguns minutos, com a sala já acima de 28 °C):

```
[controlador-pronto] Liga em >= 28.0 °C, desliga em <= 24.0 °C | notificações em http://controlador-pronto:5002/notify
[controlador-pronto] subscrição criada: 6af4d385fcc969831c03062c -> http://controlador-pronto:5002/notify
[controlador-pronto] urn:ngsi-ld:ClimateStation:ESP32001: 28.3 °C, relé OFF -> on (204)
[controlador-pronto] urn:ngsi-ld:ClimateStation:ESP32001: 23.9 °C, relé ON -> off (204)
[controlador-pronto] urn:ngsi-ld:ClimateStation:ESP32001: 28 °C, relé OFF -> on (204)
```

O primeiro `on` saiu 4 s depois da partida; o `off`, 55 s depois; o `on` seguinte, mais 80 s — um ciclo completo em
pouco mais de 2 minutos, com nenhum passo manual. Os horários do `/status` (`quando`) estão em UTC, o relógio do
contêiner.

#### O Grafana pronto

Na partida, o Grafana lê dois arquivos de provisionamento e cria a fonte de dados e o painel:

**`grafana/provisioning/datasources/mysql.yml`**

```yaml
# Grafana pronto (serviço grafana-pronto): a fonte de dados MySQL, criada sozinha na partida.
# É a mesma que os alunos criam pela interface na Etapa 7: o banco ccm130 que o Cygnus grava.
apiVersion: 1

datasources:
  - name: MySQL (histórico ccm130)
    uid: mysql-ccm130              # os painéis de grafana/paineis/ usam este uid
    type: mysql
    access: proxy
    url: mysql-db:3306             # o MySQL visto de dentro da rede Docker
    user: root
    jsonData:
      database: ccm130             # um banco por fiware-service, criado pelo Cygnus
      maxOpenConns: 10
    secureJsonData:
      password: "123"              # senha de laboratório (docker-compose.yml): não use em produção
    isDefault: true
    editable: false
```

**`grafana/provisioning/dashboards/paineis.yml`**

```yaml
# Grafana pronto (serviço grafana-pronto): carrega na partida os painéis de grafana/paineis/.
apiVersion: 1

providers:
  - name: paineis-prontos
    folder: PEL 220
    type: file
    disableDeletion: true
    allowUiUpdates: false          # o arquivo manda: mudanças pela interface não são gravadas
    options:
      path: /etc/grafana/paineis   # onde o docker-compose.yml monta a pasta grafana/paineis
```

**`grafana/paineis/painel_pronto.json`** — o painel, na pasta *PEL 220*, com as etiquetas `aula10`, `desafio` e
`pronto`, atualizado a cada 5 s, mostrando os últimos 15 minutos:

| # | Visualização | Tipo | Consulta |
|---|---|---|---|
| 1 | Temperatura agora | Stat (azul abaixo de 24 °C, verde, vermelho a partir de 28 °C) | `queries.txt`, painel 2 |
| 2 | Temperatura e os limites da regra | Time series, com faixas tracejadas em 24 e 28 °C | `queries.txt`, painel 1 |
| 3 | Relé da ESP32 | State timeline (Ligado / Desligado) | `queries.txt`, painel 3 |
| 4 | Média da temperatura por minuto | Bar chart | `queries.txt`, Etapa 9 |
| 5 | Acionamentos do relé | Stat | indicador 1, abaixo (`LAG`) |
| 6 | Tempo com o relé ligado | Gauge, em % | indicador 2 (`AVG`) |
| 7 | Temperatura no período | Stat: mínima, máxima e média | indicador 3 |

Os três indicadores (o desafio da Etapa 9), calculados no próprio SQL do MySQL 8:

```sql
-- Acionamentos do relé no período: um acionamento é um OFF seguido de ON (LAG compara com a linha anterior)
SELECT COUNT(*) AS "acionamentos"
FROM (
  SELECT attrValue,
         LAG(attrValue) OVER (ORDER BY recvTimeTs) AS anterior
  FROM `urn_ngsi-ld_ClimateStation_ESP32001_ClimateStation`
  WHERE attrName = 'state'
    AND $__unixEpochFilter(recvTimeTs / 1000)
) AS mudancas
WHERE attrValue = 'ON' AND anterior = 'OFF';

-- Tempo com o relé ligado, em %: fração das amostras ON (vale como tempo porque chegam a cada 5 s)
SELECT 100 * AVG(attrValue = 'ON') AS "tempo ligado"
FROM `urn_ngsi-ld_ClimateStation_ESP32001_ClimateStation`
WHERE attrName = 'state'
  AND $__unixEpochFilter(recvTimeTs / 1000);

-- Mínima, máxima e média da temperatura no período
SELECT
  MIN(CAST(attrValue AS DECIMAL(6,1))) AS "mínima",
  MAX(CAST(attrValue AS DECIMAL(6,1))) AS "máxima",
  AVG(CAST(attrValue AS DECIMAL(6,1))) AS "média"
FROM `urn_ngsi-ld_ClimateStation_ESP32001_ClimateStation`
WHERE attrName = 'temperature'
  AND $__unixEpochFilter(recvTimeTs / 1000);
```

![O painel pronto em http://localhost:3001, com o controlador pronto ligando e desligando o relé](fiware/grafana/painel_pronto.png)

*O painel pronto durante o teste: a temperatura sobe até 28 °C, o controlador liga o ventilador, ela cai até 24 °C, ele
desliga — dois acionamentos, relé ligado metade do tempo. Captura feita com o Grafana 13.2.4 (ver abaixo); no 10.4
fixado no Compose, as cores e fontes mudam um pouco.*

O painel é só leitura no `grafana-pronto` (`allowUiUpdates: false`): para mudar, edite o JSON e reinicie o
serviço, ou entre como `admin`/`admin`, salve uma cópia e trabalhe nela. Para usar o mesmo painel no Grafana dos
alunos, importe o JSON pela interface (*Dashboards › New › Import*) e escolha a fonte de dados MySQL criada na Etapa 7.

#### Como as versões prontas foram conferidas (11/11/2026)

Numa cópia da pasta `fiware/`, a partir de volumes vazios: Etapas 1 e 2 (**9 requisições, 15 testes**), 3 e 4 (**7,
20**) e 6 (**3, 5**) da coleção da Base, sem falhas; `controlador-pronto` criou a subscrição sozinho e fechou o ciclo
`on` → `off` → `on` do log acima; `grafana-pronto` subiu com a fonte de dados (`Database Connection OK`) e o painel
na pasta *PEL 220*, e as sete consultas devolveram dados. As pastas **Etapa 7, 8.2 e Etapa 9** da coleção, apontadas
para as versões prontas (`postman collection run … --env-var grafana=localhost:3001 --env-var
controlador=localhost:5002`), deram **13 requisições e 27 testes, zero falhas** — inclusive "O relé ligou e desligou
sozinho" e os testes de coerência de cada decisão. Nesta máquina não havia as imagens fixadas para as Etapas 6 e 7;
o teste usou as que estavam baixadas — **Cygnus 3.16.0, MySQL 8.4 e Grafana 13.2.4** — por um arquivo
`docker-compose.override.yml` só da cópia de teste. Os arquivos de provisionamento usam o formato `apiVersion: 1`,
o mesmo do Grafana 10.4.

---

## 3. O caso da aula em uma página

### 3.1 As Etapas 1 a 4 em funcionamento

```
 Postman ──── API NGSI-v2 (1026) ─────────────────▶ orion ◀──▶ mongo-db
    │                                                  ▲  │       (orion-ccm130, iotagentjson)
    └── provisionamento (4041) ──▶ iot-agent ── upsert ┘  │ registro: on/off → iot-agent-json:4041
                                       ▲  │                │
                  /json/ccm130/esp32001/attrs · /cmdexe    │ POST /op/update (comando encaminhado)
                                       │  ▼  /ccm130/esp32001/cmd
 MQTTX (você) ──▶ mosquitto:1883 ◀──▶ esp32-simulada
```

A definição de cada serviço (imagem, porta, dependências, configuração) está na seção 2; aqui, o que circula
entre eles nas Etapas 1 a 4.

**Dois nomes para o mesmo serviço.** Do seu computador: `localhost:<porta>`. De um contêiner para outro:
`<nome>:<porta>` — por isso o grupo de serviço usa `cbroker` = `http://orion:1026`, e o registro dos comandos aponta
para `http://iot-agent-json:4041` (o `hostname` do IoT Agent, configurado em `IOTA_PROVIDER_URL`).

Nesta reexecução, `docker compose up -d --wait orion` levou **13,1 s** e `… iot-agent`, **7,7 s** (imagens já
baixadas). Memória com as Etapas 1 a 4 no ar (`docker stats`): IoT Agent 120 MiB, MongoDB 76 MiB, ESP32 13 MiB,
Orion 8 MiB, Mosquitto 4 MiB — **≈ 220 MiB**. Na preparação dos slides, a mesma medida deu ≈ 192 MiB: o número
varia com o tempo de uso, mas a ordem de grandeza e a leveza do Orion se repetem.

### 3.2 Os identificadores do caso

| O quê | Valor | Onde aparece |
|---|---|---|
| Tenant | `fiware-service: ccm130` · `fiware-servicepath: /` | cabeçalhos de toda requisição da Base; banco `orion-ccm130` |
| Chave do grupo (`apikey`) | `ccm130` | grupo, dispositivo e 2º nível dos tópicos |
| `resource` | `/iot/json` | grupo de serviço (parte da chave do grupo) |
| `device_id` | `esp32001` | dispositivo e 3º nível dos tópicos |
| Entidades | `urn:ngsi-ld:Room:K501` (`Room`) · `urn:ngsi-ld:ClimateStation:ESP32001` (`ClimateStation`) | Orion |
| Medidas | `/json/ccm130/esp32001/attrs` | ESP32 → IoT Agent |
| Comandos | `/ccm130/esp32001/cmd` (**sem** `/json`) | IoT Agent → ESP32 |
| Resultado dos comandos | `/json/ccm130/esp32001/cmdexe` | ESP32 → IoT Agent |
| Bancos no MongoDB | `orion` (tenant padrão: lojas) · `orion-ccm130` (Base) · `iotagentjson` (`groups`, `devices`, `commands`) | `db-mongo` |

### 3.3 O modelo de dados e a origem de cada atributo

| Entidade | Atributo | `type` | Exemplo lido no Orion | Origem | Quem escreve |
|---|---|---|---|---|---|
| Room:K501 | `name` | Text | `"Laboratório K5-01"` | Etapa 1 (Postman) | a aplicação |
| | `capacity` | Number | `40` | Etapa 1 | a aplicação |
| ClimateStation:ESP32001 | `temperature` | Number | `24.5` | medida `t` | IoT Agent (upsert) |
| | `humidity` | Number | `61` | medida `h` | IoT Agent |
| | `state` | Text | `"OFF"` | medida `s` | IoT Agent |
| | `refRoom` | Relationship | `"urn:ngsi-ld:Room:K501"` | `static_attributes` do provisionamento | IoT Agent, junto com **toda** medida |
| | `TimeInstant` | DateTime | `"2026-11-11T19:12:31.576Z"` | `IOTA_TIMESTAMP=true` | IoT Agent (também como metadado de cada atributo) |
| | `on`, `off` | command | `""` | `commands` do provisionamento | existem pelo **registro** (seção 4.8) |
| | `on_status`, `off_status` | commandStatus | `"PENDING"` → `"OK"` | ciclo do comando | IoT Agent |
| | `on_info`, `off_info` | commandResult | `"OK - rele ligado"` | texto publicado no `cmdexe` | IoT Agent |

O relacionamento vai **do filho para o pai** (`ClimateStation → refRoom → Room`). Do filho ao pai, lê-se o atributo;
do pai aos filhos, filtra-se com `q=refRoom==urn:ngsi-ld:Room:K501` (seção 4.4).

---

## 4. A API NGSI-v2 do Orion

### 4.1 Convenções que valem para toda requisição

| Regra | Detalhe conferido |
|---|---|
| **Endereço** | `http://localhost:1026` do PC; `http://orion:1026` de dentro da rede Docker |
| **Tenant** | `fiware-service` (letras, números e `_`; maiúsculas são aceitas e tratadas como minúsculas — `CCM130` achou a K501) e `fiware-servicepath` (começa com `/`) |
| **Tenant inválido** | `ccm-130` → `400 bad character in tenant name - only underscore and alphanumeric characters are allowed`; servicepath `campus` → `400 Only /absolute/ Service Paths allowed [a service path must begin with /]` |
| **Sem tenant** | a requisição vai ao tenant padrão (banco `orion`): a K501 responde `404`, sem nenhum aviso de que está em outro tenant |
| **`Content-Type`** | `application/json` **só** em POST, PATCH e PUT com corpo. Em GET e DELETE o cabeçalho é recusado: `400 Orion accepts no payload for GET/DELETE requests. HTTP header Content-Type is thus forbidden` (X2) |
| **Paginação** | padrão de **20** entidades por resposta; máximo **1000** (`limit=1001` → `400 Bad pagination limit: /1001/ [max: 1000]`) |
| **Texto** | o Orion recusa `< > " ' = ; ( )` nos valores (`400 Invalid characters in attribute value`, X6) e espaços nos nomes (`400 Invalid characters in attribute name`) |
| **Sem validação semântica** | o Orion não confere `value` contra `type`, nem convenções de nome, nem se o alvo de um `Relationship` existe |

**As três representações.** A mesma entidade, três tamanhos (medidos nesta reexecução):

| `options` | O que vem | Store:001 | ESP32001 (depois da 1ª medida) |
|---|---|---|---|
| (nenhum: normalizado) | `type`, `value` e `metadata` de cada atributo | 396 B | 767 B |
| `keyValues` | só nome e valor | 269 B | 207 B |
| `values` (com `attrs`) | só os valores, na ordem de `attrs` | 148 B (`name,address`) | 15 B (`[24.5, 61, "OFF"]`) |

```json
// GET /v2/entities/urn:ngsi-ld:ClimateStation:ESP32001   (com tenant) — normalizado, trecho
{
  "id": "urn:ngsi-ld:ClimateStation:ESP32001",
  "type": "ClimateStation",
  "TimeInstant": {"type": "DateTime", "value": "2026-11-11T19:12:31.576Z", "metadata": {}},
  "temperature": {"type": "Number", "value": 24.5,
                  "metadata": {"TimeInstant": {"type": "DateTime", "value": "2026-11-11T19:12:31.576Z"}}},
  "refRoom": {"type": "Relationship", "value": "urn:ngsi-ld:Room:K501",
              "metadata": {"TimeInstant": {"type": "DateTime", "value": "2026-11-11T19:12:31.576Z"}}},
  "on": {"type": "command", "value": "", "metadata": {}},
  …
}

// GET …?options=keyValues — o mesmo instante
{"id": "urn:ngsi-ld:ClimateStation:ESP32001", "type": "ClimateStation",
 "TimeInstant": "2026-11-11T19:12:31.576Z", "humidity": 61, "refRoom": "urn:ngsi-ld:Room:K501",
 "state": "OFF", "temperature": 24.5, "on": "", "off": ""}
```

### 4.2 Mapa dos recursos

| Recurso | Verbos | Para quê | Pastas |
|---|---|---|---|
| `/version` | GET | versão e saúde (healthcheck do Compose) | Etapa 1, A1 |
| `/v2/entities` | GET · POST | listar e filtrar · criar (`?options=upsert`: cria ou atualiza) | A1, A2, A3 |
| `/v2/entities/{id}` | GET · DELETE | ler · remover (`?type=` quando houver ambiguidade ou registro) | A2, A4 |
| `/v2/entities/{id}/attrs` | GET · POST · PATCH · PUT | ler · acrescentar · atualizar existentes · substituir todos | A4, Etapa 4 |
| `/v2/entities/{id}/attrs/{a}` | GET · PUT · DELETE | um atributo inteiro | A4 |
| `/v2/entities/{id}/attrs/{a}/value` | GET · PUT | só o valor (`PUT` com `Content-Type: text/plain`) | A3, A4 |
| `/v2/op/update` | POST | lote: `append`, `appendStrict`, `update`, `replace`, `delete` | Etapa 1, A3, A5, A6 |
| `/v2/op/query` | POST | consulta com corpo JSON | seção 4.4 |
| `/v2/types`, `/v2/types/{t}` | GET | tipos existentes, seus atributos e contagem | seção 4.7 |
| `/v2/registrations` | GET · POST · DELETE | provedores de contexto (aqui, criados pelo IoT Agent) | Etapa 2 |
| `/v2/subscriptions` | GET · POST · PATCH · DELETE | notificações — **Aula 7** (nesta aula, `GET` devolve `[]`) | — |

### 4.3 Entidades: criar, ler, remover

**Criar uma entidade** — `POST /v2/entities` (A1):

```http
POST /v2/entities HTTP/1.1
Host: localhost:1026
Content-Type: application/json

{"id": "urn:ngsi-ld:Store:001", "type": "Store",
 "name": {"type": "Text", "value": "Bösebrücke Einkauf"},
 "location": {"type": "geo:json", "value": {"type": "Point", "coordinates": [13.3986, 52.5547]}},
 "address": {"type": "PostalAddress", "value": {"streetAddress": "Bornholmer Straße 65",
             "addressLocality": "Prenzlauer Berg", "addressRegion": "Berlin", "postalCode": "10439"}}}
```

```
201 Created
Location: /v2/entities/urn:ngsi-ld:Store:001?type=Store
```

| Variante | Resposta conferida | Quando usar |
|---|---|---|
| `POST /v2/entities` com id que já existe | `422 {"error":"Unprocessable","description":"Already Exists"}` (A4) | nunca de propósito: é o erro de quem roda a criação duas vezes |
| `POST /v2/entities?options=upsert` | `204` + `Location` (cria se não existe, atualiza se existe) | carga idempotente; é o que o IoT Agent usa a cada medida |
| `POST /v2/op/update` com `actionType: append` | `204` (Etapa 1, sala K501) | criar ou atualizar várias de uma vez; dá para repetir |
| `POST` **sem** `type` | `201` com `Location: …?type=Thing`; o atributo recebe tipo inferido do JSON (`21` → `Number`) (X1) | evite: modelo sem tipo não se consulta por tipo |
| `POST` sem corpo | `411 ContentLengthRequired` | — |
| JSON malformado | `400 {"error":"ParseError","description":"Errors found in incoming JSON buffer"}` | confira vírgulas e aspas |

**Ler** — `GET /v2/entities/{id}` (normalizado), com `?options=keyValues`, `?attrs=a,b` para recortar, `?type=T`
quando o id não basta. `GET …/attrs/{a}` traz um atributo; `GET …/attrs/{a}/value`, só o valor (`50` para
`maxCapacity`; `"Laboratório K5-01"`, com aspas, para um `Text`).

**Remover** — `DELETE /v2/entities/{id}` → `204`; um segundo `GET` → `404`
`{"error":"NotFound","description":"The requested entity has not been found. Check type and id"}` (A4).

> **Sem integridade referencial.** Apagar a `Store:001` deixa as prateleiras com `refStore` apontando para um id
> que não existe. Quem apaga o pai cuida dos filhos.

### 4.4 Consultas: `GET /v2/entities` e a linguagem `q`

Cada linha foi executada; as que têm pasta entre parênteses são testes das coleções.

| Parâmetro | Exemplo | Resultado conferido |
|---|---|---|
| `type` | `?type=Store&options=keyValues` | as duas lojas (A2) |
| `attrs` | `?type=Store&attrs=name&options=keyValues` | só `id`, `type` e `name` (A2) |
| `q` igualdade (texto) | `?type=Store&q=name=='Checkpoint Markt'` | Store:002 (A2) |
| `q` em subatributo | `?type=Store&q=address.addressLocality=='Kreuzberg'` | Store:002 (A2) |
| `q` comparação | `?type=Product&q=price>1000` | 3 produtos (A3) |
| `q` lista | `?type=Product&q=price==99,1099` | Product:001 e 002 |
| `q` faixa | `?type=Product&q=price==1000..2000` | 002 (1099) e 003 (1499) |
| `q` padrão | `?type=Product&q=name~=Wine` | Red Wine e White Wine |
| `q` E lógico (`;`) | `?type=Product&q=size==M;price>1200` | só White Wine |
| `q` unário (existe) | `?type=Store&q=address` | as duas lojas (X5) |
| `q` unário (não existe) | `?type=Store&q=!address` | `[]` — nenhuma loja **sem** `address` (X5) |
| `q` em relacionamento | `?type=Shelf&q=refStore==urn:ngsi-ld:Store:001` | 3 prateleiras (A3) |
| `q` sem `type` | `?q=refRoom==urn:ngsi-ld:Room:K501` (com tenant) | qualquer tipo que tenha `refRoom`: a ESP32001 |
| `mq` (metadado) | `?type=Teste&mq=temperature.unitCode==CEL` | a entidade cujo `temperature` tem `unitCode` CEL |
| `georel` | `?type=Store&georel=near;maxDistance:1500&geometry=point&coords=52.5162,13.3777` | só Store:002, a menos de 1,5 km (A2) |
| `idPattern` | `?idPattern=^urn:ngsi-ld:Shelf:unit00[12]` | unit001 e unit002 |
| `orderBy` | `?type=Product&orderBy=!price` | decrescente: 5000, 1499, 1099, 99 (`!` inverte) |
| `limit`, `offset`, `options=count` | `?type=Store&limit=1&offset=1&options=count` | 1 entidade; cabeçalho `Fiware-Total-Count: 2` (A2) |
| `metadata` | `/Store:001?attrs=name&metadata=dateCreated,dateModified` | datas como metadado do atributo (A2) |
| atributos embutidos | `?attrs=dateCreated,dateModified,capacity` | datas como atributos; sem pedir, não vêm (X4) |

**Atenção a três detalhes.** (1) Em `georel`, `coords` é `latitude,longitude`; dentro do `geo:json`, as coordenadas
são `[longitude, latitude]`. (2) Um valor gravado como texto não entra em comparação numérica: com
`capacity: "25"`, `q=capacity>20` devolve `[]` (X3). (3) Não há OU entre condições de atributos diferentes; a lista
(`price==99,1099`) é o OU dentro do mesmo atributo.

**A mesma consulta com corpo** — `POST /v2/op/query` (útil quando a URL fica longa):

```json
POST /v2/op/query?options=keyValues
{"entities": [{"idPattern": ".*", "type": "Product"}],
 "attrs": ["name", "price"],
 "expression": {"q": "price>1000"}}
```

Resposta (`200`): Red Wine (1099), White Wine (1499) e Vodka (5000) — o mesmo que `GET ?type=Product&q=price>1000`.

### 4.5 Atributos: acrescentar, atualizar, substituir, remover

| Operação | Requisição | Resposta conferida |
|---|---|---|
| Acrescentar (ou atualizar) | `POST /v2/entities/{id}/attrs` `{"category": {"type": "Text", "value": "beverage"}}` | `204` (A4) |
| Atualizar o que **existe** | `PATCH /v2/entities/{id}/attrs` `{"price": {"type": "Number", "value": 249}}` | `204` (A4) |
| `PATCH` em atributo novo | `PATCH …/Room:K501/attrs` `{"hasProjector": …}` | `422 do not exist: urn:ngsi-ld:Room:K501 - [ hasProjector ]` — use `POST …/attrs` |
| Substituir **todos** | `PUT /v2/entities/{id}/attrs` com `name` e `price` | `204`; `size` e `category` **somem** (A4) |
| Trocar só o valor | `PUT …/Shelf:unit001/attrs/maxCapacity/value` com corpo `55` e `Content-Type: text/plain` | `204`; o atributo fica `{"type": "Number", "value": 55}` |
| Remover um atributo | `DELETE /v2/entities/{id}/attrs/price` | `204` (A4) |
| Comando (encaminhado) | `PATCH …/ESP32001/attrs?type=ClimateStation` `{"on": {"type": "command", "value": ""}}` | `204` (Etapa 4; seção 5.6) |
| Comando não provisionado | `PATCH …?type=ClimateStation` `{"toggle": {"type": "command", "value": ""}}` | `422 do not exist: urn:ngsi-ld:ClimateStation:ESP32001/ClimateStation - [ toggle ]` |

### 4.6 Operações em lote: `POST /v2/op/update`

```json
{"actionType": "append",
 "entities": [
   {"id": "urn:ngsi-ld:Room:K501", "type": "Room",
    "name": {"type": "Text", "value": "Laboratório K5-01"},
    "capacity": {"type": "Number", "value": 40}}]}
```

| `actionType` | Faz | Se o alvo já existe / não existe | Conferido |
|---|---|---|---|
| `append` | cria a entidade ou acrescenta e atualiza atributos | atualiza; cria | `204` (Etapa 1, A3, A5) |
| `appendStrict` | só acrescenta | atributo que já existe → `422 one or more of the attributes in the request already exist: … - [ a ]` | A5 |
| `update` | só atualiza atributos existentes | — | `204` (A5) |
| `replace` | substitui todos os atributos de cada entidade | os não enviados somem (Cider perde `size`) | A5 |
| `delete` | remove as entidades listadas (só `id` e `type`) | inexistente → `404 do not exist: urn:ngsi-ld:Store:999/Store - [entity itself]`; se só parte existe, `422 PartialUpdate` e as existentes são removidas | A5, A6 |

### 4.7 Tipos: `GET /v2/types`

```json
// GET /v2/types (com tenant, depois da Etapa 1)
[{"type": "Room", "attrs": {"capacity": {"types": ["Number"]}, "name": {"types": ["Text"]}}, "count": 1}]

// GET /v2/types?options=values (tenant padrão, com as lojas)
["InventoryItem", "Product", "Shelf", "Store"]
```

Bom para descobrir o que existe num Orion que você não conhece — e para flagrar o mesmo atributo com dois tipos
(um `capacity` em `Number` e outro em `Text` apareceria com `"types": ["Number", "Text"]`).

### 4.8 Registros: a entidade que existe "por procuração"

Ao provisionar um dispositivo **com comandos**, o IoT Agent cria no Orion um **registro de provedor de contexto**:

```json
// GET /v2/registrations (com tenant), logo depois da Etapa 2
[{"id": "6af4be162bbd9c0b770d564a",
  "dataProvided": {"entities": [{"id": "urn:ngsi-ld:ClimateStation:ESP32001", "type": "ClimateStation"}],
                   "attrs": ["on", "off"]},
  "provider": {"http": {"url": "http://iot-agent-json:4041"},
               "supportedForwardingMode": "all", "legacyForwarding": false},
  "status": "active"}]
```

Consequências, todas verificadas:

- **Antes da primeira medida**, `GET …/ESP32001?options=keyValues` responde `200` com
  `{"id": …, "type": "ClimateStation", "on": "", "off": ""}` — mas o MongoDB (`orion-ccm130.entities`) só tem a
  `Room:K501`. A entidade existe por procuração; nasce no banco com a primeira medida (upsert do IoT Agent).
- **O registro é por id E tipo.** Por isso o `PATCH` de comando sem `?type=` responde `404` antes da primeira medida
  (X7: `{"error":"NotFound","description":"The requested entity has not been found. Check type and id"}`).
- **O Orion encaminha o comando**: no log, `Request forwarded (regId: 6af4be16…): POST http://iot-agent-json:4041/op/update, request payload (154 bytes)`.
- **Quem cria, apaga.** `DELETE /iot/devices/{id}` remove também o registro (depois de apagar `teste001` e
  `esp32002`, só o da ESP32001 continuava em `/v2/registrations`). Não crie nem apague esses registros à mão.
- Sem comandos não há registro: um dispositivo só com medidas não existe no Orion até publicar a primeira.

### 4.9 Erros do Orion, como chegam

| Código | `error` | `description` (literal) | Causa típica |
|---|---|---|---|
| 400 | BadRequest | `Orion accepts no payload for GET/DELETE requests. HTTP header Content-Type is thus forbidden` | `Content-Type` em GET ou DELETE (X2) |
| 400 | BadRequest | `Invalid characters in attribute value` | `< > " ' = ; ( )` num texto (X6) |
| 400 | BadRequest | `Invalid characters in attribute name` | espaço ou caractere proibido no nome |
| 400 | ParseError | `Errors found in incoming JSON buffer` | JSON malformado |
| 400 | BadRequest | `Bad pagination limit: /1001/ [max: 1000]` | `limit` acima de 1000 |
| 400 | BadRequest | `bad character in tenant name - only underscore and alphanumeric characters are allowed` | `fiware-service` com hífen |
| 404 | NotFound | `The requested entity has not been found. Check type and id` | id errado, **tenant errado**, ou comando sem `?type` |
| 404 | NotFound | `do not exist: <id>/<type> - [entity itself]` | `delete` em lote de entidade inexistente |
| 411 | ContentLengthRequired | `Zero/No Content-Length in PUT/POST/PATCH request` | POST/PATCH/PUT sem corpo |
| 422 | Unprocessable | `Already Exists` | `POST /v2/entities` com id existente |
| 422 | Unprocessable | `do not exist: <id> - [ <atributo> ]` | `PATCH` em atributo inexistente, ou comando não provisionado |
| 422 | Unprocessable | `one or more of the attributes in the request already exist: …` | `appendStrict` sobre atributo existente |
| 422 | PartialUpdate | `do not exist: <id>/<type> - [entity itself]` | lote em que só parte das entidades existe (as que existem são processadas) |

---

## 5. O IoT Agent JSON: provisionamento e MQTT

### 5.1 Três papéis e a configuração da Base

| Lado | O que faz | Na Base |
|---|---|---|
| **Sul** (dispositivo) | assina e publica MQTT; entende JSON | `mosquitto:1883`; tópicos da seção 5.4 |
| **Norte** (contexto) | medidas → `POST /v2/entities?options=upsert`; comandos → registro + encaminhamento | `orion:1026`, NGSI-v2 |
| **Gestão** | API de provisionamento: grupos, dispositivos, saúde | `localhost:4041` |

O IoT Agent **não guarda medidas**: traduz e repassa. Os cadastros (grupos, dispositivos, comandos pendentes) ficam
no banco `iotagentjson`. A configuração vem das variáveis do `docker-compose.yml`:

| Variável | Valor | Efeito |
|---|---|---|
| `IOTA_CB_HOST`, `IOTA_CB_PORT` | `orion`, `1026` | Orion padrão (o `cbroker` do grupo tem prioridade) |
| `IOTA_CB_NGSI_VERSION` | `v2` | fala NGSI-v2 com o Orion |
| `IOTA_NORTH_PORT` | `4041` | porta da API de provisionamento |
| `IOTA_PROVIDER_URL` | `http://iot-agent-json:4041` | endereço que vai no registro: é por ele que o Orion acha o IoT Agent |
| `IOTA_REGISTRY_TYPE`, `IOTA_MONGO_HOST/PORT/DB` | `mongodb`, `mongo-db`, `27017`, `iotagentjson` | cadastros persistem no MongoDB (sobrevivem a um restart) |
| `IOTA_MQTT_HOST`, `IOTA_MQTT_PORT` | `mosquitto`, `1883` | broker do lado sul |
| `IOTA_DEFAULT_TRANSPORT` | `MQTT` | transporte quando o dispositivo não diz |
| `IOTA_DEFAULT_RESOURCE` | `/iot/json` | `resource` padrão |
| `IOTA_TIMESTAMP` | `true` | acrescenta `TimeInstant` (atributo e metadado) |
| `IOTA_AUTOCAST` | `true` | **não** converteu `"24.7"` em número nesta versão: o valor chegou como texto (seção 5.5) |
| `IOTA_LOG_LEVEL` | `DEBUG` | log detalhado, inclusive o corpo NGSI enviado ao Orion |

### 5.2 A API de provisionamento (porta 4041)

Toda chamada, exceto `/iot/about`, leva o tenant. Sem ele: `400 {"name":"MISSING_HEADERS","message":"Some headers
were missing from the request: [\"fiware-service\",\"fiware-servicepath\"]"}`.

| Método e caminho | Para quê | Resposta conferida |
|---|---|---|
| `GET /iot/about` | saúde e versão | `200 {"libVersion":"4.7.0","port":"4041","baseRoot":"/","version":"3.7.0"}` |
| `POST /iot/services` | cria grupos de serviço | `201 {}`; repetido → `409 DUPLICATE_GROUP` |
| `GET /iot/services` | lista os grupos do tenant | `200 {"count": 1, "services": [ … ]}` |
| `PUT /iot/services?resource=/iot/json&apikey=<chave>` | altera um grupo | `204` |
| `DELETE /iot/services?resource=/iot/json&apikey=<chave>` | remove um grupo | `204` |
| `POST /iot/devices` | provisiona dispositivos | `201 {}`; repetido → `409 DUPLICATE_DEVICE_ID`; sem `device_id` → `400 MISSING_ATTRIBUTES` |
| `GET /iot/devices` | lista (`?limit=&offset=`) | `200 {"count": <total>, "devices": [ … ]}` — `count` é o total, não o tamanho da página |
| `GET /iot/devices/{id}` | um dispositivo | `200`; inexistente → `404 DEVICE_NOT_FOUND` |
| `PUT /iot/devices/{id}` | altera um dispositivo | `204` **se a entidade já existe no Orion**; antes da 1ª medida (e sem comandos) → `404 ENTITY_GENERIC_ERROR`, e nada muda |
| `DELETE /iot/devices/{id}` | remove o dispositivo e o registro dos comandos | `204`; **a entidade continua no Orion** (apague-a à parte) |

**Grupo de serviço** (Etapa 2):

```json
POST /iot/services            (com tenant)
{"services": [{"apikey": "ccm130", "cbroker": "http://orion:1026",
               "entity_type": "Thing", "resource": "/iot/json"}]}
→ 201 {}

GET /iot/services             (com tenant)
→ 200 {"count": 1, "services": [{"commands": [], "lazy": [], "attributes": [],
        "_id": "6af4be1555030b90c3407ed5", "resource": "/iot/json", "apikey": "ccm130",
        "service": "ccm130", "subservice": "/", "__v": 0, "static_attributes": [],
        "internal_attributes": [], "entity_type": "Thing"}]}
```

O tenant do grupo (`service`, `subservice`) vem dos **cabeçalhos** do POST, não do corpo: é nele que as entidades
vão nascer. O `GET` não devolve o `cbroker`; ele aparece na mensagem do `409`.

**Dispositivo** (Etapa 2):

```json
POST /iot/devices             (com tenant)
{"devices": [{
  "device_id": "esp32001", "apikey": "ccm130",
  "entity_name": "urn:ngsi-ld:ClimateStation:ESP32001", "entity_type": "ClimateStation",
  "transport": "MQTT",
  "attributes": [{"object_id": "t", "name": "temperature", "type": "Number"},
                 {"object_id": "h", "name": "humidity",    "type": "Number"},
                 {"object_id": "s", "name": "state",       "type": "Text"}],
  "commands":   [{"name": "on", "type": "command"}, {"name": "off", "type": "command"}],
  "static_attributes": [{"name": "refRoom", "type": "Relationship", "value": "urn:ngsi-ld:Room:K501"}]}]}
→ 201 {}

GET /iot/devices/esp32001     (com tenant) — o IoT Agent completa object_id dos comandos
→ 200 {"device_id": "esp32001", "apikey": "ccm130", "service": "ccm130", "service_path": "/",
       "entity_name": "urn:ngsi-ld:ClimateStation:ESP32001", "entity_type": "ClimateStation",
       "transport": "MQTT", "attributes": [ …os três… ], "lazy": [],
       "commands": [{"object_id": "on", "name": "on", "type": "command"},
                    {"object_id": "off", "name": "off", "type": "command"}],
       "static_attributes": [{"name": "refRoom", "type": "Relationship", "value": "urn:ngsi-ld:Room:K501"}]}
```

**Alterar um dispositivo (`PUT`)** — o corpo traz só o que muda, mas cada lista enviada (`attributes`,
`static_attributes`) **substitui** a anterior: um `PUT` com `"attributes": [h → humidity]` num dispositivo que
tinha `t → temperature` deixou só `humidity`. Para acrescentar, mande a lista inteira. Conferido com um dispositivo
de teste: depois da primeira medida, um `PUT` com `t`, `h` e o `refRoom` respondeu `204`, e a entidade passou a ter
`refRoom` e `"humidity": null` até a medida seguinte trazer o valor.

### 5.3 Os campos, um a um

| Onde | Campo | Valor na Base | Para quê |
|---|---|---|---|
| Grupo | `apikey` | `ccm130` | roteia o tópico para o grupo — **não autentica** nada (Aula 10) |
| | `resource` | `/iot/json` | obrigatório (sem ele: `400 WRONG_SYNTAX`); com `apikey`, identifica o grupo |
| | `cbroker` | `http://orion:1026` | Orion visto de dentro da rede Docker |
| | `entity_type` | `Thing` | tipo das entidades de dispositivos **não provisionados** (autoprovisionamento) |
| | cabeçalhos | `ccm130` · `/` | tenant onde as entidades nascem |
| Dispositivo | `device_id` | `esp32001` | 3º nível do tópico; único por chave e tenant |
| | `apikey` | `ccm130` | liga o dispositivo ao grupo (sem ela, a medida não casa e surge `Thing:esp32001`) |
| | `entity_name`, `entity_type` | `urn:ngsi-ld:ClimateStation:ESP32001`, `ClimateStation` | entidade que recebe as medidas |
| | `transport` | `MQTT` | lado sul usado |
| | `attributes` | `t → temperature (Number)`, … | mapa `object_id` (nome curto no JSON) → `name` (atributo NGSI) |
| | `commands` | `on`, `off` | viram registro no Orion e os atributos `_status` / `_info` |
| | `static_attributes` | `refRoom → Room:K501` | entra no Orion junto com **cada** medida |
| | `lazy` | `[]` | atributos consultados sob demanda (não usados na disciplina) |

### 5.4 O lado sul: tópicos e cargas MQTT

| Tópico | Direção | Carga (exemplo real) | O que o IoT Agent faz |
|---|---|---|---|
| `/json/ccm130/esp32001/attrs` | ESP32 → IoT Agent | `{"t": 24.5, "h": 61, "s": "OFF"}` | casa grupo e dispositivo, traduz `object_id → name`, junta `refRoom` e `TimeInstant` e faz o upsert |
| `/json/ccm130/esp32001/attrs/t` | ESP32 → IoT Agent | `23.1` (valor puro) | atualiza só aquele atributo (conferido: só `temperature` mudou) |
| `/ccm130/esp32001/cmd` | IoT Agent → ESP32 | `{"on":""}` | publica o comando com **QoS 0** (conferido: `received PUBLISH (d0, q0, …)`) |
| `/json/ccm130/esp32001/cmdexe` | ESP32 → IoT Agent | `{"on": "OK - rele ligado"}` | grava `on_status = OK` e `on_info` = o texto |

**O valor do `PATCH` vai na carga do comando.** Com um comando `dim` e `"value": 40`, o tópico `…/cmd` recebeu
`{"dim":40}`. A ESP32 da aula ignora o valor (`{"on": ""}`), mas um comando com parâmetro funciona do mesmo jeito.

**O preço da semântica.** A carga MQTT `{"t": 24.5, "h": 61, "s": "OFF"}` tem **32 B**; o corpo NGSI que o IoT
Agent manda ao Orion para uma medida da ESP32 (lido no log em DEBUG, JSON compacto) tem **656 B** — cerca de 20 vezes
mais, porque cada atributo leva `type`, `metadata.TimeInstant`, e o `refRoom` vai junto toda vez:

```json
{"id": "urn:ngsi-ld:ClimateStation:ESP32001", "type": "ClimateStation",
 "refRoom":     {"type": "Relationship", "value": "urn:ngsi-ld:Room:K501", "metadata": {"TimeInstant": {…}}},
 "temperature": {"type": "Number", "value": 26.9, "metadata": {"TimeInstant": {…}}},
 "humidity":    {"type": "Number", "value": 55.6, "metadata": {"TimeInstant": {…}}},
 "state":       {"type": "Text",   "value": "OFF", "metadata": {"TimeInstant": {…}}},
 "TimeInstant": {"type": "DateTime", "value": "2026-11-11T19:18:15.216Z"}}
```

### 5.5 Do tópico à entidade: onde a medida pode se perder

O IoT Agent encadeia quatro identificadores: **resource** (`/json` no tópico ↔ `/iot/json` no grupo) → **apikey** →
**device_id** → **tenant do grupo**. Cada linha abaixo foi publicada no broker da Base, com as Etapas 1 a 3 no ar:

| Publicação | O que o IoT Agent faz | Efeito no Orion |
|---|---|---|
| `/json/ccm130/esp32001/attrs` `{"t": 24.5, "h": 61, "s": "OFF"}` | casa tudo; log `Multiple measures for device esp32001 with apiKey ccm130 successfully updated` | upsert; a entidade passa a existir no MongoDB |
| `/json/chaveerrada/esp32001/attrs` `{"t": 30}` | nenhum grupo com a chave: `MEASURES-004: Device not found for topic /json/chaveerrada/esp32001/attrs` | nada |
| `/json/ccm130/esp32099/attrs` `{"t": 30}` | grupo existe, dispositivo não: **autoprovisiona** | nascem a entidade `Thing:esp32099` (`type` Thing, atributo `t`) e o dispositivo `esp32099` |
| `/json/ccm130/esp32001/attrs` `{"t": "24.7"}` | repassa o tipo do JSON (mesmo com `IOTA_AUTOCAST=true`) | `temperature` = `"24.7"` (texto) com `type` Number; `q=temperature>20` → `[]` |
| `/json/ccm130/esp32001/attrs` `{"x": 1}` | campo fora do provisionamento passa com o nome curto | atributo `x`, `type` Text, `value` 1 |
| GET da ESP32 **sem** `fiware-service` | — | `404`: a entidade está no tenant `ccm130` |

**Quem publicou nunca recebe erro**: MQTT não tem resposta da aplicação. Por isso a verificação é sempre do lado
do contexto (Postman) e do log do IoT Agent. Para desfazer: `DELETE /v2/entities/Thing:esp32099` e
`DELETE /iot/devices/esp32099`; `DELETE …/ESP32001/attrs/x`; o `"24.7"` some na próxima medida numérica.

> **Com a ESP32 simulada no ar, sua medida manual dura até 5 s**: a próxima publicação dela sobrescreve a sua.
> Para ver o efeito com calma, `docker compose stop esp32-simulada` antes e `start` depois.

### 5.6 Comandos: do `PATCH` ao relé e de volta

```
 Postman ── PATCH …/ESP32001/attrs?type=ClimateStation {"on": …} ──▶ Orion
 Orion   ── acha o registro; POST iot-agent-json:4041/op/update ──▶ IoT Agent
 IoT Agent ── on_status = PENDING; publica /ccm130/esp32001/cmd {"on":""} (QoS 0) ──▶ ESP32
 Orion   ── 204 ──▶ Postman            (≈ 50 ms; só quer dizer "encaminhado")
 ESP32   ── liga o relé; publica /json/ccm130/esp32001/cmdexe {"on": "OK - rele ligado"}
 IoT Agent ── on_status = OK, on_info = "OK - rele ligado"
 ESP32   ── publica /json/ccm130/esp32001/attrs {"s": "ON"}  → state = ON (medida comum)
```

Tráfego real no broker, nesta reexecução (`mosquitto_sub -F '%I %t %p'`, horário UTC):

```
2026-11-11T19:15:34+0000 /ccm130/esp32001/cmd          {"on":""}
2026-11-11T19:15:34+0000 /json/ccm130/esp32001/cmdexe  {"on": "OK - rele ligado"}
2026-11-11T19:15:34+0000 /json/ccm130/esp32001/attrs   {"s": "ON"}
2026-11-11T19:15:37+0000 /ccm130/esp32001/cmd          {"off":""}
2026-11-11T19:15:37+0000 /json/ccm130/esp32001/cmdexe  {"off": "OK - rele desligado"}
2026-11-11T19:15:37+0000 /json/ccm130/esp32001/attrs   {"s": "OFF"}
```

Os atributos de comando, normalizados:

```json
"on_status": {"type": "commandStatus", "value": "OK",
              "metadata": {"TimeInstant": {"type": "DateTime", "value": "2026-11-11T19:15:46.238Z"}}},
"on_info":   {"type": "commandResult", "value": "OK - rele ligado", "metadata": {…}}
```

**Três confirmações diferentes** — e o que cada uma não diz:

| Sinal | Significa | Não significa |
|---|---|---|
| `204` do `PATCH` | o Orion encaminhou ao IoT Agent | que o dispositivo recebeu |
| `on_status = OK` | o dispositivo **respondeu** no `cmdexe` | que deu certo: `{"on": "ERRO - rele travado"}` também vira `OK` (o erro fica em `on_info`) |
| `state` | o estado que o dispositivo diz ter, como medida | — é o que um painel deve mostrar |

**Quando o dispositivo não está lá** (conferido com `docker stop esp32-simulada`):

| Passo | Resultado |
|---|---|
| `PATCH off` com a ESP32 parada | `204` |
| `GET off_status, off_info` | `"PENDING"` e `"OK - rele desligado"` — o texto é do comando **anterior** |
| `docker start esp32-simulada`; 15 s depois | ainda `"PENDING"`: o comando saiu com QoS 0 e a ESP32 assina com sessão limpa; não há fila nem reenvio |
| novo `PATCH off` com a ESP32 no ar | `off_status = OK` em dezenas de milissegundos |

**Quanto leva.** `ferramentas/latencia_comando.py` (12 comandos alternados, consulta a cada 5 ms): nesta
reexecução, **204 em 50,0 ms** e **OK em 54,7 ms** (medianas; OK entre 44,6 e 111,9 ms), e nenhuma vez o `PENDING`
foi visto — com a ESP32 no ar, a resposta chega antes de o Postman receber o `204`. Na preparação dos slides: 50 e
64 ms; numa segunda rodada, 56 e 77 ms. O que se repete é a ordem de grandeza.

### 5.7 Erros da API do IoT Agent

| Código | `name` | Quando apareceu |
|---|---|---|
| 400 | `MISSING_HEADERS` | `GET /iot/services` ou `/iot/devices` sem `fiware-service`/`fiware-servicepath` |
| 400 | `WRONG_SYNTAX` | grupo sem `resource` (`Wrong syntax in request: Errors found validating request.`) |
| 400 | `MISSING_ATTRIBUTES` | dispositivo sem `device_id` |
| 404 | `DEVICE_NOT_FOUND` | `GET /iot/devices/naoexiste` |
| 404 | `ENTITY_GENERIC_ERROR` | `PUT /iot/devices/{id}` antes de a entidade existir no Orion |
| 409 | `DUPLICATE_GROUP` | o mesmo `resource` + `apikey` no tenant |
| 409 | `DUPLICATE_DEVICE_ID` | o mesmo `device_id` + `apikey` no tenant |

### 5.8 Ler os logs

```powershell
# medidas processadas e descartadas (o log está em DEBUG: filtre)
docker logs fiware-iot-agent 2>&1 | Select-String 'successfully updated|MEASURES-' | Select-Object -Last 5

# o corpo NGSI que o IoT Agent mandou ao Orion
docker logs fiware-iot-agent 2>&1 | Select-String 'Using the following NGSI v2 request' | Select-Object -Last 1

# comandos encaminhados pelo Orion
docker logs fiware-orion 2>&1 | Select-String 'Request forwarded' | Select-Object -Last 2
```

| Mensagem | Lida como |
|---|---|
| `Multiple measures for device esp32001 with apiKey ccm130 successfully updated` | medida chegou ao Orion |
| `Device group for fields [["resource","apikey"]] not found` + `MEASURES-004: Device not found for topic …` | chave (ou resource) errada: medida descartada |
| `Updating device value in the Context Broker at: "http://orion:1026/v2/entities?options=upsert"` | o upsert de cada medida |
| `Request forwarded (regId: …): POST http://iot-agent-json:4041/op/update` (log do Orion) | comando encaminhado pelo registro |

---

## 6. Os testes desenvolvidos

### 6.1 As duas coleções

| Coleção | Arquivo | Pastas usadas na Aula 6 | Requisições | Testes |
|---|---|---|---|---|
| **Base** (plataforma, Aulas 6 a 9) | `CCM130 - Aula 10 - Fluxo de dados completo.postman_collection.json` (pasta `fiware/`) | Etapa 1 a Etapa 4 | 16 | 35 |
| **Aula 6** (API e experimentos) | `PEL220 - Aula 06 - Introdução ao FIWARE.postman_collection.json` (esta pasta) | A1 a A6, X1 a X7 | 65 | 96 |
| | | **Total** | **81** | **131** |

Resultado da reexecução de 11/11/2026, pasta a pasta, na ordem da aula e a partir de volumes vazios:

| Pasta | Pré-requisito | Req. | Testes | Falhas |
|---|---|---:|---:|---:|
| Base › Etapa 1 - Contexto | `up -d --wait orion` | 3 | 5 | 0 |
| Aula 6 › A1 - Primeiras requisições | Etapa 1 | 3 | 6 | 0 |
| Aula 6 › A2 - Consultas | A1 | 10 | 21 | 0 |
| Aula 6 › A3 - Relações | A1 | 10 | 16 | 0 |
| Aula 6 › A4 - CRUD | Etapa 1 | 12 | 16 | 0 |
| Aula 6 › A5 - Operações em lote | Etapa 1 | 6 | 7 | 0 |
| Aula 6 › X1 a X6 | Etapa 1 (X5 precisa das lojas) | 17 | 23 | 0 |
| Aula 6 › A6 - Limpeza das lojas | A1 e A3 | 1 | 1 | 0 |
| Base › Etapa 2 - IoT Agent | `up -d --wait iot-agent` | 6 | 10 | 0 |
| Base › Etapa 3 - A ESP32 publica medidas | `up -d --build esp32-simulada` | 3 | 10 | 0 |
| Base › Etapa 4 - Comandos | Etapa 3 | 4 | 10 | 0 |
| Aula 6 › X7 - Comando sem ?type e sem dispositivo | Etapa 2 | 6 | 6 | 0 |
| | **Total** | **81** | **131** | **0** |

**Como as coleções estão escritas.** Cada requisição tem pelo menos um `pm.test`; as variáveis da coleção
(`orion`, `iota`, `service`, `servicepath`, `apikey`) concentram endereços e tenant — para outra máquina ou outro
tenant, mude a variável, não as requisições. As pastas da Base são **por etapa** (a descrição diz o que subir antes);
as da Aula 6 são **por assunto** (A) e **por comportamento surpreendente** (X), e cada experimento X se desfaz no fim.

### 6.2 Como executar

**No Postman (aplicativo).** *Import* dos dois arquivos; rode **uma requisição por vez** na aula (leia a resposta
antes do *Test Results*) ou a pasta inteira pelo *Runner* (botão *Run* da pasta), na ordem da tabela acima.

**Na linha de comando (Postman CLI).** O mesmo resultado, sem clicar — útil para conferir a pilha antes da aula ou
depois de mexer nela. Rode no PowerShell, na pasta de cada coleção:

```powershell
# Base: uma etapa por vez (cada uma depende de subir um serviço antes)
postman collection run "CCM130 - Aula 10 - Fluxo de dados completo.postman_collection.json" -i "Etapa 1 - Contexto"

# Aula 6: várias pastas numa execução, na ordem em que aparecem
postman collection run "PEL220 - Aula 06 - Introdução ao FIWARE.postman_collection.json" `
  -i "A1 - Primeiras requisições" -i "A2 - Consultas" -i "A3 - Relações" -i "A4 - CRUD" `
  -i "A5 - Operações em lote" -i "X1 - Entidade sem type" -i "X2 - Content-Type em GET (400)" `
  -i "X3 - Número entre aspas" -i "X4 - Atributos embutidos sob demanda" `
  -i "X5 - Unário: existência e ausência" -i "X6 - Caractere proibido (400)" -i "A6 - Limpeza das lojas"
```

- `-i` aceita o **nome** da pasta (as subpastas X1 a X7 também, pelo nome curto, sem o `X - Experimentos/` na
  frente); repetido, roda várias pastas numa execução só — o comando acima, conferido, dá **59 requisições e 90
  testes**, zero falhas.
- O aviso `No authorization data found. Please use the postman login command` é inofensivo: sem login, a execução é
  local e o relatório só não vai para a nuvem do Postman.
- A saída termina com uma tabela (`requests`, `assertions`, coluna de falhas) e, se algo falhar, a lista
  `# failure` com o teste, o esperado e o recebido.

### 6.3 Catálogo — coleção da Base, Etapas 1 a 4

**Etapa 1 - Contexto** (3 requisições, 5 testes; tenant `ccm130`)

| # | Requisição | Chamada | Testes | O que garante |
|---|---|---|---|---|
| 1 | O Orion está no ar | `GET /version` | Status 200 OK · Versão 4.1.0 | a versão fixada no Compose — os comportamentos deste material são do 4.1.0 |
| 2 | Cria a sala K501 | `POST /v2/op/update` (`append`) | Status 204 No Content | `append` cria ou atualiza: a requisição pode ser repetida na reentrada |
| 3 | Lê a sala | `GET …/Room:K501?options=keyValues` | Status 200 OK · Capacidade 40 | o número foi gravado como número (`40`, não `"40"`) e no tenant certo |

**Etapa 2 - IoT Agent** (6 requisições, 10 testes)

| # | Requisição | Chamada | Testes | O que garante |
|---|---|---|---|---|
| 1 | O IoT Agent está no ar | `GET {{iota}}/iot/about` | Status 200 OK | a API de gestão responde |
| 2 | Cria o grupo de serviço | `POST /iot/services` | Criado (201) ou já existente (409) | aceita `409` de propósito: o grupo pode já existir (reentrada) |
| 3 | Provisiona a ESP32 | `POST /iot/devices` | Status 201 Created | o contrato do dispositivo foi aceito |
| 4 | Lista os dispositivos | `GET /iot/devices` | Status 200 OK · A ESP32 está cadastrada em MQTT | `device_id` e `transport` como esperado |
| 5 | Registro de provedor dos comandos | `GET {{orion}}/v2/registrations` | Status 200 OK · O IoT Agent é o provedor de on e off | o registro aponta para `http://iot-agent-json:4041` com `on` e `off` |
| 6 | A entidade já existe, só com os comandos | `GET …/ESP32001?options=keyValues` | Status 200 OK · Tem on e off · Ainda sem medidas | a entidade "por procuração" (seção 4.8) |

**Etapa 3 - A ESP32 publica medidas** (3 requisições, 10 testes)

| # | Requisição | Chamada | Testes | O que garante |
|---|---|---|---|---|
| 1 | As medidas chegaram ao Orion | `GET …/ESP32001?options=keyValues&attrs=temperature,humidity,state,refRoom,TimeInstant`, depois de **esperar 6 s** (pré-requisição) | Status 200 OK · temperature e humidity numéricas · Relé desligado · Na sala K501 · Medida recente (menos de 60 s) | a cadeia tópico → grupo → dispositivo → entidade inteira, com tipos certos e dado fresco |
| 2 | Formato normalizado - os tipos | `GET …/ESP32001?attrs=temperature,state,TimeInstant` | Status 200 OK · temperature: Number · state: Text · TimeInstant acrescentado pelo IoT Agent | os tipos do provisionamento chegaram ao Orion |
| 3 | Não surgiu uma entidade Thing | `GET /v2/entities/Thing:esp32001` | 404 - o provisionamento veio antes da ESP32 | ninguém subiu a ESP32 antes da Etapa 2 |

**Etapa 4 - Comandos** (4 requisições, 10 testes)

| # | Requisição | Chamada | Testes | O que garante |
|---|---|---|---|---|
| 1 | Comando on | `PATCH …/ESP32001/attrs?type=ClimateStation` `{"on": …}` | Status 204 No Content | o Orion encaminhou |
| 2 | Resultado do on | `GET …?options=keyValues&attrs=on_status,on_info,state`, depois de **esperar 2,5 s** | Status 200 OK · on_status = OK · on_info começa com OK · state = ON | o dispositivo respondeu, sem erro no texto, e o estado mudou |
| 3 | Comando off | idem, `{"off": …}` | Status 204 No Content | — |
| 4 | Resultado do off | `GET …&attrs=off_status,off_info,state` (espera 2,5 s) | Status 200 OK · off_status = OK · off_info começa com OK · state = OFF | o ciclo completo de volta ao estado seguro |

Repare que os testes da Etapa 4 conferem **as três confirmações** da seção 5.6: o `204`, o `_status` com o texto do
`_info`, e o `state`.

### 6.4 Catálogo — coleção da Aula 6

**A1 - Primeiras requisições** (3 · 6; tenant padrão)

| # | Requisição | Chamada | Testes |
|---|---|---|---|
| 1 | Verificando a saúde do Orion | `GET /version` | Status 200 OK · Resposta em JSON · Orion respondeu com sua versão |
| 2 | Cria a loja Store:001 | `POST /v2/entities` | Status 201 Created · Header Location aponta para a entidade |
| 3 | Cria a loja Store:002 | `POST /v2/entities` | Status 201 Created |

**A2 - Consultas** (10 · 21)

| # | Requisição | Chamada | Testes |
|---|---|---|---|
| 1 | Todas as entidades | `GET /v2/entities` | 200 · Retorna uma lista |
| 2 | Por id | `GET …/Store:001` | 200 · Formato normalizado (`name.value`) |
| 3 | Por id - keyValues | `GET …/Store:001?options=keyValues` | 200 · Formato keyValues (`name`) |
| 4 | Por tipo | `?type=Store&options=keyValues` | 200 · Duas lojas |
| 5 | Apenas o nome das lojas | `?type=Store&attrs=name&options=keyValues` | 200 · Somente id, type e name |
| 6 | Por valor (q) - texto | `q=name=='Checkpoint Markt'` | 200 · Encontra a Store:002 |
| 7 | Por valor (q) - atributo composto | `q=address.addressLocality=='Kreuzberg'` | 200 · Encontra a loja de Kreuzberg |
| 8 | Por distância (georel near) | `georel=near;maxDistance:1500&geometry=point&coords=52.5162,13.3777` | 200 · Somente a Store:002 está a menos de 1,5 km |
| 9 | Paginação com contagem | `limit=1&offset=1&options=count,keyValues` | 200 · Uma entidade por página · Header Fiware-Total-Count = 2 |
| 10 | Metadados de data | `…/Store:001?attrs=name&metadata=dateCreated,dateModified` | 200 · Atributo traz dateCreated |

**A3 - Relações** (10 · 16)

| # | Requisição | Chamada | Testes |
|---|---|---|---|
| 1 | Cria 4 produtos | `POST /v2/op/update` (`append`) | 204 |
| 2 | Cria 4 prateleiras | `POST /v2/op/update` | 204 |
| 3 | Informações de uma prateleira | `GET …/Shelf:unit001/attrs/maxCapacity/value?type=Shelf` | 200 · maxCapacity = 50 |
| 4 | Chaves estrangeiras (refStore) | `POST /v2/op/update` (acrescenta `refStore`) | 204 |
| 5 | Prateleira atualizada | `GET …/Shelf:unit001?type=Shelf&options=keyValues` | 200 · Prateleira agora tem refStore |
| 6 | Chave estrangeira (filho → pai) | `GET …/Shelf:unit001/attrs/refStore/value` | 200 · Aponta para a Store:001 |
| 7 | Prateleiras de uma loja (pai → filhos) | `?type=Shelf&q=refStore==urn:ngsi-ld:Store:001` | 200 · A Store:001 tem 3 prateleiras |
| 8 | Cria item de inventário (N:N) | `POST /v2/entities` (InventoryItem) | 201 |
| 9 | Itens de inventário de uma loja | `?type=InventoryItem&q=refStore==…:Store:001` | 200 · Um item na Store:001 |
| 10 | Produtos acima de 1000 | `?type=Product&q=price>1000` | 200 · Três produtos |

**A4 - CRUD** (12 · 16; execute na ordem)

| # | Requisição | Chamada | Testes |
|---|---|---|---|
| 1 | Create | `POST /v2/entities` (Product:005) | 201 |
| 2 | Create - id repetido | o mesmo POST | 422 · Already Exists |
| 3 | Create - acrescenta atributo | `POST …/Product:005/attrs` (`category`) | 204 |
| 4 | Read - keyValues | `GET …/Product:005?options=keyValues` | 200 · Tem o novo atributo category |
| 5 | Read - só o valor | `GET …/attrs/price/value` | 200 · price = 199 |
| 6 | Update - PATCH | `PATCH …/attrs` (`price` 249) | 204 |
| 7 | Update - PATCH em atributo inexistente | `PATCH …/attrs` (`color`) | 422 |
| 8 | Update - PUT substitui todos | `PUT …/attrs` (`name`, `price`) | 204 |
| 9 | Read - confere a substituição | `GET …?options=keyValues` | 200 · size e category foram removidos |
| 10 | Delete - atributo | `DELETE …/attrs/price` | 204 |
| 11 | Delete - entidade | `DELETE …/Product:005` | 204 |
| 12 | Read - removida | `GET …/Product:005` | 404 |

**A5 - Operações em lote** (6 · 7)

| # | Requisição | `actionType` | Testes |
|---|---|---|---|
| 1 | Lote append | `append` (Product:006 e 007) | 204 |
| 2 | Lote appendStrict | `appendStrict` (os mesmos) | 422 |
| 3 | Lote update | `update` (preços) | 204 |
| 4 | Lote replace | `replace` (Product:006 sem `size`) | 204 |
| 5 | Confere os produtos | `GET ?type=Product&q=price>300` | 200 · Cider perdeu o atributo size (replace) |
| 6 | Lote delete | `delete` | 204 |

**X - Experimentos** (comportamento conferido; cada pasta se desfaz no fim)

| Pasta | Requisições e testes | O que mostra |
|---|---|---|
| **X1** Entidade sem type (3 · 6) | POST sem `type` → 201 · Location com type=Thing; GET → 200 · type da entidade = Thing · type do atributo inferido = Number; DELETE → 204 | o `type` é opcional no v2 — e um modelo sem tipo não se consulta por tipo |
| **X2** Content-Type em GET (1 · 2) | `GET /version` com `Content-Type` → 400 · mensagem cita Content-Type | GET e DELETE sem o cabeçalho |
| **X3** Número entre aspas (6 · 7) | POST `capacity: "25"` → 201 (aceito); `q=capacity>20` → 200 · lista vazia; GET → capacity é string; PATCH `25` → 204; `q` → uma entidade; DELETE → 204 | o Orion não valida `value` × `type`; o erro só aparece na consulta |
| **X4** Atributos embutidos (4 · 4) | POST → 201; GET → sem dateCreated; GET com `attrs=dateCreated,dateModified,capacity` → com as datas; DELETE → 204 | datas só quando pedidas |
| **X5** Unário (2 · 2) | `q=address` → 2 lojas; `q=!address` → 0 | sem `!`, existência; com `!`, ausência |
| **X6** Caractere proibido (1 · 2) | POST com `"OK: rele=ON"` → 400 · Invalid characters | por isso a ESP32 responde `OK - rele ligado` |
| **X7** Comando sem ?type e sem dispositivo (6 · 6; tenant `ccm130`) | provisiona `teste001` (Lamp:T01, só o comando `on`) → 201; PATCH sem `?type` → 404; com `?type=Lamp` → 204; GET → on_status = PENDING; DELETE do dispositivo → 204; DELETE da entidade → 204 ou 404 | a entidade por procuração e o comando sem ninguém do outro lado |

No X7, o último teste aceita **204 ou 404** porque o `PATCH` com `?type` faz o IoT Agent gravar `on_status` — o que
materializa a entidade no Orion (`204` ao apagar); se o `PATCH` não tiver acontecido, ela não existe (`404`).

**A6 - Limpeza das lojas** (1 · 1): `POST /v2/op/update` com `delete` das 11 entidades das pastas A1 e A3 → 204.

### 6.5 Testes complementares (fora das coleções)

Feitos com chamadas diretas, `mosquitto_pub`/`mosquitto_sub` e `docker`, sobre a mesma pilha. São a base das
seções 4 e 5; repita-os para ver com os próprios olhos.

| Caso | Como | Resultado |
|---|---|---|
| Publicação manual | `'{"t": 24.5, "h": 61, "s": "OFF"}' \| docker exec -i mosquitto mosquitto_pub -t /json/ccm130/esp32001/attrs -s` | entidade no MongoDB, com `refRoom` e `TimeInstant` |
| Medida de um atributo | publicar `23.1` em `/json/ccm130/esp32001/attrs/t` | só `temperature` mudou |
| Chave errada | `/json/chaveerrada/esp32001/attrs` | descartada; `MEASURES-004` no log |
| Dispositivo desconhecido | `/json/ccm130/esp32099/attrs` | autoprovisionado: `Thing:esp32099` |
| Número entre aspas | `{"t": "24.7"}` | texto com `type` Number; `q` numérico falha |
| Campo não mapeado | `{"x": 1}` | atributo `x` (Text, valor 1) |
| Sem tenant | GET da ESP32 sem `fiware-service` | `404` |
| Comando com a ESP32 parada | `docker stop esp32-simulada`; PATCH | `204`; `PENDING` mesmo depois de ela voltar |
| Resposta de erro do dispositivo | publicar `{"on": "ERRO - rele travado"}` no `cmdexe` | `on_status = OK`, `on_info = ERRO - rele travado` |
| Comando com parâmetro | comando `dim` com `"value": 40` | `…/cmd` recebeu `{"dim":40}` |
| QoS do comando | `mosquitto_sub -q 2 -d -t /ccm130/esp32001/cmd` | `received PUBLISH (d0, q0, …)`: QoS 0 |
| Latência | `python ferramentas/latencia_comando.py` | 204 em 50,0 ms; OK em 54,7 ms (medianas de 12) |
| Tamanho da tradução | log do IoT Agent em DEBUG | 32 B de MQTT → 656 B de NGSI |
| `PUT` de dispositivo | antes e depois da 1ª medida | `404 ENTITY_GENERIC_ERROR` antes; `204` depois |
| Ciclo de vida do registro | `DELETE /iot/devices/{id}` | o registro some; a entidade fica |
| Tenant | `CCM130`, `ccm-130`, servicepath `campus` | aceito (minúsculas) · `400` · `400` |

### 6.6 Anatomia de um teste do Postman

Os testes das coleções usam poucos padrões; com eles se escreve quase qualquer verificação de uma API de contexto.

```javascript
// 1. código de status (o mais comum)
pm.test("Status 201 Created", () => pm.response.to.have.status(201));

// 2. mais de um código aceitável (requisição que pode ser repetida)
pm.test("Criado (201) ou já existente (409)", () => pm.expect(pm.response.code).to.be.oneOf([201, 409]));

// 3. valor e tipo no corpo
const e = pm.response.json();
pm.test("temperature e humidity numéricas",
        () => ["temperature", "humidity"].forEach(a => pm.expect(e[a], a).to.be.a("number")));

// 4. frescor do dado (cuidado: compara o relógio do PC com o do contêiner)
pm.test("Medida recente (menos de 60 s)", () => pm.expect(Date.now() - Date.parse(e.TimeInstant)).to.be.below(60000));

// 5. cabeçalho da resposta
pm.test("Header Fiware-Total-Count = 2", () => pm.expect(pm.response.headers.get("Fiware-Total-Count")).to.eql("2"));

// 6. texto com padrão
pm.test("on_info começa com OK", () => pm.expect(e.on_info).to.match(/^OK/));
```

E, na aba **Pre-request** das requisições que dependem de algo assíncrono (medida, comando):

```javascript
setTimeout(() => {}, 6000);   // dá tempo de a mensagem percorrer a plataforma
```

### 6.7 Um teste para o modelo de dados do seu projeto

O marco da Aula 7 pede que cada JSON de exemplo seja aceito pelo Orion **e lido de volta sem surpresa**. Como o
Orion não confere nada (seção 4.1), vale automatizar a conferência. Cole o script abaixo na aba **Tests** de um
`GET /v2/entities/<id>` **normalizado** (sem `keyValues`):

```javascript
pm.test("Status 200 OK", () => pm.response.to.have.status(200));
const e = pm.response.json();
pm.test("id em URN com o tipo", () => pm.expect(e.id).to.match(new RegExp("^urn:ngsi-ld:" + e.type + ":")));
const regras = {
    Number: v => typeof v === "number",
    Boolean: v => typeof v === "boolean",
    Text: v => typeof v === "string",
    DateTime: v => !isNaN(Date.parse(v)),
    Relationship: v => /^urn:ngsi-ld:[A-Z][A-Za-z]+:/.test(v),
};
Object.entries(e).filter(([k]) => !["id", "type"].includes(k)).forEach(([nome, a]) => {
    if (!regras[a.type]) return;   // command, geo:json etc.: fora desta regra
    pm.test(`${nome}: value coerente com o type ${a.type}`, () => pm.expect(regras[a.type](a.value), JSON.stringify(a.value)).to.be.true);
});
```

Conferido com o Postman CLI: a `Room:K501` passa (4 testes) e a `ClimateStation:ESP32001` também (7 testes); a
sala "modelada às pressas" (`sala-k502`, com `"30"` e `"false"` entre aspas) **falha em 3**: o id sem URN,
`capacidade` e `projetor`. Os outros dois problemas daquele exemplo — nomes em português e `relationship` minúsculo —
o script não pega: ficam para a revisão com as cinco perguntas do "ache o erro" e os Smart Data Models (Aula 7).

### 6.8 O que os testes não garantem

| Limite | Consequência prática |
|---|---|
| **Dependem da ordem** | A2, A3 e X5 precisam das lojas de A1; A6 precisa de A1 e A3; X7 precisa do grupo da Etapa 2; a Etapa 4 precisa da ESP32 no ar |
| **Não são todos idempotentes** | rodar A1 de novo sem A6 dá `422` nas lojas; A6 de novo dá `404` (nada a remover) — se só parte já tiver sido removida, `422 PartialUpdate`, e as que existem são removidas mesmo assim; A4 falha se Product:005 sobrou de uma execução interrompida |
| **A reentrada da Etapa 2 tem 2 falhas esperadas** | com o volume preservado (Aula 7), *Provisiona a ESP32* recebe `409 DUPLICATE_DEVICE_ID` e *Ainda sem medidas* encontra `temperature` — nesta reexecução: 10 testes, 2 falhas, ambas por já estar tudo lá. Os outros 8 confirmam que grupo, dispositivo e registro sobreviveram |
| **Dependem de tempo** | as esperas de 6 s (Etapa 3) e 2,5 s (Etapa 4) bastaram aqui; numa máquina lenta, aumente-as. *Medida recente* compara o relógio do PC com o do contêiner |
| **Supõem um estado** | *Relé desligado* (Etapa 3) supõe `state = OFF` — verdade logo depois da Etapa 3 ou depois do `off` da Etapa 4 |
| **Não olham o MQTT** | o tráfego nos tópicos você confere no MQTTX; a coleção só vê o Orion e o IoT Agent |
| **Não conferem semântica** | um `temperature` de 900 °C, numérico, passa em todos — plausibilidade é assunto do gêmeo digital (Aula 9) |

---

## 7. Cola de comandos (PowerShell)

Tudo conferido no PowerShell 7 contra a pilha das Etapas 1 a 4. `Invoke-RestMethod` não manda `Content-Type` em GET
(o que evita o `400` do X2); no PATCH, `-ContentType` o acrescenta.

```powershell
$O = 'http://localhost:1026'
$I = 'http://localhost:4041'
$T = @{ 'fiware-service' = 'ccm130'; 'fiware-servicepath' = '/' }
$ESP = 'urn:ngsi-ld:ClimateStation:ESP32001'

# versão do Orion
(Invoke-RestMethod "$O/version").orion.version                     # 4.1.0

# a ESP32 em keyValues
Invoke-RestMethod "$O/v2/entities/${ESP}?options=keyValues&attrs=temperature,humidity,state,refRoom" -Headers $T

# só um valor
Invoke-RestMethod "$O/v2/entities/${ESP}/attrs/temperature/value" -Headers $T

# dispositivos provisionados
(Invoke-RestMethod "$I/iot/devices" -Headers $T).devices | Select-Object device_id, entity_name, transport

# contagem sem trazer as entidades (o total vem no cabeçalho)
(Invoke-WebRequest "$O/v2/entities?type=ClimateStation&limit=1&options=count" -Headers $T).Headers['Fiware-Total-Count']

# comando on, e o resultado
$on = '{"on": {"type": "command", "value": ""}}'
(Invoke-WebRequest -Method Patch "$O/v2/entities/${ESP}/attrs?type=ClimateStation" -Headers $T `
    -ContentType 'application/json' -Body $on).StatusCode            # 204
Start-Sleep -Seconds 2
Invoke-RestMethod "$O/v2/entities/${ESP}?options=keyValues&attrs=on_status,on_info,state" -Headers $T

# ver o corpo de um erro
try { Invoke-RestMethod "$O/v2/entities/urn:ngsi-ld:Room:K999" -Headers $T }
catch { "$($_.Exception.Response.StatusCode.value__) $($_.ErrorDetails.Message)" }    # 404 {"error": "NotFound", …}

# publicar uma medida à mão (com a ESP32 no ar, ela sobrescreve em até 5 s)
'{"t": 24.5, "h": 61, "s": "OFF"}' | docker exec -i mosquitto mosquitto_pub -t /json/ccm130/esp32001/attrs -s

# escutar os tópicos da ESP32 (sai depois de 6 mensagens)
docker exec mosquitto mosquitto_sub -v -t '/ccm130/#' -t '/json/ccm130/#' -C 6

# o que está no banco
docker exec db-mongo mongosh --quiet --eval "db.getMongo().getDBNames()"
docker exec db-mongo mongosh --quiet --eval "db.getSiblingDB('orion-ccm130').entities.find({}, {'_id.id': 1}).toArray()"
```

No Windows em português, o PowerShell mostra números com vírgula (`28,6`): é só a exibição; o Orion guardou `28.6`.

---

## 8. Diagnóstico: do sintoma à causa

Siga o caminho da mensagem e confira cada salto antes de mexer em código: contêineres → broker → IoT Agent
(cadastro e log) → Orion (registro, tenant e tipo).

| Sintoma | Causa provável | Como verificar / resolver |
|---|---|---|
| `400` num GET ao Orion | `Content-Type` em GET ou DELETE | remova o cabeçalho (X2) |
| `400 bad character in tenant name` | hífen ou outro símbolo em `fiware-service` | só letras, números e `_` |
| `400 MISSING_HEADERS` no IoT Agent | faltou o tenant | `fiware-service` e `fiware-servicepath` em toda chamada a `/iot/services` e `/iot/devices` |
| `411 ContentLengthRequired` | POST/PATCH/PUT sem corpo | confira a aba *Body* (raw, JSON) |
| `400 ParseError` | JSON malformado | vírgula sobrando, aspas, chaves |
| `400 Invalid characters in attribute value` | `< > " ' = ; ( )` no texto | reescreva o texto (por isso `OK - rele ligado`) |
| `422 Already Exists` | `POST /v2/entities` repetido | use `op/update` com `append` ou `?options=upsert` |
| `422 do not exist: … - [ attr ]` | `PATCH` em atributo novo, ou comando não provisionado | `POST …/attrs` para criar; confira `commands` do dispositivo |
| Lista vazia ou `404` nas entidades da ESP32 | consulta sem o tenant | cabeçalhos `ccm130` e `/` |
| A medida não chega ao Orion | tópico errado (chave, barra inicial, `/json`) | log do IoT Agent: `MEASURES-004`; `GET /iot/devices` |
| Surge `Thing:esp32001` | a ESP32 publicou antes do provisionamento | provisione primeiro; apague a entidade e o dispositivo `Thing` |
| Atributo com nome curto (`t`, `x`) | campo publicado que não está em `attributes` | confira os `object_id` e o JSON publicado |
| `temperature` com aspas; `q` numérico não acha | número publicado entre aspas | publique `{"t": 24.5}` |
| Comando responde `404` | `PATCH` sem `?type=ClimateStation` (antes da 1ª medida) | mantenha o `?type` na URL |
| Comando fica `PENDING` | dispositivo fora do ar no envio (QoS 0, sem fila) | `docker compose start esp32-simulada` e mande de novo |
| `on_status = OK`, mas o relé não mudou | o dispositivo respondeu com erro | leia `on_info` e o `state` |
| `PUT /iot/devices/{id}` → `404 ENTITY_GENERIC_ERROR` | a entidade ainda não existe no Orion | publique uma medida antes, ou `DELETE` + `POST` do dispositivo |
| `409 DUPLICATE_DEVICE_ID` | dispositivo já provisionado (reentrada) | normal na Aula 7; para mudar algo, `PUT` |
| Reentrada da Etapa 2 com 2 testes vermelhos | dispositivo e medidas já existem | esperado (seção 6.8) |
| *Medida recente* falha com a ESP32 publicando | relógio do PC e do contêiner diferentes (por exemplo, depois de o computador hibernar) | compare `Get-Date -AsUTC` com `docker exec mosquitto date -u`; reinicie o Docker Desktop |
| Tópico vira `C:/Program Files/Git/…` | Git Bash convertendo a barra | `MSYS_NO_PATHCONV=1` ou PowerShell |
| O contexto "sumiu" na aula seguinte | outra pasta (outro volume) ou `down -v` | sempre `C:\pel220\fiware`; pare com `docker compose stop` |

---

## 9. Glossário

| Termo | Nesta aula |
|---|---|
| **Contexto** | o estado atual de entidades do mundo — o que são, como estão e com quem se relacionam |
| **Entidade** | uma coisa com `id` e `type` (a sala K501, a ESP32001) |
| **Atributo** | propriedade de uma entidade, com `type`, `value` e `metadata` |
| **Metadado** | informação sobre um atributo (`TimeInstant`, `unitCode`, `dateModified`) |
| **Relationship** | atributo cujo valor é o id de outra entidade (`refRoom`) |
| **Tenant** | espaço isolado do Orion, escolhido por `fiware-service` (+ `fiware-servicepath`); um banco por serviço |
| **Upsert** | criar se não existe, atualizar se existe (`POST /v2/entities?options=upsert`) |
| **Grupo de serviço** | cadastro no IoT Agent que liga `resource` + `apikey` a um tenant e a um Orion |
| **apikey** | chave que **roteia** a mensagem MQTT para o grupo; não autentica |
| **Provisionamento** | cadastro do dispositivo no IoT Agent: quem é, o que mede, o que obedece |
| **Autoprovisionamento** | o IoT Agent cria sozinho dispositivo e entidade (`Thing:<id>`) para um `device_id` desconhecido |
| **Registro (de provedor)** | aviso ao Orion: "para estes atributos desta entidade, pergunte a este endereço" |
| **Comando** | atributo do tipo `command`: escrever nele (`PATCH`) dispara o envio ao dispositivo |
| **`_status` / `_info`** | estado do comando (`PENDING`, `OK`) e texto devolvido pelo dispositivo |

---

## 10. Referências

- FIWARE. **FIWARE-NGSI v2 Specification**. Disponível em: https://fiware.github.io/specifications/ngsiv2/stable/
  — representação, tipos, linguagem de consulta simples (`q`, `mq`), operações em lote e registros.
- FIWARE. **Orion Context Broker — documentação da versão 4.1.0**. Disponível em:
  https://fiware-orion.readthedocs.io/en/4.1.0/ — multitenancy, encaminhamento a provedores, limites e erros.
- FIWARE. **IoT Agent for JSON — documentação**. Disponível em: https://fiware-iotagent-json.readthedocs.io/ —
  tópicos MQTT, formato das medidas e dos comandos.
- FIWARE. **IoT Agent Node.js Library — documentação**. Disponível em: https://iotagent-node-lib.readthedocs.io/
  — API de provisionamento (grupos e dispositivos), autoprovisionamento, variáveis de ambiente.
- FIWARE. **FIWARE Step-by-Step Tutorials for NGSI-v2**. Disponível em: https://fiware-tutorials.readthedocs.io/
  — origem do exemplo das lojas (Store, Shelf, Product, InventoryItem), adaptado na CCM130 e nas pastas A.
- SMART DATA MODELS. **Catálogo de modelos de dados**. Disponível em: https://smartdatamodels.org/ — convenções de
  nomes e modelos candidatos para o projeto (Aula 7).
- ETSI. **GS CIM 009 — Context Information Management (CIM); NGSI-LD API**. — a especificação do NGSI-LD (Aula 7).
- LIU, X.; LIU, R.; ZHANG, X.; ABATE, A. G.; NIELSEN, P. S.; KELES, D. IoT-enabled interoperability for
  energy-mobility integration: a systematic review of protocols, platforms, and standards. **Applied Energy**,
  v. 411, 127611, 2026. DOI: 10.1016/j.apenergy.2026.127611.

---

## Apêndice A — O código dos serviços construídos

Os quatro programas que a plataforma constrói (`build:` no Compose), sem nenhuma alteração. Os comentários citam a numeração de aulas da CCM130, onde a plataforma nasceu.

### A.1 `esp32_simulada/esp32_simulada.py` — a ESP32 simulada (Etapa 3)

```python
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
```

### A.2 `clima/provedor.py` — o provedor de contexto do clima (Etapa 5)

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

### A.3 `controlador/controlador.py` — a aplicação de controle, esqueleto (Etapa 8)

```python
"""
============================================================================
 CCM130 - Conectividade e IoT | Aula 10 - Fluxo de dados completo
 Centro Universitário FEI - Prof. Rafael Gomes Alves
----------------------------------------------------------------------------
 ESQUELETO - complete a função decidir() (seção 2).

 APLICAÇÃO DE CONTROLE: fecha o laço sensor -> plataforma -> atuador.

   1. Uma SUBSCRIÇÃO do Orion avisa esta aplicação a cada mudança de
      temperatura da ESP32:  POST http://controlador:5001/notify
   2. decidir() aplica a regra com HISTERESE:
        temperatura >= LIGA     e relé desligado  ->  comando "on"
        temperatura <= DESLIGA  e relé ligado     ->  comando "off"
        entre os dois limites                     ->  nada (mantém o estado)
   3. O comando volta pelo Orion (PATCH ...?type=ClimateStation), que o
      encaminha ao IoT Agent e daí ao dispositivo -- igual ao Postman.

 A aplicação só fala com o Orion: nunca fala direto com a ESP32 nem com o broker.

 GET http://localhost:5001/status mostra os limites, os contadores e as
 últimas decisões (os testes da coleção usam esse endereço).

 Variáveis de ambiente (padrão entre parênteses):
   ORION (http://orion:1026)  SERVICE (ccm130)  SERVICEPATH (/)
   LIGA (28)  DESLIGA (24)  ESPERA (10) s entre comandos para o mesmo dispositivo
   PORTA (5001)
============================================================================
"""

import json
import os
import threading
import time
import urllib.request
from collections import deque
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# ---------------------------------------------------------------------------
# 1. Configuração
# ---------------------------------------------------------------------------
ORION = os.getenv("ORION", "http://orion:1026")
SERVICE = os.getenv("SERVICE", "ccm130")
SERVICEPATH = os.getenv("SERVICEPATH", "/")
LIGA = float(os.getenv("LIGA", "28"))
DESLIGA = float(os.getenv("DESLIGA", "24"))
ESPERA = float(os.getenv("ESPERA", "10"))
PORTA = int(os.getenv("PORTA", "5001"))

ultimo_comando = {}                 # id da entidade -> instante do último comando enviado
historico = deque(maxlen=50)        # últimas decisões, para o /status
contadores = {"notificacoes": 0, "on": 0, "off": 0, "erros": 0}
trava = threading.Lock()


def log(*args):
    print("[controlador]", *args, flush=True)


# ---------------------------------------------------------------------------
# 2. A regra -- o coração da aplicação
# ---------------------------------------------------------------------------
def decidir(temperatura, estado):
    """Devolve "on", "off" ou None (não fazer nada).

    Histerese: dois limites em vez de um. Com um limite só (liga e desliga em
    28 °C), o ruído do sensor em torno de 28 faria o relé bater sem parar.
    """
    # TODO 1: sem temperatura na notificação, não decida nada.
    # TODO 2: temperatura >= LIGA e relé que NÃO está "ON"     -> "on"
    # TODO 3: temperatura <= DESLIGA e relé que NÃO está "OFF" -> "off"
    # TODO 4: em qualquer outro caso -> None (o relé fica como está)
    #
    # Por que comparar com o estado? Sem isso, cada notificação acima de 28 °C
    # manda outro "on" -- comandos repetidos à toa para o dispositivo.
    return None


# ---------------------------------------------------------------------------
# 3. O comando volta pelo Orion
# ---------------------------------------------------------------------------
def enviar_comando(entidade, tipo, comando):
    """PATCH no Orion, como você fez no Postman na etapa 4."""
    url = f"{ORION}/v2/entities/{entidade}/attrs?type={tipo}"
    corpo = json.dumps({comando: {"type": "command", "value": ""}}).encode()
    pedido = urllib.request.Request(url, data=corpo, method="PATCH", headers={
        "Content-Type": "application/json", "fiware-service": SERVICE, "fiware-servicepath": SERVICEPATH})
    try:
        with urllib.request.urlopen(pedido, timeout=5) as resposta:
            return resposta.status                  # 204 = encaminhado ao IoT Agent
    except Exception as erro:
        log("falha ao enviar", comando, "para", entidade, ":", erro)
        return getattr(erro, "code", 0)


def tratar(entidade):
    """Uma entidade da notificação: decide e, se for o caso, comanda."""
    eid, tipo = entidade["id"], entidade.get("type", "ClimateStation")
    temperatura, estado = entidade.get("temperature"), entidade.get("state")
    comando = decidir(temperatura, estado)
    if comando is None:
        return
    with trava:
        if time.time() - ultimo_comando.get(eid, 0) < ESPERA:
            return                                  # já mandamos há pouco: o estado ainda não voltou
        ultimo_comando[eid] = time.time()
    status = enviar_comando(eid, tipo, comando)
    with trava:
        contadores[comando if status == 204 else "erros"] += 1
        historico.appendleft({"quando": datetime.now().strftime("%H:%M:%S"), "entidade": eid,
                              "temperatura": temperatura, "estado": estado, "comando": comando, "status": status})
    log(f"{eid}: {temperatura} °C, relé {estado} -> {comando} ({status})")


# ---------------------------------------------------------------------------
# 4. Servidor HTTP: recebe as notificações e mostra o status
# ---------------------------------------------------------------------------
class Controlador(BaseHTTPRequestHandler):
    def _json(self, status, corpo):
        bruto = json.dumps(corpo, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(bruto)))
        self.end_headers()
        self.wfile.write(bruto)

    def do_POST(self):
        tamanho = int(self.headers.get("Content-Length", 0))
        try:
            notificacao = json.loads(self.rfile.read(tamanho) or b"{}")
        except ValueError:
            self._json(400, {"erro": "corpo não é JSON"})
            return
        self._json(200, {"recebido": True})         # responda rápido: o Orion espera
        with trava:
            contadores["notificacoes"] += 1
        for entidade in notificacao.get("data", []):
            tratar(entidade)

    def do_GET(self):
        with trava:
            self._json(200, {"limites": {"liga": LIGA, "desliga": DESLIGA}, "contadores": contadores,
                             "ultimas": list(historico)[:10]})

    def log_message(self, formato, *args):
        pass


if __name__ == "__main__":
    log(f"Liga em >= {LIGA} °C, desliga em <= {DESLIGA} °C | notificações em :{PORTA}/notify")
    ThreadingHTTPServer(("0.0.0.0", PORTA), Controlador).serve_forever()
```

### A.4 `controlador_pronto/controlador.py` — a aplicação de controle pronta (versão automática)

```python
"""
============================================================================
 PEL 220 - Internet das Coisas e Gêmeos Digitais | Plataforma FIWARE, Etapa 8
 Centro Universitário FEI - Prof. Rafael Gomes Alves
----------------------------------------------------------------------------
 VERSÃO PRONTA do controlador (a dos alunos é controlador/controlador.py).

 APLICAÇÃO DE CONTROLE AUTOMÁTICA: fecha o laço sensor -> plataforma -> atuador
 sem nenhum passo manual.

   1. Ao iniciar, cria SOZINHA a subscrição no Orion (se ainda não existir):
      a cada medida de temperatura de qualquer ClimateStation, o Orion
      notifica  POST <NOTIFICAR_EM>  com temperature e state (keyValues).
   2. decidir() aplica a regra com HISTERESE:
        temperatura >= LIGA     e relé que não está ON   ->  comando "on"
        temperatura <= DESLIGA  e relé que não está OFF  ->  comando "off"
        entre os dois limites                            ->  nada
   3. O comando volta pelo Orion (PATCH ...?type=ClimateStation), que o
      encaminha ao IoT Agent e daí ao dispositivo.

 Vale para todas as ClimateStation do tenant: provisionou outra ESP32, ela
 passa a ser controlada também, sem mudar nada aqui.

 GET http://localhost:5002/status mostra os limites, a subscrição, os
 contadores e as últimas decisões (mesmo formato da versão dos alunos).

 Variáveis de ambiente (padrão entre parênteses):
   ORION (http://orion:1026)  SERVICE (ccm130)  SERVICEPATH (/)
   LIGA (28)  DESLIGA (24)  ESPERA (10) s entre comandos para o mesmo dispositivo
   PORTA (5002)  NOTIFICAR_EM (http://controlador-pronto:5002/notify)
============================================================================
"""

import json
import os
import threading
import time
import urllib.error
import urllib.request
from collections import deque
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# ---------------------------------------------------------------------------
# 1. Configuração
# ---------------------------------------------------------------------------
ORION = os.getenv("ORION", "http://orion:1026")
SERVICE = os.getenv("SERVICE", "ccm130")
SERVICEPATH = os.getenv("SERVICEPATH", "/")
LIGA = float(os.getenv("LIGA", "28"))
DESLIGA = float(os.getenv("DESLIGA", "24"))
ESPERA = float(os.getenv("ESPERA", "10"))
PORTA = int(os.getenv("PORTA", "5002"))
NOTIFICAR_EM = os.getenv("NOTIFICAR_EM", f"http://controlador-pronto:{PORTA}/notify")

TENANT = {"fiware-service": SERVICE, "fiware-servicepath": SERVICEPATH}
DESCRICAO = "Controlador pronto: temperatura das ClimateStation"

ultimo_comando = {}                 # id da entidade -> instante do último comando enviado
historico = deque(maxlen=50)        # últimas decisões, para o /status
contadores = {"notificacoes": 0, "on": 0, "off": 0, "erros": 0}
subscricao = {"id": None, "situacao": "aguardando o Orion"}
trava = threading.Lock()


def log(*args):
    print("[controlador-pronto]", *args, flush=True)


# ---------------------------------------------------------------------------
# 2. A regra -- o coração da aplicação
# ---------------------------------------------------------------------------
def decidir(temperatura, estado):
    """Devolve "on", "off" ou None (não fazer nada).

    Histerese: dois limites em vez de um. Com um limite só (liga e desliga em
    28 °C), o ruído do sensor em torno de 28 faria o relé bater sem parar.
    Comparar com o estado evita mandar de novo o comando que já foi cumprido.
    """
    try:
        temperatura = float(temperatura)        # tolera "24.7" entre aspas (Aula 6, seção 5.5)
    except (TypeError, ValueError):
        return None                             # sem temperatura válida, não decide nada

    estado_atual = str(estado or "").upper()
    if temperatura >= LIGA and estado_atual != "ON":
        return "on"
    if temperatura <= DESLIGA and estado_atual != "OFF":
        return "off"
    return None


# ---------------------------------------------------------------------------
# 3. Conversa com o Orion
# ---------------------------------------------------------------------------
def orion(metodo, caminho, corpo=None):
    """Uma requisição ao Orion no tenant da plataforma. Devolve (status, json ou None, cabeçalhos)."""
    cabecalhos = dict(TENANT)
    dados = None
    if corpo is not None:
        dados = json.dumps(corpo).encode()
        cabecalhos["Content-Type"] = "application/json"   # só com corpo: GET com Content-Type dá 400
    pedido = urllib.request.Request(ORION + caminho, data=dados, method=metodo, headers=cabecalhos)
    try:
        with urllib.request.urlopen(pedido, timeout=5) as resposta:
            bruto = resposta.read()
            return resposta.status, (json.loads(bruto) if bruto else None), resposta.headers
    except urllib.error.HTTPError as erro:
        return erro.code, None, erro.headers


def garantir_subscricao():
    """Espera o Orion, procura uma subscrição que já notifique este controlador e, se não houver, cria."""
    while True:
        try:
            status, lista, _ = orion("GET", "/v2/subscriptions?limit=1000")
            if status != 200:
                raise RuntimeError(f"GET /v2/subscriptions respondeu {status}")
            for s in lista:
                if s.get("notification", {}).get("http", {}).get("url") == NOTIFICAR_EM:
                    with trava:
                        subscricao.update(id=s["id"], situacao="já existia")
                    log("subscrição já existia:", s["id"])
                    return
            corpo = {
                "description": DESCRICAO,
                "subject": {"entities": [{"idPattern": ".*", "type": "ClimateStation"}],
                            "condition": {"attrs": ["temperature"]}},
                "notification": {"http": {"url": NOTIFICAR_EM},
                                 "attrs": ["temperature", "state"],
                                 "attrsFormat": "keyValues"},
            }
            status, _, cabecalhos = orion("POST", "/v2/subscriptions", corpo)
            if status != 201:
                raise RuntimeError(f"POST /v2/subscriptions respondeu {status}")
            novo = cabecalhos.get("Location", "").rsplit("/", 1)[-1]
            with trava:
                subscricao.update(id=novo, situacao="criada")
            log("subscrição criada:", novo, "->", NOTIFICAR_EM)
            return
        except Exception as erro:                       # Orion ainda subindo, rede, etc.
            with trava:
                subscricao["situacao"] = f"tentando de novo: {erro}"
            log("Orion indisponível, nova tentativa em 5 s:", erro)
            time.sleep(5)


def enviar_comando(entidade, tipo, comando):
    """PATCH no Orion, como na Etapa 4: o Orion encaminha ao IoT Agent."""
    try:
        status, _, _ = orion("PATCH", f"/v2/entities/{entidade}/attrs?type={tipo}",
                             {comando: {"type": "command", "value": ""}})
        return status                                   # 204 = encaminhado ao IoT Agent
    except Exception as erro:
        log("falha ao enviar", comando, "para", entidade, ":", erro)
        return 0


def tratar(entidade):
    """Uma entidade da notificação: decide e, se for o caso, comanda."""
    eid, tipo = entidade["id"], entidade.get("type", "ClimateStation")
    temperatura, estado = entidade.get("temperature"), entidade.get("state")
    comando = decidir(temperatura, estado)
    if comando is None:
        return
    with trava:
        if time.time() - ultimo_comando.get(eid, 0) < ESPERA:
            return                                      # já mandamos há pouco: o estado ainda não voltou
        ultimo_comando[eid] = time.time()
    status = enviar_comando(eid, tipo, comando)
    with trava:
        contadores[comando if status == 204 else "erros"] += 1
        historico.appendleft({"quando": datetime.now().strftime("%H:%M:%S"), "entidade": eid,
                              "temperatura": temperatura, "estado": estado, "comando": comando, "status": status})
    log(f"{eid}: {temperatura} °C, relé {estado} -> {comando} ({status})")


# ---------------------------------------------------------------------------
# 4. Servidor HTTP: recebe as notificações e mostra o status
# ---------------------------------------------------------------------------
class Controlador(BaseHTTPRequestHandler):
    def _json(self, status, corpo):
        bruto = json.dumps(corpo, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(bruto)))
        self.end_headers()
        self.wfile.write(bruto)

    def do_POST(self):
        tamanho = int(self.headers.get("Content-Length", 0))
        try:
            notificacao = json.loads(self.rfile.read(tamanho) or b"{}")
        except ValueError:
            self._json(400, {"erro": "corpo não é JSON"})
            return
        self._json(200, {"recebido": True})         # responda rápido: o Orion espera
        with trava:
            contadores["notificacoes"] += 1
        for entidade in notificacao.get("data", []):
            tratar(entidade)

    def do_GET(self):
        with trava:
            self._json(200, {"limites": {"liga": LIGA, "desliga": DESLIGA}, "subscricao": dict(subscricao),
                             "contadores": contadores, "ultimas": list(historico)[:10]})

    def log_message(self, formato, *args):
        pass


if __name__ == "__main__":
    log(f"Liga em >= {LIGA} °C, desliga em <= {DESLIGA} °C | notificações em {NOTIFICAR_EM}")
    threading.Thread(target=garantir_subscricao, daemon=True).start()
    ThreadingHTTPServer(("0.0.0.0", PORTA), Controlador).serve_forever()
```

---

*Material da disciplina PEL 220 (Centro Universitário FEI), construído com apoio do Claude Code. Comandos, respostas e
números obtidos em 11/11/2026 na pilha `Material de Apoio/aula06-fiware-contexto.zip`.*
