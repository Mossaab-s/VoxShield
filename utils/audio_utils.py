#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VoxShield — Fonctions utilitaires audio.
Conversion, normalisation, rééchantillonnage et validation des données audio.
"""

import numpy as np

from utils.logger import get_logger

logger = get_logger("AUDIO")


def bytes_to_float32(audio_bytes: bytes, dtype: np.dtype = np.int16) -> np.ndarray:
    """
    Convertit des bytes PCM bruts en tableau numpy float32 normalisé [-1.0, 1.0].

    Args:
        audio_bytes: Données PCM brutes.
        dtype: Type entier source (int16 par défaut, compatible Whisper).

    Returns:
        Tableau float32 normalisé.
    """
    audio = np.frombuffer(audio_bytes, dtype=dtype)
    return audio.astype(np.float32) / np.iinfo(dtype).max


def float32_to_bytes(audio: np.ndarray, dtype: np.dtype = np.int16) -> bytes:
    """
    Convertit un tableau float32 normalisé en bytes PCM.

    Args:
        audio: Tableau float32 normalisé [-1.0, 1.0].
        dtype: Type entier cible.

    Returns:
        Bytes PCM.
    """
    audio_clipped = np.clip(audio, -1.0, 1.0)
    return (audio_clipped * np.iinfo(dtype).max).astype(dtype).tobytes()


def resample(
    audio: np.ndarray,
    orig_rate: int,
    target_rate: int,
) -> np.ndarray:
    """
    Rééchantillonne un signal audio vers un nouveau taux.

    Args:
        audio: Signal source float32.
        orig_rate: Taux d'échantillonnage source (Hz).
        target_rate: Taux d'échantillonnage cible (Hz).

    Returns:
        Signal rééchantillonné float32.
    """
    if orig_rate == target_rate:
        return audio
    from scipy.signal import resample_poly
    from math import gcd
    g = gcd(orig_rate, target_rate)
    up = target_rate // g
    down = orig_rate // g
    return resample_poly(audio, up, down).astype(np.float32)


def calculate_rms(audio: np.ndarray) -> float:
    """Calcule le niveau RMS (Root Mean Square) d'un signal audio."""
    if len(audio) == 0:
        return 0.0
    return float(np.sqrt(np.mean(audio ** 2)))


def rms_to_db(rms: float) -> float:
    """Convertit un niveau RMS en décibels."""
    if rms <= 0.0:
        return -96.0
    return 20.0 * np.log10(rms)


def is_silent(audio_bytes: bytes, threshold_db: float = -40.0) -> bool:
    """
    Détermine si un segment audio est silencieux.

    Args:
        audio_bytes: Données PCM brutes int16.
        threshold_db: Seuil en dB sous lequel on considère le silence.

    Returns:
        True si le signal est en dessous du seuil.
    """
    if not audio_bytes:
        return True
    audio = bytes_to_float32(audio_bytes)
    rms = calculate_rms(audio)
    return bool(rms_to_db(rms) < threshold_db)


def validate_webrtcvad_chunk(audio_bytes: bytes, sample_rate: int, chunk_ms: int) -> bool:
    """
    Valide qu'un chunk audio est conforme aux exigences de webrtcvad.
    webrtcvad exige exactement 10ms, 20ms ou 30ms à 8000/16000/32000/48000 Hz.

    Args:
        audio_bytes: Données PCM brutes int16.
        sample_rate: Taux d'échantillonnage en Hz.
        chunk_ms: Durée du chunk en millisecondes.

    Returns:
        True si le chunk est valide.
    """
    valid_rates = {8000, 16000, 32000, 48000}
    valid_ms = {10, 20, 30}

    if sample_rate not in valid_rates:
        logger.warning("webrtcvad : taux %d Hz non supporté (valides : %s)", sample_rate, valid_rates)
        return False

    if chunk_ms not in valid_ms:
        logger.warning("webrtcvad : durée %d ms non supportée (valides : %s)", chunk_ms, valid_ms)
        return False

    expected_bytes = int(sample_rate * chunk_ms / 1000) * 2  # int16 = 2 bytes/sample
    if len(audio_bytes) != expected_bytes:
        logger.warning(
            "webrtcvad : taille %d bytes incorrecte (attendu %d pour %dHz/%dms)",
            len(audio_bytes), expected_bytes, sample_rate, chunk_ms,
        )
        return False

    return True


def mono_to_stereo(audio: np.ndarray) -> np.ndarray:
    """Duplique un canal mono en stéréo."""
    return np.stack([audio, audio], axis=1)


def stereo_to_mono(audio: np.ndarray) -> np.ndarray:
    """Mixe les canaux stéréo en mono par moyenne."""
    if audio.ndim == 1:
        return audio
    return audio.mean(axis=1).astype(np.float32)


def chunk_audio(audio_bytes: bytes, chunk_size: int) -> list[bytes]:
    """
    Découpe des bytes audio en chunks de taille fixe.

    Args:
        audio_bytes: Données audio complètes.
        chunk_size: Taille de chaque chunk en bytes.

    Returns:
        Liste de chunks. Le dernier chunk peut être plus petit.
    """
    return [
        audio_bytes[i:i + chunk_size]
        for i in range(0, len(audio_bytes), chunk_size)
    ]
