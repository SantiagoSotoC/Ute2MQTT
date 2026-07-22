ARG BUILD_FROM=python:3.11-alpine
FROM $BUILD_FROM

# Instalar dependencias del sistema
RUN \
    apk add --no-cache \
        tzdata

# Instalar dependencias Python
COPY requirements.txt /tmp/requirements.txt
RUN \
    pip install --no-cache-dir \
        -r /tmp/requirements.txt

# Copiar aplicación
COPY ute/ /app/ute/
COPY main.py /app/main.py
COPY scheduler.py /app/scheduler.py
COPY web_ui/ /app/web_ui/

# Copiar script de inicio
COPY run.sh /
RUN chmod a+x /run.sh

# Directorio de trabajo
WORKDIR /app

CMD ["/run.sh"]
