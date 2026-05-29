from __future__ import annotations

import unittest
from unittest import mock

from wificauc.connectivity import (
    _body_has_login_form,
    _body_indicates_logged_in,
    is_internet_available,
    portal_host_from_url,
)


class TestLogoutPageDetection(unittest.TestCase):
    def test_logout_page_is_logged_in_not_login_form(self) -> None:
        body = "<title>注销页</title><input name=\"logout\" type=\"button\">"
        self.assertTrue(_body_indicates_logged_in(body, "您已经成功登录"))
        self.assertFalse(_body_has_login_form(body))

    def test_login_form_page(self) -> None:
        body = '<input name="DDDDD"><input name="upass"><input name="0MKKey" type="submit">'
        self.assertFalse(_body_indicates_logged_in(body, "您已经成功登录"))
        self.assertTrue(_body_has_login_form(body))

    def test_login_page_js_comment_not_logged_in(self) -> None:
        body = (
            "<title>登录页</title>"
            "<!-- authsucc='Dr.COMWebLoginID_3.htm';//登录成功标志 -->"
            '<input name="DDDDD"><input name="upass"><input name="0MKKey" type="submit">'
        )
        self.assertFalse(_body_indicates_logged_in(body, "您已经成功登录"))
        self.assertTrue(_body_has_login_form(body))

    def test_clash_mode_online_on_logout_page(self) -> None:
        body = "<title>注销页</title>登录成功"
        host = portal_host_from_url("http://192.168.4.252/")

        class FakeResp:
            def __enter__(self):
                return self

            def __exit__(self, *args: object) -> None:
                pass

            def geturl(self) -> str:
                return "http://192.168.4.252/"

            def read(self, n: int) -> bytes:
                return body.encode("gb18030")

            status = 200

        import wificauc.connectivity as conn

        with mock.patch.object(conn, "_urlopen", return_value=FakeResp()):
            online = is_internet_available(
                [],
                host,
                portal_url="http://192.168.4.252/",
                success_text="您已经成功登录",
                clash_compatible=True,
            )
        self.assertTrue(online)


if __name__ == "__main__":
    unittest.main()
