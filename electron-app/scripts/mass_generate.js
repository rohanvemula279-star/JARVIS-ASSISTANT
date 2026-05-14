const fs = require('fs');
const path = require('path');

const agentsDir = path.join(__dirname, '../src/agents');

const data = {
  'mark-xxxix': {
    type: 'task',
    origin: 'Mark-XXXIX',
    items: [
      'browser_control', 'code_helper', 'computer_control', 'computer_settings',
      'desktop', 'dev_agent', 'file_controller', 'file_processor', 'flight_finder',
      'game_updater', 'open_app', 'reminder', 'screen_processor', 'send_message',
      'weather_report', 'web_search', 'youtube_video'
    ]
  },
  'jarvis-daemon': {
    type: 'agent',
    origin: 'VierisidJarvis',
    items: [
      'executive-assistant', 'research-specialist', 'system-admin', 'orchestrator',
      'delegation-agent', 'hierarchy-manager', 'messaging-agent', 'role-discovery', 'task-manager',
      'cdp-browser', 'terminal', 'filesystem', 'clipboard', 'screenshot', 'desktop-automation',
      'email', 'calendar', 'weather', 'web-search', 'rag-vault', 'goal-pursuit', 'workflow-automation'
    ]
  },
  'ruflo-swarm': {
    type: 'agent',
    origin: 'Ruflo',
    items: [
      'coder', 'planner', 'tester', 'reviewer', 'cicd-engineer', 'adaptive-coordinator',
      'mesh-coordinator', 'hierarchical-coordinator', 'researcher', 'analyst', 'decision-maker',
      'byzantine-coordinator', 'quorum-manager', 'security-manager', 'gossip-coordinator',
      'consensus-builder', 'fault-detector', 'recovery-agent', 'pr-reviewer', 'issue-manager',
      'release-manager', 'architect', 'spec-writer', 'implementer', 'tester-sparc', 'documenter',
      'api-docs', 'security-reviewer', 'devops-engineer', 'data-analyst', 'performance-analyst',
      'documentation-writer', 'compliance-checker'
    ]
  },
  'hermes-skills': {
    type: 'skill',
    origin: 'Hermes',
    items: [
      'apple', 'autonomous-ai-agents', 'creative', 'data-science', 'devops', 'diagramming',
      'dogfood', 'domain', 'email', 'gaming', 'gifs', 'github', 'index-cache', 'inference-sh',
      'mcp', 'media', 'mlops', 'note-taking', 'productivity', 'red-teaming', 'research',
      'smart-home', 'social-media', 'software-development', 'yuanbao'
    ]
  },
  'openclaw-skills': {
    type: 'skill',
    origin: 'OpenClaw',
    items: [
      '1password', 'apple-notes', 'apple-reminders', 'bear-notes', 'blogwatcher', 'blucli',
      'camsnap', 'canvas', 'clawhub', 'coding-agent', 'discord', 'eightctl', 'gemini',
      'gh-issues', 'gifgrep', 'github', 'gog', 'goplaces', 'healthcheck', 'himalaya', 'imsg',
      'mcporter', 'model-usage', 'nano-pdf', 'node-connect', 'notion', 'obsidian',
      'openai-whisper-api', 'openai-whisper', 'openhue', 'oracle', 'ordercli', 'peekaboo',
      'sag', 'session-logs', 'sherpa-onnx-tts', 'skill-creator', 'slack', 'songsee', 'sonoscli',
      'spotify-player', 'summarize', 'taskflow-inbox-triage', 'taskflow', 'things-mac', 'tmux',
      'trello', 'video-frames', 'voice-call', 'wacli', 'weather', 'xurl'
    ]
  }
};

if (!fs.existsSync(agentsDir)) {
  fs.mkdirSync(agentsDir, { recursive: true });
}

let totalGenerated = 0;

for (const [folder, config] of Object.entries(data)) {
  const folderPath = path.join(agentsDir, folder);
  if (!fs.existsSync(folderPath)) fs.mkdirSync(folderPath, { recursive: true });

  for (const item of config.items) {
    const itemPath = path.join(folderPath, item);
    if (!fs.existsSync(itemPath)) fs.mkdirSync(itemPath, { recursive: true });

    // manifest.json
    const manifest = {
      id: `${config.type}.${item.replace(/-/g, '_')}`,
      name: item,
      description: `Automatically imported ${config.type} from ${config.origin}`,
      kind: config.type,
      category: folder,
      origin: config.origin,
      entry: 'index.js',
      paramsSchema: { type: 'object' },
      requires: [],
      riskLevel: config.origin === 'Ruflo' ? 'high' : 'medium'
    };

    fs.writeFileSync(path.join(itemPath, 'manifest.json'), JSON.stringify(manifest, null, 2));

    // index.js
    let indexContent = '';
    if (folder === 'mark-xxxix') {
      indexContent = `module.exports = {
  execute: async (args, context) => {
    try {
      const response = await fetch('http://127.0.0.1:8000/api/v1/actions/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: '${item}', params: args })
      });
      const result = await response.json();
      return result.output || result;
    } catch (e) {
      return "Failed to execute ${item} via Python backend: " + e.message;
    }
  }
};`;
    } else {
      indexContent = `module.exports = {
  execute: async (args, context) => {
    return "Executed ${config.origin} ${config.type} [${item}] successfully. (Requires configuration)";
  }
};`;
    }

    fs.writeFileSync(path.join(itemPath, 'index.js'), indexContent);
    totalGenerated++;
  }
}

console.log("Successfully generated " + totalGenerated + " tasks/agents/skills.");
