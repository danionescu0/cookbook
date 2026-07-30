import httpx

TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


def verify_turnstile(token: str, secret_key: str) -> bool:
    # A blank secret key means Turnstile hasn't been configured yet (Settings > Turnstile secret
    # key) — fail closed rather than silently letting every signup through unchecked.
    if not secret_key:
        return False
    try:
        response = httpx.post(
            TURNSTILE_VERIFY_URL, data={"secret": secret_key, "response": token}, timeout=10.0
        )
        response.raise_for_status()
        return bool(response.json().get("success"))
    except httpx.HTTPError:
        return False
