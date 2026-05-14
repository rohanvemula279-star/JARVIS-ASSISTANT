import json
from backend.sandbox.executor import executor
from backend.tools.registry import registry, ToolDefinition, ToolParameter

class CodeIntelligence:
    def __init__(self, executor_instance):
        from backend.config.settings import get_settings
        from google import genai
        settings = get_settings()
        self.executor = executor_instance
        self.client = genai.Client(api_key=settings.gemini_api_key)
        self.model = "gemini-2.0-flash"
        self.max_retries = 3
    
    async def solve_with_code(self, problem: str, data: str = None) -> dict:
        """Write code to solve a problem, auto-fix errors up to 3 times."""
        
        attempts = []
        for attempt in range(self.max_retries):
            prompt = f"""
            Write Python code to: {problem}
            {"Data available: " + data if data else ""}
            {"Previous attempt failed: " + str(attempts[-1]) if attempts else ""}
            
            Requirements:
            - Store final answer in variable named 'result'
            - Use only: json, math, re, datetime, collections, itertools, builtins
            - Print intermediate steps for debugging
            - Code must be complete and runnable
            
            Return ONLY the Python code, no explanation. Do not wrap in markdown blocks, just raw code.
            """
            
            response = await self.client.aio.models.generate_content(
                model=self.model,
                contents=[prompt]
            )
            code = response.text.replace("```python", "").replace("```", "").strip()
            result = await self.executor.execute(code)
            attempts.append({"code": code, "result": result})
            
            if result.get("success"):
                return {
                    "success": True,
                    "code": code,
                    "result": result.get("result"),
                    "output": result.get("stdout"),
                    "attempts": len(attempts)
                }
        
        return {"success": False, "attempts": attempts, 
                "error": "Failed after max retries"}
                
    async def run_python_code(self, code: str) -> dict:
        return await self.executor.execute(code)

code_intelligence = CodeIntelligence(executor)

registry.register(ToolDefinition(
    name="solve_with_code",
    description="Write and execute Python code to solve a complex problem.",
    parameters=[
        ToolParameter(name="problem", type="string", description="The problem description"),
        ToolParameter(name="data", type="string", description="Optional data", required=False)
    ],
    handler=code_intelligence.solve_with_code,
    category="system"
))

registry.register(ToolDefinition(
    name="run_python_code",
    description="Run raw Python code in a sandboxed environment.",
    parameters=[
        ToolParameter(name="code", type="string", description="The Python code to execute")
    ],
    handler=code_intelligence.run_python_code,
    category="system"
))
