"""Prompt corpus: plain sentences selected for phoneme and diphone coverage.

Selection is lazy greedy over a submodular gain: each phoneme unit is worth less every time
it is already covered, rare units are worth more. Units come from espeak-ng with the
same voice Piper uses, so coverage matches what the model will actually be trained on.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
import csv
import hashlib
import heapq
import itertools
import math
from pathlib import Path
import shutil
import subprocess

from . import config as config_mod, text_filter
from .dataset import METADATA, read_metadata
from .languages import LanguagePack
from .synthesis import read_manifest

# sentences -> list of phoneme sequences (one list of phonemes per sentence)
Phonemizer = Callable[[list[str]], list[list[str]]]
PROMPTS = "prompts.tsv"


def read_sentences(path: Path) -> list[str]:
    """Plain text (one sentence per line) or TSV `id<TAB>text` (header row skipped)."""
    sentences = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if "\t" in line:
            _id, text = line.split("\t", 1)
            if _id == "id":
                continue
            line = text
        line = line.strip()
        if line and not line.startswith("#"):
            sentences.append(line)
    return sentences


def prompt_id(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]


def espeak_phonemizer(lang: LanguagePack, workers: int = 8) -> Phonemizer:
    binary = shutil.which("espeak-ng")
    if not binary:
        raise RuntimeError("espeak-ng not found - install it (apt install espeak-ng)")

    def one(text: str) -> list[str]:
        result = subprocess.run(
            [binary, "-q", "-v", lang.espeak_voice, "--ipa=3", text],
            capture_output=True,
            text=True,
            check=False,
        )
        # --ipa=3 separates phonemes with '_' and words with spaces
        phonemes = []
        for word in result.stdout.split():
            phonemes += [p for p in word.replace("ˈ", "").replace("ˌ", "").split("_") if p]
            phonemes.append(" ")
        return phonemes[:-1]

    def run(texts: list[str]) -> list[list[str]]:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            return list(pool.map(one, texts))

    return run


def units(phonemes: list[str]) -> set[str]:
    """Phonemes and within-word diphones."""
    found = {p for p in phonemes if p != " "}
    for a, b in itertools.pairwise(phonemes):
        if a != " " and b != " ":
            found.add(f"{a}+{b}")
    return found


def select(
    sentences: list[str],
    phonemes: list[list[str]],
    size: int,
    *,
    focus: Iterable[str] = (),
    focus_bonus: float = 2.0,
) -> list[int]:
    """Indexes of `size` sentences maximizing (diminishing) phoneme/diphone coverage."""
    sets = [units(p) for p in phonemes]
    frequency = Counter(u for s in sets for u in s)
    weight = {u: 1.0 / math.log(2 + count) for u, count in frequency.items()}
    focus = set(focus)
    for u in weight:
        if u in focus or any(part in focus for part in u.split("+")):
            weight[u] *= focus_bonus
    covered: Counter[str] = Counter()

    def gain(index: int) -> float:
        # per-unit value halves with each sentence that already covers it
        value = sum(weight[u] / (2 ** covered[u]) for u in sets[index])
        return value / math.sqrt(max(1, len(sentences[index].split())))

    heap = [(-gain(i), i) for i in range(len(sentences))]
    heapq.heapify(heap)
    chosen: list[int] = []
    while heap and len(chosen) < size:
        _stale, index = heapq.heappop(heap)
        fresh = gain(index)
        # gains only shrink, so a stale top entry is re-queued with its real value
        if heap and fresh < -heap[0][0]:
            heapq.heappush(heap, (-fresh, index))
            continue
        chosen.append(index)
        covered.update(sets[index])
    return chosen


def build(
    sources: list[Path],
    lang: LanguagePack,
    size: int,
    phonemize: Phonemizer,
    *,
    max_words: int = 20,
) -> tuple[list[tuple[str, str]], list[dict]]:
    """(selected (id, text) prompts, report rows for every input line)."""
    report: list[dict] = []
    pool: list[str] = []
    seen: set[str] = set()
    for source in sources:
        for raw in read_sentences(source):
            verdict = text_filter.check(raw, lang, max_words=max_words)
            key = lang.normalize_for_cer(verdict.text)
            reason = verdict.reason or ("duplicate" if key in seen else "")
            report.append({"source": source.name, "text": verdict.text, "reason": reason})
            if not reason:
                seen.add(key)
                pool.append(verdict.text)
    chosen = select(pool, phonemize(pool), size, focus=lang.focus_phonemes)
    return [(prompt_id(pool[i]), pool[i]) for i in chosen], report


MIN_SENTENCES = 10  # the smallest target_clips of a voice
IMPORT_REPORT = "import_report.csv"


def from_dataset(metadata: Path) -> list[tuple[str, str]]:
    """The sentences of a dataset as prompts: one text has the same id in every voice."""
    return list({prompt_id(u.text): u.text for u in read_metadata(metadata)}.items())


def refuse_imported(directory: Path) -> None:
    """An imported voice is a finished recording set: new clips belong in a new voice."""
    if (directory / "dataset" / IMPORT_REPORT).is_file():
        raise ValueError(f"'{directory.name}' is an imported voice: create a new voice to generate clips")


def use_dataset_sentences(directory: Path, source: Path) -> int:
    """Read exactly the sentences of the voice in `source`; returns how many.

    Every sentence is meant to be kept, so nothing is generated on top and the filter drops only
    clips that fail a check, not the worst tenth.
    """
    refuse_imported(directory)
    prompts = from_dataset(source / "dataset" / METADATA)
    if len(prompts) < MIN_SENTENCES:
        raise ValueError(f"only {len(prompts)} sentences in {source / 'dataset' / METADATA}")
    stale = set(read_manifest(directory / "raw")) - {utt_id for utt_id, _text in prompts}
    if stale:
        raise ValueError(f"raw/ already holds {len(stale)} clips of other sentences: use a new voice")
    write_prompts(directory / PROMPTS, prompts)
    cfg = config_mod.load(directory)
    cfg.target_clips = len(prompts)
    cfg.synthesis.overgenerate = 1.0
    cfg.quality.mos_drop_fraction = 0.0
    config_mod.save(directory, cfg)
    return len(prompts)


def write_prompts(path: Path, prompts: list[tuple[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(["id", "text"])
        writer.writerows(prompts)


def read_prompts(path: Path) -> list[tuple[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.reader(handle, delimiter="\t"))
    return [(row[0], row[1]) for row in rows[1:] if len(row) >= 2]
