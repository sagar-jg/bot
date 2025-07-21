#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')] ✅ $1${NC}"
}

print_error() {
    echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')] ❌ $1${NC}"
}

print_status "Stopping WhatsApp Bot API..."

# Stop PM2 process
if command -v pm2 &> /dev/null; then
    print_status "Stopping PM2 process..."
    pm2 stop whatsapp-bot-api 2>/dev/null || true
    pm2 delete whatsapp-bot-api 2>/dev/null || true
    print_success "PM2 process stopped"
fi

# Kill any remaining processes on port 8000
PORT=${PORT:-8000}
if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
    print_status "Killing processes on port $PORT..."
    kill $(lsof -t -i:$PORT) 2>/dev/null || true
    sleep 2
    
    # Force kill if still running
    if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
        print_status "Force killing processes on port $PORT..."
        kill -9 $(lsof -t -i:$PORT) 2>/dev/null || true
    fi
    
    print_success "Processes on port $PORT stopped"
else
    print_status "No processes running on port $PORT"
fi

# Log the shutdown
echo "$(date '+%Y-%m-%d %H:%M:%S') - Application stopped" >> logs/startup.log

print_success "WhatsApp Bot API stopped successfully"
