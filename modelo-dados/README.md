# Modelo de dados — Estufa agrícola inteligente (NGSI-v2)

Marco da Aula 7 (PEL220). Ele pede:
- o diagrama das entidades (3 tipos ou mais) e dos relacionamentos;
- para cada atributo, o tipo, a unidade e a origem;
- ids em URN;
- um JSON de exemplo por tipo, aceito pelo Orion e lido de volta;
- quem cria, atualiza e apaga cada entidade.

**Documento para apresentar:** [`Modelo de dados - Estufa PEL220.pdf`](Modelo%20de%20dados%20-%20Estufa%20PEL220.pdf), com 4 páginas:
1. MER;
2. quem cria, atualiza e apaga cada entidade, e o checklist da Aula 6;
3. arquitetura e comunicação;
4. JSON de exemplo e resultado do teste.

- **Tenant:** `fiware-service: estufa` · `fiware-servicepath: /`
- **Chave do grupo no IoT Agent (apikey):** `estufa`
- **Unidades** (metadado `unitCode`, UN/CEFACT): `CEL` = °C · `P1` = % · `C62` = adimensional (0–1) · `MTK` = m² · `MTS` = m/s
- **Smart Data Models:** `Device` (dataModel.Device) · `AgriGreenhouse` (dataModel.Agrifood) · `WeatherObserved` (dataModel.Weather)

![MER](pagina-1.png)

## Entidades

| Entidade | id | Papel | Quem escreve |
|---|---|---|---|
| `Device` | `urn:ngsi-ld:Device:ESP32-001` | o nó ESP32 da estufa | IoT Agent (MQTT) |
| `AgriGreenhouse` | `urn:ngsi-ld:AgriGreenhouse:001` | a estufa (ativo físico) | aplicação (API) |
| `WeatherObserved` | `urn:ngsi-ld:WeatherObserved:FEI` | clima externo no campus | provedor de clima (registro, Aula 7) |

**Relacionamentos.** Ficam sempre na entidade filha e apontam para o pai:
- `Device.controlledAsset` → `AgriGreenhouse`: cada nó controla 1 estufa; uma estufa tem de 0 a N nós.
- `AgriGreenhouse.hasWeatherObserved` → `WeatherObserved`: cada estufa usa 1 clima; um clima serve de 0 a N estufas.
- Para ir do pai aos filhos, use `GET /v2/entities?q=controlledAsset==urn:ngsi-ld:AgriGreenhouse:001`.

**Origem dos atributos** (categorias da Aula 6):
- **medida:** `t`, `h`, `m`, `l`, `f` e `p` via MQTT;
- **estático:** provisionamento ou cadastro;
- **comando:** `fanOn`, `fanOff`, `pumpOn`, `pumpOff`, com os respectivos `_status` e `_info`;
- **externo:** o provedor de clima;
- **calculado:** `TimeInstant`, gerado pelo IoT Agent.

**Umidade relativa:** `relativeHumidity` vai de **0 a 1** (`C62`), como no SDM e no `clima-externo` da Base. O firmware divide a leitura do DHT22 por 100.

**Tópicos MQTT:**

| Mensagem | Tópico | Exemplo |
|---|---|---|
| Medidas | `/json/estufa/estufa001/attrs` | `{"t": 26.4, "h": 0.62, "m": 38.5, "l": 71.0, "f": "OFF", "p": "OFF"}` |
| Comandos | `/estufa/estufa001/cmd` | `{"fanOn": ""}` |
| Resultado | `/json/estufa/estufa001/cmdexe` | `{"fanOn": "OK - ventilador ligado"}` |

Os números vão sem aspas. Com `"26.4"` entre aspas, o valor vira texto e os filtros `q=temperature>25` deixam de funcionar.

## Arquivos

- `exemplos/AgriGreenhouse.json` e `exemplos/WeatherObserved.json`: o que a aplicação envia ao Orion (`POST /v2/op/update`).
- `provisionamento/grupo.json` e `provisionamento/dispositivo.json`: o grupo de serviço e a ESP32 no IoT Agent.
- `exemplos/*.lido.json`: o que o Orion devolveu no teste, no formato normalizado.

## Teste: aceito pelo Orion e lido de volta

```bash
cd fiware
docker compose up -d --wait iot-agent
python3 ../modelo-dados/testar_modelo.py
```

O script segue estes passos:
1. Cria o clima e a estufa no Orion.
2. Reprovisiona a ESP32 no IoT Agent.
3. Publica uma medida MQTT.
4. Faz o ciclo completo de um comando: `PATCH fanOn` → `cmd` → `PENDING` → `cmdexe` → `fanOn_status = OK`.
5. Lê as três entidades no formato normalizado e confere:
   - id em URN com o tipo;
   - `value` coerente com o `type`;
   - `unitCode` em toda grandeza;
   - `relativeHumidity` entre 0 e 1;
   - existência do alvo de cada `Relationship`;
   - ausência de uma entidade `Thing:estufa001`.

**Resultado em 18/11/2026** (Orion 4.1.0, IoT Agent JSON 3.7.0, Mosquitto 2.0.18): 63 verificações, 0 falhas.

## Em aberto para a Aula 7

- **Prefixo `ref`:** usamos os nomes do catálogo (`controlledAsset`, `hasWeatherObserved`), e não o prefixo `ref…`.
- **Medidas no `Device`:** no SDM, o `Device` não tem `temperature` nem `soilMoisture`. Seguimos o exemplo da Aula 1.
- **`hasAgriParcelParent`:** o SDM da `AgriGreenhouse` exige essa referência à parcela de terreno. `AgriParcel` é candidata a 4ª entidade.
- **Limites de controle:** ficam na estufa. O controlador da Base ainda lê `LIGA`/`DESLIGA` de variáveis de ambiente.
