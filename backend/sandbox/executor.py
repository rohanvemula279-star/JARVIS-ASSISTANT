import io
import contextlib
import importlib

class CodeExecutor:
    TIMEOUT = 30  # seconds
    MAX_OUTPUT = 10_000  # chars
    
    BLOCKED_IMPORTS = ["os.system", "subprocess", "shutil.rmtree", 
                       "socket", "__import__"]
    
    async def execute(self, code: str, context: dict = None) -> dict:
        """Execute Python code in an isolated namespace."""
        
        # 1. Static safety scan
        for blocked in self.BLOCKED_IMPORTS:
            if blocked in code:
                return {"success": False, "error": f"Blocked: {blocked}"}
        
        # 2. Build safe namespace
        safe_globals = {
            "__builtins__": {
                "print": print, "len": len, "range": range, 
                "int": int, "float": float, "str": str, "list": list, 
                "dict": dict, "set": set, "sorted": sorted, "sum": sum,
                "max": max, "min": min, "enumerate": enumerate, "zip": zip,
                "isinstance": isinstance, "type": type
            }
        }
        # Allow safe imports: json, math, re, datetime, collections, itertools
        for safe_mod in ["json", "math", "re", "datetime", "collections", "itertools"]:
            try:
                safe_globals[safe_mod] = importlib.import_module(safe_mod)
            except ImportError:
                pass
        
        if context:
            safe_globals.update(context)
        
        # 3. Capture output
        stdout_capture = io.StringIO()
        namespace = {}
        
        try:
            with contextlib.redirect_stdout(stdout_capture):
                exec(compile(code, "<jarvis_repl>", "exec"), safe_globals, namespace)
            
            output = stdout_capture.getvalue()[:self.MAX_OUTPUT]
            # Extract the last expression value if any
            result_var = namespace.get("result", namespace.get("output", None))
            
            return {
                "success": True,
                "stdout": output,
                "result": str(result_var) if result_var is not None else None,
                "variables_created": [k for k in namespace.keys() if not k.startswith("_")]
            }
        except Exception as e:
            return {"success": False, "error": type(e).__name__ + ": " + str(e), 
                    "stdout": stdout_capture.getvalue()}

executor = CodeExecutor()
