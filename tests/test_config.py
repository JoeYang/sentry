import os
import tempfile

import pytest

from sentry.config.loader import load_config
from sentry.config.schema import SentryConfig


class TestDefaultConfig:
    def test_load_with_no_path(self):
        config = load_config(None)
        assert isinstance(config, SentryConfig)
        assert config.llm.base_url == "http://localhost:11434"
        assert config.llm.model == "qwen2.5-coder:7b"
        assert config.mcp.port == 8080
        assert config.security.max_command_timeout == 30
        assert config.logging.level == "INFO"

    def test_load_with_nonexistent_file(self):
        config = load_config("/nonexistent/path/config.yaml")
        assert isinstance(config, SentryConfig)
        assert config.llm.model == "qwen2.5-coder:7b"


class TestPartialOverrides:
    def test_partial_yaml_overrides(self):
        yaml_content = "llm:\n  model: 'gpt-4'\n  timeout: 60\n"
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            f.write(yaml_content)
            f.flush()
            config = load_config(f.name)

        os.unlink(f.name)

        assert config.llm.model == "gpt-4"
        assert config.llm.timeout == 60
        # Non-overridden values keep defaults
        assert config.llm.base_url == "http://localhost:11434"
        assert config.mcp.port == 8080

    def test_empty_yaml_returns_defaults(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            f.write("")
            f.flush()
            config = load_config(f.name)

        os.unlink(f.name)

        assert isinstance(config, SentryConfig)
        assert config.llm.model == "qwen2.5-coder:7b"


class TestInvalidConfig:
    def test_invalid_type_raises_validation_error(self):
        yaml_content = "llm:\n  timeout: 'not_a_number'\n"
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            f.write(yaml_content)
            f.flush()
            with pytest.raises(Exception):
                load_config(f.name)

        os.unlink(f.name)

    def test_invalid_nested_type(self):
        yaml_content = "mcp:\n  port: 'not_a_port'\n"
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            f.write(yaml_content)
            f.flush()
            with pytest.raises(Exception):
                load_config(f.name)

        os.unlink(f.name)
