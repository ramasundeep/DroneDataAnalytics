FROM python:3.11-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY bridge/requirements.txt /app/bridge/requirements.txt
RUN pip install --no-cache-dir -r /app/bridge/requirements.txt
COPY common /app/common
COPY bridge /app/bridge
EXPOSE 8091
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8091/health').status==200 else 1)"
CMD ["python", "-m", "bridge.mqtt_ingest"]
