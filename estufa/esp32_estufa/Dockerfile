# PEL220 - Projeto estufa: ESP32 simulada da estufa (DHT22, solo, LDR e dois relés, por MQTT)
FROM python:3.12-slim

WORKDIR /app
RUN pip install --no-cache-dir paho-mqtt==2.1.0

COPY esp32_estufa.py .

# -u: sem buffer de saída, para o "docker logs -f" mostrar cada mensagem na hora
CMD ["python", "-u", "esp32_estufa.py"]
