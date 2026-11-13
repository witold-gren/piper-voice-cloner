"""Gradio layout. Logic lives in `service` (data) and `jobs` (background `pvc` commands)."""

from __future__ import annotations

import asyncio
from functools import partial
import html
import json
import logging
import os
from pathlib import Path
import sys
import time

import gradio as gr
from pydantic import ValidationError

from .. import (
    config as config_mod,
    dataset_quality,
    ha,
    power,
    reference as reference_mod,
    remote as remote_mod,
    synthesis as synthesis_mod,
    train as train_mod,
    train_monitor,
)
from ..backends import elevenlabs
from ..corpus import use_dataset_sentences
from . import service, style
from .jobs import JobBusy, JobManager
from .machine import MachineMonitor
from .runner import STOPPED_CODES
from .texts import LANGUAGES, texts

PLAYERS = 6
SCORE_PLAYERS = 3  # worst and best rated recordings shown for listening
COMPARE_WINDOW = 10  # epochs averaged when base models are compared
BACKENDS = ["chatterbox", "xtts", "elevenlabs"]
# ssh's own exit code when it could not connect (machine off, no route, refused)
SSH_FAILED = 255
# tab ids: the numbered steps (same keys as service.steps) and the extra tabs with their stepper icon
# the chart's words (texts "chart_<key>"), handed to the browser with the data
CHART_LABELS = ("title_mos", "title_mel", "epoch", "open", "none", "from", "to", "all", "pinned", "pick",
                "best_mos", "best_mel")  # fmt: skip
STEP_TABS = ["reference", "corpus", "audition", "synthesize", "filter", "train", "export"]
EXTRA_TABS = [("settings", "⚙"), ("tools", "⚒")]


def user_error(message: str) -> gr.Error:
    """A message for the person at the panel (busy job, missing field): no traceback in the terminal."""
    return gr.Error(message, print_exception=False)


def build(
    root: Path, lang: str = "en", jobs: JobManager | None = None, machine: MachineMonitor | None = None
) -> gr.Blocks:
    t = texts(lang)
    jobs = jobs or JobManager(root)
    # rating recordings runs next to a training (on the CPU when the GPU is full)
    side_jobs = JobManager(root, slot="side")
    machine = machine or MachineMonitor(root, jobs)

    # --- helpers ------------------------------------------------------------------------------

    def step_head(tab_key: str, info_key: str, title: str | None = None) -> str:
        """Tab title ("1. Recording") with the "?" explanation of the step."""
        label = title or t[tab_key]
        number, _, name = label.partition(". ")
        if not number.isdigit():
            number, name = "", label
        return style.step_info(number, name, t["info_title"], t[info_key])

    def need_voice(voice: str | None) -> str:
        if not voice or voice not in service.list_voices(root):
            raise user_error(t["no_voice"])
        return voice

    def players(items: list[tuple[Path, str]]) -> list:
        updates = [
            gr.update(value=str(path), label=label[:120], visible=True) for path, label in items[:PLAYERS]
        ]
        return updates + [gr.update(value=None, visible=False)] * (PLAYERS - len(updates))

    def status_md(voice: str | None, current: str = STEP_TABS[0]) -> str:
        extra = [(key, t["tab_" + key], icon) for key, icon in EXTRA_TABS]
        if not voice:
            items = [(key, t["step_" + key], False, "") for key in STEP_TABS]
            return style.steps_html(items, current=current, extra=extra, empty=t["no_voice"])
        items = [(s.key, t["step_" + s.key], s.done, s.detail) for s in service.steps(root, voice)]
        return style.steps_html(items, current=current, extra=extra)

    def navigate(voice, event: gr.EventData):
        key = getattr(event, "tab", "")
        key = key if key in STEP_TABS or key in dict(EXTRA_TABS) else STEP_TABS[0]
        return gr.Tabs(selected=key), key, status_md(voice, key)

    def job_state(status) -> tuple[str, str]:
        """(css state, sentence) for the status pill."""
        if status is None:
            return "idle", t["job_none"]
        values = {
            "kind": job_name(status),
            "voice": f" ({status.voice})" if status.voice else "",
            "code": status.returncode,
        }
        if status.running:
            return "running", t["job_running"].format(**values)
        if status.finished_ok:
            return "ok", t["job_ok"].format(**values)
        if status.returncode in STOPPED_CODES:
            return "stopped", t["job_stopped"].format(**values)
        return "failed", t["job_failed"].format(**values)

    def kind_name(kind: str) -> str:
        return t.get("kind_" + kind, kind)

    def job_name(status) -> str:
        return service.job_label(root, status, kind_name(status.kind))

    def connection_failure_is_old(status, remote) -> bool:
        """A server job that could not connect (SSH 255) while the machine was off, and the machine
        has answered over SSH since: the red pill would only mislead."""
        return bool(
            status
            and not status.running
            and status.kind.startswith("remote-")
            and status.returncode == SSH_FAILED
            and status.finished
            and remote.get("answered_at")
            and remote["answered_at"] > status.finished
        )

    def job_pill(status) -> str:
        """A job here first; else what the GPU machine said (only its last known state - never waits)."""
        remote = machine.status()
        title = t["machine_ssh_error"].format(error=remote["error"]) if remote["error"] else ""
        if not (status and status.running):
            if remote["checking"]:
                return style.status_pill("checking", t["status_checking"])
            if remote["running"]:
                voice = f" ({remote['voice']})" if remote["voice"] else ""
                sentence = t["job_remote_running"].format(kind=kind_name(remote["kind"]), voice=voice)
                return style.status_pill("running", sentence, title)
        if connection_failure_is_old(status, remote):
            return style.status_pill("ok", t["server_answers"], title)
        state, sentence = job_state(status)
        return style.status_pill(state, sentence, title)

    def machine_html() -> str:
        """The machine's power button (Home Assistant), or nothing when it is not set up."""
        view = machine.machine_cached()
        if view is None:
            return ""
        kind = view.get("machine") or "unknown"
        watts = view.get("watts")
        text = t.get("machine_" + kind, t["machine_unknown"])
        if watts is not None and kind != "off":
            text += f" · {watts:.0f} W"
        if kind in ("on", "starting"):
            action, hint, confirm = "off", t["machine_off_hint"], t["machine_off_confirm"]
        elif kind == "off":
            action, hint, confirm = "on", t["machine_on_hint"], t["machine_on_confirm"]
        elif kind == "rejected":  # nothing asks Home Assistant until the connection is saved again
            return style.machine_button(kind, text, t["ha_token_rejected"])
        else:  # checking, shutting down, no reading: nothing to click
            action, hint, confirm = "", t["machine_wait_hint"], ""
        return style.machine_button(kind, text, view.get("error") or hint, action, confirm)

    def topbar_html(status) -> str:
        bar = style.topbar(t["title"], t["subtitle"], lang, LANGUAGES, guide=t["guide"])
        # machine power and status pill on the right of the top bar, next to the language switch
        return bar.replace(
            '<div class="pvc-top-right">',
            f'<div class="pvc-top-right">{machine_html()}{job_pill(status)}',
            1,
        )

    def progress_bar(status) -> str:
        """Training: epochs of the whole run + time left; other jobs: their own counter."""
        found = service.training_progress(status.log_tail)
        label = detail = ""
        if found:
            done, total, position, left = found
            unit = t["epochs"]
            if position:
                epoch, step, steps = position
                detail = t["train_position"].format(epoch=epoch, step=step, steps=steps)
        else:
            found = service.parse_progress(status.log_tail)
            if not found:
                return ""
            done, total, label = found
            left, unit = service.time_left(status.elapsed(), done, total), ""
        remaining = t["time_left"].format(time=service.format_elapsed(left)) if left else ""
        return style.progress_html(done, total, label, unit=unit, detail=detail, remaining=remaining)

    def live_card(status) -> str:
        gpu = service.gpu_stats()
        if status is None:
            return style.live_html(t, t["stage_idle"], "—", gpu)
        elapsed = service.format_elapsed(status.elapsed())
        name = f"**{job_name(status)}**" + (f" ({status.voice})" if status.voice else "")
        queue = style.queue_html(t, service.queue_steps(status))
        if status.running:
            return style.live_html(t, name, elapsed, gpu, progress=progress_bar(status), queue=queue)
        state, _sentence = job_state(status)
        stage = f"{name} – {t['result_' + state]}"
        return style.live_html(
            t, stage, elapsed, gpu, stage_label=t["stage_last"], elapsed_label=t["elapsed_took"], queue=queue
        )

    def start(kind: str, voice: str, args: list[str], *, poweroff: bool = False) -> str:
        try:
            jobs.start(kind, voice, args, poweroff=poweroff)
        except JobBusy as err:
            job = kind_name(err.kind) + (f" ({err.voice})" if err.voice else "")
            raise user_error(t["job_busy"].format(job=job)) from err
        return t["job_started"].format(kind=kind_name(kind))

    # only the GPU machine may power itself off, never the computer at the desk
    can_power_off = sys.platform == "linux"

    def tick(voice, current):
        machine.refresh_in_background()  # the answer shows up on a later tick; never waited for here
        status = jobs.status()
        return (
            topbar_html(status),
            live_card(status),
            service.compact_log(status.log_tail) if status else "",
            status_md(voice, current),
            gr.update(interactive=bool(status and status.running)),
            gr.update(visible=can_power_off and bool(status and status.running)),
            bool(status and status.poweroff),
        )

    def set_job_poweroff(poweroff):
        if not jobs.set_poweroff(poweroff):
            gr.Info(t["job_poweroff_late"])

    # --- voice ------------------------------------------------------------------------------------

    def refresh_voices(current):
        names = service.list_voices(root)
        value = current if current in names else (names[0] if names else None)
        return gr.update(choices=names, value=value)

    def open_voice():
        return gr.update(choices=service.list_voices(root), value=service.opening_voice(root))

    def create(name, piper_name):
        try:
            cfg = service.create_voice(root, name, piper_name=piper_name.strip() or None)
        except ValidationError as err:  # show only the rule, not pydantic's wrapper text
            raise user_error(t["error"].format(error="; ".join(e["msg"] for e in err.errors()))) from err
        except Exception as err:  # validation messages go to the user
            raise user_error(t["error"].format(error=err)) from err
        return gr.update(choices=service.list_voices(root), value=cfg.name), t["created"].format(
            name=cfg.name
        )

    # --- steps ------------------------------------------------------------------------------------

    def prepare_reference(voice, files, embed):
        voice = need_voice(voice)
        if not files:
            raise user_error(t["reference_files"])
        directory = service.voice_dir(root, voice)
        saved = service.save_uploads(directory / "reference" / "uploads", files)
        embedder = None
        if embed:
            from ..quality.speaker import DEFAULT_MODEL, SpeakerEmbedder, ensure_model

            embedder = SpeakerEmbedder(ensure_model(DEFAULT_MODEL, root / "models")).embed
        try:
            info = reference_mod.prepare(saved, directory / "reference", embedder)
        except Exception as err:
            raise user_error(t["error"].format(error=err)) from err
        if "min_similarity" in info:
            cfg = service.load_config(root, voice)
            cfg.quality.min_similarity = info["min_similarity"]
            config_mod.save(directory, cfg)
        message = t["reference_done"].format(
            seconds=info["seconds"], prompts=len(info["prompts"]), threshold=info.get("min_similarity", "–")
        )
        if reference_mod.is_short(info):
            message += "\n\n" + t["reference_short"].format(
                seconds=info["seconds"], prompts=len(info["prompts"])
            )
        return [message, *reference_players(voice)]

    def synth_timing_view(voice) -> str:
        """Speed of the last generation and what all sentences take at that pace."""
        if not voice:
            return ""
        timing = synthesis_mod.read_timing(service.voice_dir(root, voice) / "raw")
        if timing is None:
            return ""
        total = service.prompt_count(root, voice)
        return t["synthesize_timing"].format(
            clips=timing.clips,
            minutes=f"{timing.seconds / 60:.1f}",
            device=timing.device,
            per_clip=f"{timing.per_clip:.1f}",
            speed=f"{timing.speed:.2f}",
            total=total,
            estimate=service.format_elapsed(timing.per_clip * total),
        )

    def el_status(voice) -> str:
        sentences, characters = service.missing_sentences(root, voice)
        lines = [t["el_cost"].format(voice=voice, sentences=sentences, characters=characters)]
        if not elevenlabs.load_api_key():
            lines.append(t["el_no_key"])
        if not service.load_config(root, voice).synthesis.elevenlabs_voice_id:
            lines.append(t["el_no_voice"])
        return "\n\n".join(lines)

    def el_view(voice):
        cfg = service.load_config(root, voice) if voice else None
        backend = gr.update(value=cfg.synthesis.backend) if cfg else gr.update()
        if cfg is None or cfg.synthesis.backend != "elevenlabs":
            hidden = gr.update(choices=[], value=None)
            off = gr.update(visible=False)
            return backend, off, off, hidden, hidden, off, ""
        voice_id = cfg.synthesis.elevenlabs_voice_id
        known = [(cfg.synthesis.elevenlabs_voice_name or voice_id, voice_id)] if voice_id else []
        sets = [(f"{name} ({count})", name) for name, count in service.sentence_sets(root)]
        return (
            backend,
            gr.update(visible=True),
            gr.update(visible=True),
            gr.update(choices=known, value=voice_id),
            gr.update(choices=sets, value=None),
            gr.update(visible=True),
            el_status(voice),
        )

    def el_key_state() -> str:
        return t["el_key_ready"] if elevenlabs.load_api_key() else t["el_key_missing"]

    def el_save_key(key):
        if not key.strip():
            raise user_error(t["el_key"])
        elevenlabs.save_api_key(key)
        return "", el_key_state()

    def pick_backend(voice, backend):
        try:
            service.set_backend(root, need_voice(voice), backend)
        except ValueError as err:
            raise user_error(t["error"].format(error=err)) from err

    def names_view(voice):
        if not voice:
            return "", ""
        return voice, service.load_config(root, voice).piper_name or ""

    def rename(voice, name, piper_name):
        voice = need_voice(voice)
        for manager in (jobs, side_jobs):
            status = manager.status()
            if status and status.running and (status.voice == voice or status.kind == "train-queue"):
                raise user_error(t["rename_busy"])
        try:
            cfg = service.rename_voice(root, voice, name, piper_name)
        except ValidationError as err:  # show only the rule, not pydantic's wrapper text
            raise user_error(t["error"].format(error="; ".join(e["msg"] for e in err.errors()))) from err
        except Exception as err:  # validation messages go to the user
            raise user_error(t["error"].format(error=err)) from err
        names = service.list_voices(root)
        return gr.update(choices=names, value=cfg.name), t["renamed"].format(name=cfg.name)

    def el_refresh_account(voice, current):
        need_voice(voice)
        try:
            found = elevenlabs.list_voices()
        except Exception as err:  # wrong key, no connection: said in the panel
            raise user_error(t["error"].format(error=err)) from err
        choices = [(f"{v['name']} ({v['category']})", v["id"]) for v in found]
        value = current if current in [v["id"] for v in found] else None
        credits = elevenlabs.optional_credits()
        message = (
            t["el_credits"].format(left=credits.left, limit=credits.limit) if credits else t["el_no_credits"]
        )
        return gr.update(choices=choices, value=value), message + "\n\n" + el_status(voice)

    def el_pick_voice(voice, voice_id):
        voice = need_voice(voice)
        try:
            found = elevenlabs.list_voices()
        except Exception as err:  # wrong key, no connection: said in the panel
            raise user_error(t["error"].format(error=err)) from err
        cfg = service.load_config(root, voice)
        cfg.synthesis.elevenlabs_voice_id = voice_id
        cfg.synthesis.elevenlabs_voice_name = next((v["name"] for v in found if v["id"] == voice_id), None)
        config_mod.save(service.voice_dir(root, voice), cfg)
        return el_status(voice)

    def el_use_sentences(voice, source):
        voice = need_voice(voice)
        if not source:
            raise user_error(t["el_sentences"])
        try:
            count = use_dataset_sentences(service.voice_dir(root, voice), service.voice_dir(root, source))
        except ValueError as err:
            raise user_error(t["error"].format(error=err)) from err
        message = t["el_sentences_done"].format(count=count, source=source)
        return message + "\n\n" + el_status(voice), service.corpus_preview(root, voice)

    def reference_players(voice):
        return players([(p, p.name) for p in service.reference_clips(root, voice)] if voice else [])

    def build_corpus(voice, files, bundled, size):
        voice = need_voice(voice)
        from .. import corpus as corpus_mod
        from ..dataset import summarize, write_report
        from ..languages import get_language

        cfg = service.load_config(root, voice)
        lang_pack = get_language(cfg.language)
        directory = service.voice_dir(root, voice)
        # uploads are kept in the voice folder, so later runs reuse every file uploaded so far
        service.save_uploads(directory / "sources", files or [])
        sources = sorted((directory / "sources").glob("*")) if (directory / "sources").is_dir() else []
        if bundled:
            sources += lang_pack.prompt_paths()
        if not sources:
            raise user_error(t["corpus_files"])
        count = int(size) or round(cfg.target_clips * cfg.synthesis.overgenerate)
        try:
            prompts, report = corpus_mod.build(
                sources, lang_pack, count, corpus_mod.espeak_phonemizer(lang_pack)
            )
        except Exception as err:
            raise user_error(t["error"].format(error=err)) from err
        corpus_mod.write_prompts(directory / corpus_mod.PROMPTS, prompts)
        write_report(directory / "corpus_report.csv", report, ["source", "text", "reason"])
        message = t["corpus_done"].format(count=len(prompts)) + "\n\n```\n" + summarize(report) + "\n```"
        return message, service.corpus_preview(root, voice)

    def audition_view(voice):
        if not voice:
            return [], gr.update(choices=[], value=None), *players([])
        results = service.audition_results(root, voice)
        slugs = [r["slug"] for r in results]
        first = slugs[0] if slugs else None
        clips = service.audition_clips(root, voice, first) if first else []
        return service.audition_table(results), gr.update(choices=slugs, value=first), *players(clips)

    def audition_pick(voice, slug):
        return players(service.audition_clips(root, voice, slug) if voice and slug else [])

    def audition_apply(voice, slug):
        voice = need_voice(voice)
        if not slug:
            raise user_error(t["audition_pick"])
        options = service.apply_audition(root, voice, slug)
        return t["audition_applied"].format(options=json.dumps(options, ensure_ascii=False))

    def filter_view(voice):
        if not voice:
            return [], *players([]), *players([])
        rows = service.filter_report(root, voice)
        kept = service.sample_clips(root, voice, rows, kept=True)
        rejected = service.sample_clips(root, voice, rows, kept=False)
        return service.reason_counts(rows), *players(kept), *players(rejected)

    def train_view(voice):
        if not voice:
            return "", [], gr.update(), gr.update(), gr.update()
        cfg = service.load_config(root, voice)
        clips = service.dataset_size(root, voice)
        if clips:
            est = service.estimate(clips, cfg.train.batch_size, cfg.train.validation_split)
            low, high = est.epoch_seconds
            hours_low, hours_high = est.hours(cfg.train.max_epochs)
            info = t["train_estimate"].format(
                clips=clips,
                steps=est.steps_per_epoch,
                low=low,
                high=high,
                epochs=cfg.train.max_epochs,
                hours_low=hours_low,
                hours_high=hours_high,
            )
        else:
            info = t["train_no_dataset"]
        ckpts = [[Path(p).name, p] for p in service.checkpoint_choices(root, voice)]
        choices, value, ready = service.base_options(root, cfg.train.base)
        if cfg.train.base == config_mod.POLISH_BASE and not ready:
            info = t["base_not_ready"] + "\n\n" + info
        return (
            info,
            ckpts,
            gr.update(value=cfg.train.max_epochs),
            gr.update(choices=choices, value=value),
            gr.update(visible=not ready),
        )

    def run_train(voice, base, max_epochs, poweroff):
        voice = need_voice(voice)
        service.set_max_epochs(root, voice, int(max_epochs))
        return start("train", voice, ["train", voice, "--base", base], poweroff=poweroff)

    def run_queue(voices, base, max_epochs, poweroff):
        if not voices:
            raise user_error(t["train_queue"])
        args = ["train-queue", *voices, "--epochs", str(int(max_epochs)), "--base", base]
        return start("train-queue", "", args, poweroff=poweroff)

    def queue_view(_voice):
        return gr.update(choices=service.trainable_voices(root))

    def export_view(voice):
        if not voice:
            return gr.update(choices=[], value=None), None
        choices = service.checkpoint_choices(root, voice)
        files = [str(p) for p in service.exports(service.voice_dir(root, voice))]
        return gr.update(choices=choices, value=choices[0] if choices else None), files or None

    def run_export(voice, checkpoint):
        voice = need_voice(voice)
        args = ["export", voice] + (["--checkpoint", checkpoint] if checkpoint else [])
        return start("export", voice, args)

    def settings_view(voice):
        return service.config_yaml(root, voice) if voice else ""

    def settings_save(voice, text):
        voice = need_voice(voice)
        try:
            service.save_config_yaml(root, voice, text)
        except Exception as err:
            raise user_error(t["error"].format(error=err)) from err
        return t["saved"]

    def run_import(voice, folder, persona, verify):
        voice = need_voice(voice)
        folder = Path(folder.strip()).expanduser()
        args = ["import", voice, str(folder)]
        if persona and persona.strip():
            args += [
                "--metadata",
                str(folder / "metadata.csv"),
                "--persona",
                str(service.persona_path(folder, persona)),
            ]
        if verify:
            args.append("--verify")
        return start("import", voice, args)

    def run_base_prepare(folder, audio_dir):
        if not folder or not folder.strip():
            raise user_error(t["base_dir_missing"])
        args = ["base", "prepare", str(Path(folder.strip()).expanduser())]
        if audio_dir and audio_dir.strip():
            args += ["--audio-dir", audio_dir.strip()]
        return start("base-prepare", "", args)

    def server_view():
        keys = [(t["server_key_default"], "")] + [(k, k) for k in remote_mod.ssh_keys()]
        config = remote_mod.load_config(root) or remote_mod.ServerConfig()
        message = t["server_saved"].format(url=config.ui_url) if config.host else ""
        return (
            config.host,
            config.user,
            config.port,
            gr.update(choices=keys, value=config.key),
            config.remote_dir,
            config.ui_port,
            message,
        )

    def server_save(host, user, port, key, folder, ui_port):
        config = remote_mod.ServerConfig(
            host.strip(), user.strip(), int(port or 22), key or "", folder.strip(), int(ui_port or 7860)
        )
        try:
            remote_mod.save_config(root, config)
        except ValueError as err:
            raise user_error(t["error"].format(error=err)) from err
        return t["server_saved"].format(url=config.ui_url)

    def server_state_html() -> str:
        """The checklist from the last check (jobs/server_status.json); empty without a server."""
        config = remote_mod.load_config(root)
        if config is None:
            return ""
        saved = remote_mod.load_status(root)
        if saved is None:
            return style.checklist_html(t["ready_title"], "idle", t["ready_never"])
        checked = t["ready_checked"].format(
            time=time.strftime("%d.%m %H:%M", time.localtime(saved.get("checked") or 0))
        )
        status = saved.get("status")
        if not status:
            error = t["ready_error"].format(error=saved.get("error") or "?")
            return style.checklist_html(t["ready_title"], "failed", error, checked=checked)
        items = remote_mod.evaluate(status, config, remote_mod.local_voices(root), remote_mod.code_stamp())
        rows = []
        for item in items:
            text, command = item.detail, item.command
            if item.state == "todo":
                hint = {"code": t["ready_hint_code"], "data": t["ready_hint_data"]}.get(item.key)
                text = (
                    f"{hint} {text} · {t['ready_hint_todo']}"
                    if hint
                    else (f"{text} · {t['ready_hint_todo']}" if text else t["ready_hint_todo"])
                )
            elif item.state == "manual":
                hint = t["ready_hint_gpu"] if item.key == "gpu" else t["ready_hint_manual"]
                text = f"{text} - {hint}" if text else hint
            elif item.state == "warn":
                hint = t["ready_hint_disk"] if item.key == "disk" else t["ready_hint_train"]
                text = f"{text} - {hint}" if text else hint
            rows.append((item.state, t["ready_" + item.key], text, command))
        overall = remote_mod.summary(items)
        todo = sum(item.state == "todo" for item in items)
        headline = t["ready_" + overall].format(n=todo)
        login = (t["ready_login"], t["ready_show"], status.get("login", ""))
        return style.checklist_html(t["ready_title"], overall, headline, rows, checked=checked, login=login)

    def server_state_view(seen):
        """Re-drawn only when the saved check changed (keeps "show" of the login open meanwhile)."""
        path = remote_mod.status_path(root)
        stamp = (path.stat().st_mtime if path.exists() else 0.0, remote_mod.load_config(root) is not None)
        if seen is not None and list(stamp) == list(seen):
            return gr.update(), seen
        return server_state_html(), stamp

    # --- listening to a training run (Train tab: the voice; Tools: the base) ---------------------

    def tensorboard_html() -> str:
        server = remote_mod.load_config(root)
        if server is not None:  # this panel drives the machine: TensorBoard runs there
            return style.tensorboard_link(
                t["tensorboard_link"], f"http://{server.host}:{remote_mod.TB_PORT}/"
            )
        port = int(os.environ.get("PVC_TB_PORT") or remote_mod.TB_PORT)
        return style.tensorboard_link(t["tensorboard_link"], port=port)

    def listen(work_dir: Path | None, epoch=None) -> list:
        """[head, epoch dropdown, *players] of one training run."""
        hidden = [gr.update(visible=False, value=None) for _ in range(PLAYERS)]
        link = tensorboard_html()
        run = train_monitor.update(work_dir) if work_dir is not None else None
        if run is None or not run.epochs:
            server = remote_mod.load_config(root)
            here = work_dir is not None and work_dir.exists()
            # this panel drives the machine and trains nothing itself: the samples are over there
            text = (
                t["listen_elsewhere"].format(url=server.ui_url) if server and not here else t["listen_none"]
            )
            return [style.listen_head(text, link), gr.update(choices=[], value=None), *hidden]

        def mos(value):
            return f"{value:.2f}" if value is not None else "—"

        choices = [
            (
                t["listen_item"].format(epoch=e, mos=mos(run.value("val_mos", e)))
                + (t["listen_saved"] if e in run.saved else ""),
                e,
            )
            for e in run.epochs
        ]
        scores = run.metrics.get("val_mos", {})
        best_epoch = max(scores, key=scores.get) if scores else None
        last = max(scores) if scores else run.epochs[0]
        summary = t["listen_summary"].format(
            last=last,
            mos=mos(scores.get(last)),
            best=mos(scores.get(best_epoch)) if best_epoch is not None else "—",
            best_epoch=best_epoch if best_epoch is not None else "—",
        )
        chosen = epoch if epoch in run.samples else run.epochs[0]
        players = [
            gr.update(visible=True, value=str(sample.path), label=sample.text)
            for sample in run.samples[chosen][:PLAYERS]
        ]
        players += hidden[len(players) :]
        return [style.listen_head(summary, link), gr.update(choices=choices, value=chosen), *players]

    def chart_run(voice) -> tuple[Path | None, str]:
        """The run the chart follows: the training job running or last run here, else the chosen
        voice, else the base - whichever has logs."""
        status = jobs.status()
        quality = service.latest_base_run(root) or "medium"
        base = (service.base_work_dir(root, quality), t["chart_base"].format(quality=quality))
        candidates = []
        if status and status.kind == "base-train":
            candidates.append(base)
        elif status and status.kind in ("train", "train-queue"):
            trained = status.voice or service.queue_voice(root)
            if trained:
                candidates.append(
                    (service.voice_dir(root, trained) / "train", t["chart_voice"].format(voice=trained))
                )
        if voice in service.list_voices(root):
            candidates.append(
                (service.voice_dir(root, voice) / "train", t["chart_voice"].format(voice=voice))
            )
        candidates.append(base)
        for work_dir, name in candidates:
            if train_monitor.event_files(work_dir):
                return work_dir, name
        return None, ""

    def chart_payload(run: train_monitor.Run, name: str) -> dict:
        rows = run.table()
        mos = [(r[0], r[1]) for r in rows if r[1] is not None]
        mel = [(r[0], r[2]) for r in rows if r[2] is not None]
        labels = {key: t["chart_" + key] for key in CHART_LABELS}
        return {
            "rows": rows,
            "best": {
                "mos": max(mos, key=lambda item: item[1]) if mos else None,
                "mel": min(mel, key=lambda item: item[1]) if mel else None,
            },
            "t": {
                **labels,
                "name": name,
                "val_mos": "val_mos",
                "val_mel": "val_mel",
                "train_mel": "train_mel",
            },
            "help": "".join(f"<p>{style.bold_html(line)}</p>" for line in t["chart_help"].split("\n")),
        }

    def chart_view(voice, seen):
        """Re-drawn only when the run got a new epoch (keeps the hover and an open window steady)."""
        work_dir, name = chart_run(voice)
        if work_dir is None:
            return ("" if seen else gr.update()), None
        run = train_monitor.update(work_dir)
        key = [str(work_dir), run.last_epoch, len(run.table()), name]
        if seen == key:
            return gr.update(), seen
        return style.chart_html(chart_payload(run, name)), key

    def voice_work_dir(voice) -> Path | None:
        return service.voice_dir(root, voice) / "train" if voice else None

    def listen_voice(voice, epoch=None):
        return listen(voice_work_dir(voice), epoch)

    def listen_base(model=None, epoch=None):
        """[model choice, *listen()] for the base: the model switch shows once there are two sizes."""
        runs = service.base_runs(root)
        if model not in runs:
            model, epoch = service.latest_base_run(root) or "medium", None
        choice = gr.update(choices=runs, value=model if runs else None, visible=len(runs) > 1)
        return [choice, *listen(service.base_work_dir(root, model), epoch)]

    def download_samples(work_dir: Path | None, title: str):
        """ZIP of every kept epoch of the run, offered as a file to download."""
        try:
            if work_dir is None:
                raise ValueError
            path = train_monitor.export_samples(work_dir, title)
        except ValueError as err:
            raise user_error(t["listen_download_none"]) from err
        return gr.update(value=str(path), visible=True)

    def download_voice_samples(voice):
        return download_samples(voice_work_dir(voice), f"{voice}-samples")

    def download_base_samples(model):
        runs = service.base_runs(root)
        model = model if model in runs else service.latest_base_run(root) or "medium"
        return download_samples(
            service.base_work_dir(root, model), f"{train_mod.BASE_FOLDER}-{model}-samples"
        )

    # --- base: rating the recordings, comparing the model sizes ----------------------------------

    def run_score(sample):
        if not (service.base_dataset_dir(root) / "metadata.csv").is_file():
            raise user_error(t["base_missing"])
        try:
            side_jobs.start("base-score", "", ["base", "score", "--sample", str(max(0, int(sample or 0)))])
        except JobBusy as err:
            raise user_error(t["job_busy"].format(job=kind_name(err.kind))) from err
        return t["job_started"].format(kind=kind_name("base-score"))

    def best_base_mos() -> str:
        _common, results = service.compare_bases(root, COMPARE_WINDOW)
        best = [(r.best_mos[1], r.quality) for r in results if r.best_mos]
        return "{:.2f} ({})".format(*max(best)) if best else "—"

    def score_view(seen):
        """[box, worst head, best head, *players]; redrawn only when something changed."""
        status = side_jobs.status()
        report = service.base_score(root)
        found = service.parse_progress(status.log_tail) if status and status.running else None
        progress = list(found[:2]) if found else None
        key = [
            bool(status and status.running),
            progress,
            status.returncode if status else None,
            report and (report["count"], report["median"]),
        ]
        if key == seen:
            return [gr.update()] * (3 + 2 * SCORE_PLAYERS) + [seen]
        hidden = [gr.update(visible=False, value=None)] * (2 * SCORE_PLAYERS)
        heads = [gr.update(visible=False)] * 2
        if status and status.running:
            box = style.progress_html(*progress, t["score_running"]) if progress else t["score_starting"]
            return [box, *heads, *hidden, key]
        failed = ""
        if status and status.kind == "base-score" and status.returncode not in (0, None):
            lines = service.compact_log(status.log_tail).splitlines()[-3:]
            failed = f"<p><b>{t['score_failed']}</b></p><pre>{html.escape(chr(10).join(lines))}</pre>"
        if report is None:
            return [failed or f"<p>{t['score_none']}</p>", *heads, *hidden, key]
        tiles = [
            (t["score_median"], f"{report['median']:.2f}"),
            (t["score_p10"], f"{report['p10']:.2f}"),
            (t["score_p90"], f"{report['p90']:.2f}"),
            (t["score_good"].format(good=f"{dataset_quality.GOOD:.1f}"), f"{report['good']:.0%}"),
        ]
        text = t["score_summary"].format(
            count=report["count"],
            total=f"{report['total']:,}".replace(",", " "),
            median=f"{report['median']:.2f}",
            best=best_base_mos(),
        )
        wav_dir = service.base_dataset_dir(root) / "wav"

        def player(clip, score):
            label = t["score_clip"].format(score=f"{score:.2f}", text=report["texts"].get(clip, clip))
            return gr.update(visible=True, value=str(wav_dir / f"{clip}.wav"), label=label[:120])

        players = [player(*item) for item in report["worst"][:SCORE_PLAYERS]]
        players += [gr.update(visible=False, value=None)] * (SCORE_PLAYERS - len(players))
        best = [player(*item) for item in report["best"][:SCORE_PLAYERS]]
        players += best + [gr.update(visible=False, value=None)] * (SCORE_PLAYERS - len(best))
        heads = [gr.update(visible=True)] * 2
        return [failed + style.score_html(tiles, text), *heads, *players, key]

    def compare_view() -> str:
        common, results = service.compare_bases(root, COMPARE_WINDOW)
        if not results:
            return t["compare_none"]
        start = max(0, common - COMPARE_WINDOW + 1)

        def value(number, digits):
            return f"{number:.{digits}f}" if number is not None else "—"

        def best(pair, digits):
            return f"{pair[1]:.{digits}f} (ep. {pair[0]})" if pair else "—"

        head = [
            t["compare_model"],
            t["compare_epochs"],
            t["compare_mos_at"].format(start=start, end=common),
            t["compare_mel_at"].format(start=start, end=common),
            t["compare_best_mos"],
            t["compare_best_mel"],
        ]
        rows = [
            [r.quality, str(r.last_epoch), value(r.mos_at, 2), value(r.mel_at, 3), best(r.best_mos, 2),
             best(r.best_mel, 3)]
            for r in results
        ]  # fmt: skip
        table = "\n".join("| " + " | ".join(row) + " |" for row in [head, ["---"] * len(head), *rows])
        report = service.base_score(root)
        if report:
            table += "\n\n" + t["compare_ceiling"].format(median=f"{report['median']:.2f}")
        return table

    def run_base_train(epochs, quality, batch):
        if not epochs or int(epochs) < 1:
            raise user_error(t["base_epochs_info"])
        args = ["base", "train", "--max-epochs", str(int(epochs)), "--quality", quality or "medium"]
        if batch:
            args += ["--batch-size", str(max(1, int(batch)))]
        return start("base-train", "", args)

    def server_job(action: str) -> str:
        if remote_mod.load_config(root) is None:
            raise user_error(t["server_missing"])
        return start(f"remote-{action}", "", ["remote", action])

    def toggle_machine(voice, current, event: gr.EventData):
        action = getattr(event, "machine", "")
        if action in ("on", "off"):
            try:
                machine.switch_machine(action == "on")
            except (ValueError, RuntimeError) as err:
                raise user_error(t["error"].format(error=err)) from err
            gr.Info(t["machine_switched_on" if action == "on" else "machine_switched_off"])
        return tick(voice, current)

    # --- Home Assistant (Tools): connection and the machine's power ------------------------------

    def entity_choices(found: list[dict]) -> list[tuple[str, str]]:
        return [(f"{e['name']} ({e['id']})" if e["name"] else e["id"], e["id"]) for e in found]

    def power_lists(found: dict, switch: str | None, sensor: str | None) -> tuple:
        return (
            gr.update(choices=entity_choices(found["switches"]), value=switch or None),
            gr.update(choices=entity_choices(found["sensors"]), value=sensor or None),
        )

    def token_box():
        """Always empty: the saved token never comes back to the page."""
        placeholder = t["ha_token_saved"] if ha.token_saved() else t["ha_token_placeholder"]
        if ha.token_rejected():
            placeholder = t["ha_token_rejected"]
        return gr.update(value="", placeholder=placeholder)

    def ha_view():
        settings = power.load_power()
        return (
            ha.load_connection().url,
            token_box(),
            *power_lists(machine.entities_cached(), settings.switch, settings.sensor),
            settings.off_watts,
        )

    def ha_save(url, token, switch, sensor):
        try:
            ha.save_connection(url or "", token or None)
        except ValueError as err:
            raise user_error(t["error"].format(error=err)) from err
        machine.forget()
        found = machine.entities_cached()
        if not ha.load_connection().ready:
            message = t["ha_missing"]
        else:
            try:
                found = machine.ha_entities()
                message = t["ha_saved"].format(count=found["count"])
            except ha.HaError as err:
                message = t["ha_saved_failed"].format(error=err)
        return message, token_box(), *power_lists(found, switch, sensor)

    def ha_remove(confirmed):
        if not confirmed:
            return gr.update(), gr.update(), gr.update()
        ha.remove_connection()
        machine.forget()
        return t["ha_removed"], "", token_box()

    def power_suggest(switch, sensor):
        if not ha.load_connection().ready:
            raise user_error(t["ha_missing"])
        try:
            found = machine.ha_entities()
        except ha.HaError as err:
            raise user_error(t["error"].format(error=err)) from err
        message = t["power_suggested"].format(switches=len(found["switches"]), sensors=len(found["sensors"]))
        return message, *power_lists(found, switch, sensor)

    def power_save(switch, sensor, watts):
        settings = power.PowerSettings(switch or "", sensor or "", watts if watts is not None else 5.0)
        try:
            power.save_power(settings)
        except ValueError as err:
            raise user_error(t["error"].format(error=err)) from err
        machine.forget()
        machine.refresh_in_background()
        return t["power_saved"] if settings.ready else t["saved"]

    def open_base_section(voice):
        """ "Create bazowy-pl": the Tools tab, where the own base is made."""
        return gr.Tabs(selected="tools"), "tools", status_md(voice, "tools")

    def base_source_choices() -> tuple[list[tuple[str, str]], str | None]:
        """Voices with a cleaned dataset ("kasia - 18 395 clips"), the largest first."""
        choices = [
            (t["base_source"].format(name=name, clips=f"{clips:,}".replace(",", "\u00a0")), str(folder))
            for name, clips, folder in service.base_sources(root)
        ]
        return choices, choices[0][1] if choices else None

    def base_view(current=None):
        message = (
            t["base_selected"].format(path=root / "bases") if service.base_ready(root) else t["base_missing"]
        )
        server = remote_mod.load_config(root)
        if server is not None:  # this panel drives a GPU machine: the base is made there
            message = t["base_on_machine"].format(url=server.ui_url) + "\n\n" + message
        choices = service.base_checkpoint_choices(root)
        sources, source = base_source_choices()
        return (
            message,
            gr.update(choices=choices, value=choices[0][1] if choices else None),
            gr.update(choices=sources, value=current or source),  # a typed own path stays
        )

    def run_base_select(checkpoint):
        if not checkpoint:
            raise user_error(t["base_checkpoint"])
        start("base-select", "", ["base", "select", checkpoint])
        return t["job_started"].format(kind="base-select")

    def run_base_export(checkpoint):
        if not checkpoint:
            raise user_error(t["base_checkpoint"])
        return start("base-export", "", ["base", "export", "--checkpoint", checkpoint])

    # --- layout -----------------------------------------------------------------------------------

    with gr.Blocks(title=t["title"], analytics_enabled=False, fill_width=True) as app:
        topbar = gr.HTML(topbar_html(None), js_on_load=style.MACHINE_JS)
        status = gr.HTML(status_md(None), js_on_load=style.NAV_JS)
        current_tab = gr.State(STEP_TABS[0])
        with gr.Row(equal_height=False):
            with gr.Column(scale=7, min_width=420):
                with gr.Group():
                    with gr.Row(equal_height=True, elem_classes=["pvc-voice-row"]):
                        # custom values allowed: a browser tab from an earlier run may send a voice this
                        # session does not list (Gradio would fail before any handler); need_voice checks it
                        voice = gr.Dropdown(
                            label=t["voice"],
                            choices=service.list_voices(root),
                            scale=4,
                            allow_custom_value=True,
                        )
                        refresh = gr.Button("↻ " + t["refresh"], scale=0, min_width=130, variant="secondary")
                    with gr.Accordion(
                        "＋ " + t["new_voice"], open=not service.list_voices(root), elem_classes=["pvc-new"]
                    ):
                        gr.Markdown(t["new_voice_help"])
                        with gr.Row():
                            new_name = gr.Textbox(label=t["name"], placeholder="kuba_bajka")
                            new_piper = gr.Textbox(label=t["piper_name"], placeholder="pl_PL-kuba_bajka")
                        base_choices, base_value, base_is_ready = service.base_options(root)
                        create_button = gr.Button(t["create"], variant="primary")
                        create_msg = gr.Markdown()
                with gr.Tabs(elem_id="pvc-tabs") as tabs:
                    with gr.Tab(t["tab_reference"], id="reference"):
                        gr.HTML(step_head("tab_reference", "info_reference"))
                        gr.Markdown(t["reference_help"], elem_classes=["pvc-help"])
                        ref_files = gr.File(
                            label=t["reference_files"], file_count="multiple", type="filepath"
                        )
                        ref_embed = gr.Checkbox(value=True, label=t["reference_embed"])
                        ref_button = gr.Button(t["prepare"], variant="primary")
                        ref_msg = gr.Markdown()
                        gr.Markdown(f"**{t['reference_clips']}**")
                        ref_players = [gr.Audio(visible=False, interactive=False) for _ in range(PLAYERS)]

                    with gr.Tab(t["tab_corpus"], id="corpus"):
                        gr.HTML(step_head("tab_corpus", "info_corpus"))
                        gr.Markdown(t["corpus_help"], elem_classes=["pvc-help"])
                        corpus_files = gr.File(
                            label=t["corpus_files"],
                            file_count="multiple",
                            type="filepath",
                            file_types=[".txt", ".tsv", ".csv"],
                        )
                        with gr.Row():
                            corpus_bundled = gr.Checkbox(value=True, label=t["corpus_bundled"])
                            corpus_size = gr.Number(value=0, precision=0, label=t["corpus_size"])
                        corpus_button = gr.Button(t["build"], variant="primary")
                        corpus_msg = gr.Markdown()
                        corpus_table = gr.Dataframe(
                            headers=[t["corpus_preview"]], interactive=False, wrap=True
                        )

                    with gr.Tab(t["tab_audition"], id="audition"):
                        gr.HTML(step_head("tab_audition", "info_audition"))
                        gr.Markdown(t["audition_help"], elem_classes=["pvc-help"])
                        with gr.Row():
                            audition_count = gr.Number(value=12, precision=0, label=t["audition_count"])
                            audition_button = gr.Button(t["audition_run"], variant="primary")
                        audition_table = gr.Dataframe(
                            headers=["#", "combination", "score", "CER", "similarity", "MOS"],
                            label=t["audition_table"],
                            interactive=False,
                        )
                        with gr.Row():
                            audition_slug = gr.Dropdown(label=t["audition_pick"], choices=[])
                            audition_apply_button = gr.Button(t["audition_apply"])
                        audition_msg = gr.Markdown()
                        audition_players = [
                            gr.Audio(visible=False, interactive=False) for _ in range(PLAYERS)
                        ]

                    with gr.Tab(t["tab_synthesize"], id="synthesize"):
                        gr.HTML(step_head("tab_synthesize", "info_synthesize"))
                        gr.Markdown(t["synthesize_help"], elem_classes=["pvc-help"])
                        synth_backend = gr.Dropdown(BACKENDS, value="chatterbox", label=t["backend"])
                        # Gradio does not bring back a Markdown created hidden, a Group it does
                        with gr.Group(visible=False) as el_help:
                            gr.Markdown(t["el_help"], elem_classes=["pvc-help"])
                        with gr.Group(visible=False) as el_box:
                            el_voice = gr.Dropdown(label=t["el_voice"], choices=[])
                            el_refresh = gr.Button("↻ " + t["el_refresh"])
                            el_sentences = gr.Dropdown(label=t["el_sentences"], choices=[])
                            el_sentences_use = gr.Button(t["el_sentences_use"])
                        with gr.Group(visible=False) as el_msg_box:
                            el_msg = gr.Markdown(elem_classes=["pvc-help"])
                        synth_limit = gr.Number(value=0, precision=0, label=t["synthesize_limit"])
                        synth_button = gr.Button(t["synthesize_run"], variant="primary")
                        synth_msg = gr.Markdown()
                        synth_timing = gr.Markdown()

                    with gr.Tab(t["tab_filter"], id="filter"):
                        gr.HTML(step_head("tab_filter", "info_filter"))
                        gr.Markdown(t["filter_help"], elem_classes=["pvc-help"])
                        with gr.Row():
                            filter_target = gr.Number(value=0, precision=0, label=t["filter_target"])
                            filter_asr = gr.Checkbox(value=True, label=t["filter_asr"])
                            filter_sim = gr.Checkbox(value=True, label=t["filter_similarity"])
                            filter_mos = gr.Checkbox(value=True, label=t["filter_mos"])
                        filter_button = gr.Button(t["filter_run"], variant="primary")
                        filter_msg = gr.Markdown()
                        filter_table = gr.Dataframe(
                            headers=["reason", "count"], label=t["filter_reasons"], interactive=False
                        )
                        gr.Markdown(f"**{t['filter_kept']}**")
                        kept_players = [gr.Audio(visible=False, interactive=False) for _ in range(PLAYERS)]
                        gr.Markdown(f"**{t['filter_rejected']}**")
                        rejected_players = [
                            gr.Audio(visible=False, interactive=False) for _ in range(PLAYERS)
                        ]

                    with gr.Tab(t["tab_train"], id="train"):
                        gr.HTML(step_head("tab_train", "info_train"))
                        gr.Markdown(t["train_help"], elem_classes=["pvc-help"])
                        train_info = gr.Markdown()
                        with gr.Row():
                            train_base = gr.Dropdown(
                                base_choices, value=base_value, label=t["base"], allow_custom_value=True
                            )
                            train_epochs = gr.Number(value=1000, precision=0, label=t["max_epochs"])
                        train_base_create = gr.Button(t["base_create"], size="sm", visible=not base_is_ready)
                        train_poweroff = gr.Checkbox(
                            value=False, label=t["train_poweroff"], visible=can_power_off
                        )
                        train_button = gr.Button(t["train_run"], variant="primary")
                        train_queue = gr.Dropdown(
                            label=t["train_queue"],
                            info=t["train_queue_info"],
                            choices=service.trainable_voices(root),
                            multiselect=True,
                            allow_custom_value=True,
                        )
                        train_queue_button = gr.Button(t["train_queue_run"])
                        train_msg = gr.Markdown()
                        train_ckpts = gr.Dataframe(
                            headers=["file", "path"], label=t["checkpoints"], interactive=False
                        )
                        gr.Markdown(f"**{t['listen_title']}**")
                        gr.Markdown(t["listen_help"], elem_classes=["pvc-help"])
                        train_listen_head = gr.HTML()
                        with gr.Row():
                            train_listen_epoch = gr.Dropdown(label=t["listen_epoch"], choices=[], scale=4)
                            train_listen_refresh = gr.Button(t["listen_refresh"], scale=1)
                        train_listen_players = [
                            gr.Audio(visible=False, interactive=False) for _ in range(PLAYERS)
                        ]
                        train_samples_button = gr.Button(t["listen_download"], size="sm")
                        train_samples_file = gr.File(
                            label=t["listen_download_file"], interactive=False, visible=False
                        )

                    with gr.Tab(t["tab_export"], id="export"):
                        gr.HTML(step_head("tab_export", "info_export"))
                        gr.Markdown(t["export_help"], elem_classes=["pvc-help"])
                        export_ckpt = gr.Dropdown(label=t["checkpoint"], choices=[])
                        export_button = gr.Button(t["export_run"], variant="primary")
                        export_msg = gr.Markdown()
                        export_files = gr.File(
                            label=t["export_files"], file_count="multiple", interactive=False
                        )

                    with gr.Tab(t["tab_settings"], id="settings"):
                        gr.HTML(step_head("tab_settings", "info_settings"))
                        el_key_msg = gr.Markdown(elem_classes=["pvc-help"])
                        with gr.Group():
                            el_key = gr.Textbox(label=t["el_key"], type="password")
                            el_key_save = gr.Button(t["el_key_save"])
                        gr.Markdown(t["rename_help"], elem_classes=["pvc-help"])
                        with gr.Group():
                            with gr.Row():
                                rename_name = gr.Textbox(label=t["rename_name"])
                                rename_piper = gr.Textbox(
                                    label=t["piper_name"], placeholder="pl_PL-kuba_bajka"
                                )
                            rename_button = gr.Button(t["rename_save"])
                        rename_msg = gr.Markdown()
                        gr.Markdown(t["settings_help"], elem_classes=["pvc-help"])
                        settings_text = gr.Code(language="yaml", lines=24)
                        settings_button = gr.Button(t["save"], variant="primary")
                        settings_msg = gr.Markdown()

                    with gr.Tab(t["tab_tools"], id="tools"):
                        gr.HTML(step_head("", "info_server", t["server_title"]))
                        gr.Markdown(t["server_help"], elem_classes=["pvc-help"])
                        with gr.Group():
                            with gr.Row():
                                server_host = gr.Textbox(
                                    label=t["server_host"], placeholder="ubuntu.local", scale=3
                                )
                                server_user = gr.Textbox(label=t["server_user"], placeholder="user", scale=2)
                                server_port = gr.Number(
                                    value=22, precision=0, label=t["server_port"], scale=1
                                )
                            with gr.Row():
                                server_key = gr.Dropdown(label=t["server_key"], scale=3)
                                server_dir = gr.Textbox(
                                    value="piper-voice-cloner", label=t["server_dir"], scale=2
                                )
                                server_ui_port = gr.Number(
                                    value=7860, precision=0, label=t["server_ui_port"], scale=1
                                )
                        with gr.Row():
                            server_save_button = gr.Button(t["server_save"])
                            server_status_button = gr.Button(t["server_status"])
                            server_prepare_button = gr.Button(t["server_prepare"], variant="primary")
                        server_msg = gr.Markdown()
                        server_state = gr.HTML()
                        server_seen = gr.State(None)
                        with gr.Row():
                            server_push_button = gr.Button(t["server_push"], size="sm")
                            server_install_button = gr.Button(t["server_install"], size="sm")
                            server_pull_button = gr.Button(t["server_pull"], size="sm")
                        gr.HTML(step_head("", "info_ha", t["ha_title"]))
                        gr.Markdown(t["ha_help"], elem_classes=["pvc-help"])
                        with gr.Group(), gr.Row():
                            ha_url = gr.Textbox(
                                label=t["ha_url"], placeholder="http://homeassistant.local:8123", scale=3
                            )
                            ha_token = gr.Textbox(label=t["ha_token"], type="password", scale=3)
                        with gr.Row():
                            ha_save_button = gr.Button(t["ha_save"], variant="primary")
                            ha_remove_button = gr.Button(t["ha_remove"], variant="stop")
                        ha_confirm = gr.Checkbox(value=False, visible=False)
                        ha_msg = gr.Markdown()
                        gr.Markdown(f"**{t['power_title']}**")
                        gr.Markdown(t["power_help"], elem_classes=["pvc-help"])
                        with gr.Group(), gr.Row():
                            power_switch = gr.Dropdown(
                                label=t["power_switch"], choices=[], allow_custom_value=True, scale=3
                            )
                            power_sensor = gr.Dropdown(
                                label=t["power_sensor"], choices=[], allow_custom_value=True, scale=3
                            )
                            power_watts = gr.Number(value=5, label=t["power_watts"], minimum=0.1, scale=1)
                        with gr.Row():
                            power_suggest_button = gr.Button(t["power_suggest"])
                            power_save_button = gr.Button(t["power_save"], variant="primary")
                        power_msg = gr.Markdown()
                        gr.HTML(step_head("", "info_import", t["import_title"]))
                        gr.Markdown(t["import_help"], elem_classes=["pvc-help"])
                        import_dir = gr.Textbox(label=t["import_dir"])
                        import_persona = gr.Textbox(label=t["import_persona"])
                        import_verify = gr.Checkbox(value=False, label=t["import_verify"])
                        import_button = gr.Button(t["import_run"])
                        import_msg = gr.Markdown()
                        gr.HTML(step_head("", "info_base", t["base_title"]))
                        gr.Markdown(t["base_help"], elem_classes=["pvc-help"])
                        base_msg = gr.Markdown()
                        sources, source = base_source_choices()
                        base_dir = gr.Dropdown(
                            sources,
                            value=source,
                            label=t["base_dir"],
                            info=t["base_dir_info"],
                            allow_custom_value=True,
                        )
                        with gr.Accordion(t["base_advanced"], open=False):
                            base_audio = gr.Textbox(label=t["base_audio_dir"], info=t["base_audio_info"])
                        base_prepare_button = gr.Button(t["base_prepare"])
                        gr.Markdown(f"**{t['score_title']}**")
                        gr.Markdown(t["score_help"], elem_classes=["pvc-help"])
                        with gr.Row():
                            score_sample = gr.Number(
                                value=300,
                                precision=0,
                                minimum=0,
                                label=t["score_sample"],
                                info=t["score_sample_info"],
                            )
                            score_button = gr.Button(t["score_run"])
                        score_box = gr.HTML()
                        score_seen = gr.State(None)
                        with gr.Row():
                            with gr.Column():
                                score_worst_head = gr.Markdown(f"**{t['score_worst']}**", visible=False)
                                score_worst = [
                                    gr.Audio(visible=False, interactive=False) for _ in range(SCORE_PLAYERS)
                                ]
                            with gr.Column():
                                score_best_head = gr.Markdown(f"**{t['score_best']}**", visible=False)
                                score_best = [
                                    gr.Audio(visible=False, interactive=False) for _ in range(SCORE_PLAYERS)
                                ]
                        with gr.Row():
                            base_quality = gr.Radio(
                                [(t["base_quality_medium"], "medium"), (t["base_quality_high"], "high")],
                                value="medium",
                                label=t["base_quality"],
                                info=t["base_quality_info"],
                                scale=3,
                            )
                            base_batch = gr.Number(
                                value=train_mod.DEFAULT_BATCH["medium"],
                                precision=0,
                                minimum=1,
                                label=t["base_batch"],
                                info=t["base_batch_info"],
                                scale=1,
                            )
                        with gr.Row():
                            base_epochs = gr.Number(
                                value=3000, precision=0, label=t["base_epochs"], info=t["base_epochs_info"]
                            )
                            base_train_button = gr.Button(t["base_train"])
                        with gr.Row():
                            base_ckpt = gr.Dropdown(
                                label=t["base_checkpoint"], choices=[], info=t["base_checkpoint_info"]
                            )
                            base_select_button = gr.Button(t["base_select"])
                            base_export_button = gr.Button(t["base_export"])
                        gr.Markdown(f"**{t['compare_title']}**")
                        gr.Markdown(
                            t["compare_help"].format(window=COMPARE_WINDOW), elem_classes=["pvc-help"]
                        )
                        base_compare = gr.Markdown()
                        gr.Markdown(f"**{t['listen_title']}**")
                        gr.Markdown(t["listen_help"], elem_classes=["pvc-help"])
                        base_listen_head = gr.HTML()
                        with gr.Row():
                            base_listen_model = gr.Radio(
                                choices=[], label=t["listen_model"], visible=False, scale=2
                            )
                            base_listen_epoch = gr.Dropdown(label=t["listen_epoch"], choices=[], scale=4)
                            base_listen_refresh = gr.Button(t["listen_refresh"], scale=1)
                        base_listen_players = [
                            gr.Audio(visible=False, interactive=False) for _ in range(PLAYERS)
                        ]
                        base_samples_button = gr.Button(t["listen_download"], size="sm")
                        base_samples_file = gr.File(
                            label=t["listen_download_file"], interactive=False, visible=False
                        )

            with gr.Column(scale=4, min_width=340):
                with gr.Group():
                    live = gr.HTML(live_card(None), padding=True)
                with gr.Group(visible=False) as job_poweroff_box:
                    job_poweroff = gr.Checkbox(value=False, label=t["job_poweroff"])
                with gr.Group():
                    gr.HTML(style.log_tools(t), js_on_load=style.LOG_JS, padding=False)
                    job_log = gr.Textbox(
                        label=t["log"],
                        lines=14,
                        max_lines=14,
                        autoscroll=True,
                        interactive=False,
                        elem_classes=["pvc-log"],
                    )
                    stop_button = gr.Button("■ " + t["stop"], variant="stop", size="sm", interactive=False)
                chart = gr.HTML(js_on_load=style.CHART_JS)
                chart_seen = gr.State(None)

        # --- events -----------------------------------------------------------------------------

        views = [
            (status_md, [voice, current_tab], [status]),
            (reference_players, [voice], ref_players),
            (lambda v: service.corpus_preview(root, v) if v else [], [voice], [corpus_table]),
            (audition_view, [voice], [audition_table, audition_slug, *audition_players]),
            (synth_timing_view, [voice], [synth_timing]),
            (el_view, [voice], [synth_backend, el_help, el_box, el_voice, el_sentences, el_msg_box, el_msg]),
            (names_view, [voice], [rename_name, rename_piper]),
            (queue_view, [voice], [train_queue]),
            (filter_view, [voice], [filter_table, *kept_players, *rejected_players]),
            (train_view, [voice], [train_info, train_ckpts, train_epochs, train_base, train_base_create]),
            (listen_voice, [voice], [train_listen_head, train_listen_epoch, *train_listen_players]),
            (export_view, [voice], [export_ckpt, export_files]),
            (settings_view, [voice], [settings_text]),
        ]

        def known_voice(fn):
            """A voice that is not (or no longer) on the disk is shown as no voice, not as a traceback."""

            def view(voice, *rest):
                return fn(voice if voice in service.list_voices(root) else None, *rest)

            view.__name__ = getattr(fn, "__name__", "view")
            return view

        def load_all(event):
            for fn, inputs, outputs in views:
                event = event.then(known_voice(fn), inputs, outputs)
            return event.then(base_view, [base_dir], [base_msg, base_ckpt, base_dir])

        load_all(voice.change(lambda: None, None, None))
        load_all(refresh.click(refresh_voices, [voice], [voice]))
        load_all(app.load(open_voice, None, [voice]))
        voice.change(partial(service.remember_voice, root), [voice], None)

        create_button.click(create, [new_name, new_piper], [voice, create_msg])
        train_base_create.click(open_base_section, [voice], [tabs, current_tab, status])
        ref_button.click(prepare_reference, [voice, ref_files, ref_embed], [ref_msg, *ref_players]).then(
            status_md, [voice, current_tab], [status]
        )
        corpus_button.click(
            build_corpus, [voice, corpus_files, corpus_bundled, corpus_size], [corpus_msg, corpus_table]
        ).then(status_md, [voice, current_tab], [status])
        audition_button.click(
            lambda v, n: start("audition", need_voice(v), ["audition", v, "--count", str(int(n))]),
            [voice, audition_count],
            [audition_msg],
        )
        audition_slug.change(audition_pick, [voice, audition_slug], audition_players)
        audition_apply_button.click(audition_apply, [voice, audition_slug], [audition_msg])
        synth_button.click(
            lambda v, n: start(
                "synthesize", need_voice(v), ["synthesize", v] + (["--limit", str(int(n))] if n else [])
            ),
            [voice, synth_limit],
            [synth_msg],
        )
        app.load(el_key_state, None, [el_key_msg])
        el_outputs = [synth_backend, el_help, el_box, el_voice, el_sentences, el_msg_box, el_msg]
        el_key_save.click(el_save_key, [el_key], [el_key, el_key_msg]).then(
            known_voice(el_view), [voice], el_outputs
        )
        synth_backend.input(pick_backend, [voice, synth_backend], None).then(
            known_voice(el_view), [voice], el_outputs
        )
        rename_button.click(rename, [voice, rename_name, rename_piper], [voice, rename_msg])
        el_refresh.click(el_refresh_account, [voice, el_voice], [el_voice, el_msg])
        el_voice.input(el_pick_voice, [voice, el_voice], [el_msg])
        el_sentences_use.click(el_use_sentences, [voice, el_sentences], [el_msg, corpus_table]).then(
            status_md, [voice, current_tab], [status]
        )
        filter_button.click(
            lambda v, n, a, s, m: start(
                "filter",
                need_voice(v),
                ["filter", v]
                + (["--target", str(int(n))] if n else [])
                + ([] if a else ["--no-asr"])
                + ([] if s else ["--no-similarity"])
                + ([] if m else ["--no-mos"]),
            ),
            [voice, filter_target, filter_asr, filter_sim, filter_mos],
            [filter_msg],
        )
        train_button.click(run_train, [voice, train_base, train_epochs, train_poweroff], [train_msg])
        train_queue_button.click(
            run_queue, [train_queue, train_base, train_epochs, train_poweroff], [train_msg]
        )
        export_button.click(run_export, [voice, export_ckpt], [export_msg])
        settings_button.click(settings_save, [voice, settings_text], [settings_msg])
        import_button.click(run_import, [voice, import_dir, import_persona, import_verify], [import_msg])
        server_fields = [server_host, server_user, server_port, server_key, server_dir, server_ui_port]
        app.load(server_view, None, [*server_fields, server_msg])
        server_save_button.click(server_save, server_fields, [server_msg])
        app.load(server_state_view, [server_seen], [server_state, server_seen])
        gr.Timer(3.0).tick(server_state_view, [server_seen], [server_state, server_seen])
        for action, button in (
            ("status", server_status_button),
            ("prepare", server_prepare_button),
            ("push", server_push_button),
            ("install", server_install_button),
            ("pull", server_pull_button),
        ):
            button.click(partial(server_job, action), None, [server_msg])
        app.load(ha_view, None, [ha_url, ha_token, power_switch, power_sensor, power_watts])
        ha_save_button.click(
            ha_save,
            [ha_url, ha_token, power_switch, power_sensor],
            [ha_msg, ha_token, power_switch, power_sensor],
        )
        ha_remove_button.click(
            ha_remove,
            [ha_confirm],
            [ha_msg, ha_url, ha_token],
            js=f"async () => [await window.pvcAsk({json.dumps(t['ha_remove_confirm'])}, {{danger: true}})]",
        )
        power_suggest_button.click(
            power_suggest, [power_switch, power_sensor], [power_msg, power_switch, power_sensor]
        )
        power_save_button.click(power_save, [power_switch, power_sensor, power_watts], [power_msg])
        base_prepare_button.click(run_base_prepare, [base_dir, base_audio], [base_msg])
        base_train_button.click(run_base_train, [base_epochs, base_quality, base_batch], [base_msg])
        base_quality.input(lambda q: train_mod.DEFAULT_BATCH.get(q, 32), [base_quality], [base_batch])
        score_outputs = [score_box, score_worst_head, score_best_head, *score_worst, *score_best, score_seen]
        score_button.click(run_score, [score_sample], [base_msg]).then(
            score_view, [score_seen], score_outputs
        )
        app.load(score_view, [score_seen], score_outputs)
        gr.Timer(3.0).tick(score_view, [score_seen], score_outputs)
        app.load(compare_view, None, [base_compare])
        base_select_button.click(run_base_select, [base_ckpt], [base_msg])
        base_export_button.click(run_base_export, [base_ckpt], [base_msg])
        app.load(chart_view, [voice, chart_seen], [chart, chart_seen])
        chart_timer = gr.Timer(20.0)
        chart_timer.tick(chart_view, [voice, chart_seen], [chart, chart_seen])
        chart_timer.tick(compare_view, None, [base_compare])
        voice.change(chart_view, [voice, chart_seen], [chart, chart_seen])
        train_listen_outputs = [train_listen_head, train_listen_epoch, *train_listen_players]
        train_listen_refresh.click(listen_voice, [voice, train_listen_epoch], train_listen_outputs)
        train_listen_epoch.input(listen_voice, [voice, train_listen_epoch], train_listen_outputs)
        base_listen_outputs = [base_listen_model, base_listen_head, base_listen_epoch, *base_listen_players]
        app.load(listen_base, None, base_listen_outputs)
        base_listen_refresh.click(
            listen_base, [base_listen_model, base_listen_epoch], base_listen_outputs
        ).then(compare_view, None, [base_compare])
        base_listen_epoch.input(listen_base, [base_listen_model, base_listen_epoch], base_listen_outputs)
        base_listen_model.input(listen_base, [base_listen_model], base_listen_outputs)
        train_samples_button.click(download_voice_samples, [voice], [train_samples_file])
        base_samples_button.click(download_base_samples, [base_listen_model], [base_samples_file])
        tick_outputs = [topbar, live, job_log, status, stop_button, job_poweroff_box, job_poweroff]
        job_poweroff.input(set_job_poweroff, [job_poweroff], None)
        stop_button.click(lambda: jobs.stop() and None, None, None).then(
            tick, [voice, current_tab], tick_outputs
        )
        topbar.click(toggle_machine, [voice, current_tab], tick_outputs)

        status.click(navigate, [voice], [tabs, current_tab, status])

        # the first look at once (the machine and Home Assistant answer later, in the background)
        app.load(tick, [voice, current_tab], tick_outputs)
        timer = gr.Timer(2.0)
        timer.tick(tick, [voice, current_tab], tick_outputs)

    return app


def create_server(root: Path, default_lang: str, auth: tuple[str, str] | None):
    """One FastAPI app with /en/ and /pl/ (same jobs and data); / picks the remembered language."""
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse

    server = FastAPI()
    jobs = JobManager(root)
    machine = MachineMonitor(root, jobs)  # one for both languages: one background check at a time
    for code in LANGUAGES:
        blocks = build(root, code, jobs, machine).queue()
        gr.mount_gradio_app(
            server,
            blocks,
            path=f"/{code}",
            auth=auth,
            allowed_paths=[str(root.resolve())],
            theme=style.theme(),
            css=style.CSS,
            footer_links=[],
            head=style.head(texts(code)["ask_cancel"]),
        )

    from fastapi.responses import FileResponse, Response

    pages = {f"/{code}{end}" for code in LANGUAGES for end in ("", "/")}

    @server.middleware("http")
    async def login_style(request, call_next):
        # the login form is drawn before Gradio hands out the app's CSS and head, so its look and the
        # tab icon go into the page HTML itself (only the scoped login rules and the colours)
        response = await call_next(request)
        content_type = response.headers.get("content-type", "")
        if request.url.path not in pages or not content_type.startswith("text/html"):
            return response
        body = b"".join([chunk async for chunk in response.body_iterator])
        body = body.replace(b"</head>", style.LOGIN_HEAD.encode() + b"</head>", 1)
        headers = {k: v for k, v in response.headers.items() if k.lower() != "content-length"}
        return Response(body, status_code=response.status_code, headers=headers)

    def icon(name: str, media: str):
        def serve() -> FileResponse:
            return FileResponse(style.STATIC / name, media_type=media)

        return serve

    for route, name, media in (
        ("/favicon.svg", "favicon.svg", "image/svg+xml"),
        ("/favicon-32.png", "favicon-32.png", "image/png"),
        ("/favicon.ico", "favicon-32.png", "image/png"),
        ("/apple-touch-icon.png", "apple-touch-icon.png", "image/png"),
    ):
        server.add_api_route(route, icon(name, media), include_in_schema=False, response_model=None)

    @server.get("/guide/{code}", response_class=HTMLResponse)
    def guide_page(code: str) -> str:
        from .guide import page

        return page(code)

    @server.get("/", response_class=HTMLResponse)
    def choose_language() -> str:
        # remembered choice, else the browser language, else the default
        codes = json.dumps(LANGUAGES)
        return (
            f"<!doctype html><meta charset=utf-8>{style.ICON_LINKS}<script>"
            f"var codes={codes}, lang='{default_lang}';"
            "try{var saved=localStorage.getItem('pvc-lang');if(codes.indexOf(saved)>=0)lang=saved;"
            "else{var nav=(navigator.language||'').slice(0,2);if(codes.indexOf(nav)>=0)lang=nav;}}catch(e){}"
            "location.replace('./'+lang+'/');</script>"
        )

    return server


class _QuietShutdown(logging.Filter):
    """Hide uvicorn's tracebacks for the browser streams it cancels on Ctrl+C."""

    def filter(self, record: logging.LogRecord) -> bool:
        if "timeout graceful shutdown exceeded" in record.getMessage():
            return False
        return not (record.exc_info and isinstance(record.exc_info[1], asyncio.CancelledError))


def launch(root: Path, lang: str, host: str, port: int, auth: tuple[str, str] | None) -> None:
    import uvicorn

    logging.getLogger("uvicorn.error").addFilter(_QuietShutdown())

    # an open browser tab keeps its event stream open forever; without a limit Ctrl+C waits for it
    uvicorn.run(
        create_server(root, lang, auth),
        host=host,
        port=port,
        log_level="warning",
        timeout_graceful_shutdown=2,
    )
