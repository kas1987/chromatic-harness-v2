#!/bin/bash

# LOGHOUSE Server Startup Script
# Starts both backend and frontend servers for the LOGHOUSE dashboard

set -e

echo "╔════════════════════════════════════════════════════╗"
echo "║          🏛️  LOGHOUSE SERVER STARTUP              ║"
echo "╚════════════════════════════════════════════════════╝"
echo ""

LOGHOUSE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/LOGHOUSE_SERVER"

# Check if Node.js is installed
if ! command -v node &> /dev/null; then
    echo "❌ Node.js is not installed. Please install Node.js first."
    exit 1
fi

echo "📦 Installing dependencies..."
cd "$LOGHOUSE_DIR"

# Install server dependencies
if [ ! -d "node_modules" ]; then
    echo "  Setting up server..."
    npm install
fi

# Install client dependencies
if [ ! -d "client/node_modules" ]; then
    echo "  Setting up client..."
    cd client
    npm install
    cd ..
fi

# Check if client is built
if [ ! -d "client/build" ]; then
    echo "📦 Building React client..."
    cd client
    npm run build
    cd ..
fi

echo ""
echo "✅ Setup complete. Starting LOGHOUSE server..."
echo ""

# Start the server
PORT=3333 node index.js
