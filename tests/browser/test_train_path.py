"""Own recordings → training → export in the browser (demo data)."""

from __future__ import annotations

from playwright.sync_api import expect


def test_import_from_the_import_folder(page, demo):
    page.open("voice/tomek/import")
    expect(page.locator("[data-reasons] [data-reason='text:digits']")).to_contain_text("cyfry w tekście")
    folder = demo[1] / "import" / "nagrania_basi"
    page.locator("[data-import-folder]").select_option(str(folder))
    expect(page.locator("[data-import-path]")).to_have_value(str(folder))
    page.locator("[data-import-persona]").fill("custom_metadata.csv")
    page.locator("[data-import-persona]").dispatch_event("change")
    page.locator("[data-run-import]").click()
    expect(page.locator("[data-job='current'] [data-job-name]")).to_contain_text("Import · tomek")
    expect(page.locator("[data-job='current']")).to_have_attribute("data-state", "ok", timeout=15000)
    expect(page.locator("[data-log]")).to_contain_text("import: done")


def test_training_shows_estimate_resume_chart_and_samples(page):
    page.open("voice/kasia/train")
    expect(page.locator("[data-train-estimate]")).to_contain_text("1496 klipów")
    resume = page.locator("[data-train-resume]")
    expect(resume).to_contain_text("doszedł do epoki 1573")
    expect(resume).to_contain_text("dokończy plan do epoki 2113 (zostało 540 epok)")  # 1113 + 1000
    page.locator("[data-train-epochs]").fill("500")  # plan 1113 + 500 = 1613: 40 epochs left
    expect(resume).to_contain_text("dokończy plan do epoki 1613 (zostało 40 epok)")
    page.locator("[data-train-epochs]").fill("300")  # plan 1413 is behind epoch 1573: 300 more
    expect(resume).to_contain_text("dotrenuje jeszcze 300 epok, do 1873")
    expect(page.locator("[data-panel='mos']")).to_be_visible()
    expect(page.locator("[data-panel='mel']")).to_be_visible()
    expect(page.locator("[data-listen-summary]")).to_contain_text("Ostatnia epoka")
    expect(page.locator("[data-clips] audio")).to_have_count(4)
    # head + 3 epochs + last.ckpt, and the 3 checkpoints of the training before "start over" (kept)
    expect(page.locator("[data-checkpoints] tr")).to_have_count(8)


def test_chart_hover_and_the_big_window(page):
    page.open("voice/kasia/train")
    chart = page.locator("[data-panel='mos'] svg")
    box = chart.bounding_box()
    page.mouse.move(box["x"] + box["width"] * 0.5, box["y"] + box["height"] * 0.5)
    expect(page.locator("[data-panel='mos'] [data-tip]")).to_contain_text("Epoka")
    page.locator("[data-train-chart] [data-chart]").click()
    dialog = page.locator("[data-chart-dialog]")
    expect(dialog.locator("[data-best-mos]")).to_contain_text("Najlepsza jakość")
    dialog.locator("[data-range-from]").fill("1300")
    dialog.locator("[data-range-from]").dispatch_event("change")
    dialog.locator("[data-range-to]").fill("1400")
    dialog.locator("[data-range-to]").dispatch_event("change")
    labels = dialog.locator("[data-panel='mos'] text").all_inner_texts()
    assert "1200" not in labels and "1500" not in labels
    dialog.locator("[data-range-all]").click()
    expect(dialog.locator("[data-range-from]")).to_have_value("")


def test_training_starts_and_the_card_follows_it(page, demo):
    page.open("voice/kasia/train")
    page.locator("[data-train-base]").select_option("lessac")
    page.locator("[data-train-epochs]").fill("300")
    page.locator("[data-run-train]").click()
    expect(page.locator("[data-job='current'] [data-job-name]")).to_contain_text("Trening · kasia")
    demo[2].state.jobs["current"].wait(30)
    expect(page.locator("[data-log]")).to_contain_text("training epochs")
    assert "max_epochs: 300" in (demo[1] / "voices" / "kasia" / "voice.yaml").read_text()


def test_export_lists_files_and_starts(page):
    page.open("voice/kasia/export")
    expect(page.locator("[data-export-files] a")).to_have_text(
        ["pl_PL-kasia_glos-medium.onnx", "pl_PL-kasia_glos-medium.onnx.json"]
    )
    expect(page.locator("[data-export-checkpoint] option")).to_have_count(7)  # also the earlier training
    page.locator("[data-run-export]").click()
    expect(page.locator("[data-job='current'] [data-job-name]")).to_contain_text("Eksport · kasia")


def test_queue_keeps_the_order_of_ticking(page, demo):
    page.open("jobs/queue")
    page.locator("[data-queue-voice='tomek']").check()
    page.locator("[data-queue-voice='kasia']").check()
    expect(page.locator("[data-queue-voices] .order")).to_have_text(["2", "1"])
    page.locator("[data-queue-epochs]").fill("20")
    page.locator("[data-run-queue]").click()
    expect(page.locator("[data-queue-item='tomek']")).to_be_visible(timeout=10000)
    demo[2].state.jobs["current"].wait(30)
    expect(page.locator("[data-queue-item]")).to_have_count(2)


def test_history_opens_a_log(page, demo):
    demo[2].state.start("filter", "alicja", ["filter", "alicja"])
    demo[2].state.jobs["current"].wait(20)
    page.open("jobs/history")
    page.locator("[data-history-open]").first.click()
    expect(page.locator("[data-history-log]")).to_contain_text("filter: done")
