from __future__ import annotations

import ast
import re
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from wificauc.config import AppConfig, PortalSelectors
from wificauc.portal import LoginResult, _assert_submit_selector_safe, login


def _cfg(**overrides) -> AppConfig:
    base = dict(
        wifi_ssid="CAUC-WIFI",
        wifi_interface="auto",
        wifi_ssid_match="normalized",
        wifi_fallback_portal_detect=True,
        portal_url="http://192.168.4.252/",
        selectors=PortalSelectors(
            username='input[name="DDDDD"][type="text"]',
            password='input[name="upass"][type="password"]',
            submit='input[name="0MKKey"]',
        ),
        success_text="您已经成功登录",
        username="241540327",
        password="secret",
        poll_interval_seconds=20,
        connectivity_urls=[],
        connectivity_timeout_seconds=3.0,
        connectivity_bind_wifi=True,
        clash_compatible=True,
        headless=True,
        portal_timeout_seconds=30,
    )
    base.update(overrides)
    return AppConfig(**base)


def _mock_page(*, content: str = '<input name="DDDDD">', wait_error: Exception | None = None) -> MagicMock:
    page = MagicMock()
    page.goto = AsyncMock()
    page.content = AsyncMock(return_value=content)
    page.title = AsyncMock(return_value="ePortal Login")
    locator = MagicMock()
    locator.wait_for = AsyncMock(side_effect=wait_error)
    locator.fill = AsyncMock()
    locator.click = AsyncMock()
    locator.count = AsyncMock(return_value=0)
    page.locator.return_value = locator
    page.get_by_text.return_value.wait_for = AsyncMock()
    return page


def _mock_playwright_stack(page: MagicMock) -> tuple[AsyncMock, AsyncMock]:
    browser = AsyncMock()
    context = AsyncMock()
    context.new_page = AsyncMock(return_value=page)
    browser.new_context = AsyncMock(return_value=context)
    browser.close = AsyncMock()
    playwright = AsyncMock()
    playwright.chromium.launch = AsyncMock(return_value=browser)
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=playwright)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm, browser


class TestPortalSafety(unittest.TestCase):
    def test_submit_selector_must_not_be_logout(self) -> None:
        with self.assertRaises(ValueError):
            _assert_submit_selector_safe("text=注销")

    def test_portal_source_never_clicks_logout(self) -> None:
        source = (Path(__file__).resolve().parents[1] / "src/wificauc/portal.py").read_text(
            encoding="utf-8"
        )
        tree = ast.parse(source)
        forbidden = re.compile(r"注销|logout", re.IGNORECASE)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = ""
            if isinstance(func, ast.Attribute):
                name = func.attr
            elif isinstance(func, ast.Name):
                name = func.id
            if name != "click":
                continue
            for arg in node.args:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    self.assertFalse(
                        forbidden.search(arg.value),
                        f"forbidden click target: {arg.value!r}",
                    )


class TestPortalLogin(unittest.IsolatedAsyncioTestCase):
    async def test_login_success_after_submit(self) -> None:
        cfg = _cfg()
        page = _mock_page()
        cm, _browser = _mock_playwright_stack(page)

        with patch("wificauc.portal.async_playwright", return_value=cm):
            result = await login(cfg)

        self.assertTrue(result.ok)
        self.assertFalse(result.already_logged_in)
        page.locator.return_value.click.assert_awaited_once()

    async def test_login_already_logged_in(self) -> None:
        cfg = _cfg()
        page = _mock_page(content="您已经成功登录")
        cm, _browser = _mock_playwright_stack(page)

        with patch("wificauc.portal.async_playwright", return_value=cm):
            result = await login(cfg)

        self.assertTrue(result.ok)
        self.assertTrue(result.already_logged_in)
        page.locator.assert_not_called()

    async def test_login_failure_on_timeout(self) -> None:
        from playwright.async_api import TimeoutError as PlaywrightTimeout

        cfg = _cfg()
        page = _mock_page()
        page.get_by_text.return_value.wait_for = AsyncMock(
            side_effect=PlaywrightTimeout("wait")
        )
        cm, _browser = _mock_playwright_stack(page)

        with patch("wificauc.portal.async_playwright", return_value=cm):
            result = await login(cfg)

        self.assertFalse(result.ok)
        self.assertIn("超时", result.reason)


if __name__ == "__main__":
    unittest.main()
