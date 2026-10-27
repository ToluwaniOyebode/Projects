FROM node:24-bookworm-slim
RUN mkdir -p /data && chown node:node /data
WORKDIR /app
COPY --chown=node:node . .
USER node
ENV HOST=0.0.0.0 PORT=8103 DB_PATH=/data/data.sqlite3
VOLUME ["/data"]
EXPOSE 8103
CMD ["node", "server.js"]
