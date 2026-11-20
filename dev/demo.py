"""The editor on made-up data, without a GPU: `make demo` (Docker), `make demo-local`, browser tests.

    python dev/demo.py [--host 127.0.0.1] [--port 7861] [--root /tmp/pvc-demo] [--auth demo:demo]

Builds a data folder with a few voices at different steps, puts a fake `nvidia-smi` on PATH and
runs every job with dev/fake_pvc.py (prints the same progress lines as the real commands, quickly).
Nothing is trained, generated or downloaded.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from piper_voice_cloner import config as config_mod  # noqa: E402

sys.path.insert(0, str(REPO / "dev"))
import tfevents  # noqa: E402

SENTENCES = [
    "Dzień dobry, jak się dzisiaj czujesz?",
    "Za oknem pada deszcz i wieje mocny wiatr.",
    "Kot śpi na kanapie obok kominka.",
    "Jutro rano pojedziemy nad jezioro.",
    "Ta książka ma piękne ilustracje.",
    "Mama upiekła szarlotkę z cynamonem.",
]
FAKE_SMI = """#!/bin/sh
echo "NVIDIA GeForce RTX 4090, 87, 15360, 24564, 71, 312.5, 450.0"
"""


def _write(path: Path, text: str = "") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _wav(path: Path, seconds: float = 1.2, freq: float = 220.0) -> Path:
    import numpy as np
    import soundfile as sf

    rate = 22050
    t = np.arange(int(seconds * rate)) / rate
    wave = (0.2 * np.sin(2 * np.pi * freq * t) * np.hanning(len(t))).astype("float32")
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(path, wave, rate)
    return path


def _dataset(directory: Path, clips: int, *, imported: bool) -> None:
    lines = []
    for i in range(clips):
        clip_id = f"clip_{i:04d}"
        if i < 6:
            _wav(directory / "dataset" / "wav" / f"{clip_id}.wav", freq=180 + 20 * i)
        lines.append(f"{clip_id}|{SENTENCES[i % len(SENTENCES)]}")
    _write(directory / "dataset" / "metadata.csv", "\n".join(lines) + "\n")
    report = directory / "dataset" / ("import_report.csv" if imported else "filter_report.csv")
    rows = [[f"clip_{i:04d}", SENTENCES[i % 6], ""] for i in range(clips)]
    rows += [[f"bad_{i:03d}", "Zdanie z liczbą 12.", "text:digits"] for i in range(7)]
    cut = "duration" if imported else "too_fast_or_cut"
    rows += [[f"cut_{i:03d}", "Za krótki klip.", cut] for i in range(3)]
    with report.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["id", "text", "reason"])
        writer.writerows(rows)


def _training(directory: Path, epochs: list[int], start: int = 1113, version: int = 0) -> None:
    """Checkpoints, the run plan (run.json) and event files with quality and test sentences."""
    ckpt_dir = directory / "train" / "lightning_logs" / f"version_{version}" / "checkpoints"
    for epoch in epochs:
        _write(ckpt_dir / f"epoch={epoch}-step={epoch * 45}-val_mos={3.2 + epoch / 4000:.4f}.ckpt")
    _write(ckpt_dir / "last.ckpt")
    plan = {"start_epoch": start, "base": "bazowy-pl", "quality": "medium", "first_version": version}
    _write(directory / "train" / "run.json", json.dumps(plan))
    tfevents.training(directory / "train", start, max(epochs), SENTENCES[:4], version=version)


def _earlier_run(directory: Path) -> None:
    """A training started over before the current one (from lessac): its checkpoints stay in version_0,
    its chart and samples in train/runs/0 (what "Start over" keeps)."""
    work = directory / "train"
    ckpt_dir = work / "lightning_logs" / "version_0" / "checkpoints"
    for epoch, mos in ((2190, 3.31), (2240, 3.42), (2290, 3.47)):
        _write(ckpt_dir / f"epoch={epoch}-step={epoch * 45}-val_mos={mos:.4f}.ckpt")
    run = work / "runs" / "0"
    plan = {"start_epoch": 2164, "base": "/data/bases/en_US-lessac-medium.ckpt", "quality": "medium"}
    _write(run / "run.json", json.dumps({**plan, "first_version": 0, "last_version": 0}))
    metrics, audio = {}, {}
    for epoch in range(2165, 2296, 5):
        metrics[str(epoch)] = round(2.6 + 0.85 * (1 - 0.97 ** (epoch - 2164)), 3)
        if epoch % 10 == 0 or epoch in (2165, 2290):
            name = f"epoch{epoch:05d}-00.wav"
            _wav(run / "monitor" / "audio" / name, freq=200 + epoch % 50)
            audio[str(epoch)] = [[0, SENTENCES[0], name, epoch * 100]]
    state = {
        "version": 3, "first_version": 0, "run": plan, "offsets": {}, "metrics": {"val_mos": metrics},
        "sums": {}, "audio": audio, "last_epoch": 2295,
    }  # fmt: skip
    _write(run / "monitor" / "state.json", json.dumps(state))


def _cloning_voice(ola: Path) -> None:
    """Cloning with Chatterbox: recording prepared, sentences chosen, settings tried, clips half made."""
    cfg = config_mod.VoiceConfig(name="ola_bajka", piper_name="pl_PL-ola_bajka", target_clips=1500)
    cfg.quality.min_similarity = 0.52
    cfg.synthesis.options = {"cfg_weight": 0.5, "exaggeration": 0.5}
    config_mod.save(ola, cfg)
    _wav(ola / "reference" / "uploads" / "ola_nagranie.wav", seconds=2.0)
    for i in range(2):
        _wav(ola / "reference" / "clean" / f"ref_{i:02d}.wav", seconds=1.5, freq=240 + 40 * i)
    reference = {
        "prompts": ["ref_00.wav", "ref_01.wav"],
        "seconds": 14.6,
        "min_similarity": 0.52,
        "chunks": 4,
    }
    _write(ola / "reference" / "reference.json", json.dumps(reference))
    _write(ola / "sources" / "bajki.txt", "\n".join(SENTENCES) + "\n")
    _write(
        ola / "prompts.tsv", "id\ttext\n" + "".join(f"p{i:04d}\t{SENTENCES[i % 6]}\n" for i in range(1950))
    )
    combos = []
    for rank, (weight, exaggeration) in enumerate([(0.5, 0.5), (0.3, 0.7), (0.7, 0.3)]):
        slug = f"cfg_weight={weight}_exaggeration={exaggeration}"
        files = []
        for i in range(3):
            _wav(ola / "audition" / slug / f"p{i:04d}.wav", freq=200 + 25 * rank + 10 * i)
            files.append({"file": f"{slug}/p{i:04d}.wav", "text": SENTENCES[i]})
        combos.append(
            {
                "slug": slug,
                "options": {"cfg_weight": weight, "exaggeration": exaggeration},
                "score": 0.61 - 0.07 * rank,
                "cer": 0.012 + 0.01 * rank,
                "similarity": 0.66 - 0.04 * rank,
                "mos": 3.4 - 0.1 * rank,
                "clips": files,
            }
        )
    _write(ola / "audition" / "results.json", json.dumps(combos, ensure_ascii=False))
    (ola / "raw").mkdir(parents=True, exist_ok=True)
    with (ola / "raw" / "manifest.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["id", "text", "reference", "seed", "backend", "rate"])
        for i in range(820):
            writer.writerow([f"p{i:04d}", SENTENCES[i % 6], "ref_00.wav", 1, "chatterbox", 24000])
    timing = {"clips": 820, "seconds": 820 * 4.1, "audio_seconds": 820 * 3.2, "device": "cuda"}
    _write(ola / "raw" / "timing.json", json.dumps(timing))


def _base(bases: Path) -> None:
    """The own base: its data rated with UTMOS, medium and high trained, a few checkpoints."""
    dataset = bases / "pl-scratch" / "dataset"
    clips = {f"k{i:05d}": SENTENCES[i % 6] for i in range(12)}
    for i, clip in enumerate(clips):
        if i < 6 or i >= 9:
            _wav(dataset / "wav" / f"{clip}.wav", freq=170 + 12 * i)
    _write(dataset / "metadata.csv", "".join(f"{clip}|{text}\n" for clip, text in clips.items()))
    scores = {clip: round(2.9 + 0.08 * i, 2) for i, clip in enumerate(clips)}
    report = {"total": 18395, "scores": scores, "texts": clips}
    _write(dataset / "utmos.json", json.dumps(report, ensure_ascii=False))
    for folder, last in (("pl-scratch", 1113), ("pl-scratch-high", 640)):
        work = bases / folder / "train"
        tfevents.training(work, 0, last, SENTENCES[:3], every=20)
        ckpt_dir = work / "lightning_logs" / "version_0" / "checkpoints"
        _write(ckpt_dir / f"epoch={last - 20}-step={last * 500}-val_mos=3.7507.ckpt")
        _write(ckpt_dir / "last.ckpt")


def build(root: Path) -> Path:
    """A data folder with voices on both ways and at different steps."""
    voices = root / "voices"
    # imported, trained and exported
    kasia = voices / "kasia"
    config_mod.save(
        kasia, config_mod.VoiceConfig(name="kasia", piper_name="pl_PL-kasia_glos", workflow="import")
    )
    _dataset(kasia, 1496, imported=True)
    _earlier_run(kasia)
    _training(kasia, [1203, 1388, 1573], version=1)
    _write(kasia / "export" / "pl_PL-kasia_glos-medium.onnx")
    _write(kasia / "export" / "pl_PL-kasia_glos-medium.onnx.json", "{}")
    # imported, not trained yet
    tomek = voices / "tomek"
    config_mod.save(tomek, config_mod.VoiceConfig(name="tomek", workflow="import"))
    _dataset(tomek, 1913, imported=True)
    # cloned from ElevenLabs, filtered
    alicja = voices / "alicja"
    cfg = config_mod.VoiceConfig(name="alicja", target_clips=1500)
    cfg.synthesis.backend = "elevenlabs"
    cfg.synthesis.elevenlabs_voice_name = "Alicja Lektorka"
    config_mod.save(alicja, cfg)
    _write(
        alicja / "prompts.tsv", "id\ttext\n" + "".join(f"p{i:04d}\t{SENTENCES[i % 6]}\n" for i in range(1496))
    )
    _dataset(alicja, 1388, imported=False)
    _cloning_voice(voices / "ola_bajka")
    # own recordings waiting for the import (folder import/ of the data)
    folder = root / "import" / "nagrania_basi"
    for i in range(6):
        _wav(folder / "wav" / f"b{i:03d}.wav", freq=200 + 15 * i)
    _write(folder / "metadata.csv", "".join(f"b{i:03d}|{SENTENCES[i]}\n" for i in range(6)))
    _write(folder / "custom_metadata.csv", "b000|1. Dzień dobry, jak się dzisiaj czujesz?\n")
    _base(root / "bases")
    _write(root / "jobs" / "last_voice.txt", "kasia")
    return root


def fake_tools(directory: Path) -> Path:
    """A bin folder with a fake nvidia-smi; put it first on PATH."""
    smi = _write(directory / "nvidia-smi", FAKE_SMI)
    smi.chmod(0o755)
    return directory


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--host", default="127.0.0.1", help="0.0.0.0 in the demo container")
    parser.add_argument("--port", type=int, default=7861)
    parser.add_argument("--root", type=Path)
    parser.add_argument("--auth", default="demo:demo", help="user:password ('' = no login)")
    args = parser.parse_args()
    root = args.root or Path(tempfile.mkdtemp(prefix="pvc-demo-"))
    if args.root and root.exists():
        shutil.rmtree(root)
    build(root)
    os.environ["PATH"] = f"{fake_tools(root / '.bin')}{os.pathsep}{os.environ['PATH']}"
    # never the real Home Assistant connection or ElevenLabs key of this computer
    os.environ["PVC_HA_CONFIG"] = str(root / ".config" / "home_assistant.json")
    os.environ["PVC_ELEVENLABS_CONFIG"] = str(root / ".config" / "elevenlabs.json")
    for name in ("PVC_HA_URL", "PVC_HA_TOKEN", "ELEVENLABS_API_KEY"):
        os.environ.pop(name, None)

    import uvicorn

    from piper_voice_cloner import power
    from piper_voice_cloner.editor.auth import Login

    # a demo never powers anything off: the countdown ends here
    power.power_off = lambda: print("demo: the machine would be switched off now")
    from piper_voice_cloner.editor.server import create_app

    app = create_app(
        root,
        login=Login.parse(args.auth, "demo-secret"),
        pvc=[sys.executable, str(REPO / "dev" / "fake_pvc.py")],
        tensorboard_port=6006,
    )
    print(f"Demo editor: http://localhost:{args.port}/   data: {root}   (Ctrl+C stops)")
    try:
        uvicorn.run(app, host=args.host, port=args.port, log_level="warning", timeout_graceful_shutdown=2)
    finally:
        if not args.root:  # Ctrl+C leaves nothing behind (the gpu-studio standard, §8b)
            shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    main()
