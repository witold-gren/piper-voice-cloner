"""The editor's data side: voices, steps, results, bases, training progress, jobs and the runner."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import time

import pytest

from piper_voice_cloner import config as config_mod, corpus, dataset
from piper_voice_cloner.editor import service
from piper_voice_cloner.jobs import JobBusy, JobManager, tail

from .conftest import write_tone


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


def test_set_max_epochs_and_base_ready(tmp_path):
    service.create_voice(tmp_path, "kuba")
    service.set_max_epochs(tmp_path, "kuba", 400)
    assert service.load_config(tmp_path, "kuba").train.max_epochs == 400
    assert not service.base_ready(tmp_path)
    (tmp_path / "bases").mkdir()
    (tmp_path / "bases" / "pl-scratch.ckpt").write_bytes(b"x")
    assert service.base_ready(tmp_path)


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


def test_parse_progress_reads_our_lines_and_the_epoch_bar():
    assert service.parse_progress("") is None
    log = "$ pvc import\nprogress import 19/1915\nprogress import 38/1915\n"
    assert service.parse_progress(log) == (38, 1915, "")
    train = log + "Epoch 2170: 37%|███   | 21/56 [00:10<00:17]\rEpoch 2170: 39%|███   | 22/56 [00:11<00:16]"
    assert service.parse_progress(train) == (22, 56, "Epoch 2170")
    assert service.parse_progress("progress x 0/0") is None


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


def test_compact_log_keeps_only_the_latest_progress_line():
    log = "$ pvc import\nprogress import 1/3\nprogress import 2/3\nwarning\nprogress import 3/3\nkept 3 of 3"
    assert service.compact_log(log) == "$ pvc import\nwarning\nprogress import 3/3\nkept 3 of 3"
    assert service.compact_log("") == ""


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
    from piper_voice_cloner.runner import update_state

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
