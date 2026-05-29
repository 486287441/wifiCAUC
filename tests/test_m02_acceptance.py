from __future__ import annotations

import io
import subprocess
import sys
import unittest
from contextlib import redirect_stdout
from unittest.mock import MagicMock, patch

from wificauc.config import AppConfig, PortalSelectors
from wificauc.main import cmd_once, decide_once_outcome


def _cfg() -> AppConfig:
    return AppConfig(
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
        username="u",
        password="p",
        poll_interval_seconds=20,
        connectivity_urls=["http://captive.apple.com/hotspot-detect.html"],
        connectivity_timeout_seconds=3.0,
        connectivity_bind_wifi=True,
        clash_compatible=True,
        headless=True,
        portal_timeout_seconds=30,
    )


class TestM02Acceptance(unittest.TestCase):
    """M02 验收标准：三分支 + once 退出码 0、不启动浏览器。"""

    @patch("wificauc.main.load_config", return_value=_cfg())
    @patch("wificauc.main.get_interface_ipv4", return_value="192.168.1.100")
    @patch("wificauc.main.resolve_wifi_interface", return_value="en0")
    @patch("wificauc.main.get_current_ssid", return_value="Other-Net")
    @patch("wificauc.main.is_internet_available")
    def test_accept_wrong_wifi_skips_no_browser(
        self,
        mock_online: MagicMock,
        *_mocks: MagicMock,
    ) -> None:
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = cmd_once(MagicMock())
        out = buf.getvalue()
        self.assertEqual(code, 0)
        self.assertIn("skipped: wrong wifi", out)
        mock_online.assert_not_called()

    @patch("wificauc.main.load_config", return_value=_cfg())
    @patch("wificauc.main.get_interface_ipv4", return_value="192.168.1.100")
    @patch("wificauc.main.resolve_wifi_interface", return_value="en0")
    @patch("wificauc.main.get_current_ssid", return_value="caucwifi")
    @patch("wificauc.main.is_internet_available", return_value=True)
    def test_accept_already_online_skips(
        self,
        mock_online: MagicMock,
        *_mocks: MagicMock,
    ) -> None:
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = cmd_once(MagicMock())
        out = buf.getvalue()
        self.assertEqual(code, 0)
        self.assertIn("skipped: already online", out)
        mock_online.assert_called_once()
        _, kwargs = mock_online.call_args
        self.assertTrue(kwargs.get("clash_compatible"))

    @patch("wificauc.main.asyncio.run")
    @patch("wificauc.main.load_config", return_value=_cfg())
    @patch("wificauc.main.get_interface_ipv4", return_value="192.168.1.100")
    @patch("wificauc.main.resolve_wifi_interface", return_value="en0")
    @patch("wificauc.main.get_current_ssid", return_value="CAUC-WIFI")
    @patch("wificauc.main.is_internet_available", return_value=False)
    def test_accept_need_portal_login(
        self,
        mock_online: MagicMock,
        _mock_ssid: MagicMock,
        _mock_iface: MagicMock,
        _mock_ip: MagicMock,
        _mock_cfg: MagicMock,
        mock_asyncio_run: MagicMock,
    ) -> None:
        from wificauc.portal import LoginResult

        mock_asyncio_run.return_value = LoginResult.performed_login()
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = cmd_once(MagicMock())
        out = buf.getvalue()
        self.assertEqual(code, 0)
        self.assertIn("need_portal_login", out)
        self.assertTrue(
            "login: success" in out
            or "login: already_logged_in" in out
            or "login: skipped" in out,
            out,
        )
        self.assertIn("192.168.4.252", out)
        mock_online.assert_called_once()

    def test_decide_three_outcomes(self) -> None:
        cfg = _cfg()
        with patch("wificauc.main.is_internet_available", return_value=False):
            self.assertEqual(decide_once_outcome(cfg, "Guest"), "wrong_wifi")
            self.assertEqual(
                decide_once_outcome(cfg, "caucwifi", bind_ip="192.168.1.2"),
                "need_portal_login",
            )
        with patch("wificauc.main.is_internet_available", return_value=True):
            self.assertEqual(
                decide_once_outcome(cfg, "CAUC-WIFI", bind_ip="192.168.1.2"),
                "already_online",
            )

    @patch("wificauc.main.is_internet_available", return_value=False)
    @patch("wificauc.main.probe_portal_reachable", return_value=False)
    def test_portal_fallback_when_ssid_hidden(
        self,
        _mock_portal: MagicMock,
        _mock_online: MagicMock,
    ) -> None:
        cfg = _cfg()
        self.assertEqual(decide_once_outcome(cfg, None, bind_ip=None), "need_portal_login")

    @patch("wificauc.main.probe_portal_reachable", return_value=None)
    def test_wrong_wifi_when_ssid_hidden_and_portal_down(
        self,
        _mock_portal: MagicMock,
    ) -> None:
        cfg = _cfg()
        self.assertEqual(decide_once_outcome(cfg, None), "wrong_wifi")


class TestM02LiveSmoke(unittest.TestCase):
    """本机冒烟：能读到 SSID 时 once 必须给出三种输出之一。"""

    @unittest.skipUnless(sys.platform == "darwin", "macOS only")
    @patch.dict("os.environ", {"WIFICAUC_SKIP_LOGIN": "1"})
    def test_live_once_exits_zero_with_known_output(self) -> None:
        project_root = __import__("pathlib").Path(__file__).resolve().parents[1]
        proc = subprocess.run(
            [sys.executable, "-m", "wificauc.main", "once"],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=60,
            env={**__import__("os").environ, "WIFICAUC_SKIP_LOGIN": "1"},
        )
        combined = proc.stdout + proc.stderr
        self.assertIn(proc.returncode, (0, 1), combined)
        ok_outputs = (
            "skipped: wrong wifi",
            "skipped: already online",
            "need_portal_login",
            "login: success",
            "login: failed",
        )
        self.assertTrue(
            any(line in combined for line in ok_outputs),
            f"unexpected output:\n{combined}",
        )


if __name__ == "__main__":
    unittest.main()
