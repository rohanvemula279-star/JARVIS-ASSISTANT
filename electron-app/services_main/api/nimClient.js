const eventBus = require('../../orchestrator/eventBus');

class NimClient {
  constructor() {
    this.apiKey = process.env.NVIDIA_NIM_API_KEY;
    this.baseUrl = process.env.NVIDIA_NIM_BASE_URL || 'https://integrate.api.nvidia.com/v1';
    this.model = process.env.NVIDIA_NIM_MODEL || 'meta/llama3-70b-instruct';
  }

  async *chat(messages) {
    if (!this.apiKey) {
      eventBus.emit('stateUpdate', { providerStatus: { nim: 'missing_key' } });
      yield "JERSEY: NVIDIA NIM API key is missing. Please configure it in your environment.";
      return;
    }
    
    try {
      const response = await fetch(`${this.baseUrl}/chat/completions`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${this.apiKey}`
        },
        body: JSON.stringify({
          model: this.model,
          messages: [
            { role: 'system', content: 'You are JERSEY, a highly advanced AI assistant. You use a calm, professional female voice persona. Be concise, direct, and helpful.' },
            ...messages
          ],
          stream: true,
          max_tokens: 1024,
        })
      });

      if (!response.ok) {
        eventBus.emit('stateUpdate', { providerStatus: { nim: 'error' } });
        throw new Error(`NIM Error: ${response.status}`);
      }

      eventBus.emit('stateUpdate', { providerStatus: { nim: 'online' } });

      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value, { stream: true });
        const lines = chunk.split('\n');
        for (const line of lines) {
          if (line.startsWith('data: ') && line !== 'data: [DONE]') {
            try {
              const data = JSON.parse(line.slice(6));
              if (data.choices[0].delta.content) {
                yield data.choices[0].delta.content;
              }
            } catch (e) {
              // Ignore parse errors on partial chunks
            }
          }
        }
      }
    } catch (e) {
      console.error(e);
      eventBus.emit('stateUpdate', { providerStatus: { nim: 'offline' } });
      yield "JERSEY: I am having trouble connecting to the neural reasoning engine.";
    }
  }

  async planTask(intent, tools) {
    if (!this.apiKey) return null;
    
    try {
      const response = await fetch(`${this.baseUrl}/chat/completions`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${this.apiKey}`
        },
        body: JSON.stringify({
          model: this.model,
          messages: [
            { 
              role: 'system', 
              content: `You are a task planner for JERSEY. Given a user intent and a list of tools, decide if a tool should be called. 
              Tools: ${JSON.stringify(tools)}
              Return ONLY a JSON object: { "tool": "tool_name", "params": { ... } } or { "tool": null } if no tool matches.`
            },
            { role: 'user', content: intent }
          ],
          response_format: { type: 'json_object' }
        })
      });

      if (!response.ok) return null;
      const data = await response.json();
      return JSON.parse(data.choices[0].message.content);
    } catch (e) {
      console.error('Planning error:', e);
      return null;
    }
  }

  async vision(image, prompt) {
     return "Vision module standby.";
  }
}

module.exports = new NimClient();
