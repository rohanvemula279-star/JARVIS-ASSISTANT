"""
Tests for the Working Memory system.
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestWorkingMemory:
    """Tests for the in-memory session store."""

    @pytest.mark.asyncio
    async def test_push_and_get_history(self, working_memory):
        """Pushing turns and retrieving history works."""
        await working_memory.push_turn("session1", "user", "hello")
        await working_memory.push_turn("session1", "assistant", "hi there")

        history = await working_memory.get_history("session1")
        assert len(history) == 2
        assert history[0]["role"] == "user"
        assert history[0]["content"] == "hello"
        assert history[1]["role"] == "assistant"

    @pytest.mark.asyncio
    async def test_history_trimming(self, working_memory):
        """History is trimmed to max_turns."""
        for i in range(15):
            await working_memory.push_turn("session1", "user", f"msg {i}")

        history = await working_memory.get_history("session1")
        assert len(history) == 10  # max_turns is 10 in fixture

    @pytest.mark.asyncio
    async def test_separate_sessions(self, working_memory):
        """Different sessions have independent histories."""
        await working_memory.push_turn("s1", "user", "session 1")
        await working_memory.push_turn("s2", "user", "session 2")

        h1 = await working_memory.get_history("s1")
        h2 = await working_memory.get_history("s2")
        assert len(h1) == 1
        assert len(h2) == 1
        assert h1[0]["content"] == "session 1"
        assert h2[0]["content"] == "session 2"

    @pytest.mark.asyncio
    async def test_scratchpad(self, working_memory):
        """Scratchpad set and get works."""
        await working_memory.set_scratchpad("session1", {"step": 1, "data": "test"})
        pad = await working_memory.get_scratchpad("session1")
        assert pad["step"] == 1
        assert pad["data"] == "test"

    @pytest.mark.asyncio
    async def test_empty_scratchpad(self, working_memory):
        """Empty scratchpad returns empty dict."""
        pad = await working_memory.get_scratchpad("nonexistent")
        assert pad == {}

    @pytest.mark.asyncio
    async def test_clear_session(self, working_memory):
        """Clearing a session removes all data."""
        await working_memory.push_turn("session1", "user", "hello")
        await working_memory.set_scratchpad("session1", {"key": "val"})

        await working_memory.clear_session("session1")

        history = await working_memory.get_history("session1")
        pad = await working_memory.get_scratchpad("session1")
        assert len(history) == 0
        assert pad == {}

    def test_active_sessions_count(self, working_memory):
        """Active sessions count is correct."""
        assert working_memory.active_sessions == 0
