const eventBus = require('../../orchestrator/eventBus');

class GeminiClient {
  constructor() {
    this.apiKey = process.env.GEMINI_API_KEY;
  }

  async fetchContext() {
    if (!this.apiKey) {
      console.log('No Gemini API key - using local context');
      return this._getLocalContext();
    }
    
    try {
      // Simpler fallback context - no API call required
      return this._getLocalContext();
    } catch (e) {
      console.log('Context error:', e.message);
      return this._getLocalContext();
    }
  }

  _getLocalContext() {
    return {
      location: "Local",
      weather: "Independent",
      headline: "JARVIS: Ready for Commands",
      system: "All Systems Online"
    };
  }
}

module.exports = new GeminiClient();
