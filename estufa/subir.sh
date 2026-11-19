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

echo "== 4/5 ESP32, gravador do clima, painel e estufa em 3D"
docker compose up -d $BUILD esp32-estufa
docker compose up -d $BUILD gravador-clima
docker compose up -d grafana-estufa
docker compose restart grafana-estufa            # carrega o painel do arquivo
docker compose up -d --build estufa-3d           # só biblioteca padrão: o build não precisa do PyPI

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
  DOMINIO="${GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN:-app.github.dev}"
  echo "Painel:          https://${CODESPACE_NAME}-3002.${DOMINIO}"
  echo "Estufa em 3D:    https://${CODESPACE_NAME}-3003.${DOMINIO}"
  echo "Se um link der 404: aba PORTAS → Adicionar Porta → digite a porta (3002 ou 3003) → Enter."
else
  echo "Painel:          http://localhost:3002"
  echo "Estufa em 3D:    http://localhost:3003"
fi
