import asyncio
from backend.agents.task_graph import TaskGraph, Task, TaskStatus

class TaskExecutionEngine:
    def __init__(self, sub_orchestrator):
        self.sub_orchestrator = sub_orchestrator
        
    async def execute_graph(self, graph: TaskGraph, session_id: str) -> dict:
        """Execute task graph respecting dependencies, parallel when possible."""
        
        while not graph.is_complete():
            ready = graph.get_ready_tasks()
            if not ready:
                # Check for deadlock
                pending = [t for t in graph.tasks.values() 
                           if t.status == TaskStatus.PENDING]
                if pending:
                    raise RuntimeError(f"Deadlock: {len(pending)} tasks unresolvable")
                break
            
            # Run ready tasks in parallel using asyncio.gather
            await asyncio.gather(*[
                self._execute_task(task, graph, session_id) 
                for task in ready
            ])
        
        return graph.summary()
    
    async def _execute_task(self, task: Task, graph: TaskGraph, session_id: str):
        task.status = TaskStatus.RUNNING
        
        # Build context from completed dependencies
        dep_results = {
            dep_id: graph.tasks[dep_id].result 
            for dep_id in task.dependencies 
            if graph.tasks[dep_id].result
        }
        
        try:
            result_obj = await self.sub_orchestrator.process(
                prompt=f"Context: {dep_results}\nTask: {task.goal}",
                session_id=session_id
            )
            task.result = {"answer": result_obj.result}
            task.status = TaskStatus.COMPLETE
        except Exception as e:
            task.error = str(e)
            task.status = TaskStatus.FAILED
