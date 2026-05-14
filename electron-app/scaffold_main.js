const fs = require('fs');
const path = require('path');

const rootDir = __dirname;
const dirs = [
  'orchestrator',
  'services_main/api',
  'services_main/tasks',
  'services_main/context',
  'core/tasks/browser',
  'core/tasks/system',
  'agents/researcher'
];

dirs.forEach(d => fs.mkdirSync(path.join(rootDir, d), { recursive: true }));

const files = {
  'orchestrator/assistantOrchestrator.js': `const eventBus = require('./eventBus');\nconst taskRouter = require('./taskRouter');\nconst providerRouter = require('./providerRouter');\n\nclass AssistantOrchestrator {\n  constructor() {}\n  async handleIntent(text) { return { text: "I heard " + text }; }\n}\nmodule.exports = new AssistantOrchestrator();\n`,
  'orchestrator/providerRouter.js': `class ProviderRouter {\n  routeChat() {}\n  routeVision() {}\n  routeLiveContext() {}\n}\nmodule.exports = new ProviderRouter();\n`,
  'orchestrator/taskRouter.js': `const taskRegistry = require('../services_main/tasks/taskRegistry');\nclass TaskRouter {\n  routeTask(intent) {}\n}\nmodule.exports = new TaskRouter();\n`,
  'orchestrator/eventBus.js': `const EventEmitter = require('events');\nclass EventBus extends EventEmitter {}\nmodule.exports = new EventBus();\n`,
  'services_main/tasks/taskRegistry.js': `class TaskRegistry {\n  constructor() { this.tasks = new Map(); }\n  register(task) { this.tasks.set(task.name, task); }\n  get(name) { return this.tasks.get(name); }\n}\nmodule.exports = new TaskRegistry();\n`,
  'services_main/tasks/taskRunner.js': `class TaskRunner {\n  async run(task, args) { return await task.execute(args); }\n}\nmodule.exports = new TaskRunner();\n`,
  'services_main/api/geminiClient.js': `class GeminiClient {\n  async fetchContext() { return { weather: "Clear", location: "Unknown" }; }\n}\nmodule.exports = new GeminiClient();\n`,
  'services_main/api/nimClient.js': `class NimClient {\n  async chat(messages) { return "Response"; }\n}\nmodule.exports = new NimClient();\n`,
  'services_main/context/liveContextService.js': `const geminiClient = require('../api/geminiClient');\nclass LiveContextService {\n  async getLiveContext() { return await geminiClient.fetchContext(); }\n}\nmodule.exports = new LiveContextService();\n`,
  'core/tasks/browser/index.js': `module.exports = { name: 'open_browser', description: 'Opens browser', params: {}, execute: async () => { return "Browser opened"; } };\n`,
  'agents/researcher/manifest.json': `{\n  "name": "researcher",\n  "description": "Research agent",\n  "skills": ["search"]\n}\n`,
  'agents/researcher/index.js': `module.exports = { name: 'researcher', execute: async () => "Research done" };\n`
};

Object.entries(files).forEach(([filepath, content]) => {
  fs.writeFileSync(path.join(rootDir, filepath), content);
});

console.log('Main process scaffolding complete.');
