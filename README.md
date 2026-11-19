# Projeto PEL220 — IoT e Gêmeos Digitais

**PEL220 — Internet das Coisas e Gêmeos Digitais** · Centro Universitário FEI · Prof. Dr. Rafael Gomes Alves

Plataforma FIWARE da disciplina (Orion, IoT Agent JSON, Mosquitto, Cygnus, MySQL, Grafana), baseada no material de apoio da Aula 6.

## Estrutura

```
fiware/          a plataforma: docker-compose.yml da Base + docker-compose.override.yml (serviços da estufa)
modelo-dados/    modelo de dados NGSI-v2 da estufa (marco da Aula 7) + teste no Orion
estufa/          o projeto rodando (alface): ESP32 simulada, gravador do clima, configuração do tenant e painel no Grafana (marco da Aula 8)
docs/aula06/     roteiro da Aula 6, material complementar e coleção Postman
docs/aula07/     roteiro da Aula 7 (Orion avançado, Cygnus, Grafana), material complementar e coleção Postman
ferramentas/     scripts auxiliares (latencia_comando.py, concorrencia.py, gerar_colecao.py)
```

## O projeto: a estufa no ar, com painel

Passo a passo em [`estufa/README.md`](estufa/README.md). Em resumo, de dentro de `fiware/`:

```bash
docker compose up -d --wait orion
docker compose up -d --wait iot-agent
docker compose up -d --wait cygnus
python3 ../estufa/configurar.py
docker compose up -d --build esp32-estufa
docker compose up -d --build gravador-clima
docker compose up -d grafana-estufa      # painel em http://localhost:3002
```

Quem já roda a versão anterior: `docker compose stop esp32-estufa` antes do `configurar.py`, que reprovisiona a placa.

## A Base do professor, etapa por etapa (GitHub Codespaces ou máquina local com Docker)

Todos os comandos partem da pasta `fiware/`:

```bash
cd fiware
```

Suba **uma etapa por vez**. Não use `docker compose up -d` sem nomes, porque a ESP32 subiria antes do provisionamento.

| Etapa | Comando | O que entra |
|---|---|---|
| 1 | `docker compose up -d orion` | Orion + MongoDB |
| 2 | `docker compose up -d iot-agent` | IoT Agent + Mosquitto (depois, provisionar pelo Postman) |
| 3 | `docker compose up -d --build esp32-simulada` | ESP32 simulada (DHT22 + relé) |
| 4 | — | comandos `on`/`off` pelo Orion |
| 5 | `docker compose up -d --build clima-externo` | provedor de clima (Open-Meteo) |
| 6 | `docker compose up -d cygnus` | Cygnus + MySQL (histórico) |
| 7 | `docker compose up -d grafana` | painéis (porta 3000) |
| 8 | `docker compose up -d --build controlador` | controle automático (histerese) |

Teste rápido da Etapa 1:

```bash
curl -s http://localhost:1026/version
```

Para parar: `docker compose down`. Para apagar também os dados, use `docker compose down -v`.

## Portas

| Serviço | Porta |
|---|---|
| Orion (NGSI-v2) | 1026 |
| IoT Agent (provisionamento) | 4041 |
| Mosquitto (MQTT) | 1883 |
| MongoDB | 27017 |
| Cygnus | 5050 / 5080 |
| MySQL | 3306 |
| Grafana | 3000 (pronto: 3001 · painel da estufa: 3002) |
| Controlador | 5001 (pronto: 5002) |
| Clima externo | 3010 |

Roteiro completo: [`docs/aula06/README.md`](docs/aula06/README.md) e [`fiware/README.md`](fiware/README.md).
