FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/src \
    HACKC_DATA_DIR=/data \
    HACKC_OUTPUT_DIR=/output

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src
COPY configs ./configs
COPY README.md .

RUN mkdir -p /data /output

ENTRYPOINT ["python", "-m", "hackaithon_c.run"]
CMD ["--workflow", "contest-strict", "--data-dir", "/data", "--output-dir", "/output", "--run-dir", "/output/neko-run", "--auto-resume", "--checkpoint-every", "1"]
