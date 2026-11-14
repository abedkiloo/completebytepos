# Production image: Create React App → optimized static build → nginx
# See https://create-react-app.dev/docs/production-build/
FROM node:20-alpine AS build

WORKDIR /app

# Cap Node heap for ~2 GB VPS builds. Too low → GC thrash; too high → OOM (137).
ENV NODE_OPTIONS=--max-old-space-size=896 \
    npm_config_audit=false \
    npm_config_fund=false \
    DISABLE_ESLINT_PLUGIN=true \
    GENERATE_SOURCEMAP=false \
    INLINE_RUNTIME_CHUNK=false \
    IMAGE_INLINE_SIZE_LIMIT=0

# API URL is embedded at build time (REACT_APP_*). Use /api when nginx proxies to backend.
ARG REACT_APP_API_URL=/api
ENV REACT_APP_API_URL=$REACT_APP_API_URL
ARG REACT_APP_GOOGLE_MAPS_KEY=REPLACE_WITH_MAPS_JS_API_KEY
ENV REACT_APP_GOOGLE_MAPS_KEY=$REACT_APP_GOOGLE_MAPS_KEY

COPY package*.json ./
RUN npm ci --legacy-peer-deps --no-audit --no-fund

COPY . .

ENV NODE_ENV=production \
    CI=false

# CRA is quiet after "Creating an optimized production build…".
# On a 2 GB box this often takes 8–20 minutes (not hung).
RUN echo "=== CRA production build starting $(date -u +%Y-%m-%dT%H:%M:%SZ) ===" \
    && (free -m || true) \
    && npm run build \
    && echo "=== CRA production build finished $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="

RUN test -f /app/build/index.html

FROM nginx:alpine

RUN apk add --no-cache curl

COPY --from=build /app/build /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
