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

print_error() {
    echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')] ❌ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')] ⚠️  $1${NC}"
}

# Test runner script
print_header "WhatsApp Bot API - Test Runner"

# Get script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

# Check if virtual environment exists
VENV_PATH="venv_dev"
if [ ! -d "$VENV_PATH" ]; then
    print_error "Development virtual environment not found: $VENV_PATH"
    print_status "Please run 'bash scripts/setup.sh' first to create the development environment"
    exit 1
fi

# Activate virtual environment
print_status "Activating virtual environment: $VENV_PATH"
source "$VENV_PATH/bin/activate"

# Set test environment
export ENVIRONMENT=test
export DATABASE_URL="sqlite:///:memory:"
export DEBUG=true

# Parse command line arguments
TEST_TYPE="all"
COVERAGE=true
VERBOSE=false
PARALLEL=false

while [[ $# -gt 0 ]]; do
    case $1 in
        -t|--type)
            TEST_TYPE="$2"
            shift 2
            ;;
        --no-cov)
            COVERAGE=false
            shift
            ;;
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        -p|--parallel)
            PARALLEL=true
            shift
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo "Options:"
            echo "  -t, --type TYPE    Test type: all, unit, integration, e2e (default: all)"
            echo "  --no-cov          Disable coverage reporting"
            echo "  -v, --verbose      Verbose output"
            echo "  -p, --parallel     Run tests in parallel"
            echo "  -h, --help         Show this help message"
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Install test dependencies if needed
print_status "Checking test dependencies..."
if ! pip show pytest >/dev/null 2>&1; then
    print_status "Installing test dependencies..."
    pip install -r requirements-dev.txt
fi

# Build pytest command
PYTEST_CMD="pytest"

# Add coverage if enabled
if [ "$COVERAGE" = true ]; then
    PYTEST_CMD="$PYTEST_CMD --cov=src --cov-branch --cov-report=term-missing --cov-report=html:htmlcov --cov-report=xml"
fi

# Add verbosity if requested
if [ "$VERBOSE" = true ]; then
    PYTEST_CMD="$PYTEST_CMD -v"
fi

# Add parallel execution if requested
if [ "$PARALLEL" = true ]; then
    PYTEST_CMD="$PYTEST_CMD -n auto"
fi

# Add test path based on type
case $TEST_TYPE in
    "unit")
        PYTEST_CMD="$PYTEST_CMD tests/unit/"
        print_status "Running unit tests..."
        ;;
    "integration")
        PYTEST_CMD="$PYTEST_CMD tests/integration/"
        print_status "Running integration tests..."
        ;;
    "e2e")
        PYTEST_CMD="$PYTEST_CMD tests/e2e/"
        print_status "Running end-to-end tests..."
        ;;
    "all")
        PYTEST_CMD="$PYTEST_CMD tests/"
        print_status "Running all tests..."
        ;;
    *)
        print_error "Invalid test type: $TEST_TYPE"
        print_status "Valid types: all, unit, integration, e2e"
        exit 1
        ;;
esac

# Create logs directory for test logs
mkdir -p logs

# Run the tests
print_status "Executing: $PYTEST_CMD"
echo

if eval "$PYTEST_CMD"; then
    print_success "All tests passed!"
    
    # Show coverage summary if enabled
    if [ "$COVERAGE" = true ] && [ -f ".coverage" ]; then
        print_header "Coverage Summary"
        coverage report --show-missing
        
        if [ -d "htmlcov" ]; then
            print_status "HTML coverage report generated in htmlcov/"
            print_status "Open htmlcov/index.html in your browser to view detailed coverage"
        fi
    fi
    
else
    EXIT_CODE=$?
    print_error "Tests failed with exit code $EXIT_CODE"
    
    # Show recent test failures if available
    if [ -f ".pytest_cache/v/cache/lastfailed" ]; then
        print_header "Recent Test Failures"
        cat .pytest_cache/v/cache/lastfailed
    fi
    
    exit $EXIT_CODE
fi

# Show test artifacts
print_header "Test Artifacts"
echo "Generated files:"
ls -la | grep -E '\.(xml|html|log)$' || echo "No test artifacts found"

if [ -d "htmlcov" ]; then
    echo "Coverage HTML report: htmlcov/index.html"
fi

if [ -f "coverage.xml" ]; then
    echo "Coverage XML report: coverage.xml"
fi

print_success "Test execution completed successfully"
