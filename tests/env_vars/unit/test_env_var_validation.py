from __future__ import annotations

import pytest

from agent.api.env_vars import validate_env_var_key


pytestmark = pytest.mark.unit


def test_env_var_key_validator_accepts_only_safe_identifier_names():
    assert validate_env_var_key("  OPENCRAB_API_KEY_1  ") == "OPENCRAB_API_KEY_1"

    for raw in [
        "",
        "   ",
        "OPENCRAB-KEY",
        "DROP TABLE credentials",
        "KEY;rm -rf /",
        "<script>alert(1)</script>",
        '{"key":"VALUE"}',
        "OPENCRAB.KEY",
    ]:
        with pytest.raises(ValueError):
            validate_env_var_key(raw)

    with pytest.raises(ValueError):
        validate_env_var_key("A" * 1025)
