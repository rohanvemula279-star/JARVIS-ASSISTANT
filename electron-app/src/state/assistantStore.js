import { create } from 'zustand';
import { devtools, persist } from 'zustand/middleware';

/**
 * JARVIS Mark-XL — Single Source of Truth Store
 * 
 * Merges the previous assistantStore.js and store/index.js into one
 * unified state container. All UI components use this single store.
 */
export const useAssistantStore = create(
  devtools(
    persist(
      (set, get) => ({
        // ===== UI State =====
        assistantActive: false,
        mode: 'inactive', // inactive | idle | listening | thinking | executing | responding | error
        muted: false,
        listening: false,
        processing: false,
        responding: false,
        cameraEnabled: false,
        micEnabled: true,
        userMediaPermission: null,
        commandPaletteOpen: false,
        connectionHealth: 'good', // good | degraded | offline

        // ===== Chat State =====
        messages: [],
        isStreaming: false,
        streamingContent: '',
        streamingMessageId: null,

        // ===== System State =====
        backendStatus: 'offline', // offline | connecting | online
        currentModel: 'gemini-2.0-flash',
        systemStatus: 'Ready',
        statusMessage: null,

        // ===== Context State =====
        liveContextData: null,
        currentTime: new Date().toISOString(),
        currentDate: new Date().toISOString(),

        // ===== Task State =====
        tasks: [],
        activeTasks: [],
        taskHistory: [],
        activeSteps: [], // ReAct loop steps for current task
        activeAgents: [], // Multi-agent coordination: {id, profile, status, task}

        // ===== Provider State =====
        providerStatus: { nim: 'unknown', gemini: 'unknown', python: 'unknown' },
        voiceEnabled: true,
        ttsEnabled: true,
        transcriptPartial: '',
        transcriptFinal: '',

        // ===== Actions =====

        // Mode
        setAssistantActive: (active) => set({ 
          assistantActive: active, 
          mode: active ? 'idle' : 'inactive' 
        }),
        setMode: (mode) => set({ mode }),
        setStatusMessage: (msg) => set({ statusMessage: msg }),
        setMuted: (muted) => set({ muted }),
        setListening: (listening) => set({ listening, mode: listening ? 'listening' : 'idle' }),

        // Camera & Mic
        toggleCamera: () => set((state) => ({ cameraEnabled: !state.cameraEnabled })),
        toggleMic: () => set((state) => ({ micEnabled: !state.micEnabled })),

        // Messages
        addMessage: (msg) => set((state) => ({
          messages: [...state.messages, {
            ...msg,
            id: msg.id || Date.now().toString(),
            timestamp: msg.timestamp || new Date().toISOString(),
          }]
        })),
        updateMessage: (id, updates) => set((state) => ({
          messages: state.messages.map(m => m.id === id ? { ...m, ...updates } : m)
        })),
        clearChat: () => set({ messages: [], activeSteps: [] }),

        // Streaming
        setStreaming: (streaming) => set({ isStreaming: streaming }),
        updateStreamingContent: (chunk) => set((state) => ({
          streamingContent: state.streamingContent + chunk
        })),
        commitStreamedMessage: () => set((state) => ({
          messages: [...state.messages, {
            id: Date.now().toString(),
            role: 'assistant',
            content: state.streamingContent,
            timestamp: new Date().toISOString(),
          }],
          streamingContent: '',
          isStreaming: false,
        })),

        // ReAct Steps
        addStep: (step) => set((state) => ({
          activeSteps: [...state.activeSteps, step]
        })),
        clearSteps: () => set({ activeSteps: [] }),

        // Context
        setLiveContextData: (data) => set({ liveContextData: data }),
        setConnectionHealth: (health) => set({ connectionHealth: health }),
        setBackendStatus: (status) => set({ backendStatus: status }),

        // Command Palette
        setCommandPaletteOpen: (open) => set({ commandPaletteOpen: open }),

        // Transcript
        setTranscript: (partial, final) => set({ transcriptPartial: partial, transcriptFinal: final }),

        // Providers
        setProviderStatus: (provider, status) => set((state) => ({
          providerStatus: { ...state.providerStatus, [provider]: status }
        })),

        // Tasks
        setTasks: (tasks) => set({ tasks }),
        addTask: (task) => set((state) => ({
          activeTasks: [...state.activeTasks, task]
        })),
        updateTask: (id, update) => set((state) => ({
          activeTasks: state.activeTasks.map(t => t.id === id ? { ...t, ...update } : t)
        })),

        // Multi-Agent Coordination
        addAgent: (agent) => set((state) => ({
          activeAgents: [...state.activeAgents, agent]
        })),
        updateAgent: (id, update) => set((state) => ({
          activeAgents: state.activeAgents.map(a => a.id === id ? { ...a, ...update } : a)
        })),
        clearAgents: () => set({ activeAgents: [] }),
      }),
      {
        name: 'jarvis-store',
        // Only persist the last 50 messages and tasks
        partialize: (state) => ({
          messages: state.messages.slice(-50),
          tasks: state.tasks,
        }),
      }
    ),
    { name: 'JARVIS Store' }
  )
);

// Default export for backward compatibility with store/index.js imports
export default useAssistantStore;
