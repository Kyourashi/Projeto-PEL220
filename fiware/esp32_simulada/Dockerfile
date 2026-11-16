# CCM130 - Conectividade e IoT | Aula 10 - ESP32 simulada (DHT22 + relé, por MQTT)
FROM python:3.12-slim

WORKDIR /app
RUN pip install --no-cache-dir paho-mqtt==2.1.0

COPY esp32_simulada.py .

# -u: sem buffer de saída, para o "docker logs -f" mostrar cada mensagem na hora
CMD ["python", "-u", "esp32_simulada.py"]
