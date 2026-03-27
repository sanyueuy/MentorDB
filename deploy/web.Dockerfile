FROM node:20-alpine AS deps

WORKDIR /app
COPY web/package.json /app/package.json
RUN npm install --no-package-lock

FROM node:20-alpine AS builder

WORKDIR /app
COPY --from=deps /app/node_modules /app/node_modules
COPY web /app
ARG NEXT_PUBLIC_MENTORDB_API_BASE_URL=http://127.0.0.1:8000
ENV NEXT_PUBLIC_MENTORDB_API_BASE_URL=${NEXT_PUBLIC_MENTORDB_API_BASE_URL}
RUN npm run build

FROM node:20-alpine AS runner

ENV NODE_ENV=production \
    PORT=3000

WORKDIR /app
COPY --from=builder /app/.next /app/.next
COPY --from=builder /app/public /app/public
COPY --from=builder /app/package.json /app/package.json
COPY --from=builder /app/node_modules /app/node_modules
ENV HOSTNAME=0.0.0.0

EXPOSE 3000

CMD ["npm", "run", "start"]
