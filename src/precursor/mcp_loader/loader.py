"""
MCP server loader.

Reads `config/mcp_servers.yaml`, starts enabled MCP servers via mcp2py,
and returns both the loaded servers and a compiled allow_fn for tool filtering.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List

from precursor.config.loader import load_mcp_servers_yaml
from precursor.mcp_loader.utils import (
    apply_env,
    start_server,
    compile_allow_fn,
    load_yaml_override,
)


@dataclass
class LoadedServer:
    id: str
    client: Any  # mcp2py client (exposes .tools)


@dataclass
class MCPConfigBundle:
    servers: List[LoadedServer]
    allow_fn: Callable[[str], bool]  # e.g., allow("drive.search_files") -> True/False


def load_enabled_mcp_servers(config_path: str | None = None) -> MCPConfigBundle:
    """
    Load all enabled MCP servers + global allow/deny settings.

    Args:
        config_path: Optional explicit path to mcp_servers.yaml. If None,
                     uses PRECURSOR_MCP_SERVERS_FILE or the package default.

    Returns:
        MCPConfigBundle(servers=[LoadedServer], allow_fn=callable)
    """
    cfg = (
        load_mcp_servers_yaml()
        if config_path is None
        else load_yaml_override(config_path)
    )

    defaults: Dict[str, Any] = cfg.get("defaults") or {}
    servers_cfg: List[Dict[str, Any]] = cfg.get("servers") or []

    servers: List[LoadedServer] = []
    for spec in servers_cfg:
        enabled = spec.get("enabled", defaults.get("enabled", True))
        if not enabled:
            continue
        if "id" not in spec or "load" not in spec:
            continue

        apply_env(spec)
        client = start_server(spec)
        servers.append(LoadedServer(id=str(spec["id"]), client=client))

    allow_fn = compile_allow_fn(defaults)
    return MCPConfigBundle(servers=servers, allow_fn=allow_fn)