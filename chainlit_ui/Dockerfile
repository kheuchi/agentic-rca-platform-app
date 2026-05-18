FROM python:3.12-slim AS base

WORKDIR /app

RUN apt-get update && apt-get upgrade -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

COPY chainlit_ui/requirements.txt chainlit_ui/requirements.txt

RUN pip install --no-cache-dir -r chainlit_ui/requirements.txt

COPY backend/ backend/
COPY chainlit_ui/ chainlit_ui/

ENV PYTHONPATH=/app/backend

EXPOSE 8000

CMD ["chainlit", "run", "chainlit_ui/app.py", "--host", "0.0.0.0", "--port", "8000"]
