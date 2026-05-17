from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import agent.api.env_vars as env_vars_api
from agent.api.env_vars import EnvVaultAccessError
from agent.api.env_vars import router as env_vars_router


pytestmark = pytest.mark.api


@pytest.fixture
def env_var_client(app_factory, temp_default_db):
    app = app_factory()
    app.include_router(env_vars_router, prefix="/api")
    return TestClient(app)


@pytest.fixture
def env_var_client_no_raise(app_factory, temp_default_db):
    app = app_factory()
    app.include_router(env_vars_router, prefix="/api")
    return TestClient(app, raise_server_exceptions=False)


@pytest.mark.parametrize(
    "payload",
    [
        {"key": "TOKEN"},
        {"value": "secret"},
        {"key": "TOKEN", "value": "secret", "extra": "forbidden"},
        {"key": "", "value": "secret"},
        {"key": "   ", "value": "secret"},
        {"key": "TOKEN;DROP TABLE credentials", "value": "secret"},
        {"key": "KEY;rm -rf /", "value": "secret"},
        {"key": "<script>alert(1)</script>", "value": "secret"},
        {"key": '{"key":"VALUE"}', "value": "secret"},
        {"key": "OPENCRAB.KEY", "value": "secret"},
        {"key": "OPENCRAB-KEY", "value": "secret"},
        {"key": "A" * 1025, "value": "secret"},
        {"key": 123, "value": "secret"},
        {"key": None, "value": "secret"},
        {"key": "TOKEN", "value": 123},
        {"key": "TOKEN", "value": None},
        {"key": "TOKEN", "value": []},
        {"key": "TOKEN", "value": {}},
        None,
        [],
        "not-an-object",
    ],
)
def test_env_vars_reject_missing_invalid_type_boundary_and_injection_inputs(env_var_client, payload):
    response = env_var_client.post("/api/env-vars", json=payload)

    assert response.status_code == 400


@pytest.mark.parametrize(
    "payload",
    [
        {"key": "TOKEN", "value": "secret", "extra": "forbidden"},
        {"key": "TOKEN", "value": "secret", "nested": {"$ne": None}},
    ],
)
def test_env_vars_reject_extra_fields_declared_forbidden_by_openapi(env_var_client, payload):
    response = env_var_client.post("/api/env-vars", json=payload)

    assert response.status_code == 400


@pytest.mark.parametrize(
    "payload",
    [
        {"key": "A", "value": ""},
        {"key": "A" * 1024, "value": "x"},
        {"key": " OPENCRAB_TOKEN ", "value": "secret"},
    ],
)
def test_env_vars_accept_positive_and_boundary_values_without_leaking_secret(env_var_client, payload):
    response = env_var_client.post("/api/env-vars", json=payload)
    listed = env_var_client.get("/api/env-vars")

    assert response.status_code == 200
    assert response.json()["key"] == payload["key"].strip()
    assert listed.status_code == 200
    if payload["value"]:
        assert payload["value"] not in listed.text


@pytest.mark.parametrize(
    "payload",
    [
        {"key": "ZERO_VALUE", "value": "0"},
        {"key": "JSON_VALUE", "value": '{"safe": true, "$ne": null}'},
        {"key": "XSS_VALUE", "value": "<script>alert(1)</script>"},
        {"key": "COMMAND_VALUE", "value": "echo safe && rm -rf /"},
        {"key": "FUZZ_VALUE", "value": "\u0000\u0001 long-ish value " + "x" * 2048},
    ],
)
def test_env_vars_accept_arbitrary_secret_values_but_never_list_them(env_var_client, payload):
    response = env_var_client.post("/api/env-vars", json=payload)
    listed = env_var_client.get("/api/env-vars")

    assert response.status_code == 200
    assert response.json() == {"key": payload["key"]}
    assert listed.status_code == 200
    assert {"key": payload["key"]} in listed.json()
    assert payload["value"] not in listed.text


def test_env_vars_upsert_overwrites_without_duplicate_keys_or_secret_leak(env_var_client):
    first = env_var_client.post("/api/env-vars", json={"key": "DUP_TOKEN", "value": "first-secret"})
    second = env_var_client.post("/api/env-vars", json={"key": "DUP_TOKEN", "value": "second-secret"})
    listed = env_var_client.get("/api/env-vars")

    assert first.status_code == 200
    assert second.status_code == 200
    assert listed.status_code == 200
    assert [item["key"] for item in listed.json()].count("DUP_TOKEN") == 1
    assert "first-secret" not in listed.text
    assert "second-secret" not in listed.text


def test_env_vars_empty_value_round_trips_as_key_only_and_can_be_deleted(env_var_client):
    created = env_var_client.post("/api/env-vars", json={"key": "EMPTY_VALUE_TOKEN", "value": ""})
    listed = env_var_client.get("/api/env-vars")
    deleted = env_var_client.delete("/api/env-vars/EMPTY_VALUE_TOKEN")
    missing_delete = env_var_client.delete("/api/env-vars/EMPTY_VALUE_TOKEN")

    assert created.status_code == 200
    assert created.json() == {"key": "EMPTY_VALUE_TOKEN"}
    assert listed.status_code == 200
    assert {"key": "EMPTY_VALUE_TOKEN"} in listed.json()
    assert deleted.status_code == 200
    assert missing_delete.status_code == 404


@pytest.mark.parametrize("key", ["TOKEN;DROP", "KEY%3Brm%20-rf%20%2F", "<script>alert(1)</script>", "A" * 1025])
def test_env_vars_delete_rejects_unsafe_keys(env_var_client, key):
    response = env_var_client.delete(f"/api/env-vars/{key}")

    assert response.status_code in {400, 404}


@pytest.mark.parametrize(
    "key",
    [
        "../OPENCRAB_TOKEN",
        "..%2FOPENCRAB_TOKEN",
        "OPENCRAB_TOKEN%00",
        "OPENCRAB_TOKEN%3Fnext%3D%2Fenv-vars%2FOTHER",
    ],
)
def test_env_vars_delete_path_strings_do_not_delete_safe_key(env_var_client, key):
    created = env_var_client.post("/api/env-vars", json={"key": "OPENCRAB_TOKEN", "value": "secret"})
    response = env_var_client.delete(f"/api/env-vars/{key}")
    listed = env_var_client.get("/api/env-vars")

    assert created.status_code == 200
    assert response.status_code in {400, 404}
    assert {"key": "OPENCRAB_TOKEN"} in listed.json()


@pytest.mark.parametrize(
    ("operation", "method", "url", "kwargs"),
    [
        ("list", "get", "/api/env-vars", {}),
        ("upsert", "post", "/api/env-vars", {"json": {"key": "TOKEN", "value": "secret"}}),
        ("delete", "delete", "/api/env-vars/TOKEN", {}),
    ],
)
def test_env_var_operations_return_declared_500_on_vault_access_error(
    env_var_client_no_raise,
    monkeypatch,
    operation,
    method,
    url,
    kwargs,
):
    async def boom(*_args, **_kwargs):
        raise EnvVaultAccessError("vault unavailable")

    if operation == "list":
        monkeypatch.setattr(env_vars_api, "list_env_var_keys", boom)
    elif operation == "upsert":
        monkeypatch.setattr(env_vars_api, "upsert_env_var_value", boom)
    else:
        monkeypatch.setattr(env_vars_api, "delete_env_var_value", boom)

    response = getattr(env_var_client_no_raise, method)(url, **kwargs)

    assert response.status_code == 500
    assert "vault unavailable" in response.text


@pytest.mark.parametrize(
    "key",
    [
        "TOKEN",
        "_TOKEN",
        "TOKEN_1",
        "A" * 1024,
    ],
)
def test_env_vars_delete_accepts_declared_safe_path_key_boundaries(env_var_client, key):
    created = env_var_client.post("/api/env-vars", json={"key": key, "value": "secret"})
    deleted = env_var_client.delete(f"/api/env-vars/{key}")

    assert created.status_code == 200
    assert deleted.status_code == 200
    assert deleted.json() == {"message": "Deleted."}
