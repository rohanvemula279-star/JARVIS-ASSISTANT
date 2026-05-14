class StrategyStore:
    def __init__(self):
        self.strategies = []
        
    def save_success(self, task_type: str, agent_profile: str, tools_used: list, strategy_description: str, score: float):
        self.strategies.append({
            "task_type": task_type,
            "agent_profile": agent_profile,
            "tools_used": tools_used,
            "strategy_description": strategy_description,
            "score": score,
            "status": "PASS"
        })
        
    def save_failure(self, task_type: str, failed_strategy: str, why_it_failed: str):
        self.strategies.append({
            "task_type": task_type,
            "failed_strategy": failed_strategy,
            "why_it_failed": why_it_failed,
            "status": "FAIL"
        })
        
    def get_strategy_hint(self, task_type: str) -> str:
        hint = ""
        for s in reversed(self.strategies):
            if s["task_type"] == task_type:
                if s["status"] == "PASS":
                    hint += f"Successful strategy: {s['strategy_description']}\n"
                elif s["status"] == "FAIL":
                    hint += f"Warning, failed strategy: {s['failed_strategy']} because {s['why_it_failed']}\n"
        return hint

strategy_store = StrategyStore()
