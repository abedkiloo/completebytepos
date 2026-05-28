# Production image: Create React App → optimized static build → nginx
# See https://create-react-app.dev/docs/production-build/
FROM node:20-alpine AS build

WORKDIR /app

# API URL is embedded at build time (REACT_APP_*). Use /api when nginx proxies to backend.
ARG REACT_APP_API_URL=/api
ENV REACT_APP_API_URL=$REACT_APP_API_URL

COPY package*.json ./
RUN npm ci --legacy-peer-deps

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
