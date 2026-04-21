import json
import os
import secrets
import time
import ssl
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Optional
from urllib.parse import urlencode

import lark_oapi as lark
from lark_oapi.api.mail.v1 import (
    MailAddress,
    SendUserMailboxMessageRequest,
    SendUserMailboxMessageRequestBody,
    SendUserMailboxMessageResponse,
)


AUTH_URL = "https://accounts.feishu.cn/open-apis/authen/v1/authorize"
TOKEN_URL = "https://open.feishu.cn/open-apis/authen/v2/oauth/token"

APP_ID = os.environ.get("FEISHU_APP_ID", "cli_a92725410e38dbc7")  
APP_SECRET = os.environ.get("FEISHU_APP_SECRET", "PEWXp2i9JUUaIkap6u7Uebd2rxnnICYU")  
REDIRECT_URI = os.environ.get("FEISHU_REDIRECT_URI", "https://open.feishu.cn/api-explorer/loading")
SCOPE = os.environ.get("FEISHU_SCOPE", "offline_access mail:user_mailbox.message:send",)

TOKENS_FILE = Path(os.environ.get("FEISHU_TOKENS_FILE", Path(__file__).with_name("feishu_tokens.json")))

ACCESS_TOKEN_LEEWAY = 60  
REFRESH_TOKEN_RENEW_BEFORE = 3600 


def _request_token(payload: dict) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        TOKEN_URL,
        data=data,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    ssl_no_verify = os.getenv("FEISHU_SSL_NO_VERIFY", "").strip().lower() in {"1", "true", "yes"}
    context = None
    if ssl_no_verify:
        # For local debugging behind proxies / custom TLS environments.
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE

    retries = int(os.getenv("FEISHU_TOKEN_RETRY", "3"))
    last_exc: Exception | None = None

    for attempt in range(retries):
        try:
            urlopen_kwargs = {}
            if context is not None:
                urlopen_kwargs["context"] = context
            with urllib.request.urlopen(req, timeout=10, **urlopen_kwargs) as resp:
                body = resp.read().decode("utf-8")
            # success
            j = json.loads(body)
            if j.get("code") != 0:
                raise RuntimeError(f"Token API returned error: {json.dumps(j, ensure_ascii=False)}")
            return j
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"Failed to call token API, HTTP {e.code}: {err_body}") from e
        except urllib.error.URLError as e:
            last_exc = e
            # retry on transient network errors
            if attempt < retries - 1:
                time.sleep(1 + attempt)
                continue
            break

    assert last_exc is not None
    raise RuntimeError(f"Failed to call token API after retries: {last_exc!r}")

    # unreachable (kept for type checkers)
    return {}


def build_auth_url() -> str:
    state = secrets.token_urlsafe(16)
    params = {
        "client_id": APP_ID,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPE,
        "state": state,
    }
    return f"{AUTH_URL}?{urlencode(params)}"


def _save_tokens(tokens: dict) -> None:
    TOKENS_FILE.write_text(json.dumps(tokens, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_tokens() -> Optional[dict]:
    if not TOKENS_FILE.exists():
        return None
    try:
        return json.loads(TOKENS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return None


def _now() -> int:
    return int(time.time())


def obtain_tokens_by_code() -> dict:
    auth_url = build_auth_url()
    print("Open the following URL in a browser, complete authorization, then copy the value after ?code= from the redirect URL:")
    print(auth_url)
    print()
    code = input("Please input the authorization code (code parameter): ").strip()
    if not code:
        raise RuntimeError("Code is empty, cannot obtain token.")

    payload = {
        "grant_type": "authorization_code",
        "client_id": APP_ID,
        "client_secret": APP_SECRET,
        "code": code,
        "redirect_uri": REDIRECT_URI,
    }
    j = _request_token(payload)
    now = _now()
    tokens = {
        "access_token": j["access_token"],
        "access_expires_at": now + int(j["expires_in"]),
        "refresh_token": j.get("refresh_token"),
        "refresh_expires_at": (
            now + int(j["refresh_token_expires_in"]) if j.get("refresh_token_expires_in") is not None else None
        ),
        "scope": j.get("scope"),
    }
    _save_tokens(tokens)
    return tokens


def refresh_tokens(old_tokens: dict) -> dict:
    refresh_token = old_tokens.get("refresh_token")
    if not refresh_token:
        raise RuntimeError("No refresh_token available; please re-authorize.")

    payload = {
        "grant_type": "refresh_token",
        "client_id": APP_ID,
        "client_secret": APP_SECRET,
        "refresh_token": refresh_token,
    }
    j = _request_token(payload)
    now = _now()
    tokens = {
        "access_token": j["access_token"],
        "access_expires_at": now + int(j["expires_in"]),
        "refresh_token": j.get("refresh_token"),
        "refresh_expires_at": (
            now + int(j["refresh_token_expires_in"]) if j.get("refresh_token_expires_in") is not None else None
        ),
        "scope": j.get("scope"),
    }
    _save_tokens(tokens)
    return tokens


def ensure_valid_tokens() -> dict:
    tokens = _load_tokens()
    now = _now()

    if not tokens:
        print("No local token found; starting initial authorization.")
        return obtain_tokens_by_code()

    refresh_expires_at = tokens.get("refresh_expires_at")
    if not refresh_expires_at or now >= refresh_expires_at - REFRESH_TOKEN_RENEW_BEFORE:
        print("refresh_token has expired or is about to expire; starting authorization again.")
        return obtain_tokens_by_code()

    access_expires_at = tokens.get("access_expires_at") or 0
    if now >= access_expires_at - ACCESS_TOKEN_LEEWAY:
        print("access_token has expired or is about to expire; trying to refresh with refresh_token.")
        try:
            return refresh_tokens(tokens)
        except Exception as e:
            print("Failed to refresh with refresh_token, will re-authorize. Detail:", repr(e))
            return obtain_tokens_by_code()

    return tokens


def get_access_token_for_api() -> str:
    tokens = _load_tokens()
    if not tokens:
        raise RuntimeError("Feishu OAuth token not found; please run `python test.py` in terminal to complete authorization first.")

    now = _now()
    refresh_expires_at = tokens.get("refresh_expires_at")

    if refresh_expires_at and now >= refresh_expires_at - REFRESH_TOKEN_RENEW_BEFORE:
        tokens = refresh_tokens(tokens)

    access_expires_at = tokens.get("access_expires_at") or 0
    if now >= access_expires_at - ACCESS_TOKEN_LEEWAY:
        tokens = refresh_tokens(tokens)

    _save_tokens(tokens)
    return tokens["access_token"]


def send_verification_email(to_email: str, code: str) -> None:
    access_token = get_access_token_for_api()
    client = lark.Client.builder().enable_set_token(True).log_level(lark.LogLevel.DEBUG).build()

    subject = "OpenCrab正在向您派送验证码!"
    text_body = f"您的验证码是<b>{code}</b>。Your OpenCrab verification code is {code}. 验证码的有效期是15分钟,请不要告诉别人! It is valid for 15 minutes. Do not share it with anyone."
    html_body = f"<p>您的验证码是<b>{code}</b>。</p><p>Your OpenCrab verification code is <b>{code}</b>.</p><p>验证码的有效期是15分钟,请不要告诉别人!</p><p>It is valid for 15 minutes. Do not share it with anyone.</p>"

    request: SendUserMailboxMessageRequest = SendUserMailboxMessageRequest.builder() \
        .user_mailbox_id("me") \
        .request_body(
            SendUserMailboxMessageRequestBody.builder()
            .subject(subject)
            .to([
                MailAddress.builder()
                .mail_address(to_email)
                .name(to_email)
                .build()
            ])
            .body_html(html_body)
            .body_plain_text(text_body)
            .dedupe_key(str(uuid.uuid4()))
            .head_from(
                MailAddress.builder()
                .name("NoReply")
                .build()
            )
            .build()
        ).build()

    option = lark.RequestOption.builder().user_access_token(access_token).build()
    response: SendUserMailboxMessageResponse = client.mail.v1.user_mailbox_message.send(request, option)

    if not response.success():
        lark.logger.error(
            f"Failed to send verification email, code: {response.code}, msg: {response.msg}, log_id: {response.get_log_id()}, resp: \n"
            f"{json.dumps(json.loads(response.raw.content), indent=4, ensure_ascii=False)}"
        )
        raise RuntimeError(f"Failed to send verification email: code={response.code}, msg={response.msg}")


def main() -> None:
    tokens = ensure_valid_tokens()
    access_token = tokens["access_token"]
    print("Current user_access_token:", access_token[:20] + "..." if len(access_token) > 20 else access_token)

    default_to = os.environ.get("FEISHU_TEST_TO", "")
    prompt = "Please enter the email address to receive the verification code"
    if default_to:
        prompt += f" (press Enter to use default {default_to})"
    prompt += ": "

    to_email = input(prompt).strip() or default_to
    if not to_email:
        print("No recipient email provided; exiting.")
        return

    code = "".join(str(secrets.randbelow(10)) for _ in range(6))
    print(f"Generated verification code: {code}")

    try:
        send_verification_email(to_email, code)
        print(f"Verification code has been sent to {to_email}. Please check your mailbox.")
    except Exception as e:
        print("Error occurred when sending verification code:", repr(e))


if __name__ == "__main__":
    main()