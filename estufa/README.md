# Painel da estufa — marco da Aula 8 (25/11)

O marco pede três itens:
1. três perguntas que o painel responde, e para quem;
2. a visualização escolhida para cada uma;
3. a consulta SQL de cada painel.

**Critério de pronto:** o painel mostra dados **do próprio grupo**, gravados pelo Cygnus a partir de uma subscrição **que o grupo criou**.

| Peça | Onde |
|---|---|
| Nó da estufa (ESP32 simulada) | `esp32_estufa/`, no tenant `estufa`: publica `t`, `h`, `m`, `l`, `f`, `p` e responde aos comandos |
| Subscrição do grupo | criada por `configurar.py`: **"Historico da estufa para o Cygnus"** (Orion → `cygnus:5050`) |
| Histórico | MySQL, banco `estufa`, tabela `` `urn_ngsi-ld_Device_ESP32-001_Device` `` |
| Painel | `grafana/paineis/painel_estufa.json`, servido em `http://localhost:3002` pelo serviço `grafana-estufa` |
| Serviços novos | `fiware/docker-compose.override.yml`; o `docker-compose.yml` da Base fica intacto |

![Painel da estufa](painel-estufa.png)

## Como subir (Codespace ou máquina com Docker)

```bash
git pull
cd fiware
docker compose up -d --wait orion
docker compose up -d --wait iot-agent
docker compose up -d --wait cygnus            # inclui o MySQL
python3 ../estufa/configurar.py               # estufa, provisionamento e subscrição (pode repetir)
docker compose up -d --build esp32-estufa     # só DEPOIS do configurar.py
docker compose up -d grafana-estufa           # o painel, na porta 3002
```

- **No Codespace:** aba **Portas** → porta **3002** → ícone do globo. O painel abre direto, sem login. Para editar, entre com `admin`/`admin`.
- **Espere alguns minutos:** as curvas começam vazias e o histórico cresce uma medida a cada 5 s. A física da simulação é acelerada: um ciclo do ventilador leva cerca de 3 min, e um da bomba, cerca de 7 min.
- **Para conferir a subscrição:** `curl -s -H 'fiware-service: estufa' -H 'fiware-servicepath: /' localhost:1026/v2/subscriptions`. O esperado é `status: active`, `timesSent` subindo e `lastSuccessCode: 200`.
- **Para mandar um comando à mão:**

  ```bash
  curl -s -X PATCH 'localhost:1026/v2/entities/urn:ngsi-ld:Device:ESP32-001/attrs?type=Device' \
    -H 'fiware-service: estufa' -H 'fiware-servicepath: /' -H 'Content-Type: application/json' \
    -d '{"pumpOn": {"type": "command", "value": ""}}'
  ```

- **Para parar sem perder o histórico:** `docker compose stop`. Nunca use `down -v`.

## As três perguntas

| # | Pergunta | Para quem | Que decisão apoia | Visualização |
|---|---|---|---|---|
| 1 | **A estufa está bem agora?** | o operador da estufa | intervir já (ex.: 29 °C com o ventilador desligado, ou solo abaixo de 30 % sem a bomba) | **Stat**, com cores nos limites da AgriGreenhouse, e o estado de cada relé |
| 2 | **O controle mantém a estufa nas faixas?** | o grupo, que projeta e ajusta a regra (e, na Aula 9, o gêmeo digital) | manter ou mudar os limites 24/28 °C e 30/45 %; ver se a histerese oscila rápido demais | **Time series** com as linhas dos limites + **State timeline** dos relés |
| 3 | **Quanto tempo os atuadores ficam ligados?** | quem paga a energia (ventilador) e a energia e a água (bomba) | prever o consumo; avaliar se mudar um limite compensa | **Bar chart** do tempo ligado por janela de 5 min + **Stat** do período (% e número de acionamentos) |

Seguimos a regra da Aula 7: a pergunta escolhe a visualização.
- O valor de **agora** vai num Stat.
- A **evolução**, num Time series.
- O **estado** de cada relé, num State timeline.
- O **resumo por período**, num Bar chart.

### A consulta de cada painel

Todas leem a mesma tabela. Na tabela, `attrValue` é **texto** e `recvTimeTs` está em **milissegundos**, por isso as consultas usam `CAST` e `/ 1000`. As consultas ficam em `grafana/gerar_painel.py`, que gera o JSON do painel.

**Pergunta 1 — Stat (temperatura; o mesmo para `soilMoisture`, `relativeHumidity` e `lightLevel`)**

```sql
SELECT
  recvTimeTs / 1000 AS "time",
  CAST(attrValue AS DECIMAL(6,2)) AS "temperatura"
FROM `urn_ngsi-ld_Device_ESP32-001_Device`
WHERE attrName = 'temperature'
ORDER BY recvTimeTs DESC
LIMIT 1
```

**Pergunta 1 — Stat do relé** (formato *Table*, sem CAST; mapeamento `ON` → Ligado, `OFF` → Desligado)

```sql
SELECT attrValue AS "ventilador"
FROM `urn_ngsi-ld_Device_ESP32-001_Device`
WHERE attrName = 'fanState'
ORDER BY recvTimeTs DESC
LIMIT 1
```

**Pergunta 2 — Time series** (`temperature`; o mesmo para `soilMoisture`)

```sql
SELECT
  recvTimeTs / 1000 AS "time",
  CAST(attrValue AS DECIMAL(6,1)) AS "temperatura"
FROM `urn_ngsi-ld_Device_ESP32-001_Device`
WHERE attrName = 'temperature'
  AND $__unixEpochFilter(recvTimeTs / 1000)
ORDER BY recvTimeTs ASC
```

**Pergunta 2 — State timeline** (consulta A com `fanState`, consulta B com `pumpState`)

```sql
SELECT
  recvTimeTs / 1000 AS "time",
  attrValue AS "ventilador"
FROM `urn_ngsi-ld_Device_ESP32-001_Device`
WHERE attrName = 'fanState'
  AND $__unixEpochFilter(recvTimeTs / 1000)
ORDER BY recvTimeTs ASC
```

**Pergunta 3 — Bar chart** (tempo ligado por janela de 5 min)

```sql
SELECT
  $__unixEpochGroupAlias(recvTimeTs / 1000, '5m'),
  100 * AVG(CASE WHEN attrName = 'fanState'  THEN attrValue = 'ON' END) AS "ventilador",
  100 * AVG(CASE WHEN attrName = 'pumpState' THEN attrValue = 'ON' END) AS "bomba"
FROM `urn_ngsi-ld_Device_ESP32-001_Device`
WHERE attrName IN ('fanState', 'pumpState')
  AND $__unixEpochFilter(recvTimeTs / 1000)
GROUP BY 1
ORDER BY 1
```

**Pergunta 3 — Stat do período** (formato *Table*): a mesma média, sem o `GROUP BY`.

**Pergunta 3 — Acionamentos** (formato *Table*: quantas vezes cada relé passou de OFF para ON)

```sql
SELECT
  SUM(attrName = 'fanState')  AS "ventilador",
  SUM(attrName = 'pumpState') AS "bomba"
FROM (
  SELECT attrName, attrValue,
         LAG(attrValue) OVER (PARTITION BY attrName ORDER BY recvTimeTs) AS anterior
  FROM `urn_ngsi-ld_Device_ESP32-001_Device`
  WHERE attrName IN ('fanState', 'pumpState')
    AND $__unixEpochFilter(recvTimeTs / 1000)
) AS mudancas
WHERE attrValue = 'ON' AND anterior = 'OFF'
```

### Por que a média das amostras dá o tempo ligado

$$
D = \frac{t_{ON}}{t_{total}} \approx \frac{1}{N} \sum_{i=1}^{N} s_i
$$

- **D:** ciclo de trabalho, a fração do tempo com o relé ligado (no painel, × 100 = %).
- **t_ON, t_total:** tempo ligado e tempo total do período, em segundos.
- **s_i:** vale 1 se a amostra *i* está `ON` e 0 se está `OFF`. Vem dos `fanState` e `pumpState` gravados pelo Cygnus.
- **N:** número de amostras no período, uma a cada 5 s (o intervalo da ESP32).

A aproximação vale porque as amostras são igualmente espaçadas: cada uma "representa" 5 s. Para passar a energia, faça E = P × D × t_total, em que P é a potência do ventilador ou da bomba. Esse dado vem da folha de dados e **ainda não está definido no projeto**.

## As três perguntas do marco da Aula 7

**1. Que tenant e que caminhos?**
- Tenant `estufa`, com `fiware-servicepath: /`, porque o projeto tem uma estufa só.
- Quando houver mais de uma, a ideia é usar um caminho por estufa (`/estufa001`, `/estufa002`), com um grupo de serviço por caminho. O painel e a aplicação passariam a ler com `/#`.
- Lembrete da Aula 7: sem o cabeçalho, a leitura vale para `/#` e a gravação para `/`.

**2. Que consultas a aplicação fará?** O modelo permite todas. Conferimos estas no Orion 4.1.0:

| Para quê | Consulta |
|---|---|
| alerta de calor | `GET /v2/entities?type=Device&q=temperature>28` |
| alerta de solo seco | `GET /v2/entities?type=Device&q=soilMoisture<30` |
| os nós de uma estufa (pai → filhos) | `GET /v2/entities?q=controlledAsset==urn:ngsi-ld:AgriGreenhouse:001` |
| relés ligados | `GET /v2/entities?type=Device&q=fanState==ON` |
| só medidas em °C | `GET /v2/entities?type=Device&mq=temperature.unitCode==CEL` |
| estufas perto do campus | `GET /v2/entities?type=AgriGreenhouse&georel=near;maxDistance:1000&geometry=point&coords=-23.7245,-46.5793` |

**3. Que atributos vão para o histórico, e por qual subscrição?**
- Atributos: `temperature`, `relativeHumidity`, `soilMoisture`, `lightLevel`, `fanState` e `pumpState`.
- Subscrição: **"Historico da estufa para o Cygnus"**:
  - `entities`: `idPattern ".*"`, type `Device`;
  - `attrsFormat`: `normalized`;
  - `throttling`: 1 s;
  - URL: `http://cygnus:5050/notify`.
- Ficam fora: os comandos e o resultado deles (`fanOn`, `fanOn_status`…) e a estufa, que não muda com o tempo. O `TimeInstant` vai junto, nos metadados (coluna `attrMd`).

Quanto isso grava:

$$
L = n_{attr} \times \frac{3600}{\Delta t} = 6 \times \frac{3600}{5} = 4320 \ \text{linhas/h}
$$

- **L:** linhas gravadas por hora para o nó.
- **n_attr = 6:** os atributos da subscrição.
- **Δt = 5 s:** o intervalo da ESP32.

Dá o dobro da sala da Aula 7 (2.160 linhas/h com 3 atributos) e cerca de 104 mil linhas por dia. É o custo do esquema "uma linha por atributo, tudo em texto", que é a questão de pesquisa da Aula 8.

## Limitações e próximos passos

- **Dados simulados:** os dados vêm de uma ESP32 simulada, com física simplificada e acelerada para o painel mostrar vários ciclos em 30 min. A placa real entra no lugar dela sem mudar a plataforma, porque usa o mesmo contrato MQTT.
- **Clima externo:** fica fora do histórico. Ele chega por **registro**, e registro não notifica (Aula 7). Para entrar no painel, seria preciso gravá-lo no Orion periodicamente.
- **Umidade do ar e luz:** não têm limiar de cor, porque o grupo ainda não definiu uma faixa para a cultura.
- **Regra de controle:** hoje é **local**, na ESP32 (histerese com os limites da AgriGreenhouse). Na Aula 9, o controlador e o gêmeo digital passam a ler esses limites do Orion.
- **Build local:** `docker compose up -d --build esp32-estufa` precisa de acesso ao PyPI (`pip install paho-mqtt`). No Codespace, funciona.
