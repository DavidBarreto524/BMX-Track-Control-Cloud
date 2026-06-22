FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY bmx-track-control-cloud/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bmx-track-control-cloud/app ./app
COPY bmx-track-control-cloud/.env.example ./.env.example

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
