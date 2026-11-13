from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from piper_voice_cloner import backends
from piper_voice_cloner.backends import elevenlabs
from piper_voice_cloner.backends.base import FatalSynthesisError
from piper_voice_cloner.backends.chatterbox import relax_repetition_check
from piper_voice_cloner.backends.elevenlabs import ElevenLabsError, ElevenLabsSynthesizer


class FakeResponse:
    def __init__(self, status=200, content=b"", text="", data=None):
        self.status_code = status
        self.content = content
        self.text = text
        self.data = data

    def json(self):
        return self.data


class FakeSession:
    def __init__(self, response):
        self.response = response
        self.requests = []

    def post(self, url, **kwargs):
        self.requests.append((url, kwargs))
        return self.response

    def get(self, url, **kwargs):
        self.requests.append((url, kwargs))
        return self.response


class ScriptedSession:
    """Answers (or raises) one by one."""

    def __init__(self, *steps):
        self.steps = list(steps)
        self.calls = 0

    def post(self, url, **kwargs):
        self.calls += 1
        step = self.steps.pop(0)
        if isinstance(step, Exception):
            raise step
        return step


def synthesizer(session, sleeps=None):
    return ElevenLabsSynthesizer(
        "pl",
        {},
        voice_id="v",
        session=session,
        api_key="k",
        sleep=(sleeps if sleeps is not None else []).append,
    )


def test_unknown_backend():
    with pytest.raises(ValueError, match="unknown backend"):
        backends.create("bark", "pl", {})


def test_elevenlabs_requires_key(monkeypatch):
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    with pytest.raises(ElevenLabsError, match="ELEVENLABS_API_KEY"):
        ElevenLabsSynthesizer("pl", {}, voice_id="v", session=FakeSession(FakeResponse()))


def test_elevenlabs_requires_voice_id(monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "k")
    with pytest.raises(ElevenLabsError, match="elevenlabs_voice_id"):
        ElevenLabsSynthesizer("pl", {}, session=FakeSession(FakeResponse()))


def test_elevenlabs_rejects_unknown_options(monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "k")
    with pytest.raises(ValueError, match="unknown elevenlabs options"):
        ElevenLabsSynthesizer("pl", {"speed": 2}, voice_id="v", session=FakeSession(FakeResponse()))


def test_elevenlabs_request_and_pcm_decoding(monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "secret")
    pcm = np.array([0, 16384, -32768], dtype="<i2").tobytes()
    session = FakeSession(FakeResponse(content=pcm))
    synth = backends.create("elevenlabs", "pl", {"stability": 0.4}, voice_id="voice123", session=session)
    assert synth.remote
    wave, rate = synth.synthesize("Dzień dobry.", Path("ref.wav"), seed=5)
    assert rate == 24000
    assert np.allclose(wave, [0.0, 0.5, -1.0])
    url, kwargs = session.requests[0]
    assert url.endswith("/voice123")
    assert kwargs["headers"]["xi-api-key"] == "secret"
    assert kwargs["params"] == {"output_format": "pcm_24000"}
    assert kwargs["json"]["seed"] == 5
    assert kwargs["json"]["voice_settings"]["stability"] == 0.4
    assert kwargs["json"]["model_id"] == "eleven_multilingual_v2"


def test_elevenlabs_http_error(monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "k")
    synth = ElevenLabsSynthesizer(
        "pl", {}, voice_id="v", session=FakeSession(FakeResponse(401, text="invalid api key"))
    )
    with pytest.raises(ElevenLabsError, match="HTTP 401"):
        synth.synthesize("Tekst.", Path("r.wav"), 1)


def test_seed_everything_is_deterministic():
    from piper_voice_cloner.backends.base import seed_everything

    seed_everything(3)
    first = np.random.rand(3)
    seed_everything(3)
    assert np.allclose(first, np.random.rand(3))


class FakeTorch:
    """Just enough of torch for pick_device: which GPUs are there."""

    def __init__(self, cuda: bool, mps: bool):
        self.cuda = type("cuda", (), {"is_available": staticmethod(lambda: cuda)})
        mps_backend = type("mps", (), {"is_available": staticmethod(lambda: mps)})
        self.backends = type("backends", (), {"mps": mps_backend})


@pytest.mark.parametrize(
    ("cuda", "mps", "allow_mps", "expected"),
    [
        (True, True, True, "cuda"),  # the NVIDIA GPU first
        (False, True, True, "mps"),  # a Mac: the Apple GPU
        (False, True, False, "cpu"),  # a backend not tried on the Apple GPU
        (False, False, True, "cpu"),
    ],
)
def test_pick_device(monkeypatch, cuda, mps, allow_mps, expected):
    import sys

    from piper_voice_cloner.backends.base import pick_device

    monkeypatch.setitem(sys.modules, "torch", FakeTorch(cuda, mps))
    assert pick_device(allow_mps=allow_mps) == expected
    assert pick_device("cpu") == "cpu"  # voice.yaml synthesis.options.device wins


class FakeAnalyzer:
    """The part of chatterbox's AlignmentStreamAnalyzer the repetition fix touches."""

    def __init__(self):
        self.complete = False
        self.generated_tokens = []
        self.forced = []

    def step(self, logits, next_token=None):
        self.generated_tokens.append(next_token)
        repeated = len(self.generated_tokens) >= 3 and len(set(self.generated_tokens[-2:])) == 1
        self.forced.append(repeated)
        return logits


def test_repetition_check_waits_for_the_end_of_the_text():
    class Analyzer(FakeAnalyzer):
        pass

    relax_repetition_check(Analyzer)
    relax_repetition_check(Analyzer)  # a second synthesizer must not wrap the step twice
    analyzer = Analyzer()
    for token in (5, 7, 7, 7):  # a drawn-out sound in the middle of the text
        analyzer.step(None, token)
    assert analyzer.forced == [False, False, False, False]
    analyzer.complete = True
    for token in (9, 9, 9):  # a loop after the text is still stopped
        analyzer.step(None, token)
    assert analyzer.forced[-1] is True


def test_elevenlabs_retries_rate_limits_and_lost_connections():
    audio = np.array([1, 2], dtype="<i2").tobytes()
    session = ScriptedSession(
        FakeResponse(429, text="busy"), ConnectionError("reset"), FakeResponse(200, audio)
    )
    sleeps = []
    wave, _rate = synthesizer(session, sleeps).synthesize("Zdanie.", Path("-"), 1)
    assert len(wave) == 2
    assert sleeps == [1, 2]


def test_elevenlabs_gives_up_the_whole_run_when_the_service_stays_down():
    session = ScriptedSession(*[FakeResponse(503, text="down")] * (elevenlabs.RETRIES + 1))
    with pytest.raises(FatalSynthesisError, match="run again later"):
        synthesizer(session).synthesize("Zdanie.", Path("-"), 1)
    assert session.calls == elevenlabs.RETRIES + 1


@pytest.mark.parametrize("status", [401, 402, 403, 404])
def test_elevenlabs_stops_at_once_without_credits_or_with_a_wrong_key(status):
    session = ScriptedSession(FakeResponse(status, text="quota_exceeded"))
    with pytest.raises(FatalSynthesisError, match="quota_exceeded"):
        synthesizer(session).synthesize("Zdanie.", Path("-"), 1)
    assert session.calls == 1


def test_elevenlabs_bad_sentence_is_not_fatal():
    with pytest.raises(ElevenLabsError) as info:
        synthesizer(ScriptedSession(FakeResponse(422, text="bad text"))).synthesize("Zdanie.", Path("-"), 1)
    assert not isinstance(info.value, FatalSynthesisError)


def test_elevenlabs_source_names_the_voice():
    assert synthesizer(FakeSession(FakeResponse())).source == "elevenlabs:v"


def test_elevenlabs_key_file_is_private_and_removable(monkeypatch):
    elevenlabs.save_api_key(" secret ")
    assert elevenlabs.load_api_key() == "secret"
    assert elevenlabs.CONFIG_FILE.stat().st_mode & 0o777 == 0o600
    monkeypatch.setenv("ELEVENLABS_API_KEY", "from-env")
    assert elevenlabs.load_api_key() == "from-env"
    monkeypatch.delenv("ELEVENLABS_API_KEY")
    elevenlabs.save_api_key("")
    assert elevenlabs.load_api_key() == ""


def test_elevenlabs_synthesizer_reads_the_saved_key():
    elevenlabs.save_api_key("saved")
    synth = ElevenLabsSynthesizer("pl", {}, voice_id="v", session=FakeSession(FakeResponse()))
    assert synth.api_key == "saved"


def test_elevenlabs_lists_own_voices_first():
    data = {
        "voices": [
            {"voice_id": "a", "name": "Adam", "category": "premade"},
            {"voice_id": "b", "name": "Bartek", "category": "professional"},
            {"voice_id": "o", "name": "Alicja Lektorka", "category": "cloned"},
        ]
    }
    session = FakeSession(FakeResponse(data=data))
    assert [v["id"] for v in elevenlabs.list_voices(session, "k")] == ["o", "a", "b"]
    assert session.requests[0][1]["headers"] == {"xi-api-key": "k"}


def test_elevenlabs_credits():
    data = {"character_count": 100, "character_limit": 150, "next_character_count_reset_unix": 7}
    credits = elevenlabs.read_credits(FakeSession(FakeResponse(data=data)), "k")
    assert (credits.left, credits.reset) == (50, 7)


def test_elevenlabs_account_needs_a_key_and_reports_refusals():
    with pytest.raises(ElevenLabsError, match="no API key"):
        elevenlabs.list_voices(FakeSession(FakeResponse()))
    with pytest.raises(ElevenLabsError, match="HTTP 401"):
        elevenlabs.list_voices(FakeSession(FakeResponse(401, text="nope")), "k")


def test_elevenlabs_credits_are_optional_for_a_restricted_key():
    session = FakeSession(FakeResponse(401, text="missing_permissions"))
    assert elevenlabs.optional_credits(session, "k") is None
