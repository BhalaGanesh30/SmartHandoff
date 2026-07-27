# Multi-stage build for SmartHandoff Frontend
# Stage 1: Build the Angular application
FROM node:20-alpine AS builder

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci

# Copy source code
COPY . .

# Build for production
RUN npm run build:prod

# List the output to verify build
RUN ls -la /app/dist/
RUN ls -la /app/dist/smarthandoff-frontend/ || echo "smarthandoff-frontend dir not found"

# Stage 2: Serve with nginx
FROM nginx:alpine

# Remove default nginx config and default html
RUN rm -rf /etc/nginx/conf.d/default.conf
RUN rm -rf /usr/share/nginx/html/*

# Copy nginx configuration
COPY nginx.conf /etc/nginx/nginx.conf

# Copy built artifacts from builder
COPY --from=builder /app/dist/smarthandoff-frontend/browser /usr/share/nginx/html

# Verify files were copied
RUN ls -la /usr/share/nginx/html/

# Create a simple test to ensure nginx can start
RUN nginx -t

# Expose port 8080 (Cloud Run default)
EXPOSE 8080

# Start nginx
CMD ["nginx", "-g", "daemon off;"]
