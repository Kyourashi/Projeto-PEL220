# PEL220 - Estufa em 3D: a página (Three.js) e a ponte para o Orion.
# Só a biblioteca padrão do Python: nada a instalar.
FROM python:3.12-slim

WORKDIR /app
COPY servidor.py .
COPY web ./web

CMD ["python", "-u", "servidor.py"]
