const eventBus = require('./eventBus');
const crypto = require('crypto');

class AssistantOrchestrator {
  constructor() {
    this.isInitialized = false;
    this.backendUrl = 'http://127.0.0.1:8000';
  }

  async initialize() {
    if (this.isInitialized) return;
    this.isInitialized = true;
    console.log('[JERSEY] Orchestrator initialized');
  }

  async handleIntent(text) {
    if (!this.isInitialized) await this.initialize();

    const messageId = crypto.randomUUID();
    eventBus.emit('stateUpdate', { mode: 'thinking', processing: true });

    try {
      const response = await fetch(`${this.backendUrl}/api/v1/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prompt: text,
          correlation_id: messageId
        })
      });

      if (!response.ok) {
        throw new Error(`Backend Error: ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let fullContent = '';
      let eventType = 'message';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        const lines = chunk.split('\n');

        for (const line of lines) {
          if (line.startsWith('event: ')) {
            eventType = line.replace('event: ', '').trim();
          } else if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.replace('data: ', '').trim());

              if (data.text) {
                fullContent += data.text;
                eventBus.emit('streamChunk', {
                  id: messageId,
                  role: 'assistant',
                  content: fullContent,
                  createdAt: new Date().toISOString(),
                  streaming: true
                });
              } else if (data.message) {
                eventBus.emit('stateUpdate', { statusMessage: data.message });
              }
            } catch (e) {
              // Ignore partial JSON
            }
          }
        }
      }

      eventBus.emit('streamChunk', {
        id: messageId,
        role: 'assistant',
        content: fullContent,
        createdAt: new Date().toISOString(),
        streaming: false
      });

      eventBus.emit('stateUpdate', { mode: 'idle', processing: false, statusMessage: null });
      return fullContent;

    } catch (error) {
      console.error('[JERSEY] Orchestration error:', error);
      eventBus.emit('stateUpdate', { mode: 'error', processing: false });
      return "Sir, I am unable to connect to my primary core logic.";
    }
  }
}

module.exports = new AssistantOrchestrator();