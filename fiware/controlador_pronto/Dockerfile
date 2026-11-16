# PEL 220 | Plataforma FIWARE, Etapa 8 - Controlador PRONTO (regra com histerese + subscrição automática)
# Só a biblioteca padrão do Python. Depois de editar controlador.py:
#   docker compose up -d --build controlador-pronto
FROM python:3.12-slim

WORKDIR /app
COPY controlador.py .

CMD ["python", "-u", "controlador.py"]
