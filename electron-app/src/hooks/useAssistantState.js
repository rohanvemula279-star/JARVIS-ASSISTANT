import { useEffect, useCallback } from 'react';
import { useAssistantStore } from '../state/assistantStore';
import { ttsService } from '../services/speech/ttsService';

const BACKEND_URL = 'http://127.0.0.1:8000';

/**
 * Main assistant lifecycle hook.
 * Handles:
 *  - Backend status polling
 *  - Electron IPC event binding  
 *  - Task loading
 */
export const useAssistantState = () => {
  const { setMode, addMessage, updateMessage, setProviderStatus, setTasks, setConnectionHealth } = useAssistantStore();

  useEffect(() => {
    // Initial status check from backend
    fetch(`${BACKEND_URL}/api/v1/system/status`)
      .then(r => {
        if (!r.ok) throw new Error('Backend not responding');
        return r.json();
      })
      .then(status => {
        setConnectionHealth('good');
        if (status.providers) {
          setProviderStatus('nim', status.providers.nvidia === 'configured' ? 'online' : 'missing_key');
          setProviderStatus('gemini', status.providers.gemini === 'configured' ? 'online' : 'missing_key');
        }
        setProviderStatus('python', 'online');
        setMode(status.mode || 'idle');
      })
      .catch(err => {
        console.error('JARVIS: Backend connection failed:', err.message);
        setConnectionHealth('offline');
        setProviderStatus('nim', 'offline');
        setProviderStatus('gemini', 'offline');
        setProviderStatus('python', 'offline');
        setMode('error');
      });

    // Load tasks from Electron and backend
    const loadTasks = async () => {
      try {
        let localTasks = [];
        if (window.assistant && window.assistant.getTasks) {
          localTasks = await window.assistant.getTasks() || [];
        }

        const response = await fetch(`${BACKEND_URL}/api/v1/tools`);
        const data = await response.json();
        const backendTools = (data.tools || []).map(t => ({
          ...t,
          id: `tool-${t.name}`,
          origin: 'Backend',
          kind: 'tool',
        }));

        const allTasks = [...localTasks];
        backendTools.forEach(bt => {
          if (!allTasks.some(lt => lt.name === bt.name)) {
            allTasks.push(bt);
          }
        });

        setTasks(allTasks);
        console.log(`JARVIS: Loaded ${allTasks.length} tools/tasks`);
      } catch (err) {
        console.error('JARVIS: Failed to load tasks:', err);
      }
    };

    loadTasks();

    // Listen for Electron IPC events
    if (window.assistant) {
      const unbindState = window.assistant.onStateUpdate((state) => {
        if (state.mode) setMode(state.mode);
        if (state.processing !== undefined) useAssistantStore.setState({ processing: state.processing });
        if (state.statusMessage !== undefined) useAssistantStore.setState({ statusMessage: state.statusMessage });
        if (state.liveContextData !== undefined) useAssistantStore.setState({ liveContextData: state.liveContextData });
        if (state.providerStatus) {
          Object.entries(state.providerStatus).forEach(([provider, status]) => {
            setProviderStatus(provider, status);
          });
        }
        if (state.connectionHealth) setConnectionHealth(state.connectionHealth);
      });

      const unbindStream = window.assistant.onStreamChunk((chunk) => {
        const currentMessages = useAssistantStore.getState().messages;
        const existing = currentMessages.find(m => m.id === chunk.id);

        if (existing) {
          updateMessage(chunk.id, { content: chunk.content, streaming: chunk.streaming });
          if (existing.streaming && !chunk.streaming) {
            ttsService.speak(chunk.content);
          }
        } else {
          addMessage(chunk);
          if (chunk.role === 'assistant' && !chunk.streaming) {
            ttsService.speak(chunk.content);
          }
        }
      });

      return () => {
        if (unbindState) unbindState();
        if (unbindStream) unbindStream();
      };
    }
  }, []);
};

/**
 * Unified streaming hook for sending messages to backend.
 * Handles the Mark-XL multi-event SSE protocol:
 *   - event: metadata  → intent classification
 *   - event: step      → ReAct thinking/action/observation
 *   - event: token     → text chunks
 *   - event: done      → completion
 *   - event: error     → error details
 */
const PROFILE_COLORS = {
  RESEARCHER: 'teal',
  EXECUTOR: 'blue',
  ANALYST: 'purple',
  CODER: 'amber',
  DEFAULT: 'gray',
};

export const useBackendStream = () => {
  const { addMessage, updateMessage, setMode, setConnectionHealth, addStep, clearSteps, addAgent, updateAgent, clearAgents } = useAssistantStore();

  const sendMessage = useCallback(async (text) => {
    const correlationId = Date.now().toString();
    const assistantId = 'assistant-' + correlationId;

    // Add user message
    addMessage({
      id: 'user-' + correlationId,
      role: 'user',
      content: text,
      createdAt: new Date().toISOString(),
    });

    setMode('thinking');
    setConnectionHealth('good');
    clearSteps();
    clearAgents();

    // Create assistant placeholder
    addMessage({
      id: assistantId,
      role: 'assistant',
      content: '',
      streaming: true,
      createdAt: new Date().toISOString(),
    });

    try {
      const response = await fetch(`${BACKEND_URL}/api/v1/chat/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt: text, session_id: 'electron-main' }),
      });

      if (!response.ok) throw new Error('Stream failed: ' + response.status);

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let eventType = 'message';

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (let i = 0; i < lines.length; i++) {
          const line = lines[i];

          if (line.startsWith('event: ')) {
            eventType = line.slice(7).trim();
          } else if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));

              if (eventType === 'metadata') {
                if (data.skill_used) {
                  updateMessage(assistantId, {
                    statusMessage: `Skill activated: ${data.skill_used}`,
                  });
                } else {
                  updateMessage(assistantId, {
                    statusMessage: `Intent: ${data.intent} (${Math.round(data.confidence * 100)}%)`,
                  });
                }
                setMode('thinking');
              } else if (eventType === 'step') {
                addStep(data);

                if (data.type === 'agent_spawned') {
                  const profile = data.tool || 'DEFAULT';
                  addAgent({
                    id: data.input?.task_id || Date.now().toString(),
                    profile,
                    status: 'running',
                    task: data.content?.slice(0, 60) || '',
                  });
                  setMode('thinking');
                  updateMessage(assistantId, {
                    statusMessage: `Agent: ${data.content?.slice(0, 80)}...`,
                  });
                } else if (data.type === 'agent_complete') {
                  const profile = data.tool || 'DEFAULT';
                  updateMessage(assistantId, {
                    statusMessage: `✓ Agent complete`,
                  });
                } else if (data.type === 'agent_failed') {
                  updateMessage(assistantId, {
                    statusMessage: `✗ Agent failed`,
                  });
                } else if (data.type === 'skill_learned') {
                  updateMessage(assistantId, {
                    statusMessage: `✓ Learned new skill: ${data.skill_name}`,
                  });
                } else {
                  setMode('executing');
                  updateMessage(assistantId, {
                    statusMessage: `${data.type}: ${data.content?.slice(0, 80)}...`,
                  });
                }
              } else if (eventType === 'token' && data.text) {
                setMode('responding');
                const currentMsg = useAssistantStore.getState().messages.find(m => m.id === assistantId);
                updateMessage(assistantId, {
                  content: (currentMsg?.content || '') + data.text,
                  statusMessage: null,
                });
              } else if (eventType === 'done') {
                updateMessage(assistantId, { streaming: false });
                setMode('idle');

                const finalContent = useAssistantStore.getState().messages.find(m => m.id === assistantId)?.content;
                if (finalContent) {
                  ttsService.speak(finalContent);
                }
              } else if (eventType === 'error') {
                updateMessage(assistantId, {
                  content: data.message || "An error occurred.",
                  streaming: false,
                  error: data.message,
                });
                setMode('idle');
                setConnectionHealth('degraded');
              }
            } catch (e) {
              // Ignore partial JSON
            }
          }
        }
      }

      // Ensure final state
      const finalMsg = useAssistantStore.getState().messages.find(m => m.id === assistantId);
      updateMessage(assistantId, {
        streaming: false,
        content: finalMsg?.content || "Response complete.",
      });
      setMode('idle');

    } catch (error) {
      console.error('Stream error:', error);
      updateMessage(assistantId, {
        content: "Sir, I'm unable to connect to the neural core. Please ensure the backend is running on port 8000.",
        streaming: false,
        error: error.message,
      });
      setMode('idle');
      setConnectionHealth('offline');
    }
  }, [addMessage, updateMessage, setMode, setConnectionHealth, addStep, clearSteps, addAgent, updateAgent, clearAgents]);

  return { sendMessage };
};

/**
 * Hook for executing backend actions/tools directly.
 */
export const useBackendActions = () => {
  const executeAction = async (actionName, params = {}) => {
    try {
      const response = await fetch(`${BACKEND_URL}/api/v1/actions/execute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: actionName, params }),
      });

      const result = await response.json();
      return result.result || result;
    } catch (error) {
      return { error: `Action failed: ${error.message}` };
    }
  };

  return { executeAction };
};