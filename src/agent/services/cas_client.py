import ssl
import warnings
from re import search

import aiohttp

warnings.filterwarnings("ignore")

REQUEST_TIMEOUT_S = 15

HEADERS = {
    "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.2 Safari/605.1.15",
    "x-requested-with": "XMLHttpRequest",
}

SSL_CONTEXT = ssl.create_default_context()
SSL_CONTEXT.check_hostname = False
SSL_CONTEXT.verify_mode = ssl.CERT_NONE
CLIENT_TIMEOUT = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT_S)


async def cas_login(login_url: str, user_name: str, pwd: str) -> dict:
    jar = aiohttp.CookieJar(unsafe=True)
    session = aiohttp.ClientSession(
        headers=HEADERS,
        cookie_jar=jar,
        timeout=CLIENT_TIMEOUT,
    )
    try:
        async with session.get(login_url, ssl=SSL_CONTEXT) as resp:
            if resp.status != 200:
                await session.close()
                return {"success": False, "message": "Cannot reach CAS; check network."}
            text = await resp.text()

        match = search(r'name="execution" value="([^"]+)"', text)
        if not match:
            await session.close()
            return {"success": False, "message": "Failed to parse execution from CAS login page."}

        async with session.post(
            login_url,
            data={
                "username": user_name,
                "password": pwd,
                "execution": match.group(1),
                "_eventId": "submit",
            },
            ssl=SSL_CONTEXT,
            allow_redirects=False,
        ) as resp:
            location = resp.headers.get("Location")
            if not location:
                await session.close()
                return {"success": False, "message": "Invalid username or password."}

        async with session.get(location, ssl=SSL_CONTEXT, allow_redirects=True):
            pass

    except Exception as exc:
        await session.close()
        return {"success": False, "message": "CAS login failed", "error": str(exc)}

    return {"success": True, "session": session}
