#!/bin/bash
# JARVIS Desktop Assistant - One-Command Startup
# Usage: ./start.sh [dev|app|backend|frontend]

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  JARVIS Desktop Assistant${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"
echo ""

# Parse arguments
MODE="${1:-dev}"

# Check Python
check_python() {
    if ! command -v python3 &> /dev/null; then
        echo -e "${RED}Python 3 not found. Please install Python 3.10+${NC}"
        exit 1
    fi
    echo -e "${GREEN}✓${NC} Python found"
}

# Check Node
check_node() {
    if ! command -v node &> /dev/null; then
        echo -e "${RED}Node.js not found. Please install Node 18+${NC}"
        exit 1
    fi
    echo -e "${GREEN}✓${NC} Node.js found: $(node --version)"
}

# Check npm
check_npm() {
    if ! command -v npm &> /dev/null; then
        echo -e "${RED}npm not found${NC}"
        exit 1
    fi
    echo -e "${GREEN}✓${NC} npm found: $(npm --version)"
}

# Install frontend deps
install_frontend() {
    echo -e "\n${YELLOW}Installing frontend dependencies...${NC}"
    cd "$SCRIPT_DIR/electron-app"
    npm install
    echo -e "${GREEN}✓${NC} Frontend dependencies installed"
}

# Start backend
start_backend() {
    echo -e "\n${YELLOW}Starting Python backend...${NC}"
    cd "$SCRIPT_DIR"

    # Use venv if available
    if [ -f "$SCRIPT_DIR/.venv/Scripts/python" ]; then
        PYTHON_CMD="$SCRIPT_DIR/.venv/Scripts/python"
    elif [ -f "$SCRIPT_DIR/.venv/bin/python" ]; then
        PYTHON_CMD="$SCRIPT_DIR/.venv/bin/python"
    else
        PYTHON_CMD="python3"
    fi

    $PYTHON_CMD backend/main.py &
    BACKEND_PID=$!
    echo -e "${GREEN}✓${NC} Backend started (PID: $BACKEND_PID)"
}

# Start frontend dev server
start_frontend() {
    echo -e "\n${YELLOW}Starting frontend dev server...${NC}"
    cd "$SCRIPT_DIR/electron-app"
    npm run dev &
    FRONTEND_PID=$!
    echo -e "${GREEN}✓${NC} Frontend started (PID: $FRONTEND_PID)"
}

# Start Electron
start_electron() {
    echo -e "\n${YELLOW}Starting Electron...${NC}"
    cd "$SCRIPT_DIR/electron-app"
    npm run electron &
    ELECTRON_PID=$!
    echo -e "${GREEN}✓${NC} Electron started (PID: $ELECTRON_PID)"
}

# Wait for backend health
wait_backend() {
    echo -e "\n${YELLOW}Waiting for backend to be ready...${NC}"
    for i in {1..30}; do
        if curl -s http://127.0.0.1:8000/health > /dev/null 2>&1; then
            echo -e "${GREEN}✓${NC} Backend is ready!"
            return 0
        fi
        sleep 1
    done
    echo -e "${RED}✗ Backend failed to start${NC}"
    return 1
}

# Run development mode
run_dev() {
    check_python
    check_node
    check_npm

    # Install deps if needed
    if [ ! -d "electron-app/node_modules" ]; then
        install_frontend
    fi

    # Start backend
    start_backend

    # Wait for backend
    if ! wait_backend; then
        echo -e "${RED}Failed to start backend. Exiting.${NC}"
        exit 1
    fi

    # Start frontend
    start_frontend

    # Wait for frontend
    echo -e "\n${YELLOW}Waiting for frontend...${NC}"
    for i in {1..30}; do
        if curl -s http://localhost:5173 > /dev/null 2>&1; then
            echo -e "${GREEN}✓${NC} Frontend is ready!"
            break
        fi
        sleep 1
    done

    # Start Electron
    start_electron

    echo ""
    echo -e "${GREEN}═══════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}  JARVIS is running!${NC}"
    echo -e "${GREEN}═══════════════════════════════════════════════════${NC}"
    echo -e "  Frontend: ${BLUE}http://localhost:5173${NC}"
    echo -e "  Backend:  ${BLUE}http://127.0.0.1:8000${NC}"
    echo -e "  HUD:      ${BLUE}Press Ctrl+J to toggle${NC}"
    echo ""
    echo -e "${YELLOW}Press Ctrl+C to stop${NC}"
    echo ""

    # Wait for all processes
    wait
}

# Run backend only
run_backend() {
    check_python
    start_backend
    wait_backend
    wait
}

# Run frontend only
run_frontend() {
    check_node
    check_npm
    if [ ! -d "electron-app/node_modules" ]; then
        install_frontend
    fi
    start_frontend
    wait
}

# Show help
show_help() {
    echo "JARVIS Desktop Assistant - Startup Script"
    echo ""
    echo "Usage: ./start.sh [command]"
    echo ""
    echo "Commands:"
    echo "  dev       - Start full app (backend + frontend + Electron)"
    echo "  backend   - Start only the Python backend"
    echo "  frontend  - Start only the frontend dev server"
    echo "  install   - Install all dependencies"
    echo "  help      - Show this help"
    echo ""
}

# Main
case "$MODE" in
    dev)
        run_dev
        ;;
    backend)
        run_backend
        ;;
    frontend)
        run_frontend
        ;;
    install)
        check_python
        check_node
        check_npm
        install_frontend
        echo -e "${GREEN}✓ All dependencies installed${NC}"
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        echo -e "${RED}Unknown command: $MODE${NC}"
        show_help
        exit 1
        ;;
esac
