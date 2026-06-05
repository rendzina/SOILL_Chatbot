FROM python:3.12-slim-bookworm

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./
COPY packages ./packages
COPY apps ./apps

RUN uv sync --package soill-chatbot --no-dev

WORKDIR /app/apps/chatbot

EXPOSE 8000

CMD ["sh", "-c", "cd /app && uv run --directory apps/chatbot chainlit run app.py --host 0.0.0.0 --port ${PORT:-8000}"]
