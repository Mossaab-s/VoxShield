#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VoxShield — Moteur Speech-to-Text.
Transcrit des segments audio en texte via faster-whisper (local) ou OpenAI Whisper API.
"""

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Optional

import numpy as np

from utils.logger import get_logger

logger = get_logger("STT")


@dataclass
class STTResult:
    """Résultat d'une transcription."""

    text: str
    language: str           # Code ISO 639-1 détecté
    confidence: float       # 0.0 à 1.0
    processing_ms: int      # Temps de traitement en ms


class STTEngine:
    """
    Moteur de transcription automatique de la parole.

    Modes disponibles :
    - 'local' : faster-whisper (offline, recommandé)
    - 'api'   : OpenAI Whisper API (requiert clé API et connexion)
    """

    def __init__(
        self,
        mode: Literal["local", "api"] = "local",
        model_size: str = "base",
        language: Optional[str] = None,
        device: str = "cpu",
        compute_type: str = "int8",
        openai_api_key: Optional[str] = None,
        models_dir: Optional[Path] = None,
    ) -> None:
        """
        Args:
            mode: 'local' ou 'api'.
            model_size: Taille du modèle Whisper (tiny/base/small/medium/large-v3).
            language: Code ISO langue source. None = auto-détection.
            device: 'cpu' ou 'cuda'.
            compute_type: 'int8', 'float16' ou 'float32'.
            openai_api_key: Clé API OpenAI (mode 'api' uniquement).
            models_dir: Dossier de stockage des modèles locaux.
        """
        self._mode = mode
        self._model_size = model_size
        self._language = language
        self._device = device
        self._compute_type = compute_type
        self._openai_api_key = openai_api_key
        self._models_dir = models_dir
        self._model = None
        self._ready = False

    # ── Chargement du modèle ─────────────────────────────────────────────────

    def load_model(self) -> None:
        """
        Précharge le modèle en mémoire.
        Doit être appelé au démarrage de l'application, jamais pendant un pipeline actif.
        """
        if self._mode == "local":
            self._load_faster_whisper()
        elif self._mode == "api":
            self._verify_openai_key()
        self._ready = True

    def _load_faster_whisper(self) -> None:
        """Charge le modèle faster-whisper."""
        try:
            from faster_whisper import WhisperModel

            model_path = self._model_size
            if self._models_dir:
                custom_path = self._models_dir / self._model_size
                if custom_path.exists():
                    model_path = str(custom_path)

            logger.info(
                "Chargement faster-whisper '%s' (%s / %s)...",
                self._model_size, self._device, self._compute_type,
            )
            t0 = time.time()
            self._model = WhisperModel(
                model_path,
                device=self._device,
                compute_type=self._compute_type,
            )
            elapsed = (time.time() - t0) * 1000
            logger.info("Modèle Whisper chargé en %.0fms", elapsed)

        except ImportError:
            logger.error("faster-whisper non installé. Installer avec : pip install faster-whisper")
            raise
        except Exception as e:
            logger.error("Erreur chargement modèle Whisper : %s", e)
            raise

    def _verify_openai_key(self) -> None:
        """Vérifie que la clé API OpenAI est configurée."""
        if not self._openai_api_key:
            raise ValueError("Clé API OpenAI requise pour le mode 'api'")
        try:
            import openai  # noqa: F401
            logger.info("Mode STT API OpenAI configuré")
        except ImportError:
            logger.error("openai non installé. Installer avec : pip install openai")
            raise

    def is_ready(self) -> bool:
        """Retourne True si le moteur est prêt à transcrire."""
        return self._ready

    # ── Transcription ─────────────────────────────────────────────────────────

    def transcribe(self, audio_bytes: bytes) -> STTResult:
        """
        Transcrit un segment audio en texte.

        Args:
            audio_bytes: Données PCM int16 mono 16000 Hz.

        Returns:
            STTResult avec le texte, la langue détectée et les métriques.
        """
        if not self._ready:
            logger.warning("STTEngine non initialisé — chargement du modèle...")
            self.load_model()

        if not audio_bytes:
            return STTResult(text="", language=self._language or "fr", confidence=0.0, processing_ms=0)

        t0 = time.time()

        if self._mode == "local":
            result = self._transcribe_local(audio_bytes)
        else:
            result = self._transcribe_api(audio_bytes)

        result.processing_ms = int((time.time() - t0) * 1000)
        logger.info(
            "STT [%s] '%s' (%dms, conf=%.2f)",
            result.language, result.text[:80], result.processing_ms, result.confidence,
        )
        return result

    def _transcribe_local(self, audio_bytes: bytes) -> STTResult:
        """Transcription via faster-whisper."""
        audio_array = _bytes_to_float32(audio_bytes)

        segments, info = self._model.transcribe(
            audio_array,
            language=self._language,
            beam_size=5,
            vad_filter=False,       # VAD géré en amont
            word_timestamps=False,  # Non requis pour la traduction
        )

        text_parts = []
        total_avg_logprob = 0.0
        count = 0
        for seg in segments:
            text_parts.append(seg.text.strip())
            total_avg_logprob += seg.avg_logprob
            count += 1

        text = " ".join(text_parts).strip()

        # Conversion log-probabilité → confiance [0, 1]
        avg_logprob = total_avg_logprob / count if count > 0 else -1.0
        confidence = max(0.0, min(1.0, (avg_logprob + 1.0)))

        return STTResult(
            text=text,
            language=info.language,
            confidence=confidence,
            processing_ms=0,  # Sera calculé par l'appelant
        )

    def _transcribe_api(self, audio_bytes: bytes) -> STTResult:
        """Transcription via OpenAI Whisper API."""
        import io
        import openai

        client = openai.OpenAI(api_key=self._openai_api_key)

        # Encapsuler les bytes en fichier WAV en mémoire
        wav_buffer = _bytes_to_wav_buffer(audio_bytes, sample_rate=16000)

        response = client.audio.transcriptions.create(
            model="whisper-1",
            file=("audio.wav", wav_buffer, "audio/wav"),
            language=self._language,
            response_format="verbose_json",
        )

        return STTResult(
            text=response.text.strip(),
            language=response.language or (self._language or "fr"),
            confidence=0.9,  # L'API ne retourne pas de score de confiance
            processing_ms=0,
        )

    # ── Gestion du modèle ─────────────────────────────────────────────────────

    def set_language(self, language: Optional[str]) -> None:
        """Change la langue source (None = auto-détection)."""
        self._language = language

    def set_model_size(self, model_size: str) -> None:
        """Change la taille du modèle (nécessite un rechargement)."""
        if model_size != self._model_size:
            self._model_size = model_size
            self._ready = False
            self._model = None

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def model_size(self) -> str:
        return self._model_size

    def __repr__(self) -> str:
        return f"STTEngine(mode={self._mode}, model={self._model_size}, lang={self._language})"


# ── Fonctions utilitaires privées ─────────────────────────────────────────────

def _bytes_to_float32(audio_bytes: bytes) -> np.ndarray:
    """Convertit bytes PCM int16 en numpy float32 normalisé pour Whisper."""
    audio = np.frombuffer(audio_bytes, dtype=np.int16)
    return audio.astype(np.float32) / 32768.0


def _bytes_to_wav_buffer(audio_bytes: bytes, sample_rate: int = 16000):
    """Encapsule des bytes PCM int16 mono dans un buffer WAV en mémoire."""
    import io
    import wave

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # int16 = 2 bytes
        wf.setframerate(sample_rate)
        wf.writeframes(audio_bytes)
    buf.seek(0)
    return buf
