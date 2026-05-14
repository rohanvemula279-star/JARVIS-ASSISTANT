"""
Tests for Intent Router
"""

import pytest
import asyncio
from backend.agents.router import IntentRouter
from backend.agents import Intent


class TestIntentRouter:
    """Test intent classification"""

    @pytest.fixture
    def router(self):
        return IntentRouter()

    @pytest.mark.asyncio
    async def test_app_launch_direct(self, router):
        """Test explicit app launch"""
        result = await router.classify("open chrome")
        assert result.intent == Intent.LAUNCH_APP

    @pytest.mark.asyncio
    async def test_app_launch_not_misclassified(self, router):
        """Critical: 'How do I open a jar?' must NOT be classified as launch_app"""
        result = await router.classify("How do I open a jar of pickles?")
        assert result.intent == Intent.CONVERSATION

    @pytest.mark.asyncio
    async def test_web_search(self, router):
        """Test search intent detection"""
        result = await router.classify("search for latest AI news")
        assert result.intent in [Intent.WEB_SEARCH, Intent.BROWSER_AUTOMATION]

    @pytest.mark.asyncio
    async def test_multi_step_detection(self, router):
        """Test complex task detection"""
        result = await router.classify(
            "Find the latest Python release notes, summarize them, and save to a file"
        )
        assert result.requires_planning == True

    @pytest.mark.asyncio
    async def test_memory_recall(self, router):
        """Test memory recall detection"""
        result = await router.classify("what did we talk about yesterday?")
        assert result.intent == Intent.MEMORY_RECALL

    @pytest.mark.asyncio
    async def test_system_query(self, router):
        """Test system query detection"""
        result = await router.classify("how much memory is being used?")
        assert result.intent == Intent.SYSTEM_QUERY

    @pytest.mark.asyncio
    async def test_conversation(self, router):
        """Test general conversation"""
        result = await router.classify("hello, how are you?")
        assert result.intent == Intent.CONVERSATION