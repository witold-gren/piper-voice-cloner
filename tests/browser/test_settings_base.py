"""Voice settings (form, YAML, undo, save, history), settings pages and the base model in the browser."""

from __future__ import annotations

import re

from playwright.sync_api import expect


def test_voice_settings_form_undo_save_and_history(page, demo):
    page.open("voice/kasia/settings")
    state = page.locator("[data-settings-state]")
    expect(state).to_have_attribute("data-settings-state", "clean")
    clips = page.locator("[data-field='target_clips'] input")
    clips.fill("1500")
    expect(state).to_have_attribute("data-settings-state", "draft")
    page.locator("[data-tab='yaml']").click()
    expect(page.locator("[data-yaml]")).to_have_value(re.compile("target_clips: 1500"))
    page.locator("[data-undo]").click()
    expect(state).to_have_attribute("data-settings-state", "clean")
    page.locator("[data-redo]").click()
    page.locator("[data-save]").click()
    page.locator("[data-save-confirm]").click()
    expect(page.locator("[data-settings-notice]")).to_contain_text("Zapisano")
    assert "target_clips: 1500" in (demo[1] / "voices" / "kasia" / "voice.yaml").read_text()
    page.locator("[data-history]").click()
    page.locator("[data-history-dialog] [data-restore]").first.click()
    expect(page.locator("[data-yaml]")).to_have_value(re.compile("target_clips: 2000"))
    expect(state).to_have_attribute("data-settings-state", "draft")


def test_broken_yaml_cannot_be_saved(page):
    page.open("voice/kasia/settings")
    page.locator("[data-tab='yaml']").click()
    page.locator("[data-yaml]").fill("name: [kasia")
    expect(page.locator("[data-yaml-error]")).to_be_visible()
    expect(page.locator("[data-save]")).to_be_disabled()


def test_workflow_switch_changes_the_tree(page):
    page.open("voice/ola_bajka/settings")
    page.locator("[data-field='workflow'] select").select_option("import")
    page.locator("[data-save]").click()
    page.locator("[data-save-confirm]").click()
    expect(page.locator("[data-node='voice/ola_bajka/import']")).to_be_visible(timeout=5000)
    expect(page.locator("[data-node='voice/ola_bajka/reference']")).to_have_count(0)


def test_rename_opens_the_renamed_voice(page, demo):
    page.open("voice/tomek/settings")
    page.locator("[data-rename-name]").fill("Tomek Nowy")
    page.locator("[data-rename-run]").click()
    expect(page.locator("[data-node='voice/tomek_nowy/settings']")).to_have_class(re.compile(r"\bsel\b"))
    assert (demo[1] / "voices" / "tomek_nowy" / "voice.yaml").is_file()


def test_settings_pages_keep_secrets_out(page):
    page.open("settings/elevenlabs")
    expect(page.locator("[data-el-key-state]")).to_contain_text("Brak klucza")
    page.locator("[data-el-key]").fill("sk_test_key_123")
    page.locator("[data-el-key-save]").click()
    expect(page.locator("[data-el-key-state]")).to_contain_text("Klucz jest zapisany")
    expect(page.locator("[data-el-key]")).to_have_value("")
    page.open("settings/home_assistant")
    expect(page.locator("[data-machine]")).to_contain_text("Nie skonfigurowano")
    expect(page.locator("[data-machine-off]")).to_be_disabled()
    expect(page.locator("[data-top-machine]")).to_have_attribute("data-top-machine", "gpu")  # no HA: GPU only
    expect(page.locator("[data-machine-off-top]")).to_have_count(0)


def test_look_and_language_page(page):
    page.open("settings/editor")
    page.locator("[data-language-option='en']").click()
    expect(page.locator("header h1")).to_have_text("Voice editor")
    page.locator("[data-theme-option='light']").click()
    expect(page.locator("pvc-editor")).to_have_attribute("data-theme", "light")


def test_base_views(page, demo):
    page.open("base/score")
    expect(page.locator("[data-score]")).to_contain_text("18 395")
    page.locator("[data-run-score]").click()
    expect(page.locator("[data-job='side']")).to_have_count(1, timeout=5000)
    page.open("base/compare")
    expect(page.locator("[data-compare] tr")).to_have_count(3)
    page.open("base/train")
    expect(page.locator("[data-base-chart] [data-panel='mos']")).to_be_visible()
    expect(page.locator("[data-base-model] button")).to_have_count(2)
    page.locator("[data-quality='high']").click()
    expect(page.locator("[data-base-batch]")).to_have_attribute("placeholder", "16")
    page.open("base/select")
    expect(page.locator("[data-base-checkpoint] option")).to_have_count(4)
    page.locator("[data-run-base-select]").click()
    expect(page.locator("[data-job='current'] [data-job-name]")).to_contain_text("Baza: wybór")
