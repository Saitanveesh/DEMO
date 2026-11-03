FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8000 HOST=0.0.0.0 HUNT_DATA_DIR=/app/data
WORKDIR /app
COPY app.py ./
COPY static/ ./static/
RUN useradd -r -u 10001 hunt && mkdir -p /app/data && chown -R hunt:hunt /app/data
USER hunt
EXPOSE 8000
CMD ["python", "app.py", "serve", "--host", "0.0.0.0", "--port", "8000"]
