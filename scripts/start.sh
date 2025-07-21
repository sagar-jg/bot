#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
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

# Get the directory of this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

print_status "Starting WhatsApp Bot API..."
print_status "Project directory: $PROJECT_DIR"

# Change to project directory
cd "$PROJECT_DIR"

# Load environment variables
if [ -f ".env" ]; then
    print_status "Loading environment variables from .env"
    export $(cat .env | grep -v '^#' | xargs)
else
    print_warning "No .env file found. Using default configuration."
fi

# Set default environment if not specified
ENVIRONMENT=${ENVIRONMENT:-development}
print_status "Environment: $ENVIRONMENT"

# Create necessary directories
print_status "Creating necessary directories..."
mkdir -p logs
mkdir -p data/backups
mkdir -p data/uploads
mkdir -p tmp

# Check if virtual environment exists
VENV_PATH="$PROJECT_DIR/venv"
if [ ! -d "$VENV_PATH" ]; then
    print_status "Creating virtual environment..."
    python3 -m venv "$VENV_PATH"
    if [ $? -eq 0 ]; then
        print_success "Virtual environment created successfully"
    else
        print_error "Failed to create virtual environment"
        exit 1
    fi
else
    print_status "Virtual environment already exists"
fi

# Activate virtual environment
print_status "Activating virtual environment..."
source "$VENV_PATH/bin/activate"

if [ $? -eq 0 ]; then
    print_success "Virtual environment activated"
else
    print_error "Failed to activate virtual environment"
    exit 1
fi

# Upgrade pip
print_status "Upgrading pip..."
pip install --upgrade pip --quiet

# Install/update requirements
print_status "Installing requirements..."
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt --quiet
    if [ $? -eq 0 ]; then
        print_success "Requirements installed successfully"
    else
        print_error "Failed to install requirements"
        exit 1
    fi
else
    print_error "requirements.txt not found!"
    exit 1
fi

# Run database migrations/setup if needed
if [ -f "scripts/setup_db.sh" ]; then
    print_status "Setting up database..."
    bash scripts/setup_db.sh
fi

# Load configuration based on environment
CONFIG_FILE="config/${ENVIRONMENT}.json"
if [ ! -f "$CONFIG_FILE" ]; then
    print_warning "Config file $CONFIG_FILE not found, using defaults"
    CONFIG_FILE="config/development.json"
fi

print_status "Using configuration: $CONFIG_FILE"

# Set server configuration from config file or environment variables
HOST=${HOST:-"0.0.0.0"}
PORT=${PORT:-8000}
WORKERS=${WORKERS:-1}
LOG_LEVEL=${LOG_LEVEL:-"info"}

# Health check before starting
print_status "Running pre-start health checks..."
if command -v python3 &> /dev/null; then
    print_success "Python 3 is available"
else
    print_error "Python 3 is not available"
    exit 1
fi

# Check if port is available
if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
    print_warning "Port $PORT is already in use"
    # Kill existing process on the port (optional)
    # kill $(lsof -t -i:$PORT) 2>/dev/null || true
    # sleep 2
fi

# Start the application
print_status "Starting FastAPI application..."
print_status "Host: $HOST"
print_status "Port: $PORT"
print_status "Workers: $WORKERS"
print_status "Log Level: $LOG_LEVEL"

# Create startup log entry
echo "$(date '+%Y-%m-%d %H:%M:%S') - Application starting with PID $$" >> logs/startup.log

# Start uvicorn with proper configuration
if [ "$ENVIRONMENT" = "development" ]; then
    print_status "Starting in development mode with auto-reload..."
    exec uvicorn api.main:app \
        --host "$HOST" \
        --port "$PORT" \
        --reload \
        --log-level "$LOG_LEVEL" \
        --access-log \
        --loop asyncio
else
    print_status "Starting in production mode..."
    exec uvicorn api.main:app \
        --host "$HOST" \
        --port "$PORT" \
        --workers "$WORKERS" \
        --log-level "$LOG_LEVEL" \
        --access-log \
        --loop asyncio \
        --no-reload
fi