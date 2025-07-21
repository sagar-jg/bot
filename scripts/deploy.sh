#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

print_header() {
    echo -e "\n${PURPLE}================================${NC}"
    echo -e "${PURPLE}$1${NC}"
    echo -e "${PURPLE}================================${NC}\n"
}

print_status() {
    echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')] ✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')] ⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')] ❌ $1${NC}"
}

print_header "WhatsApp Bot API Deployment"

# Get script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

print_status "Project directory: $PROJECT_DIR"
cd "$PROJECT_DIR"

# Load environment variables
if [ -f ".env" ]; then
    print_status "Loading environment variables..."
    export $(cat .env | grep -v '^#' | xargs)
else
    print_warning "No .env file found. Please create one from .env.example"
    if [ -f "config/.env.example" ]; then
        print_status "Copying .env.example to .env"
        cp config/.env.example .env
        print_warning "Please edit .env file with your configuration before running again"
        exit 1
    fi
fi

# Set environment
ENVIRONMENT=${ENVIRONMENT:-production}
print_status "Deployment environment: $ENVIRONMENT"

# Check if PM2 is installed
if ! command -v pm2 &> /dev/null; then
    print_error "PM2 is not installed. Installing PM2..."
    npm install -g pm2
    if [ $? -eq 0 ]; then
        print_success "PM2 installed successfully"
    else
        print_error "Failed to install PM2"
        exit 1
    fi
fi

# Check system requirements
print_header "System Requirements Check"

# Check Python
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
    print_success "Python 3 is available (version: $PYTHON_VERSION)"
else
    print_error "Python 3 is not available"
    exit 1
fi

# Check pip
if command -v pip3 &> /dev/null || command -v pip &> /dev/null; then
    print_success "pip is available"
else
    print_error "pip is not available"
    exit 1
fi

# Check disk space
AVAILABLE_SPACE=$(df . | tail -1 | awk '{print $4}')
REQUIRED_SPACE=1048576  # 1GB in KB
if [ "$AVAILABLE_SPACE" -gt "$REQUIRED_SPACE" ]; then
    print_success "Sufficient disk space available ($(($AVAILABLE_SPACE/1024/1024))GB free)"
else
    print_warning "Low disk space ($(($AVAILABLE_SPACE/1024/1024))GB free)"
fi

# Pre-deployment tasks
print_header "Pre-deployment Tasks"

# Create necessary directories
print_status "Creating directory structure..."
mkdir -p logs
mkdir -p data/{backups,uploads}
mkdir -p tmp
mkdir -p config
print_success "Directory structure created"

# Stop existing PM2 process
print_status "Stopping existing processes..."
pm2 stop whatsapp-bot-api 2>/dev/null || true
pm2 delete whatsapp-bot-api 2>/dev/null || true

# Kill any processes on the port
PORT=${PORT:-8000}
if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
    print_status "Killing existing processes on port $PORT..."
    kill $(lsof -t -i:$PORT) 2>/dev/null || true
    sleep 2
fi

# Deployment
print_header "Deployment"

# Make scripts executable
print_status "Making scripts executable..."
chmod +x scripts/*.sh
print_success "Scripts are now executable"

# Virtual environment setup
VENV_PATH="$PROJECT_DIR/venv"
if [ ! -d "$VENV_PATH" ]; then
    print_status "Creating virtual environment..."
    python3 -m venv "$VENV_PATH"
    print_success "Virtual environment created"
fi

# Activate virtual environment and install dependencies
print_status "Installing dependencies..."
source "$VENV_PATH/bin/activate"
pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet
print_success "Dependencies installed"

# Database setup (if needed)
if [ -f "scripts/setup_db.sh" ]; then
    print_status "Setting up database..."
    bash scripts/setup_db.sh
fi

# Start with PM2
print_header "Starting Application with PM2"

# Update ecosystem.config.js with current project path
print_status "Updating PM2 configuration..."
sed -i "s|cwd: '/path/to/your/bot'|cwd: '$PROJECT_DIR'|g" ecosystem.config.js

# Start PM2 process
print_status "Starting PM2 process..."
pm2 start ecosystem.config.js --env $ENVIRONMENT

if [ $? -eq 0 ]; then
    print_success "PM2 process started successfully"
else
    print_error "Failed to start PM2 process"
    exit 1
fi

# Save PM2 configuration
pm2 save
pm2 startup | grep -E '^sudo' | bash || true

# Post-deployment verification
print_header "Post-deployment Verification"

# Wait for application to start
print_status "Waiting for application to start..."
sleep 10

# Health check
print_status "Performing health check..."
HEALTH_URL="http://localhost:$PORT/health"

for i in {1..5}; do
    if curl -s -f "$HEALTH_URL" > /dev/null 2>&1; then
        print_success "Health check passed"
        break
    else
        print_warning "Health check attempt $i/5 failed, retrying..."
        sleep 5
    fi
    
    if [ $i -eq 5 ]; then
        print_error "Health check failed after 5 attempts"
        print_status "Checking PM2 status..."
        pm2 status
        print_status "Checking logs..."
        pm2 logs whatsapp-bot-api --lines 20
    fi
done

# Display PM2 status
print_status "PM2 Process Status:"
pm2 status

# Display important information
print_header "Deployment Summary"
print_success "Deployment completed successfully!"
echo -e "${GREEN}📊 Application Status:${NC}"
echo -e "   • Environment: $ENVIRONMENT"
echo -e "   • Port: $PORT"
echo -e "   • Health Check: http://localhost:$PORT/health"
echo -e "   • API Documentation: http://localhost:$PORT/docs"
echo -e "   • Logs: pm2 logs whatsapp-bot-api"

echo -e "\n${BLUE}🛠️  Management Commands:${NC}"
echo -e "   • View status: pm2 status"
echo -e "   • View logs: pm2 logs whatsapp-bot-api"
echo -e "   • Restart: pm2 restart whatsapp-bot-api"
echo -e "   • Stop: pm2 stop whatsapp-bot-api"
echo -e "   • Monitor: pm2 monit"

echo -e "\n${PURPLE}🚀 Deployment completed at $(date '+%Y-%m-%d %H:%M:%S')${NC}\n"

# Log deployment
echo "$(date '+%Y-%m-%d %H:%M:%S') - Deployment completed successfully (Environment: $ENVIRONMENT)" >> logs/deployment.log
