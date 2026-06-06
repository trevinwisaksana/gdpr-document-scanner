FROM python:3.12-slim

WORKDIR /app

RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser

COPY docker/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ app/
COPY detectors/ detectors/
COPY scanner/ scanner/

USER appuser

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
