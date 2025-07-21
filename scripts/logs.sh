#!/bin/bash

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

show_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo "Options:"
    echo "  -f, --follow     Follow log output (tail -f)"
    echo "  -n, --lines N    Show last N lines (default: 50)"
    echo "  -t, --type TYPE  Show specific log type (app|pm2|error|access|all)"
    echo "  -l, --list       List available log files"
    echo "  -c, --clean      Clean old log files"
    echo "  -s, --size       Show log file sizes"
    echo "  -h, --help       Show this help message"
    echo
    echo "Examples:"
    echo "  $0 -f                    # Follow all logs"
    echo "  $0 -n 100 -t app        # Show last 100 lines of app logs"
    echo "  $0 -l                    # List all log files"
    echo "  $0 -c                    # Clean old log files"
}

# Default values
FOLLOW=false
LINES=50
LOG_TYPE="all"
LIST_ONLY=false
CLEAN_LOGS=false
SHOW_SIZE=false

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -f|--follow)
            FOLLOW=true
            shift
            ;;
        -n|--lines)
            LINES="$2"
            shift 2
            ;;
        -t|--type)
            LOG_TYPE="$2"
            shift 2
            ;;
        -l|--list)
            LIST_ONLY=true
            shift
            ;;
        -c|--clean)
            CLEAN_LOGS=true
            shift
            ;;
        -s|--size)
            SHOW_SIZE=true
            shift
            ;;
        -h|--help)
            show_usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

# Create logs directory if it doesn't exist
mkdir -p logs

# Function to list log files
list_log_files() {
    print_header "Available Log Files"
    
    if [ -d "logs" ]; then
        echo -e "${BLUE}Application Logs:${NC}"
        find logs -name "*.log" -type f | sort | while read -r file; do
            size=$(du -sh "$file" 2>/dev/null | cut -f1 || echo "N/A")
            lines=$(wc -l < "$file" 2>/dev/null || echo "0")
            modified=$(stat -c %y "$file" 2>/dev/null | cut -d' ' -f1,2 | cut -d'.' -f1 || echo "Unknown")
            echo "  • $file ($size, $lines lines, modified: $modified)"
        done
    fi
    
    if command -v pm2 &> /dev/null; then
        echo -e "\n${BLUE}PM2 Logs:${NC}"
        pm2 logs --nostream --lines 0 2>/dev/null | grep -E "(out|error)" | head -10 || echo "  No PM2 logs found"
    fi
}

# Function to show log file sizes
show_log_sizes() {
    print_header "Log File Sizes"
    
    echo -e "${BLUE}Directory Overview:${NC}"
    if [ -d "logs" ]; then
        echo "  • Total logs directory size: $(du -sh logs | cut -f1)"
        echo "  • Number of log files: $(find logs -name "*.log" -type f | wc -l)"
    fi
    
    echo -e "\n${BLUE}Individual Files:${NC}"
    find logs -name "*.log" -type f -exec du -sh {} + 2>/dev/null | sort -hr | head -10
    
    echo -e "\n${BLUE}Disk Usage Warning:${NC}"
    TOTAL_SIZE=$(du -sm logs 2>/dev/null | cut -f1 || echo "0")
    if [ "$TOTAL_SIZE" -gt 100 ]; then
        echo -e "  ${YELLOW}⚠️  Log directory is using ${TOTAL_SIZE}MB of disk space${NC}"
        echo -e "  ${YELLOW}Consider running log cleanup: $0 -c${NC}"
    else
        echo -e "  ${GREEN}✅ Log directory size is acceptable (${TOTAL_SIZE}MB)${NC}"
    fi
}

# Function to clean old logs
clean_old_logs() {
    print_header "Cleaning Old Log Files"
    
    # Rotate large log files
    find logs -name "*.log" -size +50M -exec echo "Large file found: {}" \;
    find logs -name "*.log" -size +50M | while read -r file; do
        echo "Rotating large file: $file"
        if [ -f "$file" ]; then
            mv "$file" "${file}.$(date +%Y%m%d_%H%M%S)"
            touch "$file"
            echo "  • Rotated: $(basename "$file")"
        fi
    done
    
    # Remove old rotated files (older than 30 days)
    DELETED_COUNT=$(find logs -name "*.log.*" -mtime +30 -type f | wc -l)
    find logs -name "*.log.*" -mtime +30 -type f -delete
    echo "  • Deleted $DELETED_COUNT old rotated files (>30 days)"
    
    # Compress log files older than 7 days
    find logs -name "*.log" -mtime +7 -type f | while read -r file; do
        if [[ ! "$file" =~ \.(gz|bz2)$ ]]; then
            echo "Compressing: $file"
            gzip "$file" 2>/dev/null && echo "  • Compressed: $(basename "$file")"
        fi
    done
    
    # Clean empty log files
    EMPTY_COUNT=$(find logs -name "*.log" -size 0 -type f | wc -l)
    find logs -name "*.log" -size 0 -type f -delete
    echo "  • Deleted $EMPTY_COUNT empty log files"
    
    echo -e "\n${GREEN}✅ Log cleanup completed${NC}"
    echo "  • New logs directory size: $(du -sh logs | cut -f1)"
}

# Function to show logs based on type
show_logs() {
    local log_type="$1"
    local follow="$2"
    local lines="$3"
    
    case $log_type in
        "app")
            print_header "Application Logs"
            if [ -f "logs/app.log" ]; then
                if [ "$follow" = true ]; then
                    tail -f -n "$lines" logs/app.log
                else
                    tail -n "$lines" logs/app.log
                fi
            else
                echo "No application logs found"
            fi
            ;;
        "pm2")
            print_header "PM2 Logs"
            if command -v pm2 &> /dev/null; then
                if [ "$follow" = true ]; then
                    pm2 logs whatsapp-bot-api --lines "$lines"
                else
                    pm2 logs whatsapp-bot-api --lines "$lines" --nostream
                fi
            else
                echo "PM2 not available"
            fi
            ;;
        "error")
            print_header "Error Logs"
            if [ -f "logs/error.log" ]; then
                if [ "$follow" = true ]; then
                    tail -f -n "$lines" logs/error.log
                else
                    tail -n "$lines" logs/error.log
                fi
            elif command -v pm2 &> /dev/null; then
                echo "Showing PM2 error logs:"
                if [ "$follow" = true ]; then
                    pm2 logs whatsapp-bot-api --err --lines "$lines"
                else
                    pm2 logs whatsapp-bot-api --err --lines "$lines" --nostream
                fi
            else
                echo "No error logs found"
            fi
            ;;
        "access")
            print_header "Access Logs"
            if [ -f "logs/access.log" ]; then
                if [ "$follow" = true ]; then
                    tail -f -n "$lines" logs/access.log
                else
                    tail -n "$lines" logs/access.log
                fi
            else
                echo "No access logs found"
            fi
            ;;
        "all"|*)
            print_header "All Logs (Last $lines lines each)"
            
            # Application logs
            if [ -f "logs/app.log" ]; then
                echo -e "\n${BLUE}📱 Application Logs:${NC}"
                tail -n "$lines" logs/app.log 2>/dev/null | tail -20
            fi
            
            # PM2 logs
            if command -v pm2 &> /dev/null; then
                echo -e "\n${BLUE}🔄 PM2 Logs:${NC}"
                pm2 logs whatsapp-bot-api --lines 20 --nostream 2>/dev/null || echo "No PM2 logs available"
            fi
            
            # Error logs
            if [ -f "logs/error.log" ]; then
                echo -e "\n${RED}❌ Error Logs:${NC}"
                tail -n 20 logs/error.log 2>/dev/null
            fi
            
            # Other logs
            for log_file in logs/*.log; do
                if [[ -f "$log_file" && ! "$log_file" =~ (app|error|access)\.log$ ]]; then
                    echo -e "\n${YELLOW}📝 $(basename "$log_file"):${NC}"
                    tail -n 10 "$log_file" 2>/dev/null
                fi
            done
            
            if [ "$follow" = true ]; then
                echo -e "\n${GREEN}Following logs... (Press Ctrl+C to exit)${NC}"
                if [ -f "logs/app.log" ]; then
                    tail -f logs/app.log
                elif command -v pm2 &> /dev/null; then
                    pm2 logs whatsapp-bot-api
                else
                    echo "No logs to follow"
                fi
            fi
            ;;
    esac
}

# Main logic
if [ "$LIST_ONLY" = true ]; then
    list_log_files
elif [ "$CLEAN_LOGS" = true ]; then
    clean_old_logs
elif [ "$SHOW_SIZE" = true ]; then
    show_log_sizes
else
    show_logs "$LOG_TYPE" "$FOLLOW" "$LINES"
fi
