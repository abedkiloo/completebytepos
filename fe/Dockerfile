# Production image: Create React App → optimized static build → nginx
# See https://create-react-app.dev/docs/production-build/
# Debian (not Alpine): Alpine + Node 20 prefers IPv6 and often hits ETIMEDOUT/ECONNRESET to the npm registry.
FROM node:20-bookworm-slim AS build

WORKDIR /app

# API URL is embedded at build time (REACT_APP_*). Use /api when nginx proxies to backend.
ARG REACT_APP_API_URL=/api
ENV REACT_APP_API_URL=$REACT_APP_API_URL
ARG REACT_APP_GOOGLE_MAPS_KEY=REPLACE_WITH_MAPS_JS_API_KEY
ENV REACT_APP_GOOGLE_MAPS_KEY=$REACT_APP_GOOGLE_MAPS_KEY
ENV NODE_OPTIONS=--dns-result-order=ipv4first \
    NPM_CONFIG_FETCH_RETRIES=5 \
    NPM_CONFIG_FETCH_RETRY_MINTIMEOUT=20000 \
    NPM_CONFIG_FETCH_RETRY_MAXTIMEOUT=120000 \
    NPM_CONFIG_FETCH_TIMEOUT=300000

COPY package*.json ./
COPY .npmrc ./
RUN for i in 1 2 3 4 5; do \
      npm ci --legacy-peer-deps && exit 0; \
      echo "npm ci failed (attempt $$i), retrying..."; \
      sleep $$((i * 8)); \
    done; \
    exit 1

COPY . .

ENV NODE_ENV=production \
    CI=false \
    GENERATE_SOURCEMAP=false

RUN npm run build

# Fail the image build if the production bundle is missing
RUN test -f /app/build/index.html

# Production stage — serve static build only (no Node dev server)
FROM nginx:alpine

RUN apk add --no-cache curl

COPY --from=build /app/build /usr/share/nginx/html

# Copy nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expose port
EXPOSE 80

# Start nginx
CMD ["nginx", "-g", "daemon off;"]
