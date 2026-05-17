from __future__ import annotations

import importlib

import pytest

code_interpreter_module = importlib.import_module("agent.tools.code_interpreter")


pytestmark = pytest.mark.integration


def test_code_interpreter_injects_stored_env_vars(monkeypatch, tmp_path, run_async):
    async def fake_read_credential_values(credential_type: str) -> dict[str, str]:
        assert credential_type == "env_var"
        return {"OPENCRAB_CI_TOKEN": "secret-value"}

    monkeypatch.setattr(
        code_interpreter_module,
        "read_credential_values",
        fake_read_credential_values,
    )
    monkeypatch.setattr(code_interpreter_module, "WORKSPACE_DIR", tmp_path)

    result = run_async(
        code_interpreter_module._run_script(
            "import os\nprint(os.environ['OPENCRAB_CI_TOKEN'])\n",
            "python",
            5,
        )
    )

    assert result == "secret-value\n"


def test_code_interpreter_fails_closed_when_credential_store_unavailable(
    monkeypatch,
    tmp_path,
    run_async,
):
    async def fake_read_credential_values(credential_type: str) -> dict[str, str]:
        assert credential_type == "env_var"
        raise code_interpreter_module.EnvVaultAccessError("vault unavailable")

    monkeypatch.setattr(
        code_interpreter_module,
        "read_credential_values",
        fake_read_credential_values,
    )
    monkeypatch.setattr(code_interpreter_module, "WORKSPACE_DIR", tmp_path)

    result = run_async(
        code_interpreter_module._run_script(
            "print('should-not-run')\n",
            "python",
            5,
        )
    )

    assert "credential store is unavailable: vault unavailable" in result
    assert "should-not-run" not in result
