"""Verification tests for cost-reduction controls (V-1 through V-5).

These tests verify the cost-reduction measures are correctly wired without
making any API calls. They import agent classes and inspect their configuration.
"""

import os
import sys
import importlib
from unittest.mock import patch, MagicMock

import pytest

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ---------------------------------------------------------------------------
# Helpers: mock ChatAnthropic so we can import agents without an API key
# ---------------------------------------------------------------------------

def _mock_chat_anthropic():
    """Return a mock ChatAnthropic class that records constructor kwargs."""
    instances = []

    class FakeChatAnthropic:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.model = kwargs.get("model", "")
            self.max_tokens = kwargs.get("max_tokens")
            self.temperature = kwargs.get("temperature", 0.0)
            instances.append(self)

        def bind_tools(self, tools, **kw):
            return self

        def with_structured_output(self, schema, **kw):
            return self

    return FakeChatAnthropic, instances


def _mock_create_react_agent(*args, **kwargs):
    """Mock create_react_agent that returns a dummy agent."""
    mock_agent = MagicMock()
    mock_agent.invoke.return_value = {"messages": [MagicMock(content="test")]}
    return mock_agent


# ---------------------------------------------------------------------------
# V-1: max_tokens is set on all ChatAnthropic instances
# ---------------------------------------------------------------------------

class TestV1MaxTokens:
    """V-1: Every ChatAnthropic instance has max_tokens set."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self):
        self.FakeChatAnthropic, self.instances = _mock_chat_anthropic()
        self.patches = [
            patch("langchain_anthropic.ChatAnthropic", self.FakeChatAnthropic),
            patch("langgraph.prebuilt.create_react_agent", _mock_create_react_agent),
        ]
        for p in self.patches:
            p.start()
        yield
        for p in self.patches:
            p.stop()
        # Clear module caches so re-import works
        for mod_name in list(sys.modules):
            if mod_name in ("config_agent", "procurement_agent", "prodet_agent",
                            "scheduling_agent", "grouping_optimizer"):
                del sys.modules[mod_name]

    def _import_and_instantiate(self, module_name, class_name):
        mod = importlib.import_module(module_name)
        cls = getattr(mod, class_name)
        return cls()

    def test_config_agent_max_tokens(self):
        self._import_and_instantiate("config_agent", "ConfigAgent")
        assert any(i.max_tokens is not None and i.max_tokens > 0 for i in self.instances)

    def test_procurement_agent_max_tokens(self):
        self._import_and_instantiate("procurement_agent", "ProcurementAgent")
        assert any(i.max_tokens is not None and i.max_tokens > 0 for i in self.instances)

    def test_prodet_agent_max_tokens(self):
        self._import_and_instantiate("prodet_agent", "ProDetAgent")
        assert any(i.max_tokens is not None and i.max_tokens > 0 for i in self.instances)

    def test_scheduling_agent_max_tokens(self):
        self._import_and_instantiate("scheduling_agent", "SchedulingAgent")
        assert any(i.max_tokens is not None and i.max_tokens > 0 for i in self.instances)

    def test_grouping_optimizer_max_tokens(self):
        self._import_and_instantiate("grouping_optimizer", "GroupingOptimizerAgent")
        assert any(i.max_tokens is not None and i.max_tokens > 0 for i in self.instances)


# ---------------------------------------------------------------------------
# V-2: Prompt caching metadata present on SystemMessage
# ---------------------------------------------------------------------------

class TestV2PromptCaching:
    """V-2: SystemMessage has cache_control in additional_kwargs."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self):
        self.FakeChatAnthropic, self.instances = _mock_chat_anthropic()
        self.patches = [
            patch("langchain_anthropic.ChatAnthropic", self.FakeChatAnthropic),
            patch("langgraph.prebuilt.create_react_agent", _mock_create_react_agent),
        ]
        for p in self.patches:
            p.start()
        yield
        for p in self.patches:
            p.stop()
        for mod_name in list(sys.modules):
            if mod_name in ("config_agent", "procurement_agent", "prodet_agent",
                            "scheduling_agent", "grouping_optimizer"):
                del sys.modules[mod_name]

    def _get_system_message(self, module_name, class_name):
        mod = importlib.import_module(module_name)
        cls = getattr(mod, class_name)
        agent = cls()
        return agent.system_message

    @pytest.mark.parametrize("module_name,class_name", [
        ("config_agent", "ConfigAgent"),
        ("procurement_agent", "ProcurementAgent"),
        ("prodet_agent", "ProDetAgent"),
        ("scheduling_agent", "SchedulingAgent"),
        ("grouping_optimizer", "GroupingOptimizerAgent"),
    ])
    def test_cache_control_present(self, module_name, class_name):
        sm = self._get_system_message(module_name, class_name)
        assert hasattr(sm, "additional_kwargs"), f"{class_name} SystemMessage missing additional_kwargs"
        cc = sm.additional_kwargs.get("cache_control")
        assert cc == {"type": "ephemeral"}, f"{class_name} cache_control = {cc}, expected ephemeral"


# ---------------------------------------------------------------------------
# V-3: TokenCounterCallback captures usage data
# ---------------------------------------------------------------------------

class TestV3TokenLogger:
    """V-3: TokenCounterCallback correctly extracts usage from mock LLMResult."""

    def test_usage_from_generations(self):
        from utils.token_logger import TokenCounterCallback
        cb = TokenCounterCallback(agent_name="test")

        mock_msg = MagicMock()
        mock_msg.usage_metadata = {
            "input_tokens": 500,
            "output_tokens": 100,
            "input_token_details": {"cache_read": 200, "cache_creation": 0},
        }
        mock_gen = MagicMock()
        mock_gen.message = mock_msg

        mock_result = MagicMock()
        mock_result.generations = [[mock_gen]]
        mock_result.llm_output = None

        cb.on_llm_end(mock_result)

        assert cb.total_input_tokens == 500
        assert cb.total_output_tokens == 100
        assert cb.cache_read_tokens == 200
        assert cb.call_count == 1
        assert cb.total_cost > 0

    def test_usage_from_llm_output_fallback(self):
        from utils.token_logger import TokenCounterCallback
        cb = TokenCounterCallback(agent_name="test")

        mock_result = MagicMock()
        mock_result.generations = [[]]
        mock_result.llm_output = {
            "usage": {"input_tokens": 300, "output_tokens": 50},
        }

        cb.on_llm_end(mock_result)

        assert cb.total_input_tokens == 300
        assert cb.total_output_tokens == 50
        assert cb.call_count == 1

    def test_per_agent_tracking(self):
        from utils.token_logger import TokenCounterCallback
        cb = TokenCounterCallback()
        cb.set_current_agent("config", model="claude-sonnet-4-6")

        mock_msg = MagicMock()
        mock_msg.usage_metadata = {
            "input_tokens": 100, "output_tokens": 50,
            "input_token_details": {},
        }
        mock_gen = MagicMock()
        mock_gen.message = mock_msg
        mock_result = MagicMock()
        mock_result.generations = [[mock_gen]]
        mock_result.llm_output = None

        cb.on_llm_end(mock_result)

        assert "config" in cb.agent_stats
        assert cb.agent_stats["config"].call_count == 1
        assert cb.agent_stats["config"].input_tokens == 100
        assert cb.agent_stats["config"].model == "claude-sonnet-4-6"

    def test_format_receipt(self):
        from utils.token_logger import TokenCounterCallback
        cb = TokenCounterCallback()
        cb.set_current_agent("config", model="claude-sonnet-4-6")
        cb.call_count = 1
        cb.total_input_tokens = 100
        cb.total_output_tokens = 50
        cb.agent_stats["config"].call_count = 1
        cb.agent_stats["config"].input_tokens = 100
        cb.agent_stats["config"].output_tokens = 50

        receipt = cb.format_receipt()
        assert "SESSION COST RECEIPT" in receipt
        assert "config" in receipt
        assert "Sonnet 4.6" in receipt


# ---------------------------------------------------------------------------
# V-4: Config agent prompt size and tool lists
# ---------------------------------------------------------------------------

class TestV4ConfigAgent:
    """V-4: Config agent prompt < 2500 est. tokens, correct tool list."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self):
        self.FakeChatAnthropic, self.instances = _mock_chat_anthropic()
        self.patches = [
            patch("langchain_anthropic.ChatAnthropic", self.FakeChatAnthropic),
            patch("langgraph.prebuilt.create_react_agent", _mock_create_react_agent),
        ]
        for p in self.patches:
            p.start()
        yield
        for p in self.patches:
            p.stop()
        for mod_name in list(sys.modules):
            if mod_name in ("config_agent",):
                del sys.modules[mod_name]

    def test_prompt_size_under_2500_tokens(self):
        mod = importlib.import_module("config_agent")
        agent = mod.ConfigAgent()
        # Rough estimate: 1 token ≈ 4 chars for English text
        est_tokens = len(agent.system_message.content) / 4
        assert est_tokens < 2500, f"Config prompt est. {est_tokens:.0f} tokens, expected < 2500"

    def test_tool_names(self):
        mod = importlib.import_module("config_agent")
        agent = mod.ConfigAgent()
        tool_names = {t.name for t in agent.tools}
        expected = {"load_config_summary", "update_config", "set_floor_groups", "get_reference_material"}
        assert tool_names == expected, f"Tool names: {tool_names}, expected: {expected}"

    def test_prodet_agent_no_config_tools(self):
        """Config tools should NOT be in ProDet agent's tool list (SF-3)."""
        with patch("langchain_anthropic.ChatAnthropic", self.FakeChatAnthropic), \
             patch("langgraph.prebuilt.create_react_agent", _mock_create_react_agent):
            if "prodet_agent" in sys.modules:
                del sys.modules["prodet_agent"]
            mod = importlib.import_module("prodet_agent")
            agent = mod.ProDetAgent()
            tool_names = {t.name for t in agent.tools}
            assert "load_config_summary" not in tool_names
            assert "update_config" not in tool_names


# ---------------------------------------------------------------------------
# V-5: max_iterations caps
# ---------------------------------------------------------------------------

class TestV5MaxIterations:
    """V-5: Agents have correct max_iterations defaults."""

    def test_prodet_max_iterations_20(self):
        import inspect
        from unittest.mock import patch as p
        FakeChatAnthropic, _ = _mock_chat_anthropic()
        with p("langchain_anthropic.ChatAnthropic", FakeChatAnthropic), \
             p("langgraph.prebuilt.create_react_agent", _mock_create_react_agent):
            if "prodet_agent" in sys.modules:
                del sys.modules["prodet_agent"]
            mod = importlib.import_module("prodet_agent")
            sig = inspect.signature(mod.ProDetAgent.run)
            default = sig.parameters["max_iterations"].default
            assert default <= 20, f"prodet max_iterations={default}, expected ≤20"

    def test_grouping_max_iterations_20(self):
        import inspect
        from unittest.mock import patch as p
        FakeChatAnthropic, _ = _mock_chat_anthropic()
        with p("langchain_anthropic.ChatAnthropic", FakeChatAnthropic), \
             p("langgraph.prebuilt.create_react_agent", _mock_create_react_agent):
            if "grouping_optimizer" in sys.modules:
                del sys.modules["grouping_optimizer"]
            mod = importlib.import_module("grouping_optimizer")
            sig = inspect.signature(mod.GroupingOptimizerAgent.run)
            default = sig.parameters["max_iterations"].default
            assert default <= 20, f"grouping max_iterations={default}, expected ≤20"

    def test_config_max_iterations_15(self):
        import inspect
        from unittest.mock import patch as p
        FakeChatAnthropic, _ = _mock_chat_anthropic()
        with p("langchain_anthropic.ChatAnthropic", FakeChatAnthropic), \
             p("langgraph.prebuilt.create_react_agent", _mock_create_react_agent):
            if "config_agent" in sys.modules:
                del sys.modules["config_agent"]
            mod = importlib.import_module("config_agent")
            sig = inspect.signature(mod.ConfigAgent.run)
            default = sig.parameters["max_iterations"].default
            assert default <= 15, f"config max_iterations={default}, expected ≤15"

    def test_scheduling_max_iterations_15(self):
        import inspect
        from unittest.mock import patch as p
        FakeChatAnthropic, _ = _mock_chat_anthropic()
        with p("langchain_anthropic.ChatAnthropic", FakeChatAnthropic), \
             p("langgraph.prebuilt.create_react_agent", _mock_create_react_agent):
            if "scheduling_agent" in sys.modules:
                del sys.modules["scheduling_agent"]
            mod = importlib.import_module("scheduling_agent")
            sig = inspect.signature(mod.SchedulingAgent.run)
            default = sig.parameters["max_iterations"].default
            assert default <= 15, f"scheduling max_iterations={default}, expected ≤15"

    def test_procurement_max_iterations_15(self):
        import inspect
        from unittest.mock import patch as p
        FakeChatAnthropic, _ = _mock_chat_anthropic()
        with p("langchain_anthropic.ChatAnthropic", FakeChatAnthropic), \
             p("langgraph.prebuilt.create_react_agent", _mock_create_react_agent):
            if "procurement_agent" in sys.modules:
                del sys.modules["procurement_agent"]
            mod = importlib.import_module("procurement_agent")
            sig = inspect.signature(mod.ProcurementAgent.run)
            default = sig.parameters["max_iterations"].default
            assert default <= 15, f"procurement max_iterations={default}, expected ≤15"
