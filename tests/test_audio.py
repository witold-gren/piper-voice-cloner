from __future__ import annotations

import numpy as np
import soundfile as sf

from piper_voice_cloner import audio

from .conftest import requires_ffmpeg, tone, write_mp3_named_wav, write_tone


def test_trim_keeps_padding():
    rate = 22050
    wave = tone(1.0, rate, silence=1.0)
    trimmed = audio.trim(wave, rate, pad=0.1)
    assert 1.15 <= audio.duration(trimmed, rate) <= 1.25


def test_trim_silence_only():
    assert audio.trim(np.zeros(22050, dtype=np.float32), 22050).size == 0
    assert audio.trim(np.zeros(0, dtype=np.float32), 22050).size == 0


def test_normalize_level_and_peak_limit():
    rate = 22050
    quiet = tone(1.0, rate, level=0.01)
    loud = audio.normalize_level(quiet, rate)
    rms_db = 20 * np.log10(np.sqrt(np.mean(loud**2)))
    assert abs(rms_db - audio.LOUDNESS_LUFS) < 0.5
    assert np.max(np.abs(audio.peak_limit(tone(0.5, rate, level=1.5)))) <= 10 ** (-1 / 20) + 1e-6


def test_save_wav_is_pcm16(tmp_path):
    path = tmp_path / "x.wav"
    audio.save_wav(path, tone(0.5, 22050, level=2.0))
    info = sf.info(path)
    assert (info.format, info.subtype, info.samplerate, info.channels) == ("WAV", "PCM_16", 22050, 1)


@requires_ffmpeg
def test_load_mp3_posing_as_wav(tmp_path):
    fake = write_mp3_named_wav(tmp_path / "clip.wav", 1.0)
    wave = audio.load(fake, 22050)
    assert wave.dtype == np.float32
    assert 0.9 < audio.duration(wave, 22050) < 1.2


@requires_ffmpeg
def test_load_and_resample(tmp_path):
    path = write_tone(tmp_path / "t.wav", 2.0, 24000)
    assert abs(len(audio.load(path, 16000)) - 32000) < 400
    assert abs(len(audio.resample(tone(1.0, 24000), 24000, 16000)) - 16000) < 200


@requires_ffmpeg
def test_load_error(tmp_path):
    bad = tmp_path / "bad.wav"
    bad.write_bytes(b"not audio at all")
    try:
        audio.load(bad, 22050)
    except audio.AudioError as err:
        assert "bad.wav" in str(err)
    else:
        raise AssertionError("expected AudioError")
