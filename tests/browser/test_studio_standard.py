"""The gpu-studio standard in the browser: login, the top bar, the power-off countdown, the draft."""

from __future__ import annotations

import re
import sys

from playwright.sync_api import expect
import pytest

REPO_DEV = __import__("pathlib").Path(__file__).resolve().parents[2] / "dev"


@pytest.fixture
def login_demo(tmp_path, monkeypatch, request):
    """The demo editor with a password: (base url)."""
    import socket
    import threading
    import time

    sys.path.insert(0, str(REPO_DEV))
    import demo as demo_mod
    import uvicorn

    from piper_voice_cloner.editor.auth import Login, parse_networks
    from piper_voice_cloner.editor.server import create_app

    root = demo_mod.build(tmp_path / "data")
    networks = parse_networks(getattr(request, "param", ""))
    app = create_app(
        root, login=Login("demo", "demo", "secret"), gpu=False, countdown=False, trusted_networks=networks
    )
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    threading.Thread(target=server.run, daemon=True).start()
    while not server.started:
        time.sleep(0.02)
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True


def test_login_card_then_the_editor_and_the_menu(browser, login_demo):
    page = browser.new_page()
    page.add_init_script("localStorage.setItem('pvc-studio-tour', 'done')")  # the tour is tested on its own
    page.goto(f"{login_demo}/#voice/kasia")
    expect(page).to_have_url(re.compile("/login"))
    page.locator("input[name=user]").fill("demo")
    page.locator("input[name=password]").fill("wrong")
    page.locator("button[type=submit]").click()
    expect(page.locator("[data-login-error]")).to_be_visible()
    page.locator("input[name=user]").fill("demo")
    page.locator("input[name=password]").fill("demo")
    page.locator("button[type=submit]").click()
    page.wait_for_function("window.editorReady === true")
    page.locator("[data-menu]").click()
    expect(page.locator("[data-menu-user]")).to_contain_text("demo")
    page.locator("[data-logout]").click()
    expect(page).to_have_url(re.compile("/login"))
    page.close()


@pytest.mark.parametrize("login_demo", ["127.0.0.0/8"], indirect=True)
def test_a_trusted_network_opens_without_login_and_has_no_log_out(browser, login_demo):
    page = browser.new_page()
    page.add_init_script("localStorage.setItem('pvc-studio-tour', 'done')")  # the tour is tested on its own
    page.goto(f"{login_demo}/login")
    expect(page).not_to_have_url(re.compile("/login"))
    page.wait_for_function("window.editorReady === true")
    page.locator("[data-menu]").click()
    expect(page.locator("[data-menu-trusted]")).to_contain_text("STUDIO_TRUSTED_NETWORKS")
    expect(page.locator("[data-logout]")).to_have_count(0)
    page.goto(f"{login_demo}/#settings/editor")
    page.wait_for_function("window.editorReady === true")
    expect(page.locator("[data-trusted-settings]")).to_be_visible()
    expect(page.locator("[data-logout-settings]")).to_have_count(0)
    page.close()


def test_top_bar_order_and_the_job_chip(page, demo):
    page.open()
    order = page.evaluate(
        """() => [...document.querySelector('pvc-editor').shadowRoot.querySelector('header.top').children]
              .map((el) => el.dataset ? Object.keys(el.dataset)[0] || el.className : '')"""
    )
    # ☰ first, then "?", then ⚙ last (⚙ sits in its own .menu-wrap with the box under it)
    wraps = [i for i, name in enumerate(order) if name == "menu-wrap"]
    assert wraps[0] < order.index("docs") < wraps[-1] == len(order) - 1
    expect(page.locator("header.top > .menu-wrap:last-child [data-editor-settings]")).to_have_count(1)
    import os

    os.environ["FAKE_PVC_SPEED"] = "1"
    demo[2].state.start("train", "kasia", ["train", "kasia"])
    expect(page.locator("[data-top-job]")).to_contain_text("Trening · kasia")
    expect(page.locator("[data-top-machine]")).to_contain_text("71°")
    demo[2].state.jobs["current"].stop()


def test_power_off_counts_down_and_can_be_cancelled(page, demo, no_real_poweroff):
    app = demo[2]
    app.state.machine.ready = lambda: True  # pretend Home Assistant is set up
    app.state.start("filter", "alicja", ["filter", "alicja"], poweroff=True)
    app.state.jobs["current"].wait(30)
    page.open()
    countdown = page.locator("[data-countdown]")
    expect(countdown).to_contain_text(re.compile(r"Wyłączenie za [12]:\d\d"))
    countdown.locator("[data-countdown-cancel]").click()
    expect(page.locator("[data-countdown]")).to_have_count(0)
    assert no_real_poweroff == []
    # the countdown that runs out switches the machine off through Home Assistant (here: the fake)
    app.state.start("filter", "alicja", ["filter", "alicja"], poweroff=True)
    app.state.jobs["current"].wait(30)
    timer = app.state.power_timer
    timer.check()
    timer.check(now=timer.at + 1)
    assert no_real_poweroff == ["power_off"]


def test_stop_never_powers_off(page, demo, no_real_poweroff):
    import os

    os.environ["FAKE_PVC_SPEED"] = "1"
    app = demo[2]
    app.state.start("train", "kasia", ["train", "kasia"], poweroff=True)
    app.state.jobs["current"].stop()
    app.state.jobs["current"].wait(30)
    app.state.power_timer.check()
    assert app.state.power_timer.at is None
    page.open()
    expect(page.locator("[data-countdown]")).to_have_count(0)


def test_one_field_is_one_line_of_the_diff_and_the_draft_survives(page, demo):
    page.open("voice/kasia/settings")
    page.locator("[data-field='quality.max_cer'] input").fill("0.05")
    expect(page.locator("[data-settings-state]")).to_have_text(re.compile("Szkic zapisany"), timeout=5000)
    page.reload()
    page.wait_for_function("window.editorReady === true")
    expect(page.locator("[data-field='quality.max_cer'] input")).to_have_value("0.05")  # from the server
    page.locator("[data-save]").click()
    lines = page.locator("[data-save-dialog] [data-diff-line]")
    expect(lines).to_have_count(2)
    expect(page.locator("[data-diff-line='-']")).to_contain_text("max_cer: 0.04")
    expect(page.locator("[data-diff-line='+']")).to_contain_text("max_cer: 0.05")
    page.locator("[data-save-note]").fill("ostrzejszy filtr")
    page.locator("[data-save-confirm]").click()
    expect(page.locator("[data-settings-notice]")).to_be_visible()
    text = (demo[1] / "voices" / "kasia" / "voice.yaml").read_text()
    assert "max_cer: 0.05" in text
    page.locator("[data-history]").click()
    expect(page.locator("[data-history-dialog]")).to_contain_text("ostrzejszy filtr")


def test_a_conflict_asks_before_saving(page, demo):
    page.open("voice/kasia/settings")
    page.locator("[data-field='target_clips'] input").fill("1500")
    voice = demo[1] / "voices" / "kasia" / "voice.yaml"
    voice.write_text(voice.read_text().replace("batch_size: 32", "batch_size: 24"))  # changed elsewhere
    page.locator("[data-save]").click()
    page.locator("[data-save-confirm]").click()
    expect(page.locator("[data-save-error]")).to_contain_text("zmienił się gdzie indziej")
    page.locator("[data-save-force]").click()
    expect(page.locator("[data-settings-notice]")).to_be_visible()


def test_a_slow_draft_save_never_overlaps_and_the_last_change_wins(page, demo):
    page.open("voice/kasia/settings")
    saves = {"now": 0, "most": 0, "bodies": []}

    def slow(route):
        if route.request.method != "PUT":
            route.continue_()
            return
        saves["now"] += 1
        saves["most"] = max(saves["most"], saves["now"])
        saves["bodies"].append(route.request.post_data_json["text"])
        page.wait_for_timeout(1500)
        saves["now"] -= 1
        route.continue_()

    page.route("**/settings/draft", slow)
    field = page.locator("[data-field='target_clips'] input")
    for value in ("1501", "1502", "1503", "1504"):
        field.fill(value)
        page.wait_for_timeout(900)
    page.wait_for_timeout(4000)
    page.unroute("**/settings/draft")
    assert saves["most"] == 1, saves["most"]
    assert 1 <= len(saves["bodies"]) < 4, len(saves["bodies"])
    assert "target_clips: 1504" in saves["bodies"][-1]
    draft = (demo[1] / "voices" / "kasia" / ".draft.json").read_text()
    assert "target_clips: 1504" in draft
    expect(page.locator("[data-settings-state]")).to_have_text(re.compile("Szkic zapisany"))


def test_a_failed_draft_save_says_so_and_does_not_stay_saving(page):
    page.open("voice/kasia/settings")
    page.route("**/settings/draft", lambda route: route.fulfill(status=500, body="boom"))
    page.locator("[data-field='target_clips'] input").fill("1500")
    expect(page.locator("[data-settings-state]")).to_have_attribute(
        "data-settings-state", "error", timeout=5000
    )
    page.unroute("**/settings/draft")
    page.locator("[data-field='target_clips'] input").fill("1501")  # the next change tries again
    expect(page.locator("[data-settings-state]")).to_have_text(re.compile("Szkic zapisany"), timeout=5000)
    page.errors[:] = [error for error in page.errors if "status of 500" not in error]  # the failure we made
