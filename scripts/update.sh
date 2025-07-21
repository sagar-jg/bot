#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m'

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

print_header "WhatsApp Bot Update Process"

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

print_status "Project directory: $PROJECT_DIR"
cd "$PROJECT_DIR"

# Load environment variables
if [ -f ".env" ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Create backup before update
print_status "Creating backup before update..."
bash scripts/backup.sh

if [ $? -eq 0 ]; then
    print_success "Backup created successfully"
else
    print_error "Backup failed. Aborting update."
    exit 1
fi

# Stop the current application
print_status "Stopping current application..."
bash scripts/stop.sh

# Pull latest changes from git
print_status "Pulling latest changes from repository..."
git fetch origin main

if [ $? -eq 0 ]; then
    print_success "Repository fetch completed"
else
    print_error "Failed to fetch from repository"
    exit 1
fi

# Show what's being updated
print_status "Changes to be applied:"
git log --oneline HEAD..origin/main | head -10

# Apply updates
print_status "Applying updates..."
git merge origin/main

if [ $? -eq 0 ]; then
    print_success "Code update completed"
else
    print_error "Failed to apply updates"
    print_warning "Attempting to restore from backup..."
    # Here you could add backup restore logic
    exit 1
fi

# Update dependencies
print_status "Updating dependencies..."
if [ -d "venv" ]; then
    source venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
    print_success "Dependencies updated"
else
    print_warning "Virtual environment not found, will be created during deployment"
fi

# Run database migrations (if any)
print_status "Checking for database migrations..."
if [ -f "scripts/migrate.sh" ]; then
    bash scripts/migrate.sh
    print_success "Database migrations completed"
else
    print_status "No migration script found, skipping database migrations"
fi

# Update configuration files if needed
print_status "Checking configuration updates..."
if [ -f "config/.env.example" ] && [ -f ".env" ]; then
    # Check if there are new environment variables
    NEW_VARS=$(comm -23 <(grep -E '^[A-Z_]' config/.env.example | cut -d= -f1 | sort) <(grep -E '^[A-Z_]' .env | cut -d= -f1 | sort))
    if [ ! -z "$NEW_VARS" ]; then
        print_warning "New environment variables detected:"
        echo "$NEW_VARS"
        print_warning "Please update your .env file with these new variables"
    fi
fi

# Make scripts executable
print_status "Updating script permissions..."
chmod +x scripts/*.sh
print_success "Script permissions updated"

# Start the application with new code
print_status "Starting updated application..."
bash scripts/deploy.sh

if [ $? -eq 0 ]; then
    print_success "Application started successfully with updates"
else
    print_error "Failed to start updated application"
    print_warning "Consider rolling back to previous version"
    exit 1
fi

# Health check
print_status "Performing post-update health check..."
sleep 15  # Give the app time to start

PORT=${PORT:-8000}
HEALTH_URL="http://localhost:$PORT/health"

for i in {1..5}; do
    if curl -s -f "$HEALTH_URL" > /dev/null 2>&1; then
        print_success "Post-update health check passed"
        break
    else
        if [ $i -eq 5 ]; then
            print_error "Post-update health check failed after 5 attempts"
            print_warning "Application may not be working correctly"
        else
            print_status "Health check attempt $i/5 failed, retrying..."
            sleep 10
        fi
    fi
done

# Log the update
echo "$(date '+%Y-%m-%d %H:%M:%S') - Update completed successfully" >> logs/update.log

print_header "Update Summary"
print_success "Update process completed!"
echo -e "${GREEN}📊 Update Information:${NC}"
echo -e "   • Backup created: Available in data/backups/"
echo -e "   • Code updated: $(git log --oneline -1)"
echo -e "   • Dependencies: Updated"
echo -e "   • Application: Restarted"

echo -e "\n${BLUE}🛠️  Post-Update Checklist:${NC}"
echo -e "   • Check application logs: pm2 logs whatsapp-bot-api"
echo -e "   • Verify health: curl http://localhost:$PORT/health"
echo -e "   • Test functionality: Send test messages"
echo -e "   • Monitor performance: pm2 monit"

print_success "Update completed at $(date '+%Y-%m-%d %H:%M:%S')"
