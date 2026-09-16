FROM python:3.12-slim

# Evitar escritura de archivos .pyc y forzar salida inmediata en logs
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Instalar dependencias
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código del servidor MCP
COPY kiwi_client.py server.py ./

# Puerto por defecto para transporte SSE (Server-Sent Events)
EXPOSE 8000

# Punto de entrada
CMD ["python", "server.py"]
