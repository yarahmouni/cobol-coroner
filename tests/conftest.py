"""Pytest configuration for Coroner tests."""
from hypothesis import settings, Phase

# Register a deterministic profile for reproducible tests
settings.register_profile(
    "coroner",
    derandomize=True,
    database=None,
    phases=[Phase.explicit, Phase.reuse, Phase.generate, Phase.target, Phase.shrink]
)

# Load the profile
settings.load_profile("coroner")
