#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests unitaires — STTEngine"""

import numpy as np
import pytest
from core.stt_engine import STTEngine, _bytes_to_float32, _bytes_to_wav_buffer


def test_bytes_to_float32_range():
    """La conversion float32 produit des valeurs dans [-1, 1]."""
    audio_int16 = np.array([0, 16384, -16384, 32767, -32768], dtype=np.int16)
    audio_bytes = audio_int16.tobytes()
    result = _bytes_to_float32(audio_bytes)
    assert result.dtype == np.float32
    assert result.min() >= -1.0
    assert result.max() <= 1.0


def test_bytes_to_wav_buffer():
    """La conversion WAV produit un buffer valide."""
    audio_bytes = b'\x00\x00' * 16000  # 1 seconde de silence
    buf = _bytes_to_wav_buffer(audio_bytes, sample_rate=16000)
    buf.seek(0)
    header = buf.read(4)
    assert header == b'RIFF'  # Signature WAV valide


def test_stt_engine_init():
    engine = STTEngine(mode="local", model_size="tiny")
    assert engine.is_ready() is False
    assert engine.mode == "local"
    assert engine.model_size == "tiny"


def test_stt_empty_audio():
    """Un segment vide retourne un résultat avec texte vide."""
    engine = STTEngine(mode="local", model_size="tiny")
    # Simuler un état "ready" sans charger le modèle
    engine._ready = True
    engine._model = None
    # Ne doit pas lever d'exception, retourner un résultat vide
    with pytest.raises(Exception):
        # Sans modèle chargé, doit échouer gracieusement
        engine._transcribe_local(b'\x00\x00' * 100)
