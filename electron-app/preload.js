const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('assistant', {
  toggleActive: () => ipcRenderer.invoke('assistant:toggleActive'),
  toggleMute: () => ipcRenderer.invoke('assistant:toggleMute'),
  startListening: () => ipcRenderer.invoke('assistant:startListening'),
  stopListening: () => ipcRenderer.invoke('assistant:stopListening'),
  sendMessage: (text) => ipcRenderer.invoke('assistant:sendMessage', text),
  executeCommand: (commandPayload) => ipcRenderer.invoke('assistant:executeCommand', commandPayload),
  executeTask: (taskName, params) => ipcRenderer.invoke('assistant:executeTask', taskName, params),
  getTasks: () => ipcRenderer.invoke('assistant:getTasks'),
  getLiveContext: () => ipcRenderer.invoke('assistant:getLiveContext'),
  toggleCamera: () => ipcRenderer.invoke('assistant:toggleCamera'),
  onStateUpdate: (callback) => {
    const subscription = (_, state) => callback(state);
    ipcRenderer.on('assistant:stateUpdate', subscription);
    return () => ipcRenderer.removeListener('assistant:stateUpdate', subscription);
  },
  onStreamChunk: (callback) => {
    const subscription = (_, chunk) => callback(chunk);
    ipcRenderer.on('assistant:streamChunk', subscription);
    return () => ipcRenderer.removeListener('assistant:streamChunk', subscription);
  },
  onTaskEvent: (callback) => {
    const subscription = (_, event) => callback(event);
    ipcRenderer.on('assistant:taskEvent', subscription);
    return () => ipcRenderer.removeListener('assistant:taskEvent', subscription);
  },
  onTranscript: (callback) => {
    const subscription = (_, transcript) => callback(transcript);
    ipcRenderer.on('assistant:transcript', subscription);
    return () => ipcRenderer.removeListener('assistant:transcript', subscription);
  },
});

contextBridge.exposeInMainWorld('electronAPI', {
  windowControl: {
    minimize: () => ipcRenderer.invoke('window:minimize'),
    maximize: () => ipcRenderer.invoke('window:maximize'),
    close: () => ipcRenderer.invoke('window:close'),
  },
});
