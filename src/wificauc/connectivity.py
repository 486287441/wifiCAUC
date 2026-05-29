from __future__ import annotations

import http.client
import socket
import urllib.error
import urllib.request
from urllib.parse import urlparse

_PORTAL_BODY_MARKERS = ("DDDDD", 'name="upass"', "eportal")
_PORTAL_LOGIN_FORM_MARKERS = ('name="DDDDD"', "name='DDDDD'", 'name="upass"')


def _decode_http_body(raw: bytes) -> str:
    """Campus portal pages commonly use GB2312/GB18030."""
    for encoding in ("gb18030", "gb2312", "utf-8"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def _body_has_login_form(body: str) -> bool:
    """存在登录按钮 0MKKey 时视为未登录（优先于 JS 注释里的「登录成功」）。"""
    has_submit = 'name="0MKKey"' in body or "name='0MKKey'" in body
    has_fields = "DDDDD" in body and "upass" in body
    return has_submit and has_fields


def _body_indicates_logged_in(body: str, success_text: str | None) -> bool:
    """已登录：成功文案或注销页；勿匹配 JS 注释中的「登录成功」。"""
    if _body_has_login_form(body):
        return False
    if success_text and success_text in body:
        return True
    lowered = body.lower()
    if 'name="logout"' in lowered or "name='logout'" in lowered:
        return True
    if "logout page" in lowered or "注销页" in body:
        return True
    return False


def portal_host_from_url(portal_url: str) -> str:
    host = urlparse(portal_url).hostname
    if not host:
        raise ValueError(f"无法从门户 URL 解析主机：{portal_url}")
    return host


def _host_matches_portal(host: str | None, portal_host: str) -> bool:
    if not host:
        return False
    return host.lower() == portal_host.lower()


def _body_looks_like_portal(body: str, portal_host: str) -> bool:
    if portal_host in body:
        return True
    return any(marker in body for marker in _PORTAL_BODY_MARKERS)


def _urlopen(
    url: str,
    timeout: float,
    bind_ip: str | None,
):
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (compatible; wifiCAUC/0.1)"},
    )
    parsed = urlparse(url)
    if bind_ip and parsed.scheme == "http":

        class BoundHTTPHandler(urllib.request.HTTPHandler):
            def http_open(self, inner_req: urllib.request.Request) -> http.client.HTTPResponse:
                def factory(host: str, **kwargs: object) -> http.client.HTTPConnection:
                    return http.client.HTTPConnection(
                        host,
                        timeout=timeout,
                        source_address=(bind_ip, 0),
                    )

                return self.do_open(factory, inner_req)

        opener = urllib.request.build_opener(BoundHTTPHandler)
        return opener.open(req, timeout=timeout)

    return urllib.request.urlopen(req, timeout=timeout)


def _probe_url(
    url: str,
    portal_host: str,
    timeout: float,
    *,
    bind_ip: str | None = None,
    success_text: str | None = None,
    trust_captive_success: bool = True,
) -> bool | None:
    """
    Probe one URL. True = online, False = captive/portal, None = inconclusive.
    """
    try:
        with _urlopen(url, timeout, bind_ip) as resp:
            final_url = resp.geturl()
            body = _decode_http_body(resp.read(65536))
            status = resp.status
    except urllib.error.HTTPError as exc:
        final_url = exc.geturl()
        body = _decode_http_body(exc.read(65536)) if exc.fp else ""
        status = exc.code
    except (urllib.error.URLError, TimeoutError, OSError, socket.error):
        return None

    # 先判断登录表单，避免登录页 JS 里的「登录成功」误判为已上网
    if _body_has_login_form(body):
        return False
    if _body_indicates_logged_in(body, success_text):
        return True

    final_host = urlparse(final_url).hostname
    if _host_matches_portal(final_host, portal_host) or _body_looks_like_portal(
        body, portal_host
    ):
        return False

    if trust_captive_success and "Success" in body:
        return True
    if trust_captive_success and status == 200:
        return True
    return None


def _check_portal_clash_mode(
    portal_url: str,
    portal_host: str,
    *,
    success_text: str | None,
    bind_ip: str | None,
    timeout: float,
) -> bool:
    """
    Clash-compatible: only trust the campus portal page, never captive.apple.com.

    - Success text on portal → already logged in
    - Login form on portal → need login
    - Portal unreachable → need login (do not trust proxy tunnel)
    """
    result = _probe_url(
        portal_url,
        portal_host,
        timeout,
        bind_ip=bind_ip,
        success_text=success_text,
        trust_captive_success=False,
    )
    return result is True


def probe_portal_reachable(
    portal_url: str,
    portal_host: str,
    *,
    success_text: str | None = None,
    bind_ip: str | None = None,
    timeout: float = 3.0,
) -> bool | None:
    """Return True/False if portal responds; None if unreachable."""
    return _probe_url(
        portal_url,
        portal_host,
        timeout,
        bind_ip=bind_ip,
        success_text=success_text,
        trust_captive_success=False,
    )


def is_internet_available(
    urls: list[str],
    portal_host: str,
    *,
    portal_url: str | None = None,
    success_text: str | None = None,
    bind_ip: str | None = None,
    timeout: float = 3.0,
    clash_compatible: bool = False,
) -> bool:
    """
    Return True if probes indicate campus portal session is already authenticated.

    clash_compatible=True (default in config):
      - Only probes portal_url via Wi-Fi bind IP
      - Ignores captive.apple.com (Clash TUN often fakes Success)
    """
    portal_host = portal_host.strip()

    if clash_compatible:
        if not portal_url:
            return False
        return _check_portal_clash_mode(
            portal_url,
            portal_host,
            success_text=success_text,
            bind_ip=bind_ip,
            timeout=timeout,
        )

    if not urls and not portal_url:
        return False

    saw_definite_offline = False

    if portal_url:
        portal_result = _probe_url(
            portal_url,
            portal_host,
            timeout,
            bind_ip=bind_ip,
            success_text=success_text,
        )
        if portal_result is True:
            return True
        if portal_result is False:
            return False

    for url in urls:
        result = _probe_url(
            url,
            portal_host,
            timeout,
            bind_ip=bind_ip,
            success_text=success_text,
        )
        if result is True:
            return True
        if result is False:
            saw_definite_offline = True

    if saw_definite_offline:
        return False
    return False
