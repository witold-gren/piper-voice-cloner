from __future__ import annotations

import json
from pathlib import Path
import shlex
import sys
import time

import pytest

from piper_voice_cloner import config as config_mod, corpus, dataset
from piper_voice_cloner.webui import service
from piper_voice_cloner.webui.jobs import JobBusy, JobManager, tail
from piper_voice_cloner.webui.texts import TEXTS

from .conftest import write_tone

# --- jobs ---------------------------------------------------------------------------------------


def fake_pvc(tmp_path, body: str) -> list[str]:
    """A stand-in for the CLI: a python script receiving `--root <root> <args...>`."""
    script = tmp_path / "fake_pvc.py"
    script.write_text(body, encoding="utf-8")
    return [sys.executable, str(script)]


def test_job_runs_and_records_exit_code(tmp_path):
    pvc = fake_pvc(tmp_path, "import sys\nprint('args', sys.argv[1:])\nprint('done')\n")
    jobs = JobManager(tmp_path, pvc=pvc)
    assert jobs.status() is None
    jobs.start("synthesize", "kuba", ["synthesize", "kuba"])
    status = jobs.wait()
    assert status.finished_ok
    assert (status.kind, status.voice) == ("synthesize", "kuba")
    assert "'--root'" in status.log_tail and "'synthesize', 'kuba'" in status.log_tail
    assert status.log_tail.splitlines()[-1] == "done"


def test_user_errors_show_in_the_panel_without_a_terminal_traceback():
    from piper_voice_cloner.webui.app import user_error

    error = user_error("busy")
    assert str(error) == "'busy'" or "busy" in str(error)
    assert error.print_exception is False
    for code in TEXTS:
        assert "{job}" in TEXTS[code]["job_busy"] and "{error}" not in TEXTS[code]["job_busy"]


def test_job_failure_and_single_job_rule(tmp_path):
    pvc = fake_pvc(tmp_path, "import sys, time\ntime.sleep(float(sys.argv[3]))\nsys.exit(3)\n")
    jobs = JobManager(tmp_path, pvc=pvc)
    jobs.start("train", "kuba", ["0.8"])
    assert jobs.running()
    with pytest.raises(JobBusy, match="train") as busy:
        jobs.start("filter", "kuba", ["0"])
    assert (busy.value.kind, busy.value.voice) == ("train", "kuba")  # the panel words it in its language
    status = jobs.wait()
    assert not status.running and status.returncode == 3 and not status.finished_ok
    # after it ends a new job may start
    jobs.start("filter", "kuba", ["0"])
    assert jobs.wait().returncode == 3


def test_side_slot_runs_next_to_the_training(tmp_path):
    pvc = fake_pvc(tmp_path, "import sys, time\ntime.sleep(float(sys.argv[3]))\n")
    jobs, side = JobManager(tmp_path, pvc=pvc), JobManager(tmp_path, pvc=pvc, slot="side")
    jobs.start("base-train", "", ["0.8"])
    side.start("base-score", "", ["0"])  # not blocked by the training
    assert side.wait().finished_ok and jobs.running()
    assert jobs.status().kind == "base-train" and (tmp_path / "jobs" / "side.json").is_file()
    jobs.wait()


def test_stop_sends_ctrl_c(tmp_path):
    pvc = fake_pvc(
        tmp_path,
        "import time\ntry:\n    time.sleep(30)\n"
        "except KeyboardInterrupt:\n    print('interrupted')\n    raise SystemExit(130)\n",
    )
    jobs = JobManager(tmp_path, pvc=pvc)
    assert jobs.stop() is False
    jobs.start("train", "kuba", [])
    time.sleep(0.5)  # let the child install its default SIGINT handling
    assert jobs.stop() is True
    status = jobs.wait(10)
    assert status.returncode == 130
    assert "interrupted" in status.log_tail


def test_status_survives_new_manager(tmp_path):
    pvc = fake_pvc(tmp_path, "print('ok')\n")
    JobManager(tmp_path, pvc=pvc).start("export", "kuba", [])
    JobManager(tmp_path, pvc=pvc).wait()
    status = JobManager(tmp_path, pvc=pvc).status()  # e.g. after restarting the UI
    assert status.finished_ok and status.kind == "export"


def test_dead_runner_is_reported_as_failed(tmp_path):
    (tmp_path / "jobs").mkdir()
    (tmp_path / "jobs" / "current.json").write_text(
        json.dumps({"kind": "train", "voice": "x", "runner_pid": 999999})
    )
    status = JobManager(tmp_path).status()
    assert not status.running and status.returncode == -1


def test_tail_keeps_last_progress_state(tmp_path):
    log = tmp_path / "x.log"
    log.write_bytes(b"one\nepoch 1: 10%\repoch 1: 50%\repoch 1: 100%\nlast\n")
    assert tail(log) == "one\nepoch 1: 100%\nlast"
    assert tail(tmp_path / "missing.log") == ""
    log.write_text("\n".join(str(i) for i in range(100)))
    assert tail(log, 3) == "97\n98\n99"


# --- service -------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("typed", "name"),
    [("Tomek", "tomek"), (" Kuba Bajka ", "kuba_bajka"), ("Łucja-Żółć 2", "lucja_zolc_2"), ("!!", "")],
)
def test_normalize_name(typed, name):
    assert service.normalize_name(typed) == name


def test_create_voice_normalizes_the_typed_name(tmp_path):
    assert service.create_voice(tmp_path, "Tomek").name == "tomek"
    assert service.list_voices(tmp_path) == ["tomek"]
    with pytest.raises(ValueError, match="already exists"):
        service.create_voice(tmp_path, "TOMEK")
    with pytest.raises(ValueError, match="empty"):
        service.create_voice(tmp_path, "  ")


def test_persona_path_is_relative_to_the_old_dataset(tmp_path):
    assert service.persona_path(tmp_path, " custom_metadata.csv ") == tmp_path / "custom_metadata.csv"
    assert service.persona_path(tmp_path, "/data/x.csv") == Path("/data/x.csv")


def test_create_list_and_yaml_roundtrip(tmp_path):
    assert service.list_voices(tmp_path) == []
    service.create_voice(tmp_path, "kuba", piper_name="pl_PL-kuba")
    service.create_voice(tmp_path, "ala")
    assert service.list_voices(tmp_path) == ["ala", "kuba"]
    with pytest.raises(ValueError, match="already exists"):
        service.create_voice(tmp_path, "kuba")
    text = service.config_yaml(tmp_path, "kuba").replace("target_clips: 2000", "target_clips: 1500")
    assert service.save_config_yaml(tmp_path, "kuba", text).target_clips == 1500
    with pytest.raises(ValueError):
        service.save_config_yaml(tmp_path, "kuba", text.replace("max_cer: 0.04", "max_cer: 7"))
    with pytest.raises(ValueError, match="name"):
        service.save_config_yaml(tmp_path, "kuba", text.replace("name: kuba", "name: ala"))
    assert service.load_config(tmp_path, "kuba").target_clips == 1500  # invalid edits not saved


def test_steps_follow_progress(tmp_path):
    service.create_voice(tmp_path, "kuba")
    voice = service.voice_dir(tmp_path, "kuba")
    assert [s.done for s in service.steps(tmp_path, "kuba")] == [False] * 7
    (voice / "reference").mkdir()
    (voice / "reference" / "reference.json").write_text(
        json.dumps({"prompts": ["ref_00.wav"], "seconds": 21.5})
    )
    corpus.write_prompts(voice / "prompts.tsv", [("a", "Ala ma kota.")])
    dataset.write_metadata(voice / "dataset" / "metadata.csv", [dataset.Utterance("a", "Ala ma kota.")])
    ckpt = voice / "train" / "lightning_logs" / "version_0" / "checkpoints" / "last.ckpt"
    ckpt.parent.mkdir(parents=True)
    ckpt.write_bytes(b"x")
    (voice / "export").mkdir()
    (voice / "export" / "pl_PL-kuba-medium.onnx").write_bytes(b"x")
    steps = {s.key: s for s in service.steps(tmp_path, "kuba")}
    assert steps["reference"].done and steps["reference"].detail == "21.5 s"
    assert steps["corpus"].detail == "1"
    assert steps["filter"].detail == "1 / 2000"
    assert steps["train"].done and steps["export"].detail == "pl_PL-kuba-medium.onnx"
    assert not steps["synthesize"].done and not steps["audition"].done
    assert service.checkpoint_choices(tmp_path, "kuba") == [str(ckpt)]


def test_save_uploads(tmp_path):
    upload = tmp_path / "upload" / "nagranie.m4a"
    upload.parent.mkdir()
    upload.write_bytes(b"audio")
    saved = service.save_uploads(tmp_path / "voice" / "reference" / "uploads", [str(upload)])
    assert saved[0].name == "nagranie.m4a" and saved[0].read_bytes() == b"audio"


def test_audition_results_and_apply(tmp_path):
    service.create_voice(tmp_path, "kuba")
    voice = service.voice_dir(tmp_path, "kuba")
    results = [
        {
            "slug": "cfg_weight-0.3",
            "options": {"cfg_weight": 0.3},
            "score": 0.71,
            "cer": 0.01,
            "similarity": 0.73,
            "mos": 3.9,
            "clips": [{"id": "a", "text": "Ala ma kota.", "file": "cfg_weight-0.3/a.wav"}],
        },
        {
            "slug": "cfg_weight-0.5",
            "options": {"cfg_weight": 0.5},
            "score": 0.5,
            "cer": None,
            "similarity": None,
            "mos": None,
            "clips": [],
        },
    ]
    (voice / "audition").mkdir()
    (voice / "audition" / "results.json").write_text(json.dumps(results))
    table = service.audition_table(service.audition_results(tmp_path, "kuba"))
    assert table[0] == [1, "cfg_weight-0.3", 0.71, 0.01, 0.73, 3.9]
    assert table[1][3:] == ["", "", ""]
    clips = service.audition_clips(tmp_path, "kuba", "cfg_weight-0.3")
    assert clips == [(voice / "audition" / "cfg_weight-0.3" / "a.wav", "Ala ma kota.")]
    assert service.audition_clips(tmp_path, "kuba", "nope") == []
    assert service.apply_audition(tmp_path, "kuba", "cfg_weight-0.5") == {"cfg_weight": 0.5}
    assert service.load_config(tmp_path, "kuba").synthesis.options == {"cfg_weight": 0.5}
    with pytest.raises(ValueError):
        service.apply_audition(tmp_path, "kuba", "nope")


def test_filter_report_samples(tmp_path):
    service.create_voice(tmp_path, "kuba")
    voice = service.voice_dir(tmp_path, "kuba")
    write_tone(voice / "dataset" / "wav" / "a.wav", 1.0, 22050)
    write_tone(voice / "raw" / "b.wav", 1.0)
    rows = [
        {"id": "a", "text": "Ala ma kota.", "reason": ""},
        {"id": "b", "text": "Kot ma Alę.", "reason": "asr_mismatch"},
        {"id": "c", "text": "Bez pliku.", "reason": "speaker_mismatch"},
    ]
    dataset.write_report(voice / "dataset" / "filter_report.csv", rows, ["id", "text", "reason"])
    loaded = service.filter_report(tmp_path, "kuba")
    assert service.reason_counts(loaded) == [["ok", 1], ["asr_mismatch", 1], ["speaker_mismatch", 1]]
    assert service.sample_clips(tmp_path, "kuba", loaded, kept=True) == [
        (voice / "dataset/wav/a.wav", "Ala ma kota.")
    ]
    assert service.sample_clips(tmp_path, "kuba", loaded, kept=False) == [
        (voice / "raw/b.wav", "[asr_mismatch] Kot ma Alę.")
    ]


def test_filter_report_falls_back_to_import_report(tmp_path):
    service.create_voice(tmp_path, "kasia")
    voice = service.voice_dir(tmp_path, "kasia")
    dataset.write_report(
        voice / "dataset" / "import_report.csv", [{"id": "a", "reason": "text:digits"}], ["id", "reason"]
    )
    assert service.reason_counts(service.filter_report(tmp_path, "kasia")) == [["text:digits", 1]]


def test_estimate_matches_guide_table():
    est = service.estimate(2000)
    assert est.steps_per_epoch == 59
    low, high = est.epoch_seconds
    assert 29 <= low <= 30 and 39 <= high <= 40
    hours_low, hours_high = est.hours(1000)
    assert 8 < hours_low < hours_high < 11
    assert service.estimate(18400).steps_per_epoch == 546
    assert service.estimate(5).steps_per_epoch == 1


def test_set_max_epochs_and_base_ready(tmp_path):
    service.create_voice(tmp_path, "kuba")
    service.set_max_epochs(tmp_path, "kuba", 400)
    assert service.load_config(tmp_path, "kuba").train.max_epochs == 400
    assert not service.base_ready(tmp_path)
    (tmp_path / "bases").mkdir()
    (tmp_path / "bases" / "pl-scratch.ckpt").write_bytes(b"x")
    assert service.base_ready(tmp_path)


# --- texts and layout ------------------------------------------------------------------------------


def test_every_language_has_every_text():
    keys = set(TEXTS["en"])
    for lang, values in TEXTS.items():
        assert set(values) == keys, lang
    for values in TEXTS.values():
        assert "{name}" in values["created"]
        assert "{clips}" in values["train_estimate"]


def test_app_builds_in_both_languages(tmp_path):
    pytest.importorskip("gradio")
    from piper_voice_cloner.webui.app import build

    service.create_voice(tmp_path, "kuba")
    for lang in ("en", "pl"):
        app = build(tmp_path, lang, JobManager(tmp_path))
        assert app.title == TEXTS[lang]["title"]


# --- live panel and languages -------------------------------------------------------------------


def test_parse_gpu_line():
    gpu = service.parse_gpu("NVIDIA GeForce RTX 4090, 87, 12288, 24564, 71, 402.5, 450.00")
    assert gpu["name"] == "NVIDIA GeForce RTX 4090"
    assert gpu["utilization"] == 87 and gpu["temperature"] == 71
    assert round(gpu["memory_percent"]) == 50
    assert round(gpu["power_percent"]) == 89
    assert service.parse_gpu("garbage") is None
    assert service.parse_gpu("Card, [N/A], 1, 0, 40, [N/A], [N/A]")["power_percent"] == 0


def test_gpu_stats_with_fake_nvidia_smi():
    line = "NVIDIA GeForce RTX 4090, 10, 1024, 24564, 40, 50, 450\n"
    assert service.gpu_stats(run=lambda: line)["utilization"] == 10
    assert service.gpu_stats(run=lambda: "") is None

    def broken():
        raise TimeoutError

    assert service.gpu_stats(run=broken) is None


def test_format_elapsed():
    assert service.format_elapsed(None) == "—"
    assert service.format_elapsed(65) == "00:01:05"
    assert service.format_elapsed(3 * 3600 + 7) == "03:00:07"
    assert service.format_elapsed(2 * 86400 + 3600) == "2 d 01:00:00"


def test_job_elapsed(tmp_path):
    pvc = fake_pvc(tmp_path, "import time\ntime.sleep(0.3)\n")
    jobs = JobManager(tmp_path, pvc=pvc)
    jobs.start("filter", "kuba", [])
    status = jobs.wait()
    assert status.finished is not None
    assert 0.2 < status.elapsed() < 5
    assert status.elapsed() == status.elapsed(now=status.finished + 100)  # frozen once finished


def test_steps_html_is_progress_and_navigation():
    from piper_voice_cloner.webui import style

    items = [("a", "A", True, "1 s"), ("b", "B", False, ""), ("c", "C", False, "")]
    page = style.steps_html(items, current="c", extra=[("tools", "Tools", "T")])
    assert page.count('class="pvc-step done"') == 1
    assert page.count('class="pvc-step next"') == 1
    assert 'class="pvc-step current" data-pvc-tab="c"' in page
    assert 'class="pvc-step tool" data-pvc-tab="tools"' in page
    assert "<b>✓</b>" in page and "<b>2</b>" in page
    # without a voice: the pills still navigate, the hint is shown below, nothing is "next"
    empty = style.steps_html(items, empty="**x**")
    assert "pvc-empty" in empty and "<b>x</b>" in empty and "next" not in empty
    assert empty.count("data-pvc-tab=") == 3
    assert 'trigger("click"' in style.NAV_JS and "data-pvc-tab" in style.NAV_JS


def test_step_tabs_match_service_steps(tmp_path):
    from piper_voice_cloner.webui import app

    service.create_voice(tmp_path, "kuba")
    assert [s.key for s in service.steps(tmp_path, "kuba")] == app.STEP_TABS
    for code in TEXTS:
        for key, _icon in app.EXTRA_TABS:
            assert TEXTS[code]["tab_" + key]


def test_lang_switch_and_live_card():
    from piper_voice_cloner.webui import style

    switch = style.lang_switch("pl", ["en", "pl"])
    assert 'href="../en/"' in switch and 'class="on"' in switch.split("../pl/")[1][:20]
    labels = TEXTS["pl"]
    gpu = service.parse_gpu("RTX 4090, 50, 2048, 24576, 85, 300, 450")
    card = style.live_html(labels, "Trening", "00:10:00", gpu)
    assert "RTX 4090" in card and "--value:50" in card and "var(--pvc-bad)" in card  # 85 °C = hot
    assert labels["no_gpu"] in style.live_html(labels, "—", "—", None)


def test_server_serves_both_languages(tmp_path):
    pytest.importorskip("gradio")
    from fastapi.testclient import TestClient

    from piper_voice_cloner.webui.app import create_server

    client = TestClient(create_server(tmp_path, "pl", None))
    root = client.get("/")
    assert root.status_code == 200 and "lang='pl'" in root.text and "localStorage" in root.text
    assert 'rel="icon"' in root.text
    for icon, media in (
        ("/favicon.svg", "image/svg+xml"),
        ("/favicon.ico", "image/png"),
        ("/apple-touch-icon.png", "image/png"),
    ):
        response = client.get(icon)
        assert response.status_code == 200 and response.headers["content-type"].startswith(media)
    for code in ("en", "pl"):
        page = client.get(f"/{code}/")
        assert page.status_code == 200
        guide = client.get(f"/guide/{code}")
        assert guide.status_code == 200 and 'id="toc"' in guide.text and "FAQ" in guide.text
        assert 'rel="icon" type="image/svg+xml" href="data:image/svg+xml;base64,' in guide.text
        assert "favicon.svg" in page.text


def test_login_page_gets_its_look_before_the_login(tmp_path):
    pytest.importorskip("gradio")
    from fastapi.testclient import TestClient

    from piper_voice_cloner.webui import style
    from piper_voice_cloner.webui.app import create_server

    client = TestClient(create_server(tmp_path, "pl", ("admin", "secret")))
    assert client.get("/pl/config").status_code == 401  # the app CSS is not reachable yet
    for path in ("/pl/", "/en/", "/pl"):
        page = client.get(path)
        assert page.status_code == 200 and page.text.count(style.LOGIN_CSS) == 1
        assert page.text.index(style.LOGIN_CSS) < page.text.index("</head>")
    assert "min-h-screen:has(input[type=password])" in style.LOGIN_CSS
    assert style.LOGIN_CSS not in client.get("/").text  # only the Gradio pages


def test_step_info_renders_explanation():
    from piper_voice_cloner.webui import style

    page = style.step_info(
        "2", "Zdania", "Co się stanie?", "Zapisuje `prompts.tsv`.\n\n**Ważne**: <tylko> tekst.\n"
    )
    assert page.startswith('<details class="pvc-step-info">')
    assert '<span class="num">2</span>' in page and '<span class="q"' in page
    assert page.count("<li>") == 2
    assert "<code>prompts.tsv</code>" in page and "<b>Ważne</b>" in page and "&lt;tylko&gt;" in page
    assert '<span class="num">' not in style.step_info("", "Import", "?", "a")


def test_every_step_has_an_explanation_in_both_languages():
    for lang in ("en", "pl"):
        for step in (
            "reference",
            "corpus",
            "audition",
            "synthesize",
            "filter",
            "train",
            "export",
            "settings",
            "import",
            "base",
            "server",
            "ha",
        ):
            assert len(TEXTS[lang][f"info_{step}"].splitlines()) >= 3, (lang, step)


def test_makefile_help_lists_steps(tmp_path):
    from pathlib import Path
    import shutil
    import subprocess

    if not shutil.which("make"):
        pytest.skip("make not installed")
    repo = Path(__file__).resolve().parents[1]
    for lang, word in (("pl", "Instalacja"), ("en", "Setup")):
        out = subprocess.run(
            ["make", "-s", "help", f"HELP_LANG={lang}", f"ROOT={tmp_path}"],
            cwd=repo,
            capture_output=True,
            text=True,
        )
        assert out.returncode == 0 and word in out.stdout and "train" in out.stdout


def test_parse_progress_reads_our_lines_and_the_epoch_bar():
    assert service.parse_progress("") is None
    log = "$ pvc import\nprogress import 19/1915\nprogress import 38/1915\n"
    assert service.parse_progress(log) == (38, 1915, "")
    train = log + "Epoch 2170: 37%|███   | 21/56 [00:10<00:17]\rEpoch 2170: 39%|███   | 22/56 [00:11<00:16]"
    assert service.parse_progress(train) == (22, 56, "Epoch 2170")
    assert service.parse_progress("progress x 0/0") is None


def test_progress_html_and_finished_live_card():
    from piper_voice_cloner.webui import style

    bar = style.progress_html(50, 200, "Epoch 3")
    assert "width:25.0%" in bar and "50 / 200" in bar and "Epoch 3" in bar and "25%" in bar
    assert "width:100.0%" in style.progress_html(9, 3)
    card = style.live_html(TEXTS["pl"], "x", "00:00:16", None, stage_label="Ostatnie", elapsed_label="Trwało")
    assert "Ostatnie" in card and "Trwało" in card and "pvc-progress" not in card
    for code in TEXTS:
        for key in ("stage_last", "elapsed_took", "result_ok", "result_failed", "result_stopped"):
            assert TEXTS[code][key]


def test_training_progress_counts_epochs_of_the_whole_run():
    assert service.training_progress("Epoch 3: 10%|█ | 5/50 [00:01<00:09]") is None  # no plan line
    plan = "training epochs 2164-5164\n"
    assert service.training_progress(plan) == (0.0, 3000, None, None)
    log = plan + "Epoch 2464: 40%|███ | 20/50 [00:30<00:45, 1.1it/s]\rEpoch 2464: 50%|█ | 25/50 [00:30<00:30]"
    done, total, label, left = service.training_progress(log)
    assert (done, total, label) == (300.5, 3000, (2464, 25, 50))
    # 60 s per epoch: 30 s of this one + 2699 epochs after it
    assert left == 30 + 2699 * 60
    # an hour-long epoch: h:mm:ss in the bar
    long = plan + "Epoch 2164: 1%| | 1/50 [1:00:00<0:30:00]"
    assert service.training_progress(long)[3] == 30 * 60 + 2999 * 5400


def test_time_left_and_progress_bar_texts():
    from piper_voice_cloner.webui import style

    assert service.time_left(100, 25, 100) == 300
    assert service.time_left(None, 25, 100) is None and service.time_left(100, 0, 100) is None
    detail = TEXTS["pl"]["train_position"].format(epoch=2464, step=25, steps=50)
    bar = style.progress_html(300.5, 3000, unit="epok", detail=detail, remaining="zostało ok. 1 d")
    assert "300 / 3000 epok · epoka modelu 2464 · krok 25/50 · zostało ok. 1 d" in bar
    assert "300 / 3000 epok" in bar and "zostało ok. 1 d" in bar and "10%" in bar
    for code in TEXTS:
        assert TEXTS[code]["epochs"] and "{time}" in TEXTS[code]["time_left"]


def test_compact_log_keeps_only_the_latest_progress_line():
    log = "$ pvc import\nprogress import 1/3\nprogress import 2/3\nwarning\nprogress import 3/3\nkept 3 of 3"
    assert service.compact_log(log) == "$ pvc import\nwarning\nprogress import 3/3\nkept 3 of 3"
    assert service.compact_log("") == ""


def test_quiet_shutdown_hides_only_cancelled_streams():
    import asyncio
    import logging

    from piper_voice_cloner.webui.app import _QuietShutdown

    def record(message, exc=None):
        return logging.LogRecord(
            "uvicorn.error", logging.ERROR, "", 0, message, None, (type(exc), exc, None) if exc else None
        )

    quiet = _QuietShutdown()
    assert not quiet.filter(record("Cancel 1 running task(s), timeout graceful shutdown exceeded"))
    assert not quiet.filter(record("Exception in ASGI application", asyncio.CancelledError()))
    assert quiet.filter(record("Exception in ASGI application", ValueError("real bug")))


def test_guide_slugs_match_github_anchors():
    from piper_voice_cloner.webui.guide import slug

    assert slug("Komputer z GPU przez SSH (praca z Maca lub laptopa)") == (
        "komputer-z-gpu-przez-ssh-praca-z-maca-lub-laptopa"
    )
    assert slug("FAQ i rozwiązywanie problemów") == "faq-i-rozwiązywanie-problemów"
    assert slug("1. Nagranie referencyjne") == "1-nagranie-referencyjne"


def test_guide_render_gives_ids_toc_and_escapes_html():
    from piper_voice_cloner.webui.guide import render

    body, toc = render(
        "# T\n\n## A `b`\n\ntext <script>x</script>\n\n### A b\n\n## A b\n\n| x |\n|---|\n| 1 |\n"
    )
    assert toc == [(2, "a-b", "A b"), (3, "a-b-1", "A b"), (2, "a-b-2", "A b")]
    assert '<h2 id="a-b">' in body and "<table>" in body and "<script>" not in body


def test_guide_links_in_the_docs_resolve():
    import re

    from piper_voice_cloner.webui.guide import GUIDES, render

    for path in GUIDES.values():
        _body, toc = render(path.read_text(encoding="utf-8"))
        anchors = {anchor for _level, anchor, _title in toc}
        for link in re.findall(r"\]\(#([^)]+)\)", path.read_text(encoding="utf-8")):
            assert link in anchors, f"{path.name}: #{link}"


def test_html_guides_on_disk_are_up_to_date():
    from piper_voice_cloner.webui.guide import GUIDES, page

    for lang, source in GUIDES.items():
        built = source.with_suffix(".html")
        assert built.read_text(encoding="utf-8") == page(lang), f"run `make docs` ({built})"


def test_topbar_has_the_guide_link_before_the_languages():
    from piper_voice_cloner.webui import style

    bar = style.topbar("T", "S", "pl", ["en", "pl"], guide="Instrukcja")
    assert 'href="../guide/pl" target="_blank"' in bar
    assert bar.index("pvc-guide") < bar.index("pvc-lang")


# --- GPU machine power (Home Assistant) in the top bar ----------------------------------------


def _app_fn(app, name):
    return next(block.fn for block in app.fns.values() if getattr(block.fn, "__name__", "") == name)


def test_questions_use_the_panel_window_not_the_browser_confirm():
    from piper_voice_cloner.webui import style

    head = style.head('Anuluj "x"')
    assert (
        head.startswith(style.ICON_LINKS)
        and "window.pvcAsk" in head
        and 'cancel.textContent = "Anuluj \\"x\\""' in head
    )
    assert "showModal()" in head and "__CANCEL__" not in head
    assert ".pvc-ask {" in style.CSS and ".pvc-ask-ok.danger" in style.CSS
    for code in ("en", "pl"):
        assert TEXTS[code]["ask_cancel"]
    webui = Path(style.__file__).parent
    for source in webui.glob("*.py"):
        text = source.read_text(encoding="utf-8")
        assert "window.confirm(" not in text and "window.alert(" not in text, source.name


def test_machine_button_html_asks_before_switching():
    from piper_voice_cloner.webui import style

    button = style.machine_button("on", "Machine: on · 54 W", "hint", "off", 'Really "off"?')
    assert 'data-pvc-machine="off"' in button and 'data-confirm="Really &quot;off&quot;?"' in button
    assert "pvc-machine on" in button and "54 W" in button
    waiting = style.machine_button("stopping", "Machine: shutting down", "wait")
    assert "data-pvc-machine" not in waiting and "pending" in waiting and "wait" in waiting
    assert "pvcAsk(button.dataset.confirm" in style.MACHINE_JS and 'trigger("click"' in style.MACHINE_JS
    assert 'title="x"' in style.status_pill("checking", "Checking", title="x")


def test_page_and_top_bar_never_wait_for_the_machine(tmp_path, monkeypatch):
    """The machine is off (SSH times out) and Home Assistant is slow: the first look comes at once."""
    pytest.importorskip("gradio")
    import threading

    from piper_voice_cloner import ha, power, remote
    from piper_voice_cloner.webui.app import build
    from piper_voice_cloner.webui.machine import MachineMonitor

    release = threading.Event()
    remote.save_config(tmp_path, remote.ServerConfig(host="gpu.lan"))
    ha.save_connection("http://homeassistant.local:8123", "t" * 40)
    power.save_power(power.PowerSettings("switch.maszyna_gpu", "sensor.plug_power"))
    jobs = JobManager(tmp_path)
    monitor = MachineMonitor(tmp_path, jobs, run=lambda command: release.wait(5) and "")
    monkeypatch.setattr(monitor, "_reachable", lambda: release.wait(5))
    for lang in ("en", "pl"):
        app = build(tmp_path, lang, jobs, monitor)
        tick = _app_fn(app, "tick")
        started = time.time()
        bar, *_rest = tick(None, "reference")
        assert time.time() - started < 1
        assert TEXTS[lang]["status_checking"] in bar and TEXTS[lang]["machine_checking"] in bar
        assert "data-pvc-machine" not in bar  # nothing to click while checking
    release.set()
    assert monitor.lock.acquire(timeout=5)
    monitor.lock.release()


def test_top_bar_shows_the_machine_and_the_job_on_it(tmp_path, monkeypatch):
    pytest.importorskip("gradio")
    from piper_voice_cloner import ha, power, remote
    from piper_voice_cloner.webui.app import build
    from piper_voice_cloner.webui.machine import MachineMonitor

    remote.save_config(tmp_path, remote.ServerConfig(host="gpu.lan"))
    jobs = JobManager(tmp_path)
    monitor = MachineMonitor(tmp_path, jobs)
    monkeypatch.setattr(monitor, "refresh_in_background", lambda: None)
    app = build(tmp_path, "pl", jobs, monitor)
    tick = _app_fn(app, "tick")
    assert "pvc-machine" not in tick(None, "reference")[0]  # Home Assistant not set up: no button
    ha.save_connection("http://homeassistant.local:8123", "t" * 40)
    power.save_power(power.PowerSettings("switch.maszyna_gpu", "sensor.plug_power"))
    monitor._machine_cache = (time.time(), {"switch": "on", "watts": 212.4, "machine": "on"})
    monitor._checked, monitor.remote_job = True, {"running": True, "kind": "train", "voice": "kuba"}
    bar = tick(None, "reference")[0]
    assert "Maszyna: włączona · 212 W" in bar and 'data-pvc-machine="off"' in bar
    assert "Na maszynie trwa <b>Trening</b> (kuba)" in bar
    monitor._machine_cache = (time.time(), {"switch": "off", "watts": 0.3, "machine": "off"})
    monitor.remote_job, monitor.remote_error = None, "Connection refused"
    bar = tick(None, "reference")[0]
    assert "Maszyna: wyłączona<" in bar and 'data-pvc-machine="on"' in bar and "Connection refused" in bar
    monitor._machine_cache = (
        time.time(),
        {"machine": "unknown", "watts": None, "error": "Home Assistant 401"},
    )
    bar = tick(None, "reference")[0]
    assert TEXTS["pl"]["machine_unknown"] in bar and 'title="Home Assistant 401"' in bar


def test_old_ssh_failure_of_a_server_job_clears_when_the_machine_answers(tmp_path, monkeypatch):
    pytest.importorskip("gradio")
    from piper_voice_cloner import remote
    from piper_voice_cloner.webui.app import build
    from piper_voice_cloner.webui.machine import MachineMonitor

    remote.save_config(tmp_path, remote.ServerConfig(host="gpu.lan"))
    jobs = JobManager(tmp_path)
    monitor = MachineMonitor(tmp_path, jobs, run=lambda command: '{"running": false}')
    monkeypatch.setattr(monitor, "refresh_in_background", lambda: None)
    app = build(tmp_path, "pl", jobs, monitor)
    tick = _app_fn(app, "tick")
    failed = jobs.dir
    failed.mkdir(parents=True, exist_ok=True)
    finished = time.time() - 60

    def last_job(kind, code):
        (failed / "current.json").write_text(
            json.dumps({"kind": kind, "voice": "", "log": str(failed / "x.log"), "started": finished - 4,
                        "returncode": code, "finished": finished})
        )  # fmt: skip

    last_job("remote-check", 255)
    monitor._checked = True
    assert "nie powiodło się (kod 255)" in tick(None, "reference")[0]  # machine not heard from yet
    monkeypatch.setattr(monitor, "_reachable", lambda: True)
    monitor.poll(force=True)  # the machine answered over SSH after the failure
    assert monitor.status()["answered_at"] > finished
    bar = tick(None, "reference")[0]
    assert "znów odpowiada przez SSH" in bar and "kod 255" not in bar
    last_job("remote-install", 1)  # a real failure stays red
    assert "nie powiodło się (kod 1)" in tick(None, "reference")[0]
    monitor.answered_at = finished - 10  # answered only before the failure
    last_job("remote-check", 255)
    assert "kod 255" in tick(None, "reference")[0]
    for code in TEXTS:
        assert TEXTS[code]["server_answers"]


def test_machine_switched_from_the_top_bar(tmp_path, monkeypatch):
    pytest.importorskip("gradio")
    import gradio as gr

    from piper_voice_cloner.webui.app import build
    from piper_voice_cloner.webui.machine import MachineMonitor

    jobs = JobManager(tmp_path)
    monitor = MachineMonitor(tmp_path, jobs)
    flipped = []
    monkeypatch.setattr(monitor, "switch_machine", lambda on: flipped.append(on))
    monkeypatch.setattr(monitor, "refresh_in_background", lambda: None)
    monkeypatch.setattr(gr, "Info", lambda message: None)
    app = build(tmp_path, "en", jobs, monitor)
    toggle = _app_fn(app, "toggle_machine")
    event = gr.EventData(None, {"machine": "on"})
    toggle(None, "reference", event)
    toggle(None, "reference", gr.EventData(None, {"machine": "bogus"}))
    assert flipped == [True]

    def refuse(on):
        raise RuntimeError(
            "a job is running on the machine: train (kuba) - stop it first or wait until it ends"
        )

    monkeypatch.setattr(monitor, "switch_machine", refuse)
    with pytest.raises(gr.Error, match="stop it first"):
        toggle(None, "reference", gr.EventData(None, {"machine": "off"}))


def test_home_assistant_settings_never_show_the_token(tmp_path, monkeypatch):
    pytest.importorskip("gradio")
    import gradio as gr

    from piper_voice_cloner import ha, power
    from piper_voice_cloner.webui.app import build
    from piper_voice_cloner.webui.machine import MachineMonitor

    jobs = JobManager(tmp_path)
    monitor = MachineMonitor(tmp_path, jobs)
    monkeypatch.setattr(monitor, "refresh_in_background", lambda: None)
    app = build(tmp_path, "en", jobs, monitor)
    token = "s" * 40
    found = {
        "switches": [{"id": "switch.maszyna_gpu", "name": "Maszyna GPU"}],
        "sensors": [{"id": "sensor.plug_power", "name": ""}],
        "count": 2,
    }
    monkeypatch.setattr(monitor, "ha_entities", lambda: found)
    message, box, switches, _sensors = _app_fn(app, "ha_save")("http://ha.lan:8123", token, None, None)
    assert message == TEXTS["en"]["ha_saved"].format(count=2) and ha.load_connection().token == token
    assert box["value"] == "" and box["placeholder"] == TEXTS["en"]["ha_token_saved"]
    assert switches["choices"] == [("Maszyna GPU (switch.maszyna_gpu)", "switch.maszyna_gpu")]
    url, box, *_rest = _app_fn(app, "ha_view")()
    assert url == "http://ha.lan:8123" and token not in json.dumps([url, box, *_rest], default=str)
    with pytest.raises(gr.Error, match="does not look like"):
        _app_fn(app, "ha_save")("http://ha.lan:8123", "short", None, None)

    def unreachable():
        raise ha.HaError("Home Assistant 401: the token is wrong or expired")

    monkeypatch.setattr(monitor, "ha_entities", unreachable)
    message, *_rest = _app_fn(app, "ha_save")("http://ha.lan:8123", None, None, None)
    assert "401" in message and ha.load_connection().token == token  # the empty field kept the token
    assert (
        _app_fn(app, "power_save")("switch.maszyna_gpu", "sensor.plug_power", 4) == TEXTS["en"]["power_saved"]
    )
    assert power.load_power() == power.PowerSettings("switch.maszyna_gpu", "sensor.plug_power", 4.0)
    with pytest.raises(gr.Error, match="sensor"):
        _app_fn(app, "power_save")("switch.maszyna_gpu", "switch.plug", 4)
    with pytest.raises(gr.Error, match="401"):
        _app_fn(app, "power_suggest")(None, None)
    assert _app_fn(app, "ha_remove")(False)[0] == gr.update()  # "Cancel" in the confirmation
    assert _app_fn(app, "ha_remove")(True)[0] == TEXTS["en"]["ha_removed"]
    assert not ha.load_connection().ready and power.load_power().ready
    with pytest.raises(gr.Error, match=TEXTS["en"]["ha_missing"]):
        _app_fn(app, "power_suggest")(None, None)


def test_icon_is_warm_and_not_the_purple_wake_word_square():
    Image = pytest.importorskip("PIL.Image")

    from piper_voice_cloner.webui import style

    svg = (style.STATIC / "favicon.svg").read_text(encoding="utf-8")
    assert "#f59e0b" in svg and "<circle" in svg and style.CLONE_WAVE in svg
    for purple in ("#5b5bf0", "#8b5cf6"):
        assert purple not in svg and purple not in style.ICON_LINKS
    assert style.CLONE_WAVE in style.topbar("T", "S", "en", ["en"])
    small, touch = (
        Image.open(style.STATIC / "favicon-32.png"),
        Image.open(style.STATIC / "apple-touch-icon.png"),
    )
    assert small.size == (32, 32) and touch.size == (180, 180)
    assert small.convert("RGBA").getpixel((0, 0))[3] == 0  # a circle: transparent corners
    assert touch.convert("RGBA").getpixel((0, 0))[3] == 255  # iOS rounds a full square itself
    red, green, blue, _alpha = touch.convert("RGBA").getpixel((90, 170))
    assert red > 200 and blue < 100 and red > green  # warm (amber/coral), no purple


def test_machine_checklist_in_tools(tmp_path, monkeypatch):
    gr = pytest.importorskip("gradio")
    from piper_voice_cloner import remote
    from piper_voice_cloner.webui import style
    from piper_voice_cloner.webui.app import build
    from piper_voice_cloner.webui.machine import MachineMonitor

    jobs = JobManager(tmp_path)
    app = build(tmp_path, "pl", jobs, MachineMonitor(tmp_path, jobs, run=lambda command: ""))
    view = _app_fn(app, "server_state_view")
    assert view(None)[0] == ""  # no server saved: no checklist
    remote.save_config(tmp_path, remote.ServerConfig(host="gpu.lan", user="tomek"))
    html, seen = view(None)
    assert "Jeszcze nie sprawdzona" in html
    assert view(seen)[0] == gr.update()  # nothing new: not re-drawn (keeps "pokaż" open)
    status = {
        "gpu": "NVIDIA GeForce RTX 4090, 24564, 580", "tools": dict.fromkeys(remote.SETUP_TOOLS, True),
        "uv": True, "free_gb": 900, "stamp": remote.code_stamp(), "venv": True, "train": "cuda",
        "voices": {}, "service": "active", "ui": True, "login": "admin:s3cret", "tensorboard": 6006,
    }  # fmt: skip
    remote.save_status(tmp_path, status)
    html, seen = view(None)
    assert "Gotowa do treningu" in html and "pvc-ready ready" in html and "admin / s3cret" in html
    remote.save_status(tmp_path, {**status, "stamp": "old", "service": "inactive", "ui": False})
    html = view(None)[0]
    assert "Do zrobienia: 2" in html and "zrobi Przygotuj" in html and "na maszynie jest inna wersja" in html
    tools = {**status["tools"], "ffmpeg": False}
    remote.save_status(tmp_path, {**status, "tools": tools, "sudo": False})
    html = view(None)[0]
    assert "✋" in html and "ssh -t tomek@gpu.lan sudo apt install -y ffmpeg" in html
    remote.save_status(tmp_path, None, "ssh: connect to host gpu.lan port 22: No route to host")
    assert "Maszyna nie odpowiedziała: ssh: connect" in view(None)[0]
    assert "<script" not in style.checklist_html("x", "idle", "<script>", [("ok", "<b>", "<i>", "")])


def test_bazowy_pl_is_offered_only_once_it_exists(tmp_path):
    from piper_voice_cloner import train as train_mod

    assert service.base_options(tmp_path) == (["lessac"], "lessac", False)
    # a voice set to the missing base shows lessac (train_view says why)
    assert service.base_options(tmp_path, "bazowy-pl") == (["lessac"], "lessac", False)
    assert service.base_options(tmp_path, "ckpt:/x.ckpt")[1] == "ckpt:/x.ckpt"
    (tmp_path / "bases").mkdir()
    (tmp_path / "bases" / train_mod.SCRATCH_BASE).write_bytes(b"x")
    assert service.base_options(tmp_path) == (["bazowy-pl", "lessac"], "bazowy-pl", True)
    assert service.base_options(tmp_path, "scratch-pl")[1] == "bazowy-pl"  # the old name
    assert service.base_options(tmp_path, "lessac")[1] == "lessac"
    for code in TEXTS:
        assert "bazowy-pl" in TEXTS[code]["base_create"] and TEXTS[code]["base_not_ready"]
        assert all("scratch-pl" not in text for text in TEXTS[code].values())


def test_train_tab_offers_to_create_the_missing_base(tmp_path):
    gr = pytest.importorskip("gradio")
    from piper_voice_cloner.webui.app import build
    from piper_voice_cloner.webui.machine import MachineMonitor

    service.create_voice(tmp_path, "kuba", base="bazowy-pl")
    jobs = JobManager(tmp_path)
    app = build(tmp_path, "pl", jobs, MachineMonitor(tmp_path, jobs, run=lambda command: ""))
    info, _ckpts, _epochs, base, create = _app_fn(app, "train_view")("kuba")
    assert "Model bazowy-pl jeszcze nie istnieje" in info
    assert base["choices"] == [("lessac", "lessac")] or base["choices"] == ["lessac"]
    assert base["value"] == "lessac" and create["visible"] is True
    tabs, current, _status = _app_fn(app, "open_base_section")("kuba")
    assert current == "tools" and isinstance(tabs, gr.Tabs)


def test_a_voice_the_session_does_not_know_is_no_traceback(tmp_path):
    """A browser tab from an earlier run can send a voice this run does not list."""
    gr = pytest.importorskip("gradio")
    from piper_voice_cloner.webui.app import build
    from piper_voice_cloner.webui.machine import MachineMonitor

    service.create_voice(tmp_path, "kuba")
    jobs = JobManager(tmp_path)
    app = build(tmp_path, "pl", jobs, MachineMonitor(tmp_path, jobs, run=lambda command: ""))
    dropdown = next(b for b in app.blocks.values() if isinstance(b, gr.Dropdown) and b.label == "Głos")
    assert dropdown.preprocess("kasia") == "kasia"  # no "not in the list of choices" error
    view = next(block.fn for block in app.fns.values() if getattr(block.fn, "__name__", "") == "train_view")
    assert view("kasia")[0] == ""  # treated as no voice
    with pytest.raises(gr.Error):
        _app_fn(app, "run_train")("kasia", "lessac", 10, False)


def test_base_section_offers_the_voices_largest_first(tmp_path):
    gr = pytest.importorskip("gradio")
    from piper_voice_cloner import remote
    from piper_voice_cloner.webui.app import build
    from piper_voice_cloner.webui.machine import MachineMonitor

    for name, clips in (("piotr", 3), ("kasia", 5), ("nowy", 0)):
        service.create_voice(tmp_path, name)
        if clips:
            folder = service.voice_dir(tmp_path, name) / "dataset"
            folder.mkdir()
            (folder / "metadata.csv").write_text("".join(f"{i}|Zdanie.\n" for i in range(clips)))
    sources = service.base_sources(tmp_path)
    assert [(name, clips) for name, clips, _folder in sources] == [("kasia", 5), ("piotr", 3)]
    jobs = JobManager(tmp_path)
    app = build(tmp_path, "pl", jobs, MachineMonitor(tmp_path, jobs, run=lambda command: ""))
    message, _ckpt, base_dir = _app_fn(app, "base_view")(None)
    assert "Model bazowy-pl jeszcze nie istnieje" in message and "Przygotuj dataset bazy" in message
    assert base_dir["choices"][0] == ("kasia - 5 klipów", str(sources[0][2]))
    assert base_dir["value"] == str(sources[0][2])
    assert _app_fn(app, "base_view")("/own/set")[2]["value"] == "/own/set"  # a typed path stays
    remote.save_config(tmp_path, remote.ServerConfig(host="gpu.lan"))
    assert "w panelu na maszynie** (http://gpu.lan:7860/)" in _app_fn(app, "base_view")(None)[0]
    with pytest.raises(gr.Error):
        _app_fn(app, "run_base_prepare")("", "")


def test_listening_to_the_training_in_the_panel(tmp_path, monkeypatch):
    pytest.importorskip("gradio")
    from piper_voice_cloner import remote
    from piper_voice_cloner.webui.app import build
    from piper_voice_cloner.webui.machine import MachineMonitor
    from tests.test_train_monitor import SENTENCES, validation, write

    monkeypatch.setenv("PVC_TB_PORT", "6010")
    service.create_voice(tmp_path, "kuba")
    jobs = JobManager(tmp_path)
    app = build(tmp_path, "pl", jobs, MachineMonitor(tmp_path, jobs, run=lambda command: ""))
    listen_voice, listen_base = _app_fn(app, "listen_voice"), _app_fn(app, "listen_base")
    head, epoch, *players = listen_voice("kuba")
    assert "Brak próbek" in head and ":6010/" in head and epoch["choices"] == []
    assert all(player["visible"] is False for player in players)

    logs = service.voice_dir(tmp_path, "kuba") / "train" / "lightning_logs"
    events = logs / "version_0" / "events.out.tfevents.1.host"
    write(events, *validation(100, 0, 2.0), *validation(200, 1, 3.5), *validation(300, 2, 3.25))
    head, epoch, *players = listen_voice("kuba")
    assert "Ostatnia epoka: **2**" not in head and "Ostatnia epoka: <b>2</b>" in head
    assert "najlepsza: <b>3.50</b> w epoce 1" in head and "Wykresy w TensorBoard" in head
    assert epoch["value"] == 2 and epoch["choices"][0] == ("epoka 2 · jakość 3.25", 2)
    shown = [player for player in players if player["visible"]]
    assert [player["label"] for player in shown] == SENTENCES and shown[0]["value"].endswith(".wav")
    assert listen_voice("kuba", 0)[1]["value"] == 0  # an older epoch to compare

    # the base trains elsewhere: this panel drives the machine and has no base run
    remote.save_config(tmp_path, remote.ServerConfig(host="gpu.lan"))
    head = listen_base()[1]
    assert (
        "odsłuch jest w panelu na maszynie (http://gpu.lan:7860/)" in head and "http://gpu.lan:6006/" in head
    )


def test_training_chart_under_the_log(tmp_path):
    gr = pytest.importorskip("gradio")
    import html as html_mod

    from piper_voice_cloner.webui import style
    from piper_voice_cloner.webui.app import build
    from piper_voice_cloner.webui.machine import MachineMonitor
    from tests.test_train_monitor import validation, write

    service.create_voice(tmp_path, "kuba")
    jobs = JobManager(tmp_path)
    app = build(tmp_path, "pl", jobs, MachineMonitor(tmp_path, jobs, run=lambda command: ""))
    chart_view = _app_fn(app, "chart_view")
    assert chart_view("kuba", None) == (gr.update(), None)  # no training logs anywhere: no chart
    base_events = service.base_work_dir(tmp_path) / "lightning_logs" / "version_0" / "events.out.tfevents.1.h"
    write(base_events, *validation(100, 0, 2.0), *validation(200, 1, 3.0))
    html, seen = chart_view("kuba", None)  # the voice has no logs: the base is shown
    payload = json.loads(html_mod.unescape(html.split('data-chart="')[1].split('"')[0]))
    assert payload["t"]["name"] == "Baza bazowy-pl (medium)" and payload["rows"] == [
        [0, 2.0, 1.0, 3.0],
        [1, 3.0, 0.5, 4.0],
    ]
    assert payload["best"] == {"mos": [1, 3.0], "mel": [1, 0.5]}
    assert "<b>val_mos</b>" in payload["help"] and "Przetrenowanie" in payload["help"]
    assert chart_view("kuba", seen) == (gr.update(), seen)  # no new epoch: not re-drawn
    voice_events = (
        service.voice_dir(tmp_path, "kuba")
        / "train"
        / "lightning_logs"
        / "version_0"
        / "events.out.tfevents.1.h"
    )
    write(voice_events, *validation(100, 0, 1.5))
    html, _seen = chart_view("kuba", seen)  # the chosen voice has logs now: it wins over the base
    assert "Głos kuba" in html_mod.unescape(html)
    for code in TEXTS:
        for key in ("chart_help", "chart_title_mos", "chart_best_mos", "chart_none"):
            assert TEXTS[code][key]
    assert "MutationObserver" in style.CHART_JS and "showModal" in style.CHART_JS


def _base_events(root, quality: str, *events: bytes) -> None:
    from tests.test_train_monitor import write

    work = service.base_work_dir(root, quality)
    write(work / "lightning_logs" / "version_0" / "events.out.tfevents.1.h", *events)


def test_two_base_sizes_side_by_side(tmp_path):
    from tests.test_train_monitor import validation

    assert service.base_runs(tmp_path) == [] and service.latest_base_run(tmp_path) is None
    assert service.compare_bases(tmp_path) == (None, [])
    # medium is far ahead; high has 3 epochs: compared at epoch 2 (the window clips to what exists)
    _base_events(
        tmp_path, "medium", *[e for n in range(12) for e in validation(100 * (n + 1), n, 2.0 + n / 10)]
    )
    _base_events(
        tmp_path, "high", *validation(100, 0, 2.5), *validation(200, 1, 2.9), *validation(300, 2, 3.0)
    )
    assert service.base_runs(tmp_path) == ["medium", "high"]
    common, results = service.compare_bases(tmp_path, window=2)
    assert common == 2
    medium, high = results
    assert (medium.quality, medium.last_epoch, high.last_epoch) == ("medium", 11, 2)
    assert medium.mos_at == pytest.approx((2.1 + 2.2) / 2) and high.mos_at == pytest.approx((2.9 + 3.0) / 2)
    assert medium.best_mos == (11, pytest.approx(3.1)) and high.best_mel == (2, pytest.approx(1 / 3))
    labels = [label for label, _path in service.base_checkpoint_choices(tmp_path)]
    assert labels == []  # no checkpoints written yet
    ckpt = (
        service.base_work_dir(tmp_path, "high") / "lightning_logs" / "version_0" / "checkpoints" / "last.ckpt"
    )
    ckpt.parent.mkdir(parents=True)
    ckpt.write_bytes(b"x")
    assert service.base_checkpoint_choices(tmp_path) == [("high · version_0/last.ckpt", str(ckpt))]


def test_base_panel_rates_recordings_and_compares_sizes(tmp_path, monkeypatch):
    pytest.importorskip("gradio")
    from piper_voice_cloner import dataset_quality
    from piper_voice_cloner.dataset import Utterance, write_metadata
    from piper_voice_cloner.webui.app import build
    from piper_voice_cloner.webui.machine import MachineMonitor
    from tests.test_train_monitor import _wav, validation

    jobs = JobManager(tmp_path)
    app = build(tmp_path, "pl", jobs, MachineMonitor(tmp_path, jobs, run=lambda command: ""))
    score_view, compare_view = _app_fn(app, "score_view"), _app_fn(app, "compare_view")
    run_score, run_base_train = _app_fn(app, "run_score"), _app_fn(app, "run_base_train")
    listen_base = _app_fn(app, "listen_base")

    box, worst_head, _best_head, *rest = score_view(None)
    assert "Jeszcze nie oceniono" in box and worst_head["visible"] is False
    with pytest.raises(Exception, match="bazowy-pl jeszcze nie istnieje"):
        run_score(300)  # no base dataset yet
    assert compare_view() == "Nie ma jeszcze żadnego treningu bazy."

    # a rating saved by `pvc base score`
    dataset = service.base_dataset_dir(tmp_path)
    clips = {f"c{i}": 3.0 + i / 10 for i in range(8)}
    write_metadata(dataset / "metadata.csv", [Utterance(c, f"Zdanie {c}.") for c in clips])
    (dataset / "wav").mkdir()
    for clip in clips:
        (dataset / "wav" / f"{clip}.wav").write_bytes(_wav())
    report = {"created": 1.0, "total": 8, "scores": clips, "texts": {c: f"Zdanie {c}." for c in clips}}
    dataset_quality.report_path(dataset).write_text(json.dumps(report))
    _base_events(tmp_path, "medium", *validation(100, 0, 3.2), *validation(200, 1, 3.4))
    box, worst_head, best_head, *rest = score_view(None)
    players, seen = rest[:-1], rest[-1]
    assert "Mediana" in box and "3.35" in box and "3.40 (medium)" in box
    assert worst_head["visible"] and best_head["visible"]
    assert players[0]["label"] == "3.00 · Zdanie c0." and players[3]["label"] == "3.70 · Zdanie c7."
    assert players[0]["value"].endswith("c0.wav")
    assert score_view(seen)[0] == gr_update()  # nothing new: not redrawn

    table = compare_view()
    assert "| medium | 1 | 3.30 |" in table and "val_mos, epoki 0-1" in table and "**3.35**" in table

    started = []
    monkeypatch.setattr(jobs, "start", lambda kind, voice, args, **_kw: started.append((kind, args)))
    run_base_train(200, "high", 12)
    assert started[-1] == (
        "base-train",
        ["base", "train", "--max-epochs", "200", "--quality", "high", "--batch-size", "12"],
    )

    # listening: the model switch appears with the second size, the newest run is shown first
    model = listen_base()[0]
    assert model["visible"] is False and model["value"] == "medium"
    _base_events(tmp_path, "high", *validation(100, 0, 2.5))
    model = listen_base()[0]
    assert model["visible"] is True and model["choices"] == ["medium", "high"]
    assert listen_base("medium")[0]["value"] == "medium"


def gr_update():
    import gradio as gr

    return gr.update()


def test_generation_speed_and_the_estimate_for_all_sentences(tmp_path):
    pytest.importorskip("gradio")
    from piper_voice_cloner import corpus as corpus_mod, synthesis
    from piper_voice_cloner.webui.app import build
    from piper_voice_cloner.webui.machine import MachineMonitor

    service.create_voice(tmp_path, "kuba")
    jobs = JobManager(tmp_path)
    app = build(tmp_path, "pl", jobs, MachineMonitor(tmp_path, jobs, run=lambda command: ""))
    view = _app_fn(app, "synth_timing_view")
    assert view("kuba") == "" and view(None) == ""
    directory = service.voice_dir(tmp_path, "kuba")
    corpus_mod.write_prompts(directory / corpus_mod.PROMPTS, [(f"p{i}", "Zdanie.") for i in range(1950)])
    (directory / "raw").mkdir()
    (directory / "raw" / synthesis.TIMING).write_text(
        json.dumps({"clips": 50, "seconds": 150.0, "audio_seconds": 200.0, "device": "mps"})
    )
    text = view("kuba")
    assert "**50** klipów w 2.5 min na **mps**" in text and "3.0 s na klip" in text
    assert "Wszystkie zdania (1950)" in text and "**01:37:30**" in text  # 1950 x 3 s


def test_log_window_can_be_enlarged_and_copied():
    import html as html_mod

    from piper_voice_cloner.webui import jobs, style

    tools = style.log_tools(TEXTS["pl"])
    assert 'class="expand"' in tools and 'class="copy"' in tools and "Powiększ" in tools
    raw = tools.split('data-labels="', 1)[1].split('"', 1)[0]
    labels = json.loads(html_mod.unescape(raw))
    assert labels["log_copied"] == "Skopiowano" and labels["log"] == TEXTS["pl"]["log"]
    # plain http on the LAN has no navigator.clipboard: the copy must fall back to execCommand
    assert "isSecureContext" in style.LOG_JS and 'execCommand("copy")' in style.LOG_JS
    assert ".pvc-log-dialog" in style.CSS
    # a whole Python traceback fits in the log window
    assert jobs.TAIL_LINES >= 100


def test_training_samples_can_be_downloaded_as_a_zip(tmp_path):
    pytest.importorskip("gradio")
    from piper_voice_cloner.webui.app import build
    from piper_voice_cloner.webui.machine import MachineMonitor
    from tests.test_train_monitor import validation, write

    jobs = JobManager(tmp_path)
    app = build(tmp_path, "pl", jobs, MachineMonitor(tmp_path, jobs, run=lambda command: ""))
    download_base = _app_fn(app, "download_base_samples")
    with pytest.raises(Exception, match="Nie ma jeszcze próbek"):
        download_base(None)
    events = (
        service.base_work_dir(tmp_path, "medium") / "lightning_logs" / "version_0" / "events.out.tfevents.1"
    )
    write(events, *validation(100, 0, 3.0))
    update = download_base(None)
    assert update["visible"] is True and update["value"].endswith("samples.zip")
    with pytest.raises(Exception, match="Nie ma jeszcze próbek"):
        _app_fn(app, "download_voice_samples")("")  # no voice chosen


def test_sentence_sets_are_imported_voices_only(tmp_path):
    for name, report in (("marek", "import_report.csv"), ("alicja", "filter_report.csv")):
        service.create_voice(tmp_path, name)
        dataset = service.voice_dir(tmp_path, name) / "dataset"
        dataset.mkdir()
        (dataset / "metadata.csv").write_text("a.wav|Zdanie.\n", encoding="utf-8")
        (dataset / report).write_text("", encoding="utf-8")
    assert service.sentence_sets(tmp_path) == [("marek", 1)]


def test_missing_sentences_count_what_is_left_to_pay_for(tmp_path):
    service.create_voice(tmp_path, "alicja", backend="elevenlabs")
    directory = service.voice_dir(tmp_path, "alicja")
    assert service.missing_sentences(tmp_path, "alicja") == (0, 0)
    (directory / "prompts.tsv").write_text("id\ttext\na\tAla.\nb\tOla ma.\n", encoding="utf-8")
    (directory / "raw").mkdir()
    (directory / "raw" / "manifest.csv").write_text(
        "id,text,reference,seed,backend,rate\na,Ala.,-,1,elevenlabs:o,24000\n", encoding="utf-8"
    )
    assert service.missing_sentences(tmp_path, "alicja") == (1, 7)


def test_elevenlabs_voice_needs_no_reference_step(tmp_path):
    service.create_voice(tmp_path, "alicja", backend="elevenlabs")
    service.create_voice(tmp_path, "kuba")
    assert service.steps(tmp_path, "alicja")[0].done
    assert not service.steps(tmp_path, "kuba")[0].done


def test_new_voice_starts_from_the_polish_base_and_chatterbox(tmp_path):
    cfg = service.create_voice(tmp_path, "kuba")
    assert (cfg.synthesis.backend, cfg.train.base) == ("chatterbox", "bazowy-pl")


def test_rename_voice_moves_the_folder_and_keeps_the_clips(tmp_path):
    service.create_voice(tmp_path, "kuba")
    clip = service.voice_dir(tmp_path, "kuba") / "raw" / "a.wav"
    clip.parent.mkdir()
    clip.write_bytes(b"x")
    cfg = service.rename_voice(tmp_path, "kuba", "Kuba Bajka", " pl_PL-kuba_bajka ")
    assert (cfg.name, cfg.piper_name) == ("kuba_bajka", "pl_PL-kuba_bajka")
    assert service.list_voices(tmp_path) == ["kuba_bajka"]
    assert (service.voice_dir(tmp_path, "kuba_bajka") / "raw" / "a.wav").is_file()
    assert service.load_config(tmp_path, "kuba_bajka").name == "kuba_bajka"


def test_rename_voice_can_change_only_the_piper_name(tmp_path):
    service.create_voice(tmp_path, "kuba", piper_name="pl_PL-stary")
    service.rename_voice(tmp_path, "kuba", "kuba", "")
    assert service.load_config(tmp_path, "kuba").piper_name is None


def test_rename_voice_refuses_taken_and_empty_names(tmp_path):
    service.create_voice(tmp_path, "kuba")
    service.create_voice(tmp_path, "ala")
    with pytest.raises(ValueError, match="already exists"):
        service.rename_voice(tmp_path, "kuba", "ala", "")
    with pytest.raises(ValueError):
        service.rename_voice(tmp_path, "kuba", "  ", "")
    assert service.list_voices(tmp_path) == ["ala", "kuba"]


def test_set_backend_drops_the_options_of_the_old_model(tmp_path):
    service.create_voice(tmp_path, "kuba")
    cfg = service.load_config(tmp_path, "kuba")
    cfg.synthesis.options = {"cfg_weight": 0.3}
    config_mod.save(service.voice_dir(tmp_path, "kuba"), cfg)
    service.set_backend(tmp_path, "kuba", "chatterbox")
    assert service.load_config(tmp_path, "kuba").synthesis.options == {"cfg_weight": 0.3}
    service.set_backend(tmp_path, "kuba", "elevenlabs")
    synth = service.load_config(tmp_path, "kuba").synthesis
    assert (synth.backend, synth.options) == ("elevenlabs", {})


def test_imported_voice_keeps_its_model_and_sentences(tmp_path):
    service.create_voice(tmp_path, "piotr")
    dataset = service.voice_dir(tmp_path, "piotr") / "dataset"
    dataset.mkdir()
    (dataset / "import_report.csv").write_text("", encoding="utf-8")
    with pytest.raises(ValueError, match="imported voice"):
        service.set_backend(tmp_path, "piotr", "elevenlabs")
    with pytest.raises(ValueError, match="imported voice"):
        corpus.use_dataset_sentences(service.voice_dir(tmp_path, "piotr"), tmp_path)
    assert service.load_config(tmp_path, "piotr").synthesis.backend == "chatterbox"


def test_panel_opens_the_voice_worked_on_last(tmp_path):
    assert service.opening_voice(tmp_path) is None
    service.create_voice(tmp_path, "agata")
    service.create_voice(tmp_path, "alicja")
    assert service.opening_voice(tmp_path) == "agata"
    service.remember_voice(tmp_path, "alicja")
    service.remember_voice(tmp_path, None)
    assert service.opening_voice(tmp_path) == "alicja"
    service.rename_voice(tmp_path, "alicja", "alicja_nowa", "")
    assert service.opening_voice(tmp_path) == "agata"


@pytest.mark.parametrize(
    ("poweroff", "code", "expected"),
    [(True, 0, True), (True, 1, True), (True, 130, False), (True, -2, False), (False, 0, False)],
)
def test_machine_powers_off_after_the_job_but_not_after_stop(tmp_path, monkeypatch, poweroff, code, expected):
    from piper_voice_cloner.webui import runner

    flag = tmp_path / "off"
    monkeypatch.setenv(runner.POWEROFF_ENV, shlex.join(["touch", str(flag)]))
    state = tmp_path / "current.json"
    state.write_text(json.dumps({"poweroff": poweroff}), encoding="utf-8")
    cmd = ["sh", "-c", f"exit {code}"] if code >= 0 else ["sh", "-c", "kill -INT $$"]
    runner.run(state, tmp_path / "job.log", cmd)
    assert flag.exists() is expected
    assert ("Powering" in (tmp_path / "job.log").read_text(encoding="utf-8")) is expected


def test_job_records_the_poweroff_wish(tmp_path):
    fake_pvc(tmp_path, "exit 0")
    manager = JobManager(tmp_path, pvc=fake_pvc(tmp_path, "exit 0"))
    manager.start("train", "kuba", ["train"], poweroff=True)
    assert json.loads(manager.state_path.read_text(encoding="utf-8"))["poweroff"] is True


def test_poweroff_wish_changes_while_the_job_runs(tmp_path):
    manager = JobManager(tmp_path, pvc=fake_pvc(tmp_path, "import time\ntime.sleep(30)\n"))
    manager.start("train-queue", "", ["train-queue"], poweroff=True)
    deadline = time.time() + 10
    while "child_pid" not in json.loads(manager.state_path.read_text(encoding="utf-8")):
        assert time.time() < deadline, "the runner did not start the job"
        time.sleep(0.05)
    before = json.loads(manager.state_path.read_text(encoding="utf-8"))
    assert manager.status().poweroff is True
    assert manager.set_poweroff(False) is True
    assert manager.status().poweroff is False
    after = json.loads(manager.state_path.read_text(encoding="utf-8"))
    assert after == {**before, "poweroff": False}  # the runner and its child stay tracked
    assert manager.set_poweroff(True) is True
    assert manager.status().poweroff is True
    manager.stop()
    manager.wait()


def test_poweroff_wish_cannot_change_after_the_job(tmp_path):
    manager = JobManager(tmp_path, pvc=fake_pvc(tmp_path, "exit 0"))
    manager.start("train", "kuba", ["train"], poweroff=True)
    manager.wait()
    assert manager.set_poweroff(False) is False
    assert manager.status().poweroff is True


def _write_keys(path, prefix):
    from piper_voice_cloner.webui.runner import update_state

    for i in range(40):
        update_state(path, **{f"{prefix}{i}": i})


def test_state_updates_from_two_processes_are_not_lost(tmp_path):
    import multiprocessing

    path = tmp_path / "jobs" / "current.json"
    workers = [multiprocessing.Process(target=_write_keys, args=(path, p)) for p in ("a", "b")]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(30)
    state = json.loads(path.read_text(encoding="utf-8"))
    assert len(state) == 80
    assert not list(path.parent.glob("*.tmp"))


def test_tests_never_run_the_real_poweroff():
    import os

    from piper_voice_cloner.webui import runner

    assert os.environ[runner.POWEROFF_ENV] == "true"
    assert runner.poweroff_command() == ["true"]


def test_poweroff_command_defaults_to_sudo_poweroff(monkeypatch):
    from piper_voice_cloner.webui import runner

    monkeypatch.delenv(runner.POWEROFF_ENV)
    assert runner.poweroff_command() == ["sudo", "-n", "/usr/sbin/poweroff"]


def test_runner_obeys_the_wish_changed_during_the_job(tmp_path, monkeypatch):
    from piper_voice_cloner.webui import runner

    flag = tmp_path / "off"
    monkeypatch.setenv(runner.POWEROFF_ENV, shlex.join(["touch", str(flag)]))
    state = tmp_path / "current.json"
    state.write_text(json.dumps({"poweroff": True}), encoding="utf-8")
    changed = json.dumps({"poweroff": False})
    runner.run(state, tmp_path / "job.log", ["sh", "-c", f"printf '%s' '{changed}' > '{state}'"])
    assert not flag.exists()


def test_panel_shows_the_poweroff_box_only_during_a_job_on_the_machine(tmp_path, monkeypatch):
    from piper_voice_cloner.webui.app import build

    monkeypatch.setattr("sys.platform", "linux")
    manager = JobManager(tmp_path, pvc=fake_pvc(tmp_path, "import time\ntime.sleep(30)\n"))
    tick = _app_fn(build(tmp_path, "pl", manager), "tick")
    assert tick(None, "reference")[-2]["visible"] is False
    manager.start("train", "kuba", ["train"], poweroff=True)
    box, value = tick(None, "reference")[-2:]
    assert box["visible"] is True
    assert value is True
    manager.stop()
    manager.wait()


def test_queue_offers_voices_with_a_dataset_and_follows_the_current_one(tmp_path):
    service.create_voice(tmp_path, "pusty")
    service.create_voice(tmp_path, "piotr")
    dataset = service.voice_dir(tmp_path, "piotr") / "dataset"
    dataset.mkdir()
    (dataset / "metadata.csv").write_text("a|Zdanie.\n", encoding="utf-8")
    assert service.trainable_voices(tmp_path) == ["piotr"]
    assert service.queue_voice(tmp_path) is None
    (tmp_path / "jobs").mkdir()
    (tmp_path / "jobs" / "train_queue.json").write_text('{"voice": "piotr"}', encoding="utf-8")
    assert service.queue_voice(tmp_path) == "piotr"


def test_running_queue_names_the_current_voice(tmp_path):
    from types import SimpleNamespace

    (tmp_path / "jobs").mkdir()
    (tmp_path / "jobs" / "train_queue.json").write_text('{"voice": "tomek"}', encoding="utf-8")
    running = SimpleNamespace(kind="train-queue", running=True)
    finished = SimpleNamespace(kind="train-queue", running=False)
    other = SimpleNamespace(kind="train", running=True)
    assert service.job_label(tmp_path, running, "Kolejka treningów") == "Kolejka treningów - tomek"
    assert service.job_label(tmp_path, finished, "Kolejka treningów") == "Kolejka treningów"
    assert service.job_label(tmp_path, other, "Trening") == "Trening"


def test_compact_log_keeps_the_latest_epoch_and_drops_what_every_epoch_repeats():
    log = (
        "queue 1/6: alicja_nowa\n"
        "training epochs 1113-1613\n"
        "Epoch 1113: 100%|###| 42/42 [00:15<00:00]\n"
        "Validation: |   | 0/? [00:00<?, ?it/s]\x1b[A\n"
        "Validation DataLoader 0: 100%|#| 3/3 [00:00<00:00]\x1b[AUsing cache found in /x/SpeechMOS\n"
        "/venv/torch/nn/utils/weight_norm.py:145: FutureWarning: deprecated\n"
        "  WeightNorm.apply(module, name, dim)\n"
        "Epoch 1114: 100%|###| 42/42 [00:15<00:00]\n"
        "queue: piotr failed: boom"
    )
    assert service.compact_log(log).split("\n") == [
        "queue 1/6: alicja_nowa",
        "training epochs 1113-1613",
        "Epoch 1114: 100%|###| 42/42 [00:15<00:00]",
        "queue: piotr failed: boom",
    ]


def test_training_label_adds_the_epochs_of_this_voice():
    log = "training epochs 1113-1613\nEpoch 1324: 90%|# | 38/42 [00:10<00:03]"
    done, total, label, _left = service.training_progress(log)
    assert label == (1324, 38, 42)
    assert (int(done), total) == (211, 500)


def test_status_keeps_the_training_plan_long_after_it_left_the_tail(tmp_path):
    manager = JobManager(tmp_path, pvc=fake_pvc(tmp_path, "exit 0"))
    manager.dir.mkdir()
    log = manager.dir / "train.log"
    state = {"kind": "train-queue", "voice": "", "log": str(log), "runner_pid": 1, "returncode": 0}
    manager.state_path.write_text(json.dumps(state), encoding="utf-8")
    lines = [f"Epoch {n}: 90%|# | 38/42 [00:10<00:03]" for n in range(1113, 1400)]
    log.write_text("training epochs 1113-1613\n" + "\n".join(lines) + "\n", encoding="utf-8")
    tail_text = manager.status().log_tail
    assert tail_text.split("\n")[0] == "training epochs 1113-1613"
    assert service.training_progress(tail_text)[1] == 500
    with log.open("a", encoding="utf-8") as handle:
        handle.write("training epochs 1113-1713\nEpoch 1400: 90%|# | 38/42 [00:10<00:03]\n")
    assert service.training_progress(manager.status().log_tail)[1] == 600


QUEUE_LOG = """$ pvc --root /data train-queue ali tomek bad piotr --epochs 500 --base bazowy-pl
queue 1/4: opt
queue 2/4: tomek
queue 3/4: bad
queue: bad failed: boom
queue 4/4: piotr
"""


def queue_status(log, running=True, code=None):
    from types import SimpleNamespace

    return SimpleNamespace(queue_log=log, running=running, returncode=code)


def test_queue_steps_tell_where_the_queue_is():
    short = QUEUE_LOG.split("queue 3/4")[0]
    assert service.queue_steps(queue_status(short)) == [
        ("ali", "done"),
        ("tomek", "now"),
        ("bad", "waiting"),
        ("piotr", "waiting"),
    ]
    assert [s for _n, s in service.queue_steps(queue_status(QUEUE_LOG, False, 1))] == [
        "done",
        "done",
        "failed",
        "done",
    ]
    assert service.queue_steps(queue_status(short, False, 130))[1] == ("tomek", "stopped")
    assert service.queue_steps(queue_status("")) == []


def test_queue_card_names_each_voice_and_state():
    from piper_voice_cloner.webui import style

    t = TEXTS["pl"]
    card = style.queue_html(t, [("ali", "done"), ("<j>", "now"), ("piotr", "waiting")])
    assert "Kolejka treningów: głos 2 z 3" in card
    assert "wytrenowany" in card and "trenuje teraz" in card and "czeka" in card
    assert "&lt;j&gt;" in card
    assert style.queue_html(t, []) == ""


def test_status_reads_the_whole_queue_from_the_log(tmp_path):
    manager = JobManager(tmp_path, pvc=fake_pvc(tmp_path, "exit 0"))
    manager.dir.mkdir()
    log = manager.dir / "queue.log"
    state = {"kind": "train-queue", "voice": "", "log": str(log), "runner_pid": 1, "returncode": 0}
    manager.state_path.write_text(json.dumps(state), encoding="utf-8")
    log.write_text(QUEUE_LOG.split("queue 2/4")[0] + "Epoch 1: 50%|#| 1/2\r", encoding="utf-8")
    assert len(service.queue_steps(manager.status())) == 4
    with log.open("a", encoding="utf-8") as handle:
        handle.write("Epoch 2: 90%|#| 1/2\nqueue 2/4: tomek\n")
    assert "queue 2/4: tomek" in manager.status().queue_log
    assert manager.status().queue_log.count("queue 1/4") == 1
