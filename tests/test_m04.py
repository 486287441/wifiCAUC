from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from wificauc.config import AppConfig, PortalSelectors
from wificauc.main import run_once
from wificauc.notify import _applescript_string, notify_failure, notify_success
from wificauc.portal import LoginResult
from wificauc.state import (
    STATE_DIR,
    clear_paused,
    is_paused,
    read_last_run,
    read_paused,
    set_paused,
    write_last_run,
)


def _cfg(**overrides) -> AppConfig:
    base = dict(
        wifi_ssid="CAUC-WIFI",
        wifi_interface="auto",
        wifi_ssid_match="normalized",
        wifi_fallback_portal_detect=True,
        portal_url="http://192.168.4.252/",
        selectors=PortalSelectors(
            username='input[name="DDDDD"]',
            password='input[name="upass"]',
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


class TestNotify(unittest.TestCase):
    def test_applescript_string_escapes_quotes(self) -> None:
        self.assertEqual(_applescript_string('a"b\\c'), 'a\\"b\\\\c')

    @patch("wificauc.notify.subprocess.run")
    def test_notify_success_uses_double_quotes(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        notify_success()
        mock_run.assert_called_once()
        script = mock_run.call_args.args[0][2]
        self.assertIn('"CAUC 校园网"', script)
        self.assertIn('"已成功登录"', script)
        self.assertNotIn("'已成功登录'", script)

    @patch("wificauc.notify.subprocess.run")
    def test_notify_failure_truncates_reason(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        long_reason = "x" * 200
        notify_failure(long_reason)
        script = mock_run.call_args.args[0][2]
        self.assertIn('"登录失败"', script)
        truncated = "x" * 119 + "…"
        self.assertIn(f'subtitle "{truncated}"', script)


class TestState(unittest.TestCase):
    def setUp(self) -> None:
        self._state_patch = patch("wificauc.state.STATE_DIR", Path("state_test_m04"))
        self.state_dir = self._state_patch.start()
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.addCleanup(self._cleanup_state_dir)
        self.addCleanup(self._state_patch.stop)

    def _cleanup_state_dir(self) -> None:
        for path in sorted(self.state_dir.rglob("*"), reverse=True):
            if path.is_file():
                path.unlink()
        if self.state_dir.is_dir():
            self.state_dir.rmdir()

    def test_paused_round_trip(self) -> None:
        self.assertFalse(is_paused())
        set_paused("bad password")
        self.assertTrue(is_paused())
        self.assertTrue((self.state_dir / "paused").is_file())
        paused = read_paused()
        self.assertIsNotNone(paused)
        assert paused is not None
        self.assertEqual(paused[0], "bad password")
        self.assertTrue(clear_paused())
        self.assertFalse(is_paused())

    def test_write_and_read_last_run(self) -> None:
        write_last_run("success")
        data = read_last_run()
        self.assertIsNotNone(data)
        assert data is not None
        self.assertEqual(data["result"], "success")
        self.assertTrue((self.state_dir / "last_run.json").is_file())
        payload = json.loads((self.state_dir / "last_run.json").read_text(encoding="utf-8"))
        self.assertEqual(payload["result"], "success")


class TestMainPausedIntegration(unittest.TestCase):
    def setUp(self) -> None:
        self._state_patch = patch("wificauc.state.STATE_DIR", Path("state_test_m04_main"))
        self.state_dir = self._state_patch.start()
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.addCleanup(self._cleanup_state_dir)
        self.addCleanup(self._state_patch.stop)

    def _cleanup_state_dir(self) -> None:
        for path in sorted(self.state_dir.rglob("*"), reverse=True):
            if path.is_file():
                path.unlink()
        if self.state_dir.is_dir():
            self.state_dir.rmdir()

    @patch("wificauc.main.asyncio.run")
    @patch("wificauc.main.decide_once_outcome", return_value="need_portal_login")
    @patch("wificauc.main._on_target_network", return_value=(True, "ssid"))
    @patch("wificauc.main.get_interface_ipv4", return_value="10.0.0.2")
    @patch("wificauc.main.get_current_ssid", return_value="CAUC-WIFI")
    @patch("wificauc.main.resolve_wifi_interface", return_value="en0")
    def test_run_once_skips_login_when_paused(
        self,
        _resolve: MagicMock,
        _ssid: MagicMock,
        _ip: MagicMock,
        _on_target: MagicMock,
        _decide: MagicMock,
        mock_asyncio_run: MagicMock,
    ) -> None:
        set_paused("wrong password")
        code = run_once(_cfg())
        self.assertEqual(code, 0)
        mock_asyncio_run.assert_not_called()

    @patch("wificauc.main.notify_failure")
    @patch("wificauc.main.asyncio.run")
    @patch("wificauc.main.decide_once_outcome", return_value="need_portal_login")
    @patch("wificauc.main._on_target_network", return_value=(True, "ssid"))
    @patch("wificauc.main.get_interface_ipv4", return_value="10.0.0.2")
    @patch("wificauc.main.get_current_ssid", return_value="CAUC-WIFI")
    @patch("wificauc.main.resolve_wifi_interface", return_value="en0")
    def test_run_once_failure_pauses_and_notifies(
        self,
        _resolve: MagicMock,
        _ssid: MagicMock,
        _ip: MagicMock,
        _on_target: MagicMock,
        _decide: MagicMock,
        mock_asyncio_run: MagicMock,
        mock_notify_failure: MagicMock,
    ) -> None:
        mock_asyncio_run.return_value = LoginResult.fail("密码错误")

        code = run_once(_cfg())
        self.assertEqual(code, 1)
        mock_notify_failure.assert_called_once_with("密码错误")
        self.assertTrue(is_paused())
        last_run = read_last_run()
        self.assertIsNotNone(last_run)
        assert last_run is not None
        self.assertEqual(last_run["result"], "fail")

    @patch("wificauc.main.notify_success")
    @patch("wificauc.main.asyncio.run")
    @patch("wificauc.main.decide_once_outcome", return_value="need_portal_login")
    @patch("wificauc.main._on_target_network", return_value=(True, "ssid"))
    @patch("wificauc.main.get_interface_ipv4", return_value="10.0.0.2")
    @patch("wificauc.main.get_current_ssid", return_value="CAUC-WIFI")
    @patch("wificauc.main.resolve_wifi_interface", return_value="en0")
    def test_run_once_success_notifies_without_pause(
        self,
        _resolve: MagicMock,
        _ssid: MagicMock,
        _ip: MagicMock,
        _on_target: MagicMock,
        _decide: MagicMock,
        mock_asyncio_run: MagicMock,
        mock_notify_success: MagicMock,
    ) -> None:
        mock_asyncio_run.return_value = LoginResult.performed_login()

        code = run_once(_cfg())
        self.assertEqual(code, 0)
        mock_notify_success.assert_called_once()
        self.assertFalse(is_paused())
        last_run = read_last_run()
        self.assertIsNotNone(last_run)
        assert last_run is not None
        self.assertEqual(last_run["result"], "success")


if __name__ == "__main__":
    unittest.main()
