# Aula 10 — Material complementar

**CCM130 — Conectividade e IoT** · *Fluxo de dados completo*
Centro Universitário FEI · Departamento de Ciência da Computação
Prof. Rafael Gomes Alves — ralves@fei.edu.br

---

## O que é este material

O roteiro para construir, **uma peça de cada vez**, uma solução IoT completa: um ventilador inteligente na sala
K501. Um único dispositivo, a **ESP32 simulada com DHT22 e módulo relé**, troca medidas e comandos por **MQTT**; a
plataforma guarda o contexto, busca o clima de uma API externa, grava o histórico, mostra tudo em painéis e, no
final, decide sozinha quando ligar o relé. Verificado com Orion 4.1, IoT Agent JSON 3.7, Cygnus 3.11 e Grafana 10.4.

Toda etapa tem o mesmo ritmo: **suba** o componente novo, **execute** a pasta da etapa no Postman e **verifique**
antes de seguir.

| Etapa | O que entra | Pergunta que responde |
|---|---|---|
| 1 | Orion + MongoDB | Onde a plataforma guarda o estado do mundo? |
| 2 | IoT Agent + Mosquitto | Como a plataforma conhece o dispositivo? |
| 3 | ESP32 simulada | Como o dado do sensor vira contexto? |
| 4 | — | Como a aplicação aciona o relé? |
| 5 | Provedor de clima | Como trazer dados de outra API? |
| 6 | Cygnus + MySQL | Como guardar o passado? |
| 7 | Grafana | Como mostrar para pessoas? |
| 8 | Controlador | Como a plataforma decide sozinha? |
| 9 | — | O que os dados dizem? |

---

## Estrutura

```
Aula 10 - Material complementar/
│
├── docker-compose.yml                todos os serviços, comentados por etapa
├── mosquitto/mosquitto.conf
├── CCM130 - Aula 10 - Fluxo de dados completo.postman_collection.json     uma pasta por etapa
├── queries.txt                       consultas para os painéis (etapas 7 e 9)
├── esp32_simulada/                   o dispositivo: DHT22 + relé, por MQTT
├── clima/                            provedor de contexto: clima do campus pela API Open-Meteo
├── controlador/
│     └── controlador.py              ESQUELETO: complete a função decidir() na etapa 8
└── Atividade GABARITO/               ⚠ não distribuir antes da entrega
      ├── controlador.py
      ├── painel_aula.json            Dashboards → New → Import
      ├── painel_desafio.json
      └── queries_desafio.txt
```

---

## Antes de começar

1. Pare o ambiente da aula anterior: `docker compose down` na pasta da Aula 9. Os contêineres têm os mesmos nomes.
2. Abra um terminal **nesta pasta**. Todos os comandos abaixo partem daqui.
3. No Postman: **Import** → a coleção desta pasta.
4. No MQTTX: conexão `localhost:1883` (a partir da etapa 2), assinando `/json/ccm130/#` e `/ccm130/#`.

> **Não use `docker compose up -d` sem nomes.** A ESP32 subiria antes do provisionamento e criaria a entidade
> `Thing:esp32001`.

---

## Etapa 1 — O Orion guarda o contexto

```bash
docker compose up -d orion
```

**Postman, pasta Etapa 1:** confere a versão, cria a sala `urn:ngsi-ld:Room:K501` e a lê.

**Verifique:** `docker ps` mostra `fiware-orion` e `db-mongo`; a sala volta com `capacity` 40.

## Etapa 2 — O IoT Agent conhece a ESP32

```bash
docker compose up -d iot-agent
```

**Postman, pasta Etapa 2:** cria o grupo de serviço (chave `ccm130`) e provisiona o dispositivo `esp32001`
(entidade `urn:ngsi-ld:ClimateStation:ESP32001`):

| Medida (`object_id` → atributo) | Comando | Estático |
|---|---|---|
| `t` → `temperature` (Number) | `on` | `refRoom` → `urn:ngsi-ld:Room:K501` |
| `h` → `humidity` (Number) | `off` | |
| `s` → `state` (Text) | | |

**Verifique:** o dispositivo aparece em `/iot/devices`; o Orion ganhou um **registro** com o IoT Agent como provedor de
`on` e `off`; a entidade já existe, só com esses comandos.

## Etapa 3 — A ESP32 publica medidas

```bash
docker compose up -d --build esp32-simulada
docker logs -f esp32-simulada
```

| Mensagem | Tópico | Exemplo |
|---|---|---|
| Medidas | `/json/ccm130/esp32001/attrs` | `{"t": 25.5, "h": 63.3, "s": "OFF"}` |
| Comandos | `/ccm130/esp32001/cmd` | `{"on": ""}` |
| Resultado | `/json/ccm130/esp32001/cmdexe` | `{"on": "OK - rele ligado"}` |

**Postman, pasta Etapa 3:** lê a entidade, confere os tipos e que `Thing:esp32001` não existe.

**Verifique:** o JSON chega ao MQTTX a cada 5 s, e a temperatura sobe devagar (a sala esquenta até perto de 29 °C).

> **A placa real entra no lugar da simulada sem mudar nada na plataforma.** `docker compose stop esp32-simulada` e rode
> o firmware da Aula 9 (`esp32/estacao_esp32.py`, com `TRANSPORTE = "MQTT"` e o IP do seu computador).

## Etapa 4 — A aplicação comanda o relé

Nada novo para subir. **Postman, pasta Etapa 4:** envia `on` e `off` ao **Orion**, nunca à ESP32:

```
PATCH http://localhost:1026/v2/entities/urn:ngsi-ld:ClimateStation:ESP32001/attrs?type=ClimateStation
{"on": {"type": "command", "value": ""}}
```

**Verifique no MQTTX:** `{"on":""}` em `.../cmd`, depois `.../cmdexe` e `{"s":"ON"}` em `.../attrs`. **No Orion:** `on_status`
OK, `on_info` com o texto e `state` ON. Nas medidas seguintes, a temperatura cai. O `204` só quer dizer que o Orion
encaminhou; quem confirma é a ESP32.

## Etapa 5 — O clima do campus entra no contexto

```bash
docker compose up -d --build clima-externo
```

`clima/provedor.py` é um **provedor de contexto**: quando alguém lê `urn:ngsi-ld:WeatherObserved:FEI`, o Orion encontra o
registro e faz `POST http://clima-externo:3010/v2/op/query`; o provedor consulta a API pública **Open-Meteo**, converte as
unidades (umidade de 0 a 1, vento em m/s) e responde em NGSI v2, guardando a resposta por 60 s.

**Postman, pasta Etapa 5:** cria o registro, lê o clima e testa uma subscrição sobre ele.

**Verifique:** a entidade traz o clima real; `docker logs clima-externo` mostra a pergunta do Orion.

- **Sem internet?** O provedor responde valores simulados com `source = simulado` (ou force com `MODO=simulado`).
- **Presente, não histórico.** O Orion não guarda atributo de provedor: a subscrição **nunca** dispara (`timesSent` 0).
  Para guardar o clima, alguém precisa gravá-lo no Orion periodicamente.
- **No Projeto 2**, só `buscar_clima()` muda. Chave de API vai em variável de ambiente, nunca no GitHub.

## Etapa 6 — O Cygnus guarda o passado

```bash
docker compose up -d cygnus
```

Sobe também o MySQL. Espere `fiware-cygnus` ficar `healthy` em `docker ps`.

**Postman, pasta Etapa 6:** cria a subscrição para `http://cygnus:5050/notify`, com `attrsFormat: normalized` (o Orion 4
recusa `legacy`), e confere o status (`timesSent` subindo, `lastSuccessCode` 200).

**Verifique no banco:**

```bash
docker exec -it db-mysql mysql -uroot -p123
SHOW TABLES FROM ccm130;
SELECT * FROM ccm130.`urn_ngsi-ld_ClimateStation_ESP32001_ClimateStation` ORDER BY recvTimeTs DESC LIMIT 6;
```

Uma tabela por entidade, uma linha por atributo e **tudo em texto**. Daí o `CAST` e o `/ 1000` nas consultas.

## Etapa 7 — Painéis no Grafana

```bash
docker compose up -d grafana
```

**Abra `http://localhost:3000`:** `admin` / `admin`, e *Skip* na troca de senha (se trocar, ajuste a variável `grafanaPass`
da coleção).

**A fonte de dados:** *Connections → Data sources → Add new data source → MySQL*:

| Campo | Valor |
|---|---|
| Host URL | `mysql-db:3306` (nome do contêiner, não `localhost`) |
| Database name | `ccm130` |
| Username / Password | `root` / `123` |

*Save & test* deve dar mensagem verde.

**O painel:** *Dashboards → New → New dashboard → Add visualization*, fonte MySQL. Em cada visualização: troque o editor
para **Code** (o *Builder* não serve, porque o Cygnus grava texto), *Format* **Time series**, cole a consulta de
`queries.txt` e clique *Apply*.

| Painel | Visualização | Dica |
|---|---|---|
| Histórico | Time series | *Standard options → Unit → Celsius* |
| Presente | Stat | É o `LIMIT 1` que dá o valor atual |
| Relé | State timeline | Sem `CAST`: o valor é `ON` ou `OFF` |

Período *Last 15 minutes*, atualização *5s*. Em *Dashboard settings → General → Tags*, coloque `aula10` e salve.

**Postman, pasta Etapa 7:** confere a fonte de dados, o histórico e as três visualizações.

## Etapa 8 — Fechando o laço

```bash
docker compose up -d --build controlador
```

**Postman, pasta 8.1:** cria a subscrição para `http://controlador:5001/notify` (`temperature` e `state`, em `keyValues`).

**Verifique:** em `http://localhost:5001/status`, `notificacoes` sobe e `on`/`off` seguem em zero: o contexto chega, mas o
esqueleto ainda não decide.

**Sua vez:** complete `decidir()` em `controlador/controlador.py` com a regra de **histerese**:

| Temperatura | Relé | Comando |
|---|---|---|
| ≥ 28 °C (`LIGA`) | não está ON | `on` |
| ≤ 24 °C (`DESLIGA`) | não está OFF | `off` |
| entre 24 e 28 °C | qualquer | nenhum — mantém o estado |

```bash
docker compose up -d --build controlador
docker logs -f controlador
```

Com um limite só, o ruído do sensor faria o relé bater sem parar. O restante (receber a notificação, enviar o `PATCH` e
não repetir comando em menos de `ESPERA` = 10 s) já está pronto.

**Verifique:** no painel, a temperatura sobe até 28 °C, o relé liga, ela cai até 24 °C e o relé desliga. Um ciclo leva
cerca de 2 minutos. **Postman, pasta 8.2:** confere cada decisão contra a regra.

## Etapa 9 — Indicadores

Acrescente ao painel um **Bar chart** com a média por minuto (`queries.txt`). Depois, o **desafio:** crie um painel com a
etiqueta `desafio` e três indicadores do período, calculados no SQL:

1. **número de acionamentos do relé** (dica: `LAG(attrValue) OVER (ORDER BY recvTimeTs)`);
2. **tempo com o relé ligado, em %** (dica: `AVG(attrValue = 'ON')`);
3. **mínima, máxima e média** da temperatura.

**Postman, pasta Etapa 9:** confere a média e o painel do desafio.

---

## Recomeçando

```bash
docker compose stop esp32-simulada      # antes da pasta Limpeza do Postman
docker compose down                     # para tudo e mantém os dados
docker compose down -v                  # apaga também histórico, painéis e fonte de dados
```

---

## Problemas comuns

| Sintoma | Etapa | Causa | Solução |
|---|---|---|---|
| `Container name already in use` | 1 | Contêineres de outra aula | `docker compose down` na pasta da outra aula |
| Surge `Thing:esp32001` | 3 | A ESP32 subiu antes do provisionamento, ou publicou depois da limpeza | Provisione primeiro; pare a ESP32 antes da limpeza; remova a `Thing` |
| Comando responde 404 | 4 | Falta o `?type=ClimateStation` | Mantenha o `type` na URL |
| `400` num GET ao Orion | todas | Cabeçalho `Content-Type` em GET ou DELETE | Remova o cabeçalho |
| `404` ao ler o clima | 5 | Registro não criado ou provedor fora do ar | Pasta Etapa 5; `http://localhost:3010/health` |
| `source: simulado` | 5 | O contêiner não alcança a internet | Normal em rede bloqueada; a aula segue |
| `400 invalid attrsFormat` | 6 | `legacy` de tutoriais antigos | Use `normalized` |
| `failsCounter` subindo | 6, 8 | Serviço parado ou URL com `localhost` | `docker ps`; use `cygnus:5050` e `controlador:5001` |
| `Table doesn't exist` | 6, 7 | A tabela nasce com a primeira notificação | Confira a subscrição; `SHOW TABLES FROM ccm130;` |
| *Save & test* falha | 7 | Host `localhost`, ou MySQL ainda subindo | Use `mysql-db:3306`; espere `healthy` |
| Painel vazio | 7 | Modo *Builder*, ou período antigo | Modo *Code*; *Last 15 minutes* |
| Postman: 401 no Grafana | 7 | Você trocou a senha do admin | Ajuste `grafanaPass` na coleção |
| Nenhuma decisão em 8.2 | 8 | `decidir()` incompleta, ou faltou reconstruir | `docker compose up -d --build controlador` |
| O relé bate a cada medida | 8 | Um limite só, ou faltou comparar com o estado | Dois limites e `estado != "ON"` |
