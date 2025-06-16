#!/bin/bash

# Deployment script for Linode server
# Run this script on your Linode server as root

echo "🚀 Starting YTAPI deployment..."

# Stop and remove existing container if it exists
docker stop ytapi-container 2>/dev/null || true
docker rm ytapi-container 2>/dev/null || true

# Pull the latest image
echo "📦 Pulling latest Docker image..."
docker pull vladsbeat/ytapi:latest

# Run the new container
echo "🔄 Starting new container..."
docker run -d \
  --name ytapi-container \
  --restart unless-stopped \
  -p 8001:8001 \
  vladsbeat/ytapi:latest

# Check if container is running
echo "✅ Checking container status..."
docker ps | grep ytapi-container

echo "🎉 Deployment complete!"
echo "📍 API is available at: http://45.33.70.141:8001"
echo "📚 API docs at: http://45.33.70.141:8001/docs"