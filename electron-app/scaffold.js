const fs = require('fs');
const path = require('path');

const srcDir = path.join(__dirname, 'src');
const dirs = [
  'components',
  'hooks',
  'state',
  'services/api',
  'services/speech',
  'services/context',
  'services/chat',
  'services/system',
  'utils'
];

dirs.forEach(d => fs.mkdirSync(path.join(srcDir, d), { recursive: true }));

const components = [
  'AppShell', 'CenterAssistantOrb', 'AssistantStatusLine', 'ChatPanel',
  'ChatHeader', 'ChatMessageList', 'ChatComposer', 'CameraWidget',
  'DateTimeWidget', 'LiveContextPanel', 'ContextCard', 'TopUtilityBar',
  'CommandPalette', 'StatusBadge', 'ProviderStatusPill', 'TaskActivityFeed'
];

components.forEach(c => {
  const content = `import React from 'react';\n\nconst ${c} = () => {\n  return (\n    <div className="${c.toLowerCase()}">\n      {/* TODO: Implement ${c} */}\n    </div>\n  );\n};\n\nexport default ${c};\n`;
  fs.writeFileSync(path.join(srcDir, 'components', `${c}.jsx`), content);
});

const hooks = [
  'useAssistantState', 'useClock', 'useDoubleClick', 'useVoiceControls',
  'useStreamingChat', 'useLiveContext', 'useCameraPreview', 'useCommandPalette'
];

hooks.forEach(h => {
  const content = `import { useState, useEffect } from 'react';\n\nexport const ${h} = () => {\n  // TODO: Implement ${h}\n  return {};\n};\n`;
  fs.writeFileSync(path.join(srcDir, 'hooks', `${h}.js`), content);
});

const storeContent = `import { create } from 'zustand';

export const useAssistantStore = create((set) => ({
  assistantActive: false,
  mode: 'inactive', // inactive | idle | listening | thinking | executing | responding | muted | error
  muted: false,
  listening: false,
  processing: false,
  responding: false,
  cameraEnabled: false,
  userMediaPermission: null,
  messages: [],
  streamingMessageId: null,
  commandPaletteOpen: false,
  currentTime: new Date().toISOString(),
  currentDate: new Date().toISOString(),
  liveContextData: null,
  systemStatus: 'Ready',
  taskQueue: [],
  transcriptPartial: '',
  transcriptFinal: '',
  providerStatus: { nim: 'unknown', gemini: 'unknown' },
  voiceEnabled: true,
  ttsEnabled: true,
  connectionHealth: 'good',

  setAssistantActive: (active) => set({ assistantActive: active, mode: active ? 'idle' : 'inactive' }),
  setMode: (mode) => set({ mode }),
  setMuted: (muted) => set({ muted }),
  setListening: (listening) => set({ listening, mode: listening ? 'listening' : 'idle' }),
  addMessage: (msg) => set((state) => ({ messages: [...state.messages, msg] })),
  updateMessage: (id, updates) => set((state) => ({
    messages: state.messages.map(m => m.id === id ? { ...m, ...updates } : m)
  })),
  setCommandPaletteOpen: (open) => set({ commandPaletteOpen: open }),
  setLiveContextData: (data) => set({ liveContextData: data }),
  setTranscript: (partial, final) => set({ transcriptPartial: partial, transcriptFinal: final })
}));
`;
fs.writeFileSync(path.join(srcDir, 'state', 'assistantStore.js'), storeContent);

console.log('Scaffolding complete.');
