"""Stands in for `pvc` in the demo: prints the progress lines of the real command, then ends.

Called as `fake_pvc.py --root <root> <command> [args...]`. FAKE_PVC_SPEED (default 1) scales the
waiting; tests set it high.
"""

from __future__ import annotations

import os
import sys
import time

SPEED = float(os.environ.get("FAKE_PVC_SPEED", "1"))


def wait(seconds: float) -> None:
    time.sleep(seconds / SPEED)


def main(argv: list[str]) -> int:
    args = argv[argv.index("--root") + 2 :] if "--root" in argv else argv
    command = args[0] if args else ""
    if command in ("train", "base") and "train" in args:
        print("training epochs 1574-1594", flush=True)
        for epoch in range(1574, 1594):
            for step in range(0, 46, 9):
                bar = f"{step}/45 [00:{step:02d}<00:{45 - step:02d}, 1.8it/s]"
                print(f"\rEpoch {epoch}: {step * 2}%|##   | {bar}", end="", flush=True)
                wait(0.2)
            print(flush=True)
        return 0
    if command == "train-queue":
        voices = [a for a in args[1:] if not a.startswith("--")][:-2] or args[1:2]
        for index, voice in enumerate(voices, 1):
            print(f"queue {index}/{len(voices)}: {voice}", flush=True)
            print("training epochs 0-10", flush=True)
            for epoch in range(10):
                print(f"Epoch {epoch}: 100%|#####| 45/45 [00:20<00:00, 1.8it/s]", flush=True)
                wait(0.3)
        return 0
    total = 200
    for done in range(0, total + 1, 10):
        print(f"progress {command or 'job'} {done}/{total}", flush=True)
        wait(0.15)
    print(f"{command}: done", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
