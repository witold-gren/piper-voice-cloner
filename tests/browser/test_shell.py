"""The editor's shell: tree, search, folding, theme, language, new voice, the job card."""

from __future__ import annotations

import re

from playwright.sync_api import expect


def test_tree_shows_voices_with_the_steps_of_their_way(page):
    page.open("voice/kasia")
    expect(page.locator("[data-node='voice/kasia']")).to_have_class(re.compile(r"\bsel\b"))
    # kasia has its own recordings: import, training, export (+ the voice's settings)
    expect(page.locator("[data-node^='voice/kasia/']")).to_have_count(4)
    expect(page.locator("[data-node='voice/kasia/import']")).to_contain_text("Import")
    # other voices stay folded until opened
    expect(page.locator("[data-node^='voice/alicja/']")).to_have_count(0)
    page.locator("[data-fold='voice/alicja']").click()
    expect(page.locator("[data-node^='voice/alicja/']")).to_have_count(8)
    expect(page.locator("[data-voice-overview='kasia'] [data-overview-step]")).to_have_count(3)


def test_search_finds_steps_and_unfolds(page):
    page.open()
    page.locator("[data-search]").fill("filtr")
    expect(page.locator("[data-node='voice/alicja/filter']")).to_be_visible()
    expect(page.locator("[data-node='voice/kasia']")).to_have_count(0)


def test_overview_step_opens_the_step(page):
    page.open("voice/alicja")
    page.locator("[data-overview-step='filter']").click()
    expect(page.locator("[data-node='voice/alicja/filter']")).to_have_class(re.compile(r"\bsel\b"))
    assert page.evaluate("location.hash") == "#voice%2Falicja%2Ffilter"


def test_theme_and_language_switch_and_are_remembered(page):
    page.open()
    shell = page.locator("pvc-editor")
    page.locator("[data-theme-button]").click()  # auto -> light
    expect(shell).to_have_attribute("data-theme", "light")
    page.locator("[data-theme-button]").click()  # -> dark
    expect(shell).to_have_attribute("data-theme", "dark")
    expect(page.locator("header h1")).to_have_text("Edytor głosów")
    page.locator("[data-editor-settings]").click()  # ⚙: look and language
    page.locator("[data-language-option='en']").click()
    expect(page.locator("header h1")).to_have_text("Voice editor")
    page.reload()
    page.wait_for_function("window.editorReady === true")
    expect(page.locator("header h1")).to_have_text("Voice editor")
    expect(shell).to_have_attribute("data-theme", "dark")


def test_new_voice_asks_the_way_first(page, demo):
    page.open()
    page.locator("[data-new-voice-button]").click()
    dialog = page.locator("[data-new-voice]")
    expect(dialog.locator("[data-workflow='clone']")).to_have_attribute("aria-pressed", "true")
    dialog.locator("[data-workflow='import']").click()
    dialog.locator("[data-new-name]").fill("Kuba Bajka")
    dialog.locator("[data-new-create]").click()
    expect(page.locator("[data-new-voice]")).to_have_count(0)
    expect(page.locator("[data-node='voice/kuba_bajka/import']")).to_have_class(re.compile(r"\bsel\b"))
    assert (demo[1] / "voices" / "kuba_bajka" / "voice.yaml").read_text().count("workflow: import") == 1
    # the same name again is refused in the window
    page.locator("[data-new-voice-button]").click()
    page.locator("[data-new-name]").fill("kuba_bajka")
    page.locator("[data-new-create]").click()
    expect(page.locator("[data-new-error]")).to_contain_text("already exists")


def test_job_card_follows_a_job_and_stops_it(page, demo):
    page.open()
    expect(page.locator("[data-job='current']")).to_have_attribute("data-state", "idle")
    expect(page.locator("[data-gpu]")).to_contain_text("RTX 4090")
    expect(page.locator("[data-ring='temp']")).to_contain_text("71°")
    import os

    os.environ["FAKE_PVC_SPEED"] = "1"  # slow enough to see it running
    demo[2].state.start("train", "kasia", ["train", "kasia"])
    expect(page.locator("[data-job='current']")).to_have_attribute("data-state", "running")
    expect(page.locator("[data-top-job]")).to_contain_text("Trening · kasia")
    expect(page.locator("[data-progress]")).to_contain_text("epok", timeout=10000)
    expect(page.locator("[data-log]")).to_contain_text("training epochs")
    page.locator("[data-stop='current']").click()
    expect(page.locator("[data-job='current']")).to_have_attribute("data-state", "stopped", timeout=10000)
    expect(page.locator("[data-job-state]")).to_contain_text("Zatrzymane")


def test_enlarged_log_and_copy(page, demo):
    demo[2].state.start("filter", "alicja", ["filter", "alicja"])
    demo[2].state.jobs["current"].wait(20)
    page.open()
    expect(page.locator("[data-log]")).to_contain_text("filter: done")
    page.locator("[data-log-enlarge]").click()
    expect(page.locator("[data-log-dialog]")).to_contain_text("filter: done")
    page.keyboard.press("Escape")
    page.locator("[data-log-dialog] button").first.click()
    expect(page.locator("[data-log-dialog]")).to_have_count(0)
    page.locator("[data-log-copy]").click()
    expect(page.locator("[data-log-copy]")).to_contain_text("Skopiowano")


def test_splitter_resizes_and_double_click_resets(page):
    page.open()
    tree = page.locator("[data-tree]")
    before = tree.bounding_box()["width"]
    bar = page.locator("[data-splitter='left']").bounding_box()
    page.mouse.move(bar["x"] + 3, bar["y"] + 200)
    page.mouse.down()
    page.mouse.move(bar["x"] + 120, bar["y"] + 200, steps=5)
    page.mouse.up()
    assert tree.bounding_box()["width"] > before + 80
    page.locator("[data-splitter='left']").dblclick()
    assert abs(tree.bounding_box()["width"] - before) < 2


def test_the_overview_shows_the_next_step(page):
    page.open("voice/ola_bajka")
    expect(page.locator("[data-next-step]")).to_have_attribute("data-next-step", "filter")
    page.locator("[data-next-step]").click()
    expect(page.locator("[data-node='voice/ola_bajka/filter']")).to_have_class(re.compile(r"\bsel\b"))
    page.open("voice/kasia")
    expect(page.locator("[data-voice-ready]")).to_be_visible()


def test_side_columns_fold_by_button_and_keys_and_stay_folded(page):
    page.open("voice/kasia")
    middle = page.locator("[data-middle]")
    wide = middle.bounding_box()["width"]
    tree_width = page.locator("[data-tree]").bounding_box()["width"]
    page.locator("[data-fold-column='left']").click()
    expect(page.locator("[data-tree]")).to_have_count(0)
    expect(page.locator("[data-fold-bar='left']")).to_be_visible()
    assert middle.bounding_box()["width"] > wide + 150
    expect(page.locator("[data-splitter-folded]")).to_have_count(1)  # nothing to drag
    page.keyboard.press("ControlOrMeta+Alt+KeyB")  # the right one
    expect(page.locator("[data-side]")).to_have_count(0)
    expect(page.locator("[data-fold-bar='right']")).to_be_visible()
    page.reload()
    page.wait_for_function("window.editorReady === true")
    expect(page.locator("[data-fold-bar='left']")).to_be_visible()  # remembered
    expect(page.locator("[data-fold-bar='right']")).to_be_visible()
    page.keyboard.press("ControlOrMeta+KeyB")
    expect(page.locator("[data-tree]")).to_be_visible()
    assert abs(page.locator("[data-tree]").bounding_box()["width"] - tree_width) < 2  # its width came back
    page.locator("[data-unfold='right']").click()
    expect(page.locator("[data-side]")).to_be_visible()
    title = page.locator("[data-fold-column='left']").get_attribute("title")
    assert "Ctrl/⌘+B" in title


def test_a_narrow_window_starts_with_the_right_column_folded(browser, demo):
    context = browser.new_context(viewport={"width": 860, "height": 800})
    page = context.new_page()
    page.goto(f"{demo[0]}/")
    page.wait_for_function("window.editorReady === true")
    expect(page.locator("[data-fold-bar='right']")).to_be_visible()
    context.close()
