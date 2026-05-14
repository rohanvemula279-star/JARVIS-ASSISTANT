# GEMINI.md - Project Mandates & Overview

This document serves as the foundational mandate for the **ASSISTANT (JARVIS Mark-XXXIX)** research environment. It provides the architectural blueprint, technology stack, and operational conventions that must be followed by all agents and developers.

## 🚀 Project Vision
JARVIS Mark-XXXIX is a premium, cinematic AI assistant designed for high-fidelity desktop and web interactions. The workspace serves as a multi-framework research lab, housing the primary JARVIS application alongside advanced autonomous agent frameworks.

---

## 🏗️ Architectural Overview (Triple-Interface System)

### 1. Web Command Center (Premium Core)
- **URL**: `http://localhost:8000/console`
- **Purpose**: The primary interface for complex tasks and PC control. 
- **Design**: Premium black theme, ChatGPT-style chat, full system integration.

### 2. Showcase HUD (Electron)
- **Purpose**: A fullscreen, cinematic interface for voice communication and "playing" with JARVIS.
- **Design**: Fullscreen, transparent, focus on aesthetics and voice.

### 3. Pointer Overlay (Quick Access)
- **Purpose**: A small, floating "white dot" for immediate task execution.
- **Access**: Click/Drag the dot for quick commands.

### 4. Personality Engine (Backend)
- **Rituals**: Responds to "Welcome Daddy's Home" with a full schedule report.
- **Tone**: Formal, helpful, senior assistant (JARVIS).

### 2. Integrated Frameworks & Research
- **`hermes-agent/`**: A self-improving autonomous agent framework with a built-in learning loop and multi-platform gateway (Telegram, Discord, etc.).
- **`ruflo/` (Claude Flow)**: An orchestration-led framework focused on coordination (claude-flow) and execution (Codex/Agent).
- **`OpenJarvis/`**: A modular assistant framework with Rust components and cross-platform support.
- **`Mark-XXXIX/`**: The legacy implementation of the Jarvis Mark 39 assistant.

---

## 🛠️ Technology Stack (Primary)

| Layer | Technologies |
| :--- | :--- |
| **Frontend** | React 19, Vite, Tailwind CSS 3, Framer Motion, Zustand |
| **Desktop** | Electron |
| **Backend** | Python 3.10+, FastAPI, Asyncio, Uvicorn |
| **Database** | SQLite (via `apps/agent-service/app/db/` and `hermes_state.py`) |
| **AI Models** | Google Gemini (2.0 Flash), NVIDIA NIM (Llama 3) |
| **Automation** | PyAutoGUI, Playwright, HTTPX |

---

## 📜 Development Conventions

### Python Standards
- **Async First**: Use `async/await` for all I/O bound operations.
- **Type Hinting**: Mandatory for all new functions and classes.
- **Framework**: Use FastAPI for API endpoints and `pydantic` for data validation.

### Frontend Standards
- **Styling**: Prefer Vanilla CSS for flexibility, but follow Tailwind patterns if already established in the specific app.
- **State Management**: Use Zustand for global state in the Electron app.
- **Bundling**: Vite is the standard across all web/desktop frontend projects.

### Security & Integrity
- **Credential Protection**: Never log, print, or commit secrets, API keys, or `.env` files. Rigorously protect system configuration folders.
- **Type Safety**: Maintain structural integrity and type safety; avoid hacks or suppressing warnings. Use explicit language features (e.g., type guards).

---

## 📂 Directory Map (Key Locations)
- `/apps/agent-service/app/agents/`: Core JARVIS agent logic (Orchestrator, Planner, Verifier).
- `/electron-app/src/`: JARVIS Desktop UI source code.
- `/hermes-agent/`: Autonomous agent framework (Research/Gateway).
- `/ruflo/`: Claude Flow V3 orchestration framework.
- `/packages/tools/`: Shared registry for modularized tools.
- `/actions/`: Individual action implementations (scripts).
- `/skills/`: Specialized behavioral guidelines and procedural knowledge.
- `/Mark-XXXIX/`: Legacy codebase for reference.
