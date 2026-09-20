FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    TZ=Asia/Karachi

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends tzdata fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN mkdir -p data

# Default: run the built-in daily scheduler (keeps the container alive).
# Override at `docker run`/`docker compose run` time for one-off commands, e.g.:
#   docker compose run --rm tender-poster python main.py --dry-run
CMD ["python", "scheduler.py"]
