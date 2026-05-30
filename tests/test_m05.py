from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from wificauc.config import AppConfig, PortalSelectors
from wificauc.main import ssid_just_joined_target


class TestSsidJustJoinedTarget(unittest.TestCase):
    def test_false_when_still_off_target(self) -> None:
        self.assertFalse(
            ssid_just_joined_target("Other", "Other", "CAUC-WIFI", match_mode="normalized")
        )

    def test_false_when_already_on_target(self) -> None:
        self.assertFalse(
            ssid_just_joined_target(
                "CAUC-WIFI",
                "CAUC-WIFI",
                "CAUC-WIFI",
                match_mode="normalized",
            )
        )

    def test_true_when_joining_from_other(self) -> None:
        self.assertTrue(
            ssid_just_joined_target(
                "Other",
                "CAUC-WIFI",
                "CAUC-WIFI",
                match_mode="normalized",
            )
        )

    def test_true_on_first_poll_when_on_target(self) -> None:
        self.assertTrue(
            ssid_just_joined_target(
                None,
                "CAUC-WIFI",
                "CAUC-WIFI",
                match_mode="normalized",
            )
        )

    def test_normalized_match(self) -> None:
        self.assertTrue(
            ssid_just_joined_target(
                "guest",
                "cauc wifi",
                "CAUC-WIFI",
                match_mode="normalized",
            )
        )


class TestLaunchAgentFiles(unittest.TestCase):
    def test_plist_template_and_scripts_exist(self) -> None:
        root = Path(__file__).resolve().parents[1]
        self.assertTrue(
            (root / "launchd" / "com.wificauc.agent.plist.template").is_file()
        )
        self.assertTrue((root / "scripts" / "install-launchagent.sh").is_file())
        self.assertTrue((root / "scripts" / "uninstall-launchagent.sh").is_file())


class TestCmdRunExtraRound(unittest.TestCase):
    @patch("wificauc.main.time.sleep", side_effect=KeyboardInterrupt)
    @patch("wificauc.main.run_once")
    @patch("wificauc.main.get_current_ssid")
    @patch("wificauc.main.resolve_wifi_interface", return_value="en0")
    @patch("wificauc.main.is_paused", return_value=False)
    @patch("wificauc.main.load_config")
    def test_extra_round_when_joining_target_wifi(
        self,
        mock_load: MagicMock,
        _paused: MagicMock,
        _resolve: MagicMock,
        mock_ssid: MagicMock,
        mock_run_once: MagicMock,
        _sleep: MagicMock,
    ) -> None:
        mock_load.return_value = AppConfig(
            wifi_ssid="CAUC-WIFI",
            wifi_interface="auto",
            wifi_ssid_match="normalized",
            wifi_fallback_portal_detect=True,
            portal_url="http://192.168.4.252/",
            selectors=PortalSelectors("u", "p", "s"),
            success_text="您已经成功登录",
            username="u",
            password="p",
            poll_interval_seconds=20,
            connectivity_urls=[],
            connectivity_timeout_seconds=3.0,
            connectivity_bind_wifi=True,
            clash_compatible=True,
            headless=True,
            portal_timeout_seconds=30,
        )
        # First poll: None -> CAUC-WIFI triggers extra round in same iteration.
        mock_ssid.side_effect = ["CAUC-WIFI", "CAUC-WIFI"]

        from wificauc.main import cmd_run

        import argparse

        code = cmd_run(argparse.Namespace())
        self.assertEqual(code, 0)
        self.assertEqual(mock_run_once.call_count, 2)


if __name__ == "__main__":
    unittest.main()
