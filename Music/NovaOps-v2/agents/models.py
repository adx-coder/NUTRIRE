"""Model provider configuration for NovaOps v2.

Maps agent roles to Nova 2 Lite thinking budgets.
Loads credentials from .env file automatically.
"""

import os
from dotenv import load_dotenv
from strands.models import BedrockModel

# Load .env for credentials
load_dotenv()

# Nova 2 Lite model ID
NOVA_MODEL_ID = os.environ.get("NOVA_MODEL_ID", "us.amazon.nova-2-lite-v1:0")

# Thinking budget tiers per agent role
THINKING_BUDGET = {
    "LOW": 1024,      # Triage, Critic, Executor
    "MEDIUM": 4096,   # Analysts, RemediationPlanner
    "HIGH": 8192,     # RootCauseReasoner
}


def get_model(thinking_tier: str = "MEDIUM", temperature: float = 0.2) -> BedrockModel:
    """Create a BedrockModel configured for a specific thinking budget."""
    region = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")

    return BedrockModel(
        model_id=NOVA_MODEL_ID,
        region_name=region,
        temperature=temperature,
    )
