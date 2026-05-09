"""
GeoSupply MCP Server — FastMCP entry point.

Exposes the GeoSupply swarm as an MCP server over stdio transport.
Compatible with Claude Code, Claude Desktop, and any MCP-aware client.

Start:
    geosupply-mcp                        # via console script
    python -m geosupply.mcp.server       # direct invocation
    uvx mcp run geosupply-mcp            # via uvx

Claude Code integration (.claude/mcp.json):
    {
      "mcpServers": {
        "geosupply": {
          "command": "geosupply-mcp",
          "env": {
            "ANTHROPIC_API_KEY": "${ANTHROPIC_API_KEY}",
            "SQLITE_PATH": "./geosupply.db"
          }
        }
      }
    }
"""
from __future__ import annotations

import logging
import sys

logger = logging.getLogger(__name__)

# ── Build the FastMCP application ─────────────────────────────────────────────


def _build_mcp():
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:
        raise SystemExit(
            "FastMCP not installed. Run: pip install 'mcp>=1.0.0'"
        ) from exc

    mcp = FastMCP(
        name="GeoSupply AI",
        instructions=(
            "GeoSupply AI is an India-centric geopolitical supply-chain intelligence platform. "
            "It provides tools for: NLP analysis of news and reports, entity sanctions screening, "
            "supply-chain risk assessment, knowledge graph queries, brief generation, "
            "and full swarm orchestration across 14 supervisors and 19 workers.\n\n"
            "Key tools:\n"
            "- analyze_text: NLP pipeline (sentiment, NER, claims)\n"
            "- screen_entity: Sanctions + supplier risk\n"
            "- run_supply_brief: Full 10-step intelligence DAG\n"
            "- query_knowledge_graph: Entity relationship mapping\n"
            "- ingest_and_analyze: Fetch + analyse a news URL\n\n"
            "Key resources:\n"
            "- geosupply://health: System health\n"
            "- geosupply://config: Runtime configuration\n"
            "- geosupply://supervisors: Supervisor registry\n"
            "- geosupply://workers: Worker registry with capabilities\n\n"
            "Key prompts:\n"
            "- supply_chain_brief: Full brief generation workflow\n"
            "- risk_assessment: Structured entity risk workflow\n"
            "- sanctions_check: Compliance-grade screening workflow"
        ),
    )

    # Register tools, resources, and prompts
    from geosupply.mcp.tools import register_tools
    from geosupply.mcp.resources import register_resources
    from geosupply.mcp.prompts import register_prompts

    register_tools(mcp)
    register_resources(mcp)
    register_prompts(mcp)

    return mcp


mcp = _build_mcp()


def main() -> None:
    """Console script entry point — runs the MCP server over stdio."""
    import os

    # Configure logging to stderr (stdout is reserved for MCP protocol messages)
    logging.basicConfig(
        stream=sys.stderr,
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    # Warn about missing optional services
    optional = {
        "ANTHROPIC_API_KEY": "Tier-2/3 LLM inference will use heuristic fallbacks",
        "NEO4J_URI": "Knowledge graph queries will return stub data",
        "SUPABASE_URL": "Task persistence will be in-memory only",
    }
    for key, warning in optional.items():
        if not os.getenv(key):
            logger.warning("Environment variable %s not set — %s", key, warning)

    # Bootstrap swarm on startup (blocks until complete)
    logger.info("GeoSupply MCP: bootstrapping swarm...")
    from geosupply.mcp._context import get_swarm, get_budget
    get_swarm()
    get_budget()
    logger.info("GeoSupply MCP: swarm ready — starting stdio transport")

    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
