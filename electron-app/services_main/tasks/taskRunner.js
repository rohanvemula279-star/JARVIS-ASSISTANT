const taskRegistry = require('./taskRegistry');

class TaskRunner {
  async run(taskName, args = {}) {
    const task = taskRegistry.get(taskName);
    if (!task) throw new Error(`Task \${taskName} not found`);

    if (typeof task.execute !== 'function') {
      throw new Error(`Task \${taskName} has no valid execution logic`);
    }

    return await task.execute(args, { registry: taskRegistry });
  }
}

module.exports = new TaskRunner();
