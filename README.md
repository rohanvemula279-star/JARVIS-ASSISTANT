# JARVIS Desktop Assistant

An integrated, multi-agent desktop assistant with an always-on Electron HUD, fast local execution, and a modular Python backend. Inspired by `vierisid/jarvis` and `Mark-XXXIX`.

## Features
- **One-Command Startup**: Boot the frontend, backend, and health checks seamlessly.
- **Fast Action Mode**: Zero-latency execution for simple desktop tasks (opening apps, typing, screenshots, web search) bypassing heavy LLM planners.
- **Multi-Agent Backend**: Commander, Avenger (Desktop), Navigator (Web), Memory (SQLite), and Planner modules working together.
- **HUD Interface**: Global shortcut (`Ctrl/Cmd + J`), system tray support, and a transparent floating interface.
- **Local Memory**: SQLite-based memory system that learns your application paths and successful workflows over time.

## Requirements
- **Node.js**: v18+
- **Python**: 3.10+
- OS: Windows 11 prioritized, MacOS/Linux compatible.

## Installation & Setup

1. Install dependencies for both frontend and backend:
   ```bash
   npm run install:all
   ```
2. Configure `.env` if using the LLM Planner agent:
   ```env
   GEMINI_API_KEY="your_api_key_here"
   ```

## Usage

**Start the Assistant:**
```bash
npm start
```

This single command will:
1. Boot the `uvicorn` Python backend on port 8000.
2. Boot the Vite React server on port 5173.
3. Wait for the backend health check to pass.
4. Launch the Electron HUD.

**Access Anywhere:**
Press `Ctrl+J` (or `Cmd+J`) to instantly summon or hide the JARVIS HUD from any screen.

## Architecture
See [ARCHITECTURE.md](ARCHITECTURE.md) for details on the multi-agent design, the difference between Fast Paths and Planner flows, and security implementations.

## Acknowledgements
This project consolidates ideas from:
- [vierisid/jarvis](https://github.com/vierisid/jarvis) (Daemon/Sidecar architecture)
- [FatihMakes/Mark-XXXIX](https://github.com/FatihMakes/Mark-XXXIX) (HUD UX & Desktop Automation)
- [ruvnet/ruflo](https://github.com/ruvnet/ruflo) (Multi-agent workflows)
