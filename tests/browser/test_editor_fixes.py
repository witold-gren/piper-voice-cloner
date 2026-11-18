"""The editor fixes found while writing the step-by-step guide: optional steps, the job history's result,
the training time as a duration, "Start over", base checkpoint labels."""

from __future__ import annotations

import os
import re

from playwright.sync_api import expect

OPTIONAL = {"audition"}


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
