from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from wificauc.config import AppConfig, PortalSelectors
from wificauc.connectivity import is_internet_available, portal_host_from_url
from wificauc.main import decide_once_outcome
from wificauc.wifi import (
    get_current_ssid,
    is_target_wifi,
    normalize_ssid,
    resolve_wifi_interface,
)


def _sample_config(**overrides) -> AppConfig:
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
    base.update(overrides)
    return AppConfig(**base)


class TestWifi(unittest.TestCase):
    def test_normalize_ssid(self) -> None:
        self.assertEqual(normalize_ssid("CAUC-WIFI"), "caucwifi")
        self.assertEqual(normalize_ssid("caucwifi"), "caucwifi")

    def test_is_target_wifi_normalized(self) -> None:
        self.assertTrue(is_target_wifi("caucwifi", "CAUC-WIFI", match_mode="normalized"))
        self.assertTrue(is_target_wifi("CAUC-WIFI", "CAUC-WIFI", match_mode="strict"))
        self.assertFalse(is_target_wifi("Other", "CAUC-WIFI"))
        self.assertFalse(is_target_wifi(None, "CAUC-WIFI"))

    @patch("wificauc.wifi.subprocess.run")
    def test_get_current_ssid_parses_english(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Current Wi-Fi Network: CAUC-WIFI\n",
        )
        self.assertEqual(get_current_ssid("en0"), "CAUC-WIFI")

    @patch("wificauc.wifi.find_wifi_interface", return_value="en0")
    def test_resolve_wifi_interface_auto(self, _mock_find: MagicMock) -> None:
        self.assertEqual(resolve_wifi_interface("auto"), "en0")

    @patch("wificauc.wifi._get_ssid_via_airport", return_value=None)
    @patch("wificauc.wifi.subprocess.run")
    def test_get_current_ssid_not_associated(
        self,
        mock_run: MagicMock,
        _mock_airport: MagicMock,
    ) -> None:
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="You are not associated with an AirPort network.\n",
        )
        self.assertIsNone(get_current_ssid("en0"))

    @patch("wificauc.wifi._get_ssid_via_networksetup", return_value=None)
    @patch("wificauc.wifi._get_ssid_via_airport", return_value="caucwifi")
    def test_get_current_ssid_airport_fallback(self, *_mocks: MagicMock) -> None:
        self.assertEqual(get_current_ssid("en0"), "caucwifi")


class TestConnectivity(unittest.TestCase):
    def test_portal_host_from_url(self) -> None:
        self.assertEqual(portal_host_from_url("http://192.168.4.252/"), "192.168.4.252")

    @patch("wificauc.connectivity._urlopen")
    def test_clash_mode_ignores_fake_captive_success(self, mock_urlopen: MagicMock) -> None:
        resp = MagicMock()
        resp.__enter__.return_value = resp
        resp.geturl.return_value = "http://captive.apple.com/hotspot-detect.html"
        resp.status = 200
        resp.read.return_value = b"Success"
        mock_urlopen.return_value = resp

        login_resp = MagicMock()
        login_resp.__enter__.return_value = login_resp
        login_resp.geturl.return_value = "http://192.168.4.252/"
        login_resp.status = 200
        login_resp.read.return_value = b'<input name="DDDDD">'

        mock_urlopen.side_effect = [resp, login_resp]

        self.assertFalse(
            is_internet_available(
                ["http://captive.apple.com/hotspot-detect.html"],
                "192.168.4.252",
                portal_url="http://192.168.4.252/",
                clash_compatible=True,
            )
        )
        mock_urlopen.assert_called_once()

    @patch("wificauc.connectivity._urlopen")
    def test_apple_success_means_online(self, mock_urlopen: MagicMock) -> None:
        resp = MagicMock()
        resp.__enter__.return_value = resp
        resp.geturl.return_value = "http://captive.apple.com/hotspot-detect.html"
        resp.status = 200
        resp.read.return_value = b"<HTML><HEAD><TITLE>Success</TITLE></HEAD><BODY>Success</BODY></HTML>"
        mock_urlopen.return_value = resp

        self.assertTrue(
            is_internet_available(
                ["http://captive.apple.com/hotspot-detect.html"],
                "192.168.4.252",
                clash_compatible=False,
            )
        )

    @patch("wificauc.connectivity._urlopen")
    def test_portal_login_page_means_offline(self, mock_urlopen: MagicMock) -> None:
        resp = MagicMock()
        resp.__enter__.return_value = resp
        resp.geturl.return_value = "http://192.168.4.252/"
        resp.status = 200
        resp.read.return_value = b'<input name="DDDDD">'
        mock_urlopen.return_value = resp

        self.assertFalse(
            is_internet_available(
                ["http://captive.apple.com/hotspot-detect.html"],
                "192.168.4.252",
                portal_url="http://192.168.4.252/",
            )
        )
        mock_urlopen.assert_called_once()

    @patch("wificauc.connectivity._urlopen")
    def test_portal_success_text_means_online(self, mock_urlopen: MagicMock) -> None:
        resp = MagicMock()
        resp.__enter__.return_value = resp
        resp.geturl.return_value = "http://192.168.4.252/"
        resp.status = 200
        resp.read.return_value = "您已经成功登录".encode()
        mock_urlopen.return_value = resp

        self.assertTrue(
            is_internet_available(
                [],
                "192.168.4.252",
                portal_url="http://192.168.4.252/",
                success_text="您已经成功登录",
            )
        )


class TestOnceOutcome(unittest.TestCase):
    @patch("wificauc.main.is_internet_available")
    def test_wrong_wifi(self, mock_online: MagicMock) -> None:
        cfg = _sample_config()
        self.assertEqual(decide_once_outcome(cfg, "Other-WiFi"), "wrong_wifi")
        mock_online.assert_not_called()

    @patch("wificauc.main.is_internet_available", return_value=True)
    def test_already_online_caucwifi_alias(self, mock_online: MagicMock) -> None:
        cfg = _sample_config()
        self.assertEqual(decide_once_outcome(cfg, "caucwifi"), "already_online")
        mock_online.assert_called_once()

    @patch("wificauc.main.is_internet_available", return_value=False)
    def test_need_portal_login(self, _mock_online: MagicMock) -> None:
        cfg = _sample_config()
        self.assertEqual(decide_once_outcome(cfg, "CAUC-WIFI"), "need_portal_login")


if __name__ == "__main__":
    unittest.main()
