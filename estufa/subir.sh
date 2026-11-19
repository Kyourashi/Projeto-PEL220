#!/usr/bin/env bash
# =================================================================================
#  PEL220 - Estufa: sobe (ou atualiza) a estufa inteira, na ordem certa.
#  Pode rodar sempre: com a pilha no ar, parada, ou depois que o Codespace desligou.
#
#      bash estufa/subir.sh
#
#  Para no primeiro erro e mostra onde foi.
# =================================================================================
set -e
cd "$(dirname "$0")/../fiware"
BUILD="--build"
[ "${SEM_BUILD:-}" = 1 ] && BUILD="--no-build"     # só para testes sem acesso ao PyPI

echo "== 1/5 Parando a ESP32 e o gravador do clima (voltam depois do cadastro)"
docker compose stop esp32-estufa gravador-clima

echo "== 2/5 Orion, IoT Agent e Cygnus"
docker compose up -d --wait orion
docker compose up -d --wait iot-agent
docker compose up -d --wait cygnus

echo "== 3/5 Estufa, cadastro da ESP32 e subscrições"
python3 ../estufa/configurar.py

echo "== 4/5 ESP32, gravador do clima e painel"
docker compose up -d $BUILD esp32-estufa
docker compose up -d $BUILD gravador-clima
docker compose up -d grafana-estufa
docker compose restart grafana-estufa            # carrega o painel do arquivo

echo "== 5/5 Conferência"
sleep 15
docker compose ps --format "table {{.Name}}\t{{.Status}}"
echo
echo "Última medida da ESP32:"
docker logs --tail 1 esp32-estufa
echo "Última leitura do clima:"
docker logs --tail 1 gravador-clima
echo
if [ -n "${CODESPACE_NAME:-}" ]; then
  echo "Painel: https://${CODESPACE_NAME}-3002.${GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN:-app.github.dev}"
  echo "Se o link der 404: aba PORTAS → Encaminhar uma Porta → 3002 → Enter, e abra o link de novo."
else
  echo "Painel: http://localhost:3002"
fi
