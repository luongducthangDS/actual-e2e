"""Fixtures: a fresh Actual server + fresh browser context per test, Playwright trace kept on failure.

Each test gets its own server and data directory, so tests are order-independent and run in parallel with
pytest-xdist (`-n 2`) without sharing state.
"""
import os
import shutil
import socket
import subprocess
import tempfile
import time
from pathlib import Path

import pytest
import requests
from playwright.sync_api import sync_playwright

from pages.app import LoginPage

SUT = Path(os.getenv("ACTUAL_DIR", "../sut")).resolve() / "node_modules" / ".bin" / "actual-server"
PASSWORD = "e2e-Password-1"
ARTIFACTS = Path(__file__).resolve().parents[1] / "artifacts"


class ActualServer:
    def __init__(self):
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            self.port = s.getsockname()[1]
        self.data = Path(tempfile.mkdtemp(prefix="actual-e2e-"))
        env = {**os.environ, "ACTUAL_HOSTNAME": "127.0.0.1", "ACTUAL_PORT": str(self.port),
               "ACTUAL_DATA_DIR": str(self.data)}
        self.proc = subprocess.Popen([str(SUT)], cwd=self.data, env=env,
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.url = f"http://127.0.0.1:{self.port}"
        for _ in range(150):
            try:
                requests.get(self.url + "/info", timeout=1)
                return
            except requests.ConnectionError:
                time.sleep(0.2)
        raise RuntimeError("Actual server did not start")

    def stop(self):
        self.proc.terminate()
        self.proc.wait(timeout=10)
        shutil.rmtree(self.data, ignore_errors=True)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    setattr(item, "rep_" + outcome.get_result().when, outcome.get_result())


@pytest.fixture(scope="session")
def browser():
    with sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


@pytest.fixture
def server():
    s = ActualServer()
    yield s
    s.stop()


@pytest.fixture
def page(browser, server, request):
    ctx = browser.new_context(viewport={"width": 1500, "height": 950})
    ctx.tracing.start(screenshots=True, snapshots=True)
    pg = ctx.new_page()
    pg.set_default_timeout(20_000)
    yield pg
    failed = getattr(request.node, "rep_call", None) and request.node.rep_call.failed
    if failed:
        ARTIFACTS.mkdir(exist_ok=True)
        ctx.tracing.stop(path=ARTIFACTS / f"{request.node.name}.zip")   # open with: playwright show-trace <zip>
    else:
        ctx.tracing.stop()
    ctx.close()


@pytest.fixture
def budget(page, server):
    """Logged-in user with a brand-new budget file: the starting point of most journeys."""
    requests.post(server.url + "/account/bootstrap", json={"password": PASSWORD}, timeout=10)
    login = LoginPage(page, server.url)
    login.login(PASSWORD)
    return login.start_new_budget()
