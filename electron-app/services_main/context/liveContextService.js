const geminiClient = require('../api/geminiClient');
const eventBus = require('../../orchestrator/eventBus');

class LiveContextService {
  constructor() {
    this.interval = 60000; // 1 minute
    this.timer = null;
    this.retryCount = 0;
    this.maxRetries = 3;
  }

  async start() {
    this.update();
    this.timer = setInterval(() => this.update(), this.interval);
  }

  async update() {
    try {
      const context = await Promise.race([
        geminiClient.fetchContext(),
        new Promise((_, reject) => setTimeout(() => reject(new Error('Timeout')), 5000))
      ]);
      eventBus.emit('stateUpdate', { liveContextData: context });
      this.retryCount = 0;
    } catch (e) {
      console.error('Live Context Update Failed:', e);
      // Send degraded state instead of failing
      eventBus.emit('stateUpdate', { 
        liveContextData: {
          location: "Sector Unknown",
          weather: "Atmospheric Data Unavailable",
          headline: "JERSEY: Live feed offline - running in local mode",
          system: "Local Operation"
        }
      });
      if (this.retryCount < this.maxRetries) {
        this.retryCount++;
        const backoff = Math.pow(2, this.retryCount) * 1000;
        setTimeout(() => this.update(), backoff);
      }
    }
  }

  async getLiveContext() {
    return await geminiClient.fetchContext();
  }
}

module.exports = new LiveContextService();
