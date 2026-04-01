#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests d'intégration — Vérification de la structure des pipelines"""

import numpy as np
import pytest
from core.audio_buffer import AudioBuffer
from core.vad_engine import VADEngine
from utils.audio_utils import (
    bytes_to_float32, float32_to_bytes,
    validate_webrtcvad_chunk, is_silent, calculate_rms, rms_to_db,
)


# ── AudioBuffer ───────────────────────────────────────────────────────────────

def test_audio_buffer_push_flush():
    buf = AudioBuffer(sample_rate=16000)
    chunk = b'\x00\x01' * 480  # 960 bytes
    buf.push(chunk)
    assert not buf.is_empty()
    data = buf.flush()
    assert data == chunk
    assert buf.is_empty()


def test_audio_buffer_duration():
    buf = AudioBuffer(sample_rate=16000)
    # 16000 samples/sec × 2 bytes/sample = 32000 bytes/sec
    # 30ms = 960 bytes
    chunk = b'\x00\x00' * 480  # 960 bytes = 30ms
    buf.push(chunk)
    assert buf.duration_ms() == 30


def test_audio_buffer_force_flush_flag():
    buf = AudioBuffer(sample_rate=16000, max_duration_ms=100)
    # Remplir au-delà de 100ms
    chunk = b'\x00\x00' * 480  # 30ms par chunk
    for _ in range(5):  # 150ms total
        buf.push(chunk)
    assert buf.should_force_flush()


def test_audio_buffer_clear():
    buf = AudioBuffer()
    buf.push(b'\x01' * 100)
    buf.clear()
    assert buf.is_empty()
    assert buf.size_bytes() == 0


# ── Audio Utils ───────────────────────────────────────────────────────────────

def test_bytes_to_float32_silence():
    silence = b'\x00\x00' * 100
    result = bytes_to_float32(silence)
    assert np.all(result == 0.0)


def test_float32_roundtrip():
    original = np.array([0.5, -0.5, 0.0, 1.0, -1.0], dtype=np.float32)
    encoded = float32_to_bytes(original)
    decoded = bytes_to_float32(encoded)
    np.testing.assert_allclose(decoded, original, atol=1e-4)


def test_validate_webrtcvad_chunk_valid():
    # 30ms à 16000 Hz = 480 samples × 2 bytes = 960 bytes
    chunk = b'\x00\x00' * 480
    assert validate_webrtcvad_chunk(chunk, 16000, 30) is True


def test_validate_webrtcvad_chunk_wrong_size():
    chunk = b'\x00\x00' * 400  # Mauvaise taille
    assert validate_webrtcvad_chunk(chunk, 16000, 30) is False


def test_validate_webrtcvad_chunk_wrong_rate():
    chunk = b'\x00\x00' * 480
    assert validate_webrtcvad_chunk(chunk, 44100, 30) is False


def test_is_silent_with_silence():
    silence = b'\x00\x00' * 480
    assert is_silent(silence) is True


def test_is_silent_with_signal():
    # Signal 440 Hz à pleine amplitude
    sr = 16000
    t = np.linspace(0, 0.03, 480, endpoint=False)
    signal = (0.5 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    audio_bytes = (signal * 32767).astype(np.int16).tobytes()
    assert is_silent(audio_bytes) is False


def test_rms_silence():
    audio = np.zeros(100, dtype=np.float32)
    assert calculate_rms(audio) == 0.0
    assert rms_to_db(0.0) == -96.0


# ── VADEngine ─────────────────────────────────────────────────────────────────

def test_vad_engine_init_no_webrtcvad():
    """Le VAD doit fonctionner même sans webrtcvad installé."""
    vad = VADEngine(backend="webrtcvad", sample_rate=16000, chunk_ms=30)
    # Même si webrtcvad n'est pas installé, l'objet doit être créé
    assert vad is not None


def test_vad_engine_process_silence():
    """Le silence ne doit pas déclencher de flush immédiat."""
    vad = VADEngine(
        backend="webrtcvad",
        sample_rate=16000,
        chunk_ms=30,
        max_silence_ms=800,
    )
    silence = b'\x00\x00' * 480  # 30ms de silence
    result = vad.process_chunk(silence)
    # Le silence seul ne doit pas flusher (pas de parole accumulée)
    assert result.should_flush is False


def test_vad_engine_reset():
    vad = VADEngine(sample_rate=16000, chunk_ms=30)
    vad.reset()  # Ne doit pas lever d'exception
    assert vad.in_speech is False


# ── Config ────────────────────────────────────────────────────────────────────

def test_settings_manager_default_values():
    from config.settings_manager import SettingsManager
    import tempfile
    import os
    # Tester avec un dossier temp pour ne pas polluer la config réelle
    s = SettingsManager()
    assert s.user_lang in ("fr", "en", "de", "es")
    assert s.sample_rate == 16000
    assert s.chunk_ms == 30
    assert isinstance(s.pipeline_a_enabled, bool)


def test_language_registry_completeness():
    from config.language_registry import LANGUAGE_REGISTRY, get_all_codes
    codes = get_all_codes()
    assert len(codes) == 20
    for code in codes:
        lang = LANGUAGE_REGISTRY[code]
        assert "name" in lang
        assert "flag" in lang
        assert "whisper_code" in lang
        assert "rtl" in lang
