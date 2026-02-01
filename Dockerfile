FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY *.py .
COPY ute ./ute

# Run as non-root user
RUN useradd -m -u 1000 ute2mqtt
USER ute2mqtt

CMD ["python", "main.py"]
