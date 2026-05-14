module.exports = {
  execute: async (args, context) => {
    try {
      const response = await fetch('http://127.0.0.1:8000/api/v1/actions/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: 'file_processor', params: args })
      });
      const result = await response.json();
      return result.output || result;
    } catch (e) {
      return "Failed to execute file_processor via Python backend: " + e.message;
    }
  }
};