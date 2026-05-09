"""
GeoSupply MCP — Prompt templates.

3 reusable prompt templates for common intelligence workflows:

  supply_chain_brief  — Full brief generation for a topic/region
  risk_assessment     — Structured risk assessment for an entity or event
  sanctions_check     — Sanctions screening workflow with evidence summary
"""
from __future__ import annotations

from typing import Any


def register_prompts(mcp_instance: Any) -> None:

    # ── 1. supply_chain_brief ─────────────────────────────────────────────────

    @mcp_instance.prompt()
    def supply_chain_brief(
        topic: str,
        region: str = "India",
        time_horizon: str = "30 days",
    ) -> list[dict]:
        """Generate a structured supply-chain intelligence brief.

        Args:
            topic:        The supply chain topic, commodity, or event.
                          E.g. "wheat export restrictions", "rare earth mining".
            region:       Geographic focus (default: India).
            time_horizon: Forecast window (e.g. "30 days", "Q3 2025").

        Returns:
            A multi-turn prompt sequence ready for an MCP client to execute.
        """
        return [
            {
                "role": "user",
                "content": {
                    "type": "text",
                    "text": (
                        f"You are a geopolitical supply-chain analyst specialising in {region}.\n\n"
                        f"Generate a comprehensive intelligence brief on: **{topic}**\n\n"
                        f"Time horizon: {time_horizon}\n\n"
                        "Structure your brief as:\n"
                        "1. **Executive Summary** (3 sentences max)\n"
                        "2. **Key Entities** (companies, governments, ports involved)\n"
                        "3. **Verified Claims** (use the `analyze_text` and `screen_entity` tools)\n"
                        "4. **Risk Assessment** (supply disruption probability: LOW / MEDIUM / HIGH / CRITICAL)\n"
                        "5. **Alternative Sourcing Options** (if disruption risk > MEDIUM)\n"
                        "6. **Confidence Score** (0.0–1.0) and data gaps\n\n"
                        "Use the GeoSupply MCP tools to gather live data before writing the brief:\n"
                        "- `analyze_text` for NLP signal extraction\n"
                        "- `screen_entity` for sanctions and supplier risk\n"
                        "- `query_knowledge_graph` for relationship mapping\n"
                        "- `run_supply_brief` for the full automated DAG"
                    ),
                },
            }
        ]

    # ── 2. risk_assessment ────────────────────────────────────────────────────

    @mcp_instance.prompt()
    def risk_assessment(
        entity: str,
        entity_type: str = "supplier",
        context: str = "",
    ) -> list[dict]:
        """Structured risk assessment for a supply chain entity or event.

        Args:
            entity:      Name of the entity, company, country, or event.
            entity_type: supplier | country | port | vessel | commodity | event
            context:     Additional background context (optional).

        Returns:
            Prompt sequence that guides systematic risk evaluation.
        """
        context_block = f"\n\nAdditional context:\n{context}" if context else ""
        return [
            {
                "role": "user",
                "content": {
                    "type": "text",
                    "text": (
                        f"Conduct a structured supply-chain risk assessment for:\n\n"
                        f"**Entity:** {entity}\n"
                        f"**Type:** {entity_type}{context_block}\n\n"
                        "Follow this methodology:\n\n"
                        "**Step 1 — Sanctions & Compliance**\n"
                        "→ Use `screen_entity` to check OFAC, EU, and UN sanctions lists.\n\n"
                        "**Step 2 — Network Analysis**\n"
                        "→ Use `query_knowledge_graph` to map ownership, subsidiaries, and trade routes.\n\n"
                        "**Step 3 — News & Sentiment**\n"
                        "→ Use `analyze_text` on recent news about this entity.\n\n"
                        "**Step 4 — Risk Scoring**\n"
                        "Produce a risk matrix:\n"
                        "| Dimension | Score (0–10) | Evidence |\n"
                        "|---|---|---|\n"
                        "| Sanctions exposure | | |\n"
                        "| Financial stability | | |\n"
                        "| Geopolitical risk | | |\n"
                        "| Supply concentration | | |\n"
                        "| Operational resilience | | |\n\n"
                        "**Step 5 — Recommendation**\n"
                        "APPROVE / CONDITIONAL APPROVE / REJECT with justification.\n\n"
                        "Be explicit about data gaps and confidence limitations."
                    ),
                },
            }
        ]

    # ── 3. sanctions_check ────────────────────────────────────────────────────

    @mcp_instance.prompt()
    def sanctions_check(
        entity_name: str,
        transaction_value_usd: float = 0.0,
        counterparty_country: str = "",
    ) -> list[dict]:
        """Compliance-grade sanctions screening workflow.

        Args:
            entity_name:           Full legal name of the entity to screen.
            transaction_value_usd: Value of the transaction in USD (0 = unknown).
            counterparty_country:  Country of the counterparty (ISO-2 code or name).

        Returns:
            Step-by-step sanctions screening prompt with evidence collection.
        """
        txn_block = (
            f"\n**Transaction value:** ${transaction_value_usd:,.0f} USD"
            if transaction_value_usd > 0 else ""
        )
        country_block = (
            f"\n**Counterparty country:** {counterparty_country}"
            if counterparty_country else ""
        )
        return [
            {
                "role": "user",
                "content": {
                    "type": "text",
                    "text": (
                        f"Perform a compliance-grade sanctions screening for:\n\n"
                        f"**Entity:** {entity_name}{txn_block}{country_block}\n\n"
                        "Screening checklist:\n\n"
                        "1. **Primary screen** — `screen_entity` against OFAC SDN, EU Consolidated, UN 1267\n"
                        "2. **Ownership screen** — `query_knowledge_graph` for beneficial ownership ≥ 25%\n"
                        "3. **Country risk** — Flag if counterparty country is under comprehensive sanctions\n"
                        "   (Cuba, Iran, North Korea, Russia, Syria, Venezuela, Belarus)\n"
                        "4. **PEP check** — Politically Exposed Persons in ownership chain\n"
                        "5. **Adverse media** — `analyze_text` on recent news for red flags\n\n"
                        "Produce a compliance report:\n"
                        "- **CLEAR**: No sanctions matches, proceed normally\n"
                        "- **REVIEW**: Potential match or elevated country risk, escalate to compliance\n"
                        "- **BLOCK**: Confirmed sanctions match, do not proceed\n\n"
                        "Include match type, list name, list date, and confidence for each finding.\n"
                        "Document all tools used and their results for audit trail."
                    ),
                },
            }
        ]
