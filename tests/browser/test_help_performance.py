"""The "?" windows and the editor never hanging (the gpu-studio standard, §5 help and §9a)."""

from __future__ import annotations

import re
import time

from playwright.sync_api import expect


def test_the_question_mark_opens_a_small_window_not_the_guide(page):
    page.open("voice/kasia/train")
    pages_before = len(page.context.pages)
    help_button = page.locator("pvc-step-train [data-step-help] [data-help-button]")
    help_button.click()
    window = page.locator("pvc-step-train [data-help-pop]")
    expect(window).to_contain_text("Trening")
    expect(window).to_contain_text("Uczy Pipera głosu")
    assert len(page.context.pages) == pages_before  # no new tab
    expect(window.locator("[data-help-more]")).to_have_attribute("href", "/docs/pl/training/")
    page.keyboard.press("Escape")
    expect(window).to_have_count(0)
    help_button.click()
    page.mouse.click(5, 880)  # beside it
    expect(window).to_have_count(0)
    help_button.click()
    page.locator("pvc-step-train [data-help-close]").click()
    expect(window).to_have_count(0)
    help_button.click()
    help_button.click()  # "?" again closes it
    expect(window).to_have_count(0)


def test_the_job_card_has_its_own_help(page):
    page.open()
    page.locator("[data-job-help] [data-help-button]").click()
    expect(page.locator("[data-job-help] [data-help-pop]")).to_contain_text("Zatrzymaj")


def test_only_the_top_bar_opens_the_guide(page):
    page.open("voice/kasia")
    with page.context.expect_page() as guide:
        page.locator("[data-docs]").click()
    assert guide.value.url.endswith("/docs/pl/")
    guide.value.close()


def test_one_state_question_at_a_time_on_a_slow_server(page):
    page.open()
    in_flight = {"now": 0, "most": 0, "count": 0}

    def slow(route):
        in_flight["now"] += 1
        in_flight["count"] += 1
        in_flight["most"] = max(in_flight["most"], in_flight["now"])
        time.sleep(3)  # slower than the 2 s between questions
        in_flight["now"] -= 1
        route.continue_()

    page.route("**/api/state", slow)
    page.wait_for_timeout(9000)
    page.unroute("**/api/state")
    assert in_flight["count"] >= 2 and in_flight["most"] == 1


def test_a_tab_in_the_background_asks_nothing(page):
    page.open()
    asked = []
    page.on("request", lambda request: "/api/state" in request.url and asked.append(request.url))
    page.evaluate(
        """() => {
          Object.defineProperty(document, 'hidden', {configurable: true, get: () => true});
          document.dispatchEvent(new Event('visibilitychange'));
        }"""
    )
    page.wait_for_timeout(2500)
    asked.clear()
    page.wait_for_timeout(5000)
    assert asked == []
    page.evaluate(
        """() => {
          Object.defineProperty(document, 'hidden', {configurable: true, get: () => false});
          document.dispatchEvent(new Event('visibilitychange'));
        }"""
    )
    page.wait_for_timeout(1000)
    assert asked  # back in front: it asks at once


def test_a_question_without_an_answer_ends_with_a_message(page):
    page.open()
    page.evaluate("window.pvcRequestTimeoutMs = 1500")
    page.route("**/api/state", lambda route: None)  # never answered
    expect(page.locator("[data-notice='error']")).to_contain_text(
        re.compile("nie odpowiedział w ciągu 2 s"), timeout=10000
    )
    page.unroute("**/api/state")
    page.evaluate("window.pvcRequestTimeoutMs = undefined")
    expect(page.locator("[data-notice='error']")).to_have_count(0, timeout=10000)  # answers again: it goes


def test_every_view_on_big_data_without_a_long_task(page, demo):
    import sys

    sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "dev"))
    import demo as demo_mod
    import tfevents

    from piper_voice_cloner import config as config_mod

    root = demo[1]
    for i in range(40):  # many voices
        config_mod.save(root / "voices" / f"glos_{i:02d}", config_mod.VoiceConfig(name=f"glos_{i:02d}"))
    tfevents.training(
        root / "voices" / "kasia" / "train", 0, 2000, demo_mod.SENTENCES[:2], every=2
    )  # 1000 epochs
    jobs = root / "jobs"
    for i in range(120):  # a long job history
        (jobs / f"202611{10 + i // 60:02d}-{i % 24:02d}{i % 60:02d}00-train-kasia.log").write_text("x\n")
    page.add_init_script(
        """window.longTasks = [];
        new PerformanceObserver((list) => list.getEntries().forEach((e) => window.longTasks.push(e.duration)))
          .observe({type: 'longtask', buffered: true});"""
    )
    page.open("voice/kasia")
    views = [
        "voice/kasia/import", "voice/kasia/train", "voice/kasia/export", "voice/kasia/settings",
        "voice/ola_bajka/reference", "voice/ola_bajka/corpus", "voice/ola_bajka/audition",
        "voice/ola_bajka/synthesize", "voice/alicja/filter", "base/prepare", "base/score", "base/train",
        "base/compare", "base/select", "jobs/current", "jobs/queue", "jobs/history",
        "settings/elevenlabs", "settings/home_assistant", "settings/editor",
    ]  # fmt: skip
    for view in views:
        page.evaluate(f"location.hash = {view!r}")
        page.wait_for_timeout(400)
    page.locator("[data-search]").fill("glos_3")
    page.wait_for_timeout(300)
    longest = max(page.evaluate("window.longTasks") or [0])
    assert longest < 500, f"a long task of {longest:.0f} ms"
