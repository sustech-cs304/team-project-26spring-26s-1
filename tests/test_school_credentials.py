import json
import sqlite3
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from agent.api import env_vars as env_vars_module
from agent.api import school_settings
from agent.services import school_credentials


@pytest.fixture(autouse=True)
def isolated_school_credentials(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    db_path = tmp_path / "agent.db"
    cron_dir = tmp_path / "cron"
    env_vault_path = cron_dir / "env_vars.json"

    monkeypatch.setenv("AGENT_ENV_VAULT_MASTER_KEY", "test-master-key")
    monkeypatch.delenv("SUSTECH_STUDENT_ID", raising=False)
    monkeypatch.delenv("SUSTECH_CAS_PASSWORD", raising=False)

    monkeypatch.setattr(school_credentials, "_DB_PATH", db_path)
    monkeypatch.setattr(env_vars_module, "CRON_DIR", cron_dir)
    monkeypatch.setattr(env_vars_module, "ENV_VARS_FILE", env_vault_path)

    yield


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(school_settings.router, prefix="/api")
    return TestClient(app)


def test_set_school_cas_credentials_stores_encrypted_password_in_database():
    school_credentials.set_school_cas_credentials("12345678", "super-secret")

    with sqlite3.connect(school_credentials._DB_PATH) as conn:
        row = conn.execute(
            "SELECT student_id, password_ciphertext FROM school_credentials WHERE scope = ?",
            (school_credentials._CREDENTIAL_SCOPE,),
        ).fetchone()

    assert row is not None
    assert row[0] == "12345678"
    assert "super-secret" not in row[1]
    payload = json.loads(row[1])
    assert payload["format"] == "encrypted-v2"

    student_id, password = school_credentials.resolve_tis_credentials(None, None)
    assert student_id == "12345678"
    assert password == "super-secret"


def test_reading_shared_cas_migrates_legacy_env_vault_to_database():
    env_vars_module.upsert_env_var_value("SUSTECH_STUDENT_ID", "11810000")
    env_vars_module.upsert_env_var_value("SUSTECH_CAS_PASSWORD", "from-vault")

    student_id, password = school_credentials.resolve_bb_credentials(None, None)

    assert student_id == "11810000"
    assert password == "from-vault"
    assert env_vars_module.get_env_var_value("SUSTECH_STUDENT_ID") is None
    assert env_vars_module.get_env_var_value("SUSTECH_CAS_PASSWORD") is None

    with sqlite3.connect(school_credentials._DB_PATH) as conn:
        row = conn.execute(
            "SELECT student_id, password_ciphertext FROM school_credentials WHERE scope = ?",
            (school_credentials._CREDENTIAL_SCOPE,),
        ).fetchone()

    assert row is not None
    assert row[0] == "11810000"
    assert "from-vault" not in row[1]


def test_clear_school_cas_credentials_removes_database_and_legacy_vault():
    school_credentials.set_school_cas_credentials("12345678", "super-secret")
    env_vars_module.upsert_env_var_value("SUSTECH_STUDENT_ID", "stale-user")
    env_vars_module.upsert_env_var_value("SUSTECH_CAS_PASSWORD", "stale-password")

    school_credentials.clear_school_cas_credentials()

    with sqlite3.connect(school_credentials._DB_PATH) as conn:
        row = conn.execute(
            "SELECT COUNT(*) FROM school_credentials WHERE scope = ?",
            (school_credentials._CREDENTIAL_SCOPE,),
        ).fetchone()

    assert row == (0,)
    assert env_vars_module.get_env_var_value("SUSTECH_STUDENT_ID") is None
    assert env_vars_module.get_env_var_value("SUSTECH_CAS_PASSWORD") is None


def test_get_cas_route_is_not_exposed(client: TestClient):
    school_credentials.set_school_cas_credentials("12223333", "cas-password")

    response = client.get("/api/get_cas")

    assert response.status_code == 404


def test_patch_cas_merges_partial_update(client: TestClient):
    response = client.patch(
        "/api/patch_cas",
        json={
            "id": "12223333",
            "password": "old-password",
        },
    )
    assert response.status_code == 200
    assert response.json()["message"] == "CAS config updated successfully."

    response = client.patch(
        "/api/patch_cas",
        json={
            "password": "new-password",
        },
    )
    assert response.status_code == 200

    with sqlite3.connect(school_credentials._DB_PATH) as conn:
        row = conn.execute(
            "SELECT student_id, password_ciphertext FROM school_credentials WHERE scope = ?",
            (school_credentials._CREDENTIAL_SCOPE,),
        ).fetchone()

    assert row is not None
    assert row[0] == "12223333"
    assert env_vars_module.decrypt_secret_value(row[1]) == "new-password"


def test_patch_cas_rejects_incomplete_payload_for_missing_existing_config(client: TestClient):
    response = client.patch(
        "/api/patch_cas",
        json={
            "id": "12223333",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Both id and password are required after patch merge"
