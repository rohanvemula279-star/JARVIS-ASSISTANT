import asyncio
from backend.agents.orchestrator import ReActOrchestrator
from backend.tools.registry import registry
from backend.memory.chroma_store import VectorMemory
from backend.memory.working_memory import WorkingMemory
from backend.context.context_service import LiveContextService
import backend.tools.system_tools
import backend.tools.search_tools
import backend.tools.browser_tools
import backend.tools.vision_tools
import backend.tools.computer_use
import backend.tools.input_controller
import backend.tools.code_tools

async def run_test():
    print("Initializing services...")
    vec_mem = VectorMemory("data/chroma_db")
    work_mem = WorkingMemory()
    ctx = LiveContextService()
    
    orchestrator = ReActOrchestrator(
        tool_registry=registry,
        vector_memory=vec_mem,
        working_memory=work_mem,
        context_service=ctx
    )
    
    prompt = "Research the top 3 Python web frameworks in 2025, write a 200-word comparison, save it as ~/Desktop/frameworks.md, then open it in VS Code."
    
    print(f"\nExecuting prompt: {prompt}\n")
    result = await orchestrator.process(prompt)
    
    print("\n--- STEPS ---")
    for step in result.steps:
        if step.type == 'action':
            print(f"🔧 ACTION: {step.tool_name}({step.tool_input})")
        elif step.type == 'observation':
            print(f"👁️ OBSERVE: {step.content[:100]}...")
        elif step.type == 'thought':
            print(f"🤔 THOUGHT: {step.content}")
        elif step.type == 'error':
            print(f"❌ ERROR: {step.content}")
    
    print("\n--- FINAL ANSWER ---")
    print(result.result)

if __name__ == "__main__":
    asyncio.run(run_test())
