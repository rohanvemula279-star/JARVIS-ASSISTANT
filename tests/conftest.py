import pytest
from backend.tools.registry import ToolRegistry
from backend.memory.chroma_store import VectorMemory
from backend.memory.working_memory import WorkingMemory
from backend.context.context_service import LiveContextService

@pytest.fixture
def tool_registry():
    return ToolRegistry()

@pytest.fixture
def vector_memory():
    return VectorMemory(persist_dir="./data/test_chroma")

@pytest.fixture
def working_memory():
    return WorkingMemory()

@pytest.fixture
def context_service():
    return LiveContextService()
