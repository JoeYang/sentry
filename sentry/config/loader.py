from pathlib import Path

import yaml

from sentry.config.schema import SentryConfig


def load_config(path: str | None = None) -> SentryConfig:
    """Load config from YAML file, falling back to defaults."""
    if path is None:
        return SentryConfig()

    config_path = Path(path)
    if not config_path.exists():
        return SentryConfig()

    with open(config_path) as f:
        raw = yaml.safe_load(f)

    if not isinstance(raw, dict):
        return SentryConfig()

    return SentryConfig(**raw)
