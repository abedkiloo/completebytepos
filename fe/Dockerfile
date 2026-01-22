FROM node:20-alpine as build

# Set working directory
WORKDIR /app

# Accept build argument for API URL
ARG REACT_APP_API_URL=http://backend:8000/api
ENV REACT_APP_API_URL=$REACT_APP_API_URL

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm install --legacy-peer-deps

# Copy source code
COPY . .

# Build React app with environment variable
# Use CI=false to prevent build failures on warnings
ENV CI=false
RUN npm run build

# Production stage
FROM nginx:alpine

# Copy built files from build stage
COPY --from=build /app/build /usr/share/nginx/html

# Copy nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expose port
EXPOSE 80

# Start nginx
CMD ["nginx", "-g", "daemon off;"]
