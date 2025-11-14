"""
Toolset builder.

Builds final DSPy tool list from:
  1) Config-loaded MCP servers (via mcp2py), tools namespaced as '{server_id}.{fn.__name__}'
  2) Always-on core tools (namespaced as 'core.*'), e.g. scratchpad + store_artifact
Filters everything through the allow_fn compiled from config/mcp_servers.yaml defaults.
"""

from __future__ import annotations
from typing import Any, Callable, List, Tuple
import logging
import inspect

import dspy

# Core environment tools (direct wrappers; docstrings are important for DSPy)
from precursor.core_tools.artifacts import store_artifact
from precursor.scratchpad.scratchpad_tools import (
    append_to_scratchpad,
    remove_from_scratchpad,
    edit_in_scratchpad,
    get_refreshed_scratchpad,
)

def _namespace_tool(server_id: str, fn: Any) -> Tuple[str, Any]:
    name = getattr(fn, "__name__", "tool").strip() or "tool"
    return f"{server_id}.{name}", fn

def _with_logging(ns_name: str, fn: Any) -> Any:
    """
    Wrap a callable with logging while preserving docstring, name, and signature.
    We attach the original signature to __signature__ so that agent tooling
    (which introspects parameter names and docstrings) sees the original API.
    """
    logger = logging.getLogger("precursor.tools")
    sig = inspect.signature(fn)

    if inspect.iscoroutinefunction(fn):
        async def _wrapped(*args, **kwargs):
            logger.info("tool_call start: %s args=%r kwargs=%r", ns_name, args, kwargs)
            try:
                result = await fn(*args, **kwargs)
            except Exception:
                logger.exception("tool_call error: %s", ns_name)
                raise
            else:
                logger.info("tool_call end: %s result=%r", ns_name, result)
                return result
    else:
        def _wrapped(*args, **kwargs):
            logger.info("tool_call start: %s args=%r kwargs=%r", ns_name, args, kwargs)
            try:
                result = fn(*args, **kwargs)
            except Exception:
                logger.exception("tool_call error: %s", ns_name)
                raise
            else:
                logger.info("tool_call end: %s result=%r", ns_name, result)
                return result

    # Preserve metadata critical to DSPy/tool callers
    _wrapped.__name__ = getattr(fn, "__name__", "tool")
    _wrapped.__qualname__ = getattr(fn, "__qualname__", _wrapped.__name__)
    _wrapped.__doc__ = getattr(fn, "__doc__", None)
    _wrapped.__signature__ = sig  # type: ignore[attr-defined]
    _wrapped.__module__ = getattr(fn, "__module__", _wrapped.__module__)

    return _wrapped

def _wrap_as_dspy_tool(ns_name: str, fn: Any) -> dspy.Tool:
    return dspy.Tool(_with_logging(ns_name, fn))

def build_toolset(servers_bundle) -> List[dspy.Tool]:
    """
    Parameters
    ----------
    servers_bundle: MCPConfigBundle
        .servers = [LoadedServer(id, client)], where client.tools is iterable
        .allow_fn = Callable[[str], bool] over namespaced tool names

    Returns
    -------
    List[dspy.Tool]
    """
    allow_fn: Callable[[str], bool] = servers_bundle.allow_fn
    tools: List[dspy.Tool] = []

    # 1) MCP tools (namespaced as '{id}.{tool_name}')
    for s in servers_bundle.servers:
        for fn in getattr(s.client, "tools", []):
            ns_name, real_fn = _namespace_tool(s.id, fn)
            if allow_fn(ns_name):
                tools.append(_wrap_as_dspy_tool(ns_name, real_fn))

    # 2) Core tools (namespaced as 'core.*')
    core_tool_fns = [
        store_artifact,            # record artifacts (short summary visible; long_summary in metadata)
        append_to_scratchpad,      # add notes/resources/objectives/etc.
        remove_from_scratchpad,    # remove by display index
        edit_in_scratchpad,        # edit by display index
        get_refreshed_scratchpad,  # render current scratchpad
    ]
    for core_fn in core_tool_fns:
        ns = f"core.{getattr(core_fn, '__name__', 'tool')}"
        if allow_fn(ns):
            tools.append(_wrap_as_dspy_tool(ns, core_fn))

    return tools