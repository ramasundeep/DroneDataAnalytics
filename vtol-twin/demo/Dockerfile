FROM python:3.11-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY demo/requirements.txt /app/demo/requirements.txt
RUN pip install --no-cache-dir -r /app/demo/requirements.txt
COPY ditto/thing-VTOL-1.json /app/ditto/thing-VTOL-1.json
COPY demo /app/demo
EXPOSE 8090
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8090/health').status==200 else 1)"
CMD ["python", "-m", "demo"]
