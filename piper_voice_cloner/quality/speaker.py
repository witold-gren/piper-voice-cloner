"""Speaker similarity with sherpa-onnx speaker embeddings (3D-Speaker CAM++ by default).

Same model as Assist Speaker ID: CAM++ zh+en "advanced" separated Piper voices and human
recordings almost perfectly there, while the VoxCeleb CAM++ variant did not.
"""

from __future__ import annotations

from pathlib import Path
import urllib.request

import numpy as np

from ..audio import EMBED_RATE

MODELS_URL = "https://github.com/k2-fsa/sherpa-onnx/releases/download/speaker-recongition-models/"
DEFAULT_MODEL = "3dspeaker_speech_campplus_sv_zh_en_16k-common_advanced.onnx"


def ensure_model(name_or_path: str, models_dir: Path) -> Path:
    path = Path(name_or_path)
    if path.is_file():
        return path
    target = models_dir / path.name
    if not target.is_file():
        models_dir.mkdir(parents=True, exist_ok=True)
        part = target.with_suffix(".part")
        urllib.request.urlretrieve(MODELS_URL + path.name, part)
        part.rename(target)
    return target


def normalize(vector: np.ndarray) -> np.ndarray:
    norm = float(np.linalg.norm(vector))
    return vector / norm if norm > 0 else vector


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(normalize(a), normalize(b)))


def centroid(vectors: list[np.ndarray]) -> np.ndarray:
    if not vectors:
        raise ValueError("no embeddings")
    return normalize(np.mean([normalize(v) for v in vectors], axis=0))


def calibrate_threshold(vectors: list[np.ndarray], *, margin: float = 0.10, floor: float = 0.35) -> float:
    """Minimum similarity for synthetic clips, derived from the reference itself.

    Leave-one-out similarity of each reference chunk to the others shows how much the real
    voice varies; synthetic clips may sit somewhat lower (`margin`), never below `floor`.
    Child voices typically score lower overall, which this adapts to automatically.
    """
    if len(vectors) < 2:
        return floor
    scores = []
    for index, vector in enumerate(vectors):
        others = [v for i, v in enumerate(vectors) if i != index]
        scores.append(cosine(vector, centroid(others)))
    return round(max(floor, float(np.percentile(scores, 10)) - margin), 3)


class SpeakerEmbedder:
    def __init__(self, model: Path, threads: int = 4) -> None:
        import sherpa_onnx  # heavy import, quality environment only

        config = sherpa_onnx.SpeakerEmbeddingExtractorConfig(model=str(model), num_threads=threads)
        if not config.validate():
            raise ValueError(f"invalid speaker model {model}")
        self._extractor = sherpa_onnx.SpeakerEmbeddingExtractor(config)

    def embed(self, audio_16k: np.ndarray) -> np.ndarray:
        stream = self._extractor.create_stream()
        stream.accept_waveform(EMBED_RATE, audio_16k.astype(np.float32))
        stream.input_finished()
        return np.asarray(self._extractor.compute(stream), dtype=np.float32)
