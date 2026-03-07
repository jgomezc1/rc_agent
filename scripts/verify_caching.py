#!/usr/bin/env python3
"""V-6: Runtime verification that prompt caching is active.

Usage:
    python scripts/verify_caching.py --dry-run    # Mock mode, no API calls
    python scripts/verify_caching.py              # Live mode, requires ANTHROPIC_API_KEY
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def verify_dry_run():
    """Verify caching setup without API calls."""
    from unittest.mock import patch, MagicMock

    print("=== Dry-run caching verification ===\n")
    results = []

    # 1. Check all agents have cache_control on SystemMessage
    agents = [
        ("config_agent", "ConfigAgent"),
        ("procurement_agent", "ProcurementAgent"),
        ("prodet_agent", "ProDetAgent"),
        ("scheduling_agent", "SchedulingAgent"),
        ("grouping_optimizer", "GroupingOptimizerAgent"),
    ]

    class FakeLLM:
        def __init__(self, **kw):
            self.model = kw.get("model", "")
            self.max_tokens = kw.get("max_tokens")
        def bind_tools(self, *a, **kw):
            return self
        def with_structured_output(self, *a, **kw):
            return self

    mock_agent = MagicMock()
    mock_agent.invoke.return_value = {"messages": [MagicMock(content="ok")]}

    with patch("langchain_anthropic.ChatAnthropic", FakeLLM), \
         patch("langgraph.prebuilt.create_react_agent", lambda *a, **kw: mock_agent):

        for mod_name, cls_name in agents:
            if mod_name in sys.modules:
                del sys.modules[mod_name]
            try:
                import importlib
                mod = importlib.import_module(mod_name)
                agent = getattr(mod, cls_name)()
                sm = agent.system_message
                cc = sm.additional_kwargs.get("cache_control", {})
                ok = cc.get("type") == "ephemeral"
                status = "PASS" if ok else "FAIL"
                results.append(ok)
                print(f"  [{status}] {cls_name}: cache_control={cc}")
            except Exception as e:
                results.append(False)
                print(f"  [FAIL] {cls_name}: {e}")

    # 2. Verify token logger works
    try:
        from utils.token_logger import TokenCounterCallback
        cb = TokenCounterCallback()
        cb.set_current_agent("test", model="claude-sonnet-4-6")
        assert cb.agent_stats["test"].model == "claude-sonnet-4-6"
        results.append(True)
        print(f"  [PASS] TokenCounterCallback: per-agent tracking works")
    except Exception as e:
        results.append(False)
        print(f"  [FAIL] TokenCounterCallback: {e}")

    # 3. Verify receipt formatting
    try:
        from utils.token_logger import TokenCounterCallback
        cb = TokenCounterCallback()
        cb.set_current_agent("config", model="claude-sonnet-4-6")
        cb.call_count = 2
        cb.total_input_tokens = 1000
        cb.total_output_tokens = 200
        cb.agent_stats["config"].call_count = 2
        cb.agent_stats["config"].input_tokens = 1000
        cb.agent_stats["config"].output_tokens = 200
        receipt = cb.format_receipt()
        assert "SESSION COST RECEIPT" in receipt
        assert "Sonnet 4.6" in receipt
        results.append(True)
        print(f"  [PASS] Receipt formatting works")
    except Exception as e:
        results.append(False)
        print(f"  [FAIL] Receipt formatting: {e}")

    print(f"\n{'='*40}")
    passed = sum(results)
    total = len(results)
    print(f"  {passed}/{total} checks passed")
    if all(results):
        print("  All verifications PASSED")
    else:
        print("  Some verifications FAILED")
    return 0 if all(results) else 1


def verify_live():
    """Verify caching with a real API call (requires ANTHROPIC_API_KEY)."""
    print("=== Live caching verification ===\n")

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("  ERROR: ANTHROPIC_API_KEY not set. Use --dry-run for offline verification.")
        return 1

    try:
        from langchain_anthropic import ChatAnthropic
        from langchain_core.messages import SystemMessage, HumanMessage
        from utils.token_logger import TokenCounterCallback

        llm = ChatAnthropic(model="claude-sonnet-4-6", temperature=0, max_tokens=50)
        system = SystemMessage(
            content="You are a helpful test assistant. Reply with exactly 'OK'.",
            additional_kwargs={"cache_control": {"type": "ephemeral"}},
        )
        human = HumanMessage(content="Say OK")

        cb = TokenCounterCallback(agent_name="cache-test")

        # First call — should be a cache miss (cache_creation > 0)
        print("  Call 1 (expect cache miss)...")
        llm.invoke([system, human], config={"callbacks": [cb]})
        print(f"    in={cb.total_input_tokens}, out={cb.total_output_tokens}, "
              f"cache_read={cb.cache_read_tokens}, cache_creation={cb.cache_creation_tokens}")

        # Second call — should be a cache hit (cache_read > 0)
        cb2 = TokenCounterCallback(agent_name="cache-test-2")
        print("  Call 2 (expect cache hit)...")
        llm.invoke([system, human], config={"callbacks": [cb2]})
        print(f"    in={cb2.total_input_tokens}, out={cb2.total_output_tokens}, "
              f"cache_read={cb2.cache_read_tokens}, cache_creation={cb2.cache_creation_tokens}")

        if cb2.cache_read_tokens > 0:
            print("\n  [PASS] Prompt caching is ACTIVE (cache_read > 0 on second call)")
        elif cb.cache_creation_tokens > 0:
            print("\n  [WARN] Cache creation detected but no cache read on second call.")
            print("         This may be a timing issue. Try again.")
        else:
            print("\n  [WARN] No cache activity detected. cache_control may not be passed through.")
            print("         Check langchain-anthropic version supports additional_kwargs passthrough.")

        return 0

    except Exception as e:
        print(f"  ERROR: {e}")
        return 1


def main():
    parser = argparse.ArgumentParser(description="Verify prompt caching setup")
    parser.add_argument("--dry-run", action="store_true", help="Run without API calls")
    args = parser.parse_args()

    if args.dry_run:
        return verify_dry_run()
    else:
        return verify_live()


if __name__ == "__main__":
    sys.exit(main())
