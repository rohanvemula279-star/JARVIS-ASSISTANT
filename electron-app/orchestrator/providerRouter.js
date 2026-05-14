const nimClient = require('../services_main/api/nimClient');
const geminiClient = require('../services_main/api/geminiClient');

class ProviderRouter {
  async routeChat(messages) {
    return await nimClient.chat(messages);
  }
  
  async routeVision(image, prompt) {
    return await nimClient.vision(image, prompt);
  }
  
  async routeLiveContext() {
    return await geminiClient.fetchContext();
  }
  
  async routeTaskPlanning(intent) {
    return await nimClient.planTask(intent);
  }
}

module.exports = new ProviderRouter();
