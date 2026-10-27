FROM python:3.12-slim
RUN useradd --create-home app && mkdir /data && chown app:app /data
WORKDIR /app
COPY --chown=app:app . .
USER app
ENV HOST=0.0.0.0 PORT=8104 DB_PATH=/data/data.sqlite3 PYTHONUNBUFFERED=1
VOLUME ["/data"]
EXPOSE 8104
CMD ["python", "server.py"]
