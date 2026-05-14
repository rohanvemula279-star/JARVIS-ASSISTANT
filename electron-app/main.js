require('dotenv').config();
const { app, BrowserWindow, globalShortcut, ipcMain, session, Tray, Menu } = require('electron');
const path = require('path');
const isDev = !app.isPackaged;

let mainWindow;
let pointerWindow;
let tray;

function createPointerWindow() {
  pointerWindow = new BrowserWindow({
    width: 20,
    height: 20,
    transparent: true,
    frame: false,
    alwaysOnTop: true,
    skipTaskbar: true,
    resizable: false,
    hasShadow: false,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
    },
  });

  // Simple white dot
  pointerWindow.loadURL('data:text/html,<html><body style="margin:0;overflow:hidden;-webkit-app-region:drag;"><div style="width:12px;height:12px;background:white;border-radius:50%;border:2px solid rgba(0,0,0,0.5);box-shadow:0 0 10px rgba(255,255,255,0.8);"></div></body></html>');
  
  pointerWindow.setIgnoreMouseEvents(false); // Allow dragging/clicking
  pointerWindow.setPosition(100, 100); // Initial position
}

function createWindow() {
  const { screen, systemPreferences } = require('electron');
  const primaryDisplay = screen.getPrimaryDisplay();
  const { width, height } = primaryDisplay.workAreaSize;

  mainWindow = new BrowserWindow({
    fullscreen: true,
    frame: false,
    alwaysOnTop: true,
    skipTaskbar: false,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js'),
    },
  });

  // Handle macOS specific media permissions
  if (process.platform === 'darwin') {
    const askForPermissions = async () => {
      try {
        const cameraStatus = systemPreferences.getMediaAccessStatus('camera');
        if (cameraStatus !== 'granted') {
          await systemPreferences.askForMediaAccess('camera');
        }
        const micStatus = systemPreferences.getMediaAccessStatus('microphone');
        if (micStatus !== 'granted') {
          await systemPreferences.askForMediaAccess('microphone');
        }
      } catch (err) {
        console.error('macOS Permission Error:', err);
      }
    };
    askForPermissions();
  }

  // Complete permission handling - both check and request handlers
  session.defaultSession.setPermissionCheckHandler((webContents, permission, requestingOrigin, details) => {
    // Check permissions before they're requested
    const allowedPermissions = ['media', 'camera', 'microphone'];
    if (allowedPermissions.includes(permission)) {
      return true;
    }
    return false;
  });

  session.defaultSession.setPermissionRequestHandler((webContents, permission, callback) => {
    const url = webContents.getURL();
    const isTrusted = url.startsWith('http://localhost') || url.startsWith('file://');

    if (!isTrusted) {
      console.warn(`[SECURITY] Permission ${permission} denied for untrusted origin: ${url}`);
      return callback(false);
    }

    const allowedPermissions = ['media', 'camera', 'microphone', 'fullscreen', 'notifications'];
    if (allowedPermissions.includes(permission)) {
      callback(true);
    } else {
      callback(false);
    }
  });

  // Set content security policy for camera access
  session.defaultSession.webRequest.onHeadersReceived((details, callback) => {
    callback({
      responseHeaders: {
        ...details.responseHeaders,
        'Content-Security-Policy': ["default-src 'self' 'unsafe-inline' 'unsafe-eval' https://generativelanguage.googleapis.com; connect-src 'self' http://127.0.0.1:8000 ws://127.0.0.1:8000; media-src 'self' blob: mediastream:; img-src 'self' data: blob:;"]
      }
    });
  });

  if (isDev && process.env.NODE_ENV === 'development') {
    mainWindow.loadURL('http://localhost:5173');
    // mainWindow.webContents.openDevTools();
  } else {
    mainWindow.loadFile(path.join(__dirname, 'dist/index.html'));
  }

  setupIpcHandlers(mainWindow);
  setupEventBus(mainWindow);
}

function createTray() {
  // Try multiple icon paths for compatibility
  const possiblePaths = [
    path.join(__dirname, 'public', 'icon.png'),
    path.join(__dirname, 'public', 'icon.ico'),
    path.join(__dirname, 'build', 'icon.png'),
  ];
  let iconPath = null;
  for (const p of possiblePaths) {
    try {
      if (require('fs').existsSync(p)) {
        iconPath = p;
        break;
      }
    } catch (e) {}
  }

  if (!iconPath) {
    console.warn("JARVIS: Tray icon not found, skipping tray creation.");
    return;
  }

  try {
    tray = new Tray(iconPath);
  } catch (e) {
    console.warn("JARVIS: Failed to load tray icon, skipping:", e.message);
    return;
  }
  const contextMenu = Menu.buildFromTemplate([
    { label: 'Show JARVIS', click: () => { mainWindow.show(); mainWindow.focus(); } },
    { label: 'Quit', click: () => { app.isQuitting = true; app.quit(); } }
  ]);
  tray.setToolTip('JARVIS System');
  tray.setContextMenu(contextMenu);
  tray.on('click', () => {
    mainWindow.isVisible() ? mainWindow.hide() : mainWindow.show();
  });
}

// Retry with exponential backoff for API calls
async function fetchWithRetry(url, options, maxRetries = 3) {
  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    try {
      const response = await fetch(url, {
        ...options,
        signal: AbortSignal.timeout(5000)
      });
      return response;
    } catch (err) {
      if (attempt === maxRetries) throw err;
      await new Promise(r => setTimeout(r, 300 * Math.pow(2, attempt - 1)));
    }
  }
  throw new Error('Max retries exceeded');
}

function setupIpcHandlers(win) {
  // Toggle active state
  ipcMain.handle('assistant:toggleActive', async () => {
    return { active: true };
  });

  // Toggle mute state
  ipcMain.handle('assistant:toggleMute', async () => {
    return { muted: true };
  });

  // Send message to backend - uses fast endpoint with retry
  ipcMain.handle('assistant:sendMessage', async (event, text) => {
    const startTime = Date.now();
    try {
      const response = await fetchWithRetry('http://127.0.0.1:8000/api/v1/fast', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt: text })
      });
      const data = await response.json();
      const latency = Date.now() - startTime;
      console.log(`[JARVIS] Message sent in ${latency}ms`);
      return data.answer || data.output || 'Response received';
    } catch (err) {
      console.error('Send message error:', err);
      return 'Error communicating with backend';
    }
  });

  // Get live context from Gemini - fast response
  ipcMain.handle('assistant:getLiveContext', async () => {
    try {
      const response = await fetch('http://127.0.0.1:8000/api/v1/system/status');
      const data = await response.json();
      return {
        location: data.location || 'Local',
        weather: data.weather || 'Clear',
        status: data.status,
        fastMode: data.fast_mode
      };
    } catch (err) {
      console.error('Live context error:', err);
      return { location: 'Unknown', weather: 'Unavailable', status: 'offline' };
    }
  });

  // Execute command - uses fast endpoint for <4s execution
  ipcMain.handle('assistant:executeCommand', async (event, payload) => {
    const taskName = payload.name || payload;

    // Try local task first
    if (taskRegistry && taskRegistry.get(taskName)) {
      try {
        const localTask = taskRegistry.get(taskName);
        if (localTask.execute) {
          return await localTask.execute(payload.params || {});
        }
      } catch (err) {
        console.error(`Local task failed: ${taskName}`, err);
      }
    }

    // Fallback to fast backend endpoint
    try {
      const response = await fetch('http://127.0.0.1:8000/api/v1/fast', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt: `execute ${taskName}`, params: payload.params || {} })
      });
      const result = await response.json();
      return result.answer || result.output || result;
    } catch (err) {
      console.error('Backend execution error:', err);
      return `Error: ${err.message}`;
    }
  });

  // Get all tasks from local registry
  ipcMain.handle('assistant:getTasks', async () => {
    if (!taskRegistry) return [];
    return taskRegistry.getAll().map((t, index) => ({
      id: t.id || t.name || `task-${index}`,
      name: t.name,
      description: t.description || '',
      kind: t.kind || 'task',
      category: t.category || 'general',
      origin: t.origin || 'Local',
      riskLevel: t.riskLevel || 'low'
    }));
  });

  // Execute a specific task
  ipcMain.handle('assistant:executeTask', async (event, taskName, params) => {
    if (taskRegistry && taskRegistry.get(taskName)) {
      const task = taskRegistry.get(taskName);
      if (task.execute) {
        return { success: true, result: await task.execute(params || {}) };
      }
    }
    return { success: false, error: 'Task not found' };
  });

  // Toggle camera
  ipcMain.handle('assistant:toggleCamera', async () => {
    return { cameraEnabled: true };
  });

  // Window controls
  ipcMain.handle('window:minimize', async () => {
    if (win) {
      win.minimize();
      return { success: true };
    }
    return { success: false };
  });

  ipcMain.handle('window:maximize', async () => {
    if (win) {
      if (win.isMaximized()) {
        win.unmaximize();
      } else {
        win.maximize();
      }
      return { success: true };
    }
    return { success: false };
  });

  ipcMain.handle('window:close', async () => {
    if (win) {
      win.close();
      return { success: true };
    }
    return { success: false };
  });
}

function setupEventBus(win) {
  const eventBus = require('./orchestrator/eventBus');

  eventBus.on('stateUpdate', (state) => {
    if (win && !win.isDestroyed()) {
      win.webContents.send('assistant:stateUpdate', state);
    }
  });

  eventBus.on('streamChunk', (chunk) => {
    if (win && !win.isDestroyed()) {
      win.webContents.send('assistant:streamChunk', chunk);
    }
  });

  eventBus.on('taskEvent', (event) => {
    if (win && !win.isDestroyed()) {
      win.webContents.send('assistant:taskEvent', event);
    }
  });
}

// Initialize services on startup
async function initializeServices() {
  try {
    // Initialize Task Registry
    taskRegistry = require('./services_main/tasks/taskRegistry');
    await taskRegistry.initialize();
    console.log(`[JARVIS] Loaded ${taskRegistry.getAll().length} tasks`);

    // Initialize Live Context Service
    liveContextService = require('./services_main/context/liveContextService');
    liveContextService.start();
    console.log('[JARVIS] Live context service started');

    // Load orchestrator
    assistantOrchestrator = require('./orchestrator/assistantOrchestrator');
    await assistantOrchestrator.initialize();
    console.log('[JARVIS] Orchestrator initialized');

  } catch (err) {
    console.error('[JARVIS] Service initialization warning:', err.message);
    // Don't fail - app can still run with reduced functionality
  }
}

// Retry logic with exponential backoff for backend health check
async function waitForBackend(maxRetries = 8, baseDelay = 500) {
  console.log('[JARVIS] Checking backend health...');

  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    try {
      const response = await fetch('http://127.0.0.1:8000/health', {
        method: 'GET',
        signal: AbortSignal.timeout(3000)
      });
      if (response.ok) {
        console.log(`[JARVIS] Backend ready after ${attempt} attempt(s)`);
        return true;
      }
    } catch (err) {
      // Backend not ready yet
    }

    const delay = Math.min(baseDelay * Math.pow(1.5, attempt - 1), 5000);
    console.log(`[JARVIS] Waiting for backend... attempt ${attempt}/${maxRetries} (${Math.round(delay)}ms)`);
    await new Promise(resolve => setTimeout(resolve, delay));
  }

  console.error('[JARVIS] Backend failed to start after maximum retries');
  return false;
}

app.whenReady().then(async () => {
  createTray();

  // Wait for backend to be ready before loading window
  const backendReady = await waitForBackend();

  if (!backendReady) {
    console.error('[JARVIS] Warning: Backend not available, starting in degraded mode');
  }

  await initializeServices();
  createWindow();
  createPointerWindow();

  // Register global shortcut for fast access anywhere
  globalShortcut.register('CommandOrControl+J', () => {
    if (mainWindow) {
      if (mainWindow.isVisible()) {
        if (mainWindow.isFocused()) {
          mainWindow.hide();
        } else {
          mainWindow.show();
          mainWindow.focus();
        }
      } else {
        mainWindow.show();
        mainWindow.focus();
      }
      // Notify frontend to wake up/start listening
      mainWindow.webContents.send('assistant:wake');
    }
  });

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('will-quit', () => {
  globalShortcut.unregisterAll();
  if (tray) tray.destroy();
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

// Handle uncaught exceptions
process.on('uncaughtException', (err) => {
  console.error('[JARVIS] Uncaught exception:', err.message);
});