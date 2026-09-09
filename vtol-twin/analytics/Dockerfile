FROM python:3.11-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY analytics/requirements.txt /app/analytics/requirements.txt
RUN pip install --no-cache-dir -r /app/analytics/requirements.txt
COPY common /app/common
COPY bridge /app/bridge
COPY analytics /app/analytics
COPY ditto/thing-VTOL-1.json /app/ditto/thing-VTOL-1.json
COPY data/samples /app/data/samples
EXPOSE 8092
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8092/health').status==200 else 1)"
CMD ["python", "-m", "analytics"]
