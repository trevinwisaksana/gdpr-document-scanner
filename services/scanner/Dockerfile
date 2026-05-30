# Build context must be the repo root so app/ and detectors/ are available.
# Cloud Build passes "." as the context — see cloudbuild.yaml.
FROM python:3.12-slim

WORKDIR /app

RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ app/
COPY detectors/ detectors/
COPY services/scanner/main.py .

USER appuser

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
