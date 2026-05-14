# JARVIS Mark-XXXIX: Premium Desktop AI

A high-fidelity, cinematic desktop AI assistant built with **Electron**, **React**, and **Tailwind CSS**.

## 🎨 Visual Interface
- **Monochrome HUD**: A deep black, minimal interface inspired by sci-fi cinema.
- **Interactive Orb**: Centered "JARVIS" wordmark that pulses and scales.
- **Neural Stream**: A side-aligned, black-themed chat interface for command monitoring.
- **Optical Feed**: Top-left webcam preview widget.
- **Environment Context**: Bottom-left live stats panel.

## 🕹️ Controls
- **Single Click Orb**: Toggle Active/Inactive state.
- **Double Click Orb**: Toggle Mute/Unmute.
- **Ctrl+K**: Summon Command Palette (Bridge implementation required).

## 🚀 Execution

### 1. Prerequisites
- Node.js 20+

### 2. Installation
```bash
cd electron-app
npm install
```

### 3. Development
```bash
npm start
```

### 4. Production Build
```bash
npm run build
```

## 🏗️ Technical Stack
- **Shell**: Electron
- **Frontend**: React 19 + Vite
- **Styling**: Tailwind CSS 3
- **Animations**: Framer Motion
- **State**: Zustand
- **Media**: react-webcam

## 🧠 Future Integration Notes
- **Voice**: Integrate `Web Speech API` or `Deepgram` in `src/hooks/useVoice.js`.
- **Backend**: Connect to the existing Python sidecar via `fetch` to `127.0.0.1:8000`.
- **Learning**: Store session trajectory data in the `LiveContext` SQLite bridge.
