FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY stockbot ./stockbot

ENV PYTHONUNBUFFERED=1 STATE_PATH=/data/state.json
VOLUME ["/data"]

CMD ["python", "-m", "stockbot"]
