#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VoxShield — Voice Activity Detection (VAD).
Détecte les segments de parole et déclenche le flush vers le STT.
Supporte webrtcvad (léger) et Silero VAD (précis).
"""

import threading
from dataclasses import dataclass, field
from typing import Optional

from core.audio_buffer import AudioBuffer
from utils.audio_utils import validate_webrtcvad_chunk
from utils.logger import get_logger

logger = get_logger("VAD")

# Durée maximale du buffer avant flush forcé
MAX_BUFFER_MS = 15_000


@dataclass
class VADResult:
    """Résultat d'analyse VAD pour un chunk audio."""

    is_speech: bool
    should_flush: bool  # True = envoyer le buffer au STT
    audio_segment: bytes  # Segment complet si flush, sinon b""


class VADEngine:
    """
    Moteur de détection d'activité vocale avec segmentation automatique.

    Algorithme :
    - Accumule les chunks audio dans un buffer interne.
    - Détecte la parole via webrtcvad ou Silero VAD.
    - Flush le buffer quand N frames de silence consécutives sont détectées.
    - Flush forcé si le buffer dépasse 15 secondes.
    - Inclut min_pre_speech_ms de contexte pré-parole pour ne pas couper le début.
    """

    def __init__(
        self,
        mode: int = 2,
        sample_rate: int = 16000,
        chunk_ms: int = 30,
        min_speech_ms: int = 250,
        max_silence_ms: int = 800,
        pre_speech_ms: int = 200,
        backend: str = "webrtcvad",
    ) -> None:
        """
        Args:
            mode: Agressivité VAD 0-3 (0=permissif, 3=strict).
            sample_rate: Taux d'échantillonnage en Hz.
            chunk_ms: Durée de chaque chunk en ms (10/20/30 pour webrtcvad).
            min_speech_ms: Durée minimale de parole pour déclencher le flush.
            max_silence_ms: Durée de silence consécutif avant flush.
            pre_speech_ms: Contexte audio inclus avant le début de la parole.
            backend: 'webrtcvad' ou 'silero'.
        """
        self._mode = mode
        self._sample_rate = sample_rate
        self._chunk_ms = chunk_ms
        self._min_speech_ms = min_speech_ms
        self._max_silence_ms = max_silence_ms
        self._pre_speech_ms = pre_speech_ms
        self._backend = backend

        # Calcul en frames
        self._silence_frames_threshold = max(1, max_silence_ms // chunk_ms)
        self._min_speech_frames = max(1, min_speech_ms // chunk_ms)

        # État interne
        self._buffer = AudioBuffer(sample_rate=sample_rate, max_duration_ms=MAX_BUFFER_MS)
        self._pre_buffer: list[bytes] = []  # Fenêtre glissante pré-speech
        self._pre_buffer_max = max(1, pre_speech_ms // chunk_ms)
        self._silence_frames = 0
        self._speech_frames = 0
        self._in_speech = False
        self._lock = threading.Lock()

        # Initialiser le backend VAD
        self._vad = self._init_backend()

    # ── Initialisation ────────────────────────────────────────────────────────

    def _init_backend(self):
        if self._backend == "webrtcvad":
            return self._init_webrtcvad()
        elif self._backend == "silero":
            return self._init_silero()
        else:
            logger.warning("Backend VAD inconnu '%s' — fallback webrtcvad", self._backend)
            self._backend = "webrtcvad"
            return self._init_webrtcvad()

    def _init_webrtcvad(self):
        try:
            import webrtcvad
            vad = webrtcvad.Vad(self._mode)
            logger.info("webrtcvad initialisé (mode=%d)", self._mode)
            return vad
        except ImportError:
            logger.warning("webrtcvad non installé — VAD désactivé (tout sera considéré comme parole)")
            return None

    def _init_silero(self):
        try:
            import torch
            model, utils = torch.hub.load(
                repo_or_dir="snakers4/silero-vad",
                model="silero_vad",
                force_reload=False,
            )
            logger.info("Silero VAD initialisé")
            return {"model": model, "utils": utils}
        except Exception as e:
            logger.warning("Silero VAD non disponible (%s) — fallback webrtcvad", e)
            self._backend = "webrtcvad"
            return self._init_webrtcvad()

    # ── Traitement principal ──────────────────────────────────────────────────

    def process_chunk(self, audio_bytes: bytes) -> VADResult:
        """
        Analyse un chunk audio et détermine si un flush vers le STT est nécessaire.

        Args:
            audio_bytes: Chunk PCM int16 mono de durée chunk_ms.

        Returns:
            VADResult avec is_speech, should_flush et audio_segment.
        """
        with self._lock:
            is_speech = self._detect_speech(audio_bytes)

            if is_speech:
                self._silence_frames = 0
                self._speech_frames += 1
                if not self._in_speech:
                    # Début de parole détecté — inclure le contexte pré-speech
                    self._in_speech = True
                    for pre_chunk in self._pre_buffer:
                        self._buffer.push(pre_chunk)
                    self._pre_buffer.clear()
                self._buffer.push(audio_bytes)

            else:
                # Mise à jour de la fenêtre glissante pré-speech
                self._pre_buffer.append(audio_bytes)
                if len(self._pre_buffer) > self._pre_buffer_max:
                    self._pre_buffer.pop(0)

                if self._in_speech:
                    self._silence_frames += 1
                    self._buffer.push(audio_bytes)

                    # Flush si assez de silence et assez de parole accumulée
                    silence_reached = self._silence_frames >= self._silence_frames_threshold
                    speech_reached = self._speech_frames >= self._min_speech_frames

                    if silence_reached and speech_reached:
                        return self._do_flush(is_speech=False)

            # Flush forcé si buffer trop long
            if self._buffer.should_force_flush():
                logger.warning("Flush forcé — buffer > %dms", MAX_BUFFER_MS)
                return self._do_flush(is_speech=is_speech)

            return VADResult(is_speech=is_speech, should_flush=False, audio_segment=b"")

    def _do_flush(self, is_speech: bool) -> VADResult:
        """Vide le buffer et réinitialise l'état."""
        segment = self._buffer.flush()
        self._in_speech = False
        self._silence_frames = 0
        self._speech_frames = 0
        self._pre_buffer.clear()
        logger.debug("Flush VAD — segment de %d bytes (%.1fs)", len(segment), len(segment) / (self._sample_rate * 2))
        return VADResult(is_speech=is_speech, should_flush=True, audio_segment=segment)

    def _detect_speech(self, audio_bytes: bytes) -> bool:
        """Détecte si le chunk contient de la parole."""
        if self._vad is None:
            return True  # Pas de VAD = tout passe

        if self._backend == "webrtcvad":
            return self._detect_webrtcvad(audio_bytes)
        elif self._backend == "silero":
            return self._detect_silero(audio_bytes)
        return True

    def _detect_webrtcvad(self, audio_bytes: bytes) -> bool:
        """Détection via webrtcvad."""
        if not validate_webrtcvad_chunk(audio_bytes, self._sample_rate, self._chunk_ms):
            return False
        try:
            return self._vad.is_speech(audio_bytes, self._sample_rate)
        except Exception as e:
            logger.debug("webrtcvad erreur : %s", e)
            return False

    def _detect_silero(self, audio_bytes: bytes) -> bool:
        """Détection via Silero VAD."""
        try:
            import torch
            import numpy as np
            audio = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
            tensor = torch.from_numpy(audio)
            confidence = self._vad["model"](tensor, self._sample_rate).item()
            return confidence > 0.5
        except Exception as e:
            logger.debug("Silero VAD erreur : %s", e)
            return False

    # ── Contrôle ──────────────────────────────────────────────────────────────

    def reset(self) -> None:
        """Réinitialise l'état interne du VAD (à appeler lors d'un stop)."""
        with self._lock:
            self._buffer.clear()
            self._pre_buffer.clear()
            self._silence_frames = 0
            self._speech_frames = 0
            self._in_speech = False

    def flush_remaining(self) -> Optional[bytes]:
        """
        Flush le buffer restant même sans silence suffisant.
        Utile à l'arrêt du pipeline pour ne pas perdre la dernière phrase.
        """
        with self._lock:
            if self._buffer.is_empty() or self._speech_frames < self._min_speech_frames:
                self._buffer.clear()
                return None
            segment = self._buffer.flush()
            self._in_speech = False
            self._silence_frames = 0
            self._speech_frames = 0
            return segment

    @property
    def backend(self) -> str:
        return self._backend

    @property
    def in_speech(self) -> bool:
        return self._in_speech

    def __repr__(self) -> str:
        return (
            f"VADEngine(backend={self._backend}, mode={self._mode}, "
            f"silence_threshold={self._max_silence_ms}ms)"
        )
