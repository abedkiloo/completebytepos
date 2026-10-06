# Production image: Create React App → optimized static build → nginx
# See https://create-react-app.dev/docs/production-build/
FROM node:20-alpine AS build

WORKDIR /app

# Cap Node heap so npm/CRA do not OOM-kill the VPS (exit 137/152) when
# production + UAT build on the same ~2 GB box.
ENV NODE_OPTIONS=--max-old-space-size=768 \
    npm_config_audit=false \
    npm_config_fund=false

# API URL is embedded at build time (REACT_APP_*). Use /api when nginx proxies to backend.
ARG REACT_APP_API_URL=/api
ENV REACT_APP_API_URL=$REACT_APP_API_URL
ARG REACT_APP_GOOGLE_MAPS_KEY=REPLACE_WITH_MAPS_JS_API_KEY
ENV REACT_APP_GOOGLE_MAPS_KEY=$REACT_APP_GOOGLE_MAPS_KEY

COPY package*.json ./
# Prefer fewer concurrent workers on small VPS builds.
RUN npm ci --legacy-peer-deps --no-audit --no-fund

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
