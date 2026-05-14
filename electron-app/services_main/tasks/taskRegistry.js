const path = require('path');
const fs = require('fs');

class TaskRegistry {
  constructor() {
    this.tasks = new Map();
  }

  async initialize() {
    await this.scanDirectories();
  }

  async scanDirectories() {
    const basePaths = [
      path.join(__dirname, '../../../src/agents'),
      path.join(__dirname, '../../../src/core/tasks')
    ];

    let totalLoaded = 0;

    for (const basePath of basePaths) {
      if (!fs.existsSync(basePath)) continue;

      const categories = fs.readdirSync(basePath, { withFileTypes: true })
        .filter(dirent => dirent.isDirectory())
        .map(dirent => dirent.name);

      for (const category of categories) {
        const categoryPath = path.join(basePath, category);
        const items = fs.readdirSync(categoryPath, { withFileTypes: true })
          .filter(dirent => dirent.isDirectory())
          .map(dirent => dirent.name);

        for (const item of items) {
          const itemPath = path.join(categoryPath, item);
          const manifestPath = path.join(itemPath, 'manifest.json');
          const indexPath = path.join(itemPath, 'index.js');

          if (fs.existsSync(manifestPath) && fs.existsSync(indexPath)) {
            try {
              const manifestContent = fs.readFileSync(manifestPath, 'utf-8');
              const manifest = JSON.parse(manifestContent);
              const logic = require(indexPath);

              this.register({
                ...manifest,
                execute: logic.execute
              });
              totalLoaded++;
            } catch (err) {
              console.error(`Failed to load task/agent at ${itemPath}: ${err.message}`);
            }
          }
        }
      }
    }
    console.log(`TaskRegistry initialized. Loaded ${totalLoaded} capabilities.`);
  }

  register(task) {
    this.tasks.set(task.name, task);
  }

  get(name) {
    return this.tasks.get(name);
  }

  getAll() {
    return Array.from(this.tasks.values());
  }
}

module.exports = new TaskRegistry();
