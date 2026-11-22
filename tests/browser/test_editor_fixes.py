"""The editor fixes found while writing the step-by-step guide: optional steps, the job history's result,
the training time as a duration, "Start over", base checkpoint labels."""

from __future__ import annotations

import json
import os
import re

from playwright.sync_api import expect

OPTIONAL = {"audition", "score"}


def test_an_optional_step_is_not_counted_until_done(page, demo):
    page.open()
    state = page.evaluate("fetch('/api/state').then((r) => r.json())")
    for voice in state["voices"]:
        needed = [s for s in voice["steps"] if s["done"] or s["key"] not in OPTIONAL]
        done = sum(s["done"] for s in needed)
        row = page.locator(f"[data-node='voice/{voice['name']}'] > .count").first
        expect(row).to_have_text(f"{done}/{len(needed)}")


def test_the_job_history_shows_the_result_and_the_time(page, demo):
    app = demo[2]
    os.environ["FAKE_PVC_SPEED"] = "50"
    app.state.start("filter", "alicja", ["filter", "alicja"])
    app.state.jobs["current"].wait(30)
    page.open("jobs/history")
    first = page.locator("[data-history] [data-history-status]").first
    expect(first).to_have_attribute("data-history-status", "ok")
    expect(first).to_contain_text("Zakończone")


def test_the_training_time_reads_as_a_duration_not_a_clock(page):
    page.open("voice/kasia/train")
    estimate = page.locator("[data-train-estimate]")
    expect(estimate).to_contain_text("potrwa ok.")
    text = estimate.inner_text()
    assert not re.search(r"\d\d:\d\d:\d\d", text), text
    assert re.search(r"\d[–-]\d+(,\d)? (h|min|dni)", text), text


def test_start_over_asks_and_trains_from_the_base(page, demo):
    root, app = demo[1], demo[2]
    page.open("voice/kasia/train")
    expect(page.locator("[data-train-base-resume]")).to_be_visible()  # "Resume" ignores the base
    page.once("dialog", lambda dialog: dialog.accept())
    os.environ["FAKE_PVC_SPEED"] = "50"
    page.locator("[data-train-fresh]").click()
    expect(page.locator("[data-top-job], [data-job-state]").first).to_be_visible()
    app.state.jobs["current"].wait(30)
    log = sorted((root / "jobs").glob("*-train-kasia.log"))[-1].read_text(encoding="utf-8")
    assert "--no-resume" in log.splitlines()[0]


def test_start_over_can_be_cancelled(page, demo):
    root = demo[1]
    page.open("voice/kasia/train")
    page.once("dialog", lambda dialog: dialog.dismiss())
    page.locator("[data-train-fresh]").click()
    page.wait_for_timeout(500)
    assert not list((root / "jobs").glob("*-train-kasia.log"))


def test_base_checkpoints_name_their_epoch_and_quality(page):
    page.open("base/select")
    expect(page.locator("[data-base-checkpoint] option").first).to_be_attached()
    options = page.locator("[data-base-checkpoint] option").all_inner_texts()
    assert options and any(re.search(r"Epoka \d+ · val_mos \d,\d{3}", o) for o in options), options
    assert all(o.split(" · ")[0] in ("medium", "high") for o in options), options


def test_an_earlier_training_can_be_shown_and_heard(page):
    """kasia was started over once: the run before (from lessac) is kept whole in train/runs/0."""
    page.open("voice/kasia/train")
    pick = page.locator("[data-train-run]")
    expect(pick.locator("option")).to_have_count(2)
    expect(pick.locator("option").nth(1)).to_contain_text("od lessac, epoki 2164–2295")
    expect(page.locator("[data-listen-zip]")).to_be_visible()
    pick.select_option("0")
    epochs = page.locator("[data-listen-epoch] option")
    expect(epochs.first).to_contain_text("epoka 2290")
    expect(page.locator("[data-listen-zip]")).to_have_count(0)  # a kept run is only listened to
    expect(page.locator("pvc-chart")).to_be_visible()
    pick.select_option("")
    expect(epochs.first).not_to_contain_text("epoka 2290")


def test_an_earlier_training_can_be_trained_further(page):
    page.open("voice/kasia/train")
    expect(page.locator("[data-train-continue]")).to_have_count(0)  # only for an earlier one
    page.locator("[data-train-run]").select_option("0")
    button = page.locator("[data-train-continue]")
    expect(button).to_contain_text("Dotrenuj ten trening")
    expect(page.locator(".run-continue")).to_contain_text("Doszedł do epoki 2295")
    sent = []

    def watch(request):
        if request.method == "POST" and request.url.endswith("/kasia/train"):
            sent.append(request.post_data_json)

    page.on("request", watch)
    page.once("dialog", lambda dialog: dialog.dismiss())  # cancelled: nothing starts
    button.click()
    page.wait_for_timeout(300)
    assert sent == []
    page.once("dialog", lambda dialog: dialog.accept())
    button.click()
    expect(page.locator("[data-train-run]")).to_have_value("")  # back on the current training
    assert sent and sent[-1]["continue_run"] == "0" and sent[-1]["fresh"] is True


def test_the_export_says_the_name_the_next_file_gets(page):
    page.open("voice/kasia/export")
    expect(page.locator("pvc-step-export")).to_contain_text("pl_PL-kasia_glos_2-medium.onnx")


def test_the_recordings_of_a_voice_are_rated_and_the_scores_shown(page, demo):
    root = demo[1]
    dataset = root / "voices" / "kasia" / "dataset"
    clips = sorted(p.stem for p in (dataset / "wav").glob("*.wav"))[:3]
    report = {
        "total": 1500,
        "scores": dict(zip(clips, (2.4, 3.1, 4.2), strict=True)),
        "texts": {clip: f"Zdanie {clip}." for clip in clips},
    }
    (dataset / "utmos.json").write_text(json.dumps(report), encoding="utf-8")
    try:
        page.open("voice/kasia/score")
        total = len((dataset / "metadata.csv").read_text().splitlines())
        expect(page.locator("[data-node='voice/kasia/score'] .count")).to_contain_text(f"3.10 · 3/{total}")
        expect(page.locator("[data-score-kept]")).to_contain_text("dataset/utmos.json")
        expect(page.locator("[data-score-below]")).to_contain_text("poniżej 2,5: 1")
        expect(page.locator("[data-score]")).to_contain_text("Ocenione nagrania: 3 z")
        page.locator("[data-run-score]").click()
        expect(page.locator("[data-score-running], [data-score]").first).to_be_visible()
    finally:
        (dataset / "utmos.json").unlink()


def test_weak_recordings_are_taken_out_from_the_rating_step(page, demo):
    root = demo[1]
    dataset = root / "voices" / "kasia" / "dataset"
    clips = [
        line.split("|")[0].removesuffix(".wav")
        for line in (dataset / "metadata.csv").read_text().splitlines()
    ]
    report = {
        "total": len(clips),
        "scores": {clip: 2.8 if i < 3 else 3.5 for i, clip in enumerate(clips)},
        "texts": {},
    }
    (dataset / "utmos.json").write_text(json.dumps(report), encoding="utf-8")
    try:
        page.open("voice/kasia/score")
        expect(page.locator("[data-prune-clips]")).to_contain_text(f"Dataset ma {len(clips)}")
        expect(page.locator("[data-prune-unscored]")).to_have_count(0)
        with page.expect_request(lambda r: r.url.endswith("/kasia/prune")) as sent:
            page.once("dialog", lambda dialog: dialog.accept())
            page.locator("[data-run-prune]").click()
        assert sent.value.post_data_json == {"below": 3.0}
    finally:
        (dataset / "utmos.json").unlink()


def test_the_level_shows_what_stays_and_every_clip_is_listed(page, demo):
    root = demo[1]
    dataset = root / "voices" / "kasia" / "dataset"
    clips = [
        line.split("|")[0].removesuffix(".wav")
        for line in (dataset / "metadata.csv").read_text().splitlines()
    ]
    # the first 20 weak (2.5), the rest good (3.8)
    report = {"scores": {clip: 2.5 if i < 20 else 3.8 for i, clip in enumerate(clips)}, "texts": {}}
    (dataset / "utmos.json").write_text(json.dumps(report), encoding="utf-8")
    try:
        page.open("voice/kasia/score")
        preview = page.locator("[data-prune-preview]")
        expect(preview).to_contain_text(f"zostanie {len(clips) - 20}")
        expect(preview).to_contain_text("wypadnie 20")
        page.locator("[data-prune-below]").fill("4.0")  # live, before anything is taken out
        expect(preview).to_contain_text("zostanie 0")
        expect(page.locator("[data-prune-preview-short]")).to_contain_text("Brakuje 1500 do 1500")
        page.locator("[data-prune-below]").fill("3.0")
        table = page.locator("[data-clips-table] tbody tr")
        expect(table).to_have_count(50)  # one page
        expect(table.first.locator("td").nth(1)).to_have_text("2,50")  # weakest first
        expect(page.locator("[data-clips-range]")).to_contain_text(f"1–50 z {len(clips)}")
        page.locator("[data-clips-below]").check()
        expect(table).to_have_count(20)
        page.locator("[data-clips-below]").uncheck()
        page.locator("[data-clips-order]").click()
        expect(table.first.locator("td").nth(1)).to_have_text("3,80")
        page.locator("[data-clips-next]").click()
        expect(page.locator("[data-clips-range]")).to_contain_text("51–100")
        page.locator("[data-clips-where='out']").click()
        expect(page.locator("[data-clips-none]")).to_be_visible()
    finally:
        (dataset / "utmos.json").unlink()
