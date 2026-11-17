"""The cloning way in the browser (demo data)."""

from __future__ import annotations

import re

from playwright.sync_api import expect


def test_recording_lists_files_shows_the_prepared_clips_and_runs(page):
    page.open("voice/ola_bajka/reference")
    expect(page.locator("[data-files] li")).to_have_count(1)
    expect(page.locator("[data-reference-result]")).to_contain_text("14,6 s mowy, 2 fragmentów")
    expect(page.locator("[data-reference-short]")).to_contain_text("Krótkie nagranie")
    expect(page.locator("[data-reference-result] audio")).to_have_count(2)
    page.locator("[data-reference-upload]").set_input_files(
        files=[{"name": "drugie.wav", "mimeType": "audio/wav", "buffer": b"RIFF0000WAVE"}]
    )
    expect(page.locator("[data-files] li")).to_have_count(2)
    page.locator("[data-remove-file='drugie.wav']").click()
    expect(page.locator("[data-files] li")).to_have_count(1)
    page.locator("[data-run-reference]").click()
    expect(page.locator("[data-job='current'] [data-job-name]")).to_contain_text("Nagranie · ola_bajka")


def test_sentences_preview_and_run(page):
    page.open("voice/ola_bajka/corpus")
    expect(page.locator("[data-corpus-preview] h3")).to_contain_text("1950")
    expect(page.locator("[data-corpus-preview] li")).to_have_count(50)
    page.locator("[data-corpus-size]").fill("300")
    page.locator("[data-run-corpus]").click()
    expect(page.locator("[data-job='current'] [data-job-name]")).to_contain_text("Zdania · ola_bajka")


def test_audition_rows_switch_the_clips_and_apply(page, demo):
    page.open("voice/ola_bajka/audition")
    rows = page.locator("[data-audition-row]")
    expect(rows).to_have_count(3)
    expect(rows.first).to_have_class(re.compile(r"\bsel\b"))
    rows.nth(1).click()
    expect(rows.nth(1)).to_have_class(re.compile(r"\bsel\b"))
    page.locator("[data-audition-apply]").click()
    expect(page.locator("[data-audition-applied]")).to_contain_text('"cfg_weight":0.3')
    assert "cfg_weight: 0.3" in (demo[1] / "voices" / "ola_bajka" / "voice.yaml").read_text()


def test_generating_shows_speed_and_switches_the_model(page):
    page.open("voice/ola_bajka/synthesize")
    expect(page.locator("[data-synthesize-count]")).to_contain_text("820 z 1950")
    expect(page.locator("[data-synthesize-timing]")).to_contain_text("4,1 s na klip")
    expect(page.locator("[data-elevenlabs]")).to_have_count(0)
    page.locator("[data-backend-option='elevenlabs']").click()
    expect(page.locator("[data-elevenlabs] [data-el-cost]")).to_contain_text("1130 zdań")
    expect(page.locator("[data-el-no-key]")).to_be_visible()
    page.locator("[data-backend-option='chatterbox']").click()
    expect(page.locator("[data-elevenlabs]")).to_have_count(0)
    page.locator("[data-synthesize-limit]").fill("20")
    page.locator("[data-run-synthesize]").click()
    expect(page.locator("[data-job='current'] [data-job-name]")).to_contain_text(
        "Generowanie klipów · ola_bajka"
    )


def test_filter_report_and_run(page):
    page.open("voice/alicja/filter")
    expect(page.locator("[data-filter-report] [data-reason='too_fast_or_cut']")).to_contain_text(
        "za szybko albo ucięte"
    )
    expect(page.locator("[data-run-filter]")).to_be_disabled()  # alicja has no generated clips in the demo
    page.open("voice/ola_bajka/filter")
    page.locator("[data-filter-check='mos']").uncheck()
    page.locator("[data-run-filter]").click()
    expect(page.locator("[data-job='current'] [data-job-name]")).to_contain_text("Filtrowanie · ola_bajka")
