FROM python:3.12-slim

WORKDIR /app

RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser

COPY services/dispatcher/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/dispatcher/main.py .

USER appuser

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
