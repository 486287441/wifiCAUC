from __future__ import annotations

import os
import re
from dataclasses import dataclass
from urllib.parse import urlparse

from playwright.async_api import TimeoutError as PlaywrightTimeout
from playwright.async_api import async_playwright

from wificauc.clash import portal_no_proxy_bypass
from wificauc.config import AppConfig

# Code must never click these (never_click_only). Only cfg.selectors.submit is clicked.
_LOGOUT_TEXT_PATTERN = re.compile(r"注销|logout", re.IGNORECASE)


@dataclass(frozen=True)
class LoginResult:
    ok: bool
    already_logged_in: bool = False
    reason: str = ""

    @classmethod
    def performed_login(cls) -> LoginResult:
        return cls(ok=True, already_logged_in=False)

    @classmethod
    def already_logged_in(cls) -> LoginResult:
        return cls(ok=True, already_logged_in=True)

    @classmethod
    def fail(cls, reason: str) -> LoginResult:
        return cls(ok=False, reason=reason)


def _assert_submit_selector_safe(submit_selector: str) -> None:
    if _LOGOUT_TEXT_PATTERN.search(submit_selector):
        raise ValueError("submit 选择器不得包含注销/logout 文案")


async def _visible_locator(page, selector: str):
    """Portal pages often duplicate fields (hidden + visible); pick the visible one."""
    loc = page.locator(selector)
    count = await loc.count()
    if count <= 1:
        return loc
    for i in range(count):
        candidate = loc.nth(i)
        if await candidate.is_visible():
            return candidate
    return loc.first


async def _page_indicates_logged_in(page, success_text: str) -> bool:
    body = await page.content()
    if success_text in body:
        return True
    if await page.locator('input[name="logout"]').count() > 0:
        return True
    title = await page.title()
    if title and "logout" in title.lower():
        return True
    return False


async def login(cfg: AppConfig) -> LoginResult:
    """
    Headless portal login. Only fills credentials and clicks submit.
    Never clicks logout / 注销 elements.
    """
    _assert_submit_selector_safe(cfg.selectors.submit)
    timeout_ms = cfg.portal_timeout_seconds * 1000
    bypass = ",".join(portal_no_proxy_bypass(cfg.portal_url))
    portal_host = urlparse(cfg.portal_url).hostname or ""
    launch_env = dict(os.environ)
    if portal_host:
        existing = launch_env.get("NO_PROXY", "")
        extra = ",".join(x for x in (existing, portal_host, "127.0.0.1", "localhost") if x)
        launch_env["NO_PROXY"] = extra

    try:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(
                headless=cfg.headless,
                env=launch_env,
            )
            try:
                context = await browser.new_context(
                    proxy={"server": "direct://", "bypass": bypass},
                    ignore_https_errors=True,
                )
                page = await context.new_page()
                await page.goto(
                    cfg.portal_url,
                    wait_until="networkidle",
                    timeout=timeout_ms,
                )

                if await _page_indicates_logged_in(page, cfg.success_text):
                    return LoginResult.already_logged_in()

                username = await _visible_locator(page, cfg.selectors.username)
                try:
                    await username.wait_for(state="visible", timeout=10_000)
                except PlaywrightTimeout:
                    if await _page_indicates_logged_in(page, cfg.success_text):
                        return LoginResult.already_logged_in()
                    return LoginResult.fail(
                        "未找到可见的登录表单（可能已登录或门户页面结构已变更）"
                    )

                password = await _visible_locator(page, cfg.selectors.password)
                submit = await _visible_locator(page, cfg.selectors.submit)
                await username.fill(cfg.username)
                await password.fill(cfg.password)
                await submit.click()

                await page.get_by_text(cfg.success_text).wait_for(
                    state="visible",
                    timeout=timeout_ms,
                )
                return LoginResult.performed_login()
            finally:
                await browser.close()
    except PlaywrightTimeout as exc:
        return LoginResult.fail(f"超时：{exc}")
    except Exception as exc:  # noqa: BLE001 — surface portal errors to caller
        return LoginResult.fail(str(exc))
