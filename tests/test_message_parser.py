"""Tests for message parser — @mention extraction and routing intent."""
import pytest
from engine.message_parser import parse_message, get_agent_by_name, build_cici_analysis_prompt
from engine.config import AGENT_CICI, AGENT_COCO, AGENT_SOSO

class TestParseMentions:
    def test_single_mention(self):
        msg = parse_message("@coco咪 fix dark mode")
        assert msg.is_direct is True
        assert msg.direct_target.name == "coco咪"

    def test_multiple_mentions_no_direct(self):
        msg = parse_message("@cici咪 @soso咪 what do you think")
        assert msg.is_direct is False
        assert len(msg.mentions) == 2

    def test_no_mention(self):
        msg = parse_message("add a refresh button")
        assert msg.is_direct is False
        assert msg.needs_cici_analysis is True

    def test_cleaned_content(self):
        msg = parse_message("@coco咪 write an API")
        assert "coco咪" not in msg.cleaned_content

    def test_mention_mid_sentence(self):
        msg = parse_message("can @coco咪 fix this bug")
        assert msg.is_direct is True
        assert msg.direct_target.name == "coco咪"

class TestAgentLookup:
    def test_get_agents(self):
        assert get_agent_by_name("cici咪") is AGENT_CICI
        assert get_agent_by_name("coco咪") is AGENT_COCO
        assert get_agent_by_name("soso咪") is AGENT_SOSO
        assert get_agent_by_name("unknown") is None

class TestAnalysisPrompt:
    def test_prompt_structure(self):
        prompt = build_cici_analysis_prompt("add refresh button")
        assert "add refresh button" in prompt
        assert "mcp__teamchat__create_task" in prompt
        assert "create_task" in prompt
        assert "depends_on" in prompt
