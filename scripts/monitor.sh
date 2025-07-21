#!/bin/bash

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
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_header "WhatsApp Bot Monitoring Dashboard"

# Load environment variables
if [ -f ".env" ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

PORT=${PORT:-8000}
HEALTH_URL="http://localhost:$PORT/health"
STATS_URL="http://localhost:$PORT/stats/database"

# Function to check service health
check_health() {
    if curl -s -f "$HEALTH_URL" > /dev/null 2>&1; then
        print_success "Service is healthy"
        return 0
    else
        print_error "Service health check failed"
        return 1
    fi
}

# Function to get system stats
get_system_stats() {
    echo -e "${BLUE}📊 System Statistics:${NC}"
    echo "   • CPU Usage: $(top -bn1 | grep load | awk '{printf "%.2f%%", $(NF-2)}')" 
    echo "   • Memory Usage: $(free | grep Mem | awk '{printf "%.2f%% (%.1f/%.1fGB)", $3/$2 * 100.0, $3/1024/1024, $2/1024/1024}')" 
    echo "   • Disk Usage: $(df -h . | tail -1 | awk '{print $5 " (" $3 "/" $2 ")"}')"
    echo "   • Uptime: $(uptime | awk -F'up ' '{print $2}' | awk -F',' '{print $1}')"
}

# Function to get PM2 stats
get_pm2_stats() {
    echo -e "\n${BLUE}🔄 PM2 Process Status:${NC}"
    if command -v pm2 &> /dev/null; then
        pm2 jlist | jq -r '.[] | select(.name=="whatsapp-bot-api") | "   • Status: \(.pm2_env.status)\n   • CPU: \(.monit.cpu)%\n   • Memory: \(.monit.memory / 1024 / 1024 | floor)MB\n   • Restarts: \(.pm2_env.restart_time)\n   • Uptime: \(.pm2_env.pm_uptime | tonumber | . / 1000 | floor)s"'
    else
        print_warning "PM2 not available"
    fi
}

# Function to get application stats
get_app_stats() {
    echo -e "\n${BLUE}📈 Application Statistics:${NC}"
    if check_health; then
        # Try to get database stats
        if command -v curl &> /dev/null; then
            STATS=$(curl -s "$STATS_URL" 2>/dev/null || echo '{}')
            if [ "$STATS" != "{}" ] && [ -n "$STATS" ]; then
                echo "   • Database Status: Available"
                echo "   • API Response: OK"
            else
                echo "   • Database Status: Unknown"
                echo "   • API Response: Limited"
            fi
        fi
        
        # Check log file sizes
        if [ -d "logs" ]; then
            echo "   • Log Directory Size: $(du -sh logs 2>/dev/null | cut -f1 || echo 'N/A')"
            if [ -f "logs/app.log" ]; then
                LOG_SIZE=$(du -sh logs/app.log 2>/dev/null | cut -f1 || echo 'N/A')
                LOG_LINES=$(wc -l < logs/app.log 2>/dev/null || echo '0')
                echo "   • Main Log: $LOG_SIZE ($LOG_LINES lines)"
            fi
        fi
    else
        print_error "Application is not responding"
    fi
}

# Function to show recent logs
show_recent_logs() {
    echo -e "\n${BLUE}📝 Recent Logs (last 10 lines):${NC}"
    if [ -f "logs/app.log" ]; then
        tail -n 10 logs/app.log | while read line; do
            echo "   $line"
        done
    else
        print_warning "No application logs found"
    fi
    
    if command -v pm2 &> /dev/null; then
        echo -e "\n${BLUE}📝 PM2 Logs (last 5 lines):${NC}"
        pm2 logs whatsapp-bot-api --lines 5 --nostream 2>/dev/null | tail -n 5 | while read line; do
            echo "   $line"
        done
    fi
}

# Function to check port availability
check_port() {
    echo -e "\n${BLUE}🔌 Port Status:${NC}"
    if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
        PROCESS=$(lsof -Pi :$PORT -sTCP:LISTEN | tail -n 1 | awk '{print $2, $1}')
        print_success "Port $PORT is active (PID: $PROCESS)"
    else
        print_error "Port $PORT is not in use"
    fi
}

# Function to show quick actions
show_quick_actions() {
    echo -e "\n${PURPLE}🛠️  Quick Actions:${NC}"
    echo -e "   ${GREEN}r)${NC} Restart service"
    echo -e "   ${GREEN}s)${NC} Stop service"
    echo -e "   ${GREEN}t)${NC} Start service"
    echo -e "   ${GREEN}l)${NC} View live logs"
    echo -e "   ${GREEN}h)${NC} Health check"
    echo -e "   ${GREEN}q)${NC} Quit monitor"
    echo -e "   ${GREEN}m)${NC} PM2 monitor (GUI)"
    echo
}

# Main monitoring function
run_monitor() {
    while true; do
        clear
        print_header "WhatsApp Bot Monitoring Dashboard - $(date '+%Y-%m-%d %H:%M:%S')"
        
        check_health
        get_system_stats
        get_pm2_stats
        get_app_stats
        check_port
        show_recent_logs
        show_quick_actions
        
        read -t 30 -p "Choose action (auto-refresh in 30s): " action
        
        case $action in
            r|R)
                print_status "Restarting service..."
                bash scripts/restart.sh
                read -p "Press Enter to continue..."
                ;;
            s|S)
                print_status "Stopping service..."
                bash scripts/stop.sh
                read -p "Press Enter to continue..."
                ;;
            t|T)
                print_status "Starting service..."
                bash scripts/deploy.sh
                read -p "Press Enter to continue..."
                ;;
            l|L)
                print_status "Showing live logs (Ctrl+C to exit)..."
                if command -v pm2 &> /dev/null; then
                    pm2 logs whatsapp-bot-api
                else
                    tail -f logs/app.log 2>/dev/null || echo "No logs available"
                fi
                ;;
            h|H)
                print_status "Running health check..."
                if check_health; then
                    curl -s "$HEALTH_URL" | jq . 2>/dev/null || curl -s "$HEALTH_URL"
                fi
                read -p "Press Enter to continue..."
                ;;
            m|M)
                if command -v pm2 &> /dev/null; then
                    pm2 monit
                else
                    print_error "PM2 not available"
                    read -p "Press Enter to continue..."
                fi
                ;;
            q|Q)
                print_success "Exiting monitor..."
                exit 0
                ;;
            "")
                # Auto-refresh (timeout reached)
                ;;
            *)
                print_warning "Invalid option: $action"
                sleep 2
                ;;
        esac
    done
}

# Check if running in interactive mode
if [ -t 0 ]; then
    # Interactive mode
    run_monitor
else
    # Non-interactive mode - just show current status
    check_health
    get_system_stats
    get_pm2_stats
    get_app_stats
    check_port
fi
