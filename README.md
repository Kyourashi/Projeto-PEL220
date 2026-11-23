# Projeto PEL220 — IoT e Gêmeos Digitais

**PEL220 — Internet das Coisas e Gêmeos Digitais** · Centro Universitário FEI · Prof. Dr. Rafael Gomes Alves

Plataforma FIWARE da disciplina (Orion, IoT Agent JSON, Mosquitto, Cygnus, MySQL, Grafana), baseada no material de apoio da Aula 6.

## Estrutura

```
fiware/          a plataforma: docker-compose.yml da Base + docker-compose.override.yml (serviços da estufa)
modelo-dados/    modelo de dados NGSI-v2 da estufa (marco da Aula 7) + teste no Orion
estufa/          o projeto rodando (alface): ESP32 simulada, gravador do clima, configuração do tenant, painel no Grafana (marco da Aula 8) e estufa em 3D
docs/aula06/     roteiro da Aula 6, material complementar e coleção Postman
docs/aula07/     roteiro da Aula 7 (Orion avançado, Cygnus, Grafana), material complementar e coleção Postman
ferramentas/     scripts auxiliares (refazer_aula7.py, custo_cygnus.sql, latencia_comando.py, concorrencia.py, gerar_colecao.py)
```

## O projeto: a estufa no ar, com painel

Da raiz do repositório, um comando sobe (ou atualiza) tudo na ordem certa:

```bash
git pull && bash estufa/subir.sh       # painel em http://localhost:3002 · estufa em 3D em http://localhost:3003
```

O passo a passo e o que cada etapa faz estão em [`estufa/README.md`](estufa/README.md).

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

## A Aula 7 de novo, num comando

Num Codespace novo, ou quando o Grafana da Base volta vazio, este script refaz o que a Aula 7 montou no tenant `ccm130`, mais o exercício de antes da Aula 8:

```bash
python3 ferramentas/refazer_aula7.py
```

- cadastra a sala K501 e a ESP32 (Etapas 1 e 2) e cria a subscrição do histórico para o Cygnus (Etapa 6);
- cria no Grafana da Base (porta 3000, `admin`/`admin`) a fonte MySQL e o painel com a etiqueta `aula10`: temperatura agora, temperatura, relé e média por minuto (Etapa 7), mais a umidade e a máxima do período (exercício);
- cria a subscrição *Umidade alta via MQTT*: com `humidity>70`, o Orion avisa em `pel220/umida`;
- no fim, confere tudo como os testes das Etapas 3, 6 e 7 da coleção da Base.

Pode rodar de novo: o que já existe é conferido, e o painel é regravado (o que for mudado nele pela interface se perde).

- Para ver o aviso de umidade: `docker exec mosquitto mosquitto_sub -t 'pel220/umida' -v`.
- Para forçar um aviso: `docker exec mosquitto mosquitto_pub -t /json/ccm130/esp32001/attrs -m '{"h": 75}'`. O valor vai também para o histórico.

A questão de pesquisa da Aula 8 (o custo do esquema do Cygnus) está em [`estufa/README.md`](estufa/README.md#questão-de-pesquisa-da-aula-8-quanto-custa-esse-esquema).

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
| Estufa em 3D | 3003 |
| Controlador | 5001 (pronto: 5002) |
| Clima externo | 3010 |

Roteiro completo: [`docs/aula06/README.md`](docs/aula06/README.md) e [`fiware/README.md`](fiware/README.md).
