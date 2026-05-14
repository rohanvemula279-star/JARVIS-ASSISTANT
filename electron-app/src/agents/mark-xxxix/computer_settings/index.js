module.exports = {
  execute: async (args, context) => {
    try {
      const response = await fetch('http://127.0.0.1:8000/api/v1/actions/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: 'computer_settings', params: args })
      });
      const result = await response.json();
      return result.output || result;
    } catch (e) {
      return "Failed to execute computer_settings via Python backend: " + e.message;
    }
  }
};