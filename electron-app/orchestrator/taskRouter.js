const taskRunner = require('./taskRunner');

class TaskRouter {
  async routeTask(taskName, args = {}) {
    try {
      return await taskRunner.run(taskName, args);
    } catch (error) {
      console.error(`Task routing error for ${taskName}:`, error);
      throw error;
    }
  }
}

module.exports = new TaskRouter();
