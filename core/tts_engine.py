#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VoxShield — Moteur Text-to-Speech.
Supporte Piper TTS (local, haute qualité), OpenAI TTS (API) et pyttsx3 (système, fallback).
"""

import io
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Optional

import numpy as np

from utils.logger import get_logger

logger = get_logger("TTS")

# Taux d'échantillonnage par défaut pour la sortie TTS
DEFAULT_SAMPLE_RATE = 22050


@dataclass
class AudioData:
    """Données audio produites par le TTS."""

    samples: np.ndarray     # float32, normalisé [-1.0, 1.0]
    sample_rate: int        # Hz


@dataclass
class VoiceInfo:
    """Informations sur une voix TTS disponible."""

    voice_id: str
    name: str
    language: str
    engine: str


class TTSEngine:
    """
    Moteur de synthèse vocale multi-moteur.

    Modes :
    - 'piper'  : Piper TTS local (haute qualité, offline)
    - 'openai' : OpenAI TTS API (excellente qualité, connexion requise)
    - 'system' : pyttsx3 (voix OS, qualité basique, toujours disponible)
    """

    def __init__(
        self,
        mode: Literal["piper", "openai", "system"] = "piper",
        language: str = "en",
        voice_id: Optional[str] = None,
        speed: float = 1.0,
        openai_api_key: Optional[str] = None,
        piper_bin_path: Optional[Path] = None,
        models_dir: Optional[Path] = None,
    ) -> None:
        """
        Args:
            mode: Moteur TTS à utiliser.
            language: Code ISO 639-1 de la langue cible.
            voice_id: Identifiant de voix spécifique (facultatif).
            speed: Vitesse de parole (0.5x à 2.0x).
            openai_api_key: Clé API OpenAI (mode 'openai' uniquement).
            piper_bin_path: Chemin vers le binaire piper (détecté automatiquement si None).
            models_dir: Dossier contenant les modèles Piper (.onnx).
        """
        self._mode = mode
        self._language = language
        self._voice_id = voice_id
        self._speed = max(0.5, min(2.0, speed))
        self._openai_api_key = openai_api_key
        self._models_dir = models_dir
        self._piper_bin = self._find_piper_bin(piper_bin_path)

        # Cache du moteur système (pyttsx3)
        self._system_engine = None

    # ── Préchargement ─────────────────────────────────────────────────────────

    def load_model(self) -> None:
        """Alias de preload_model() pour interface uniforme avec STTEngine."""
        self.preload_model()

    def preload_model(self) -> None:
        """
        Précharge le modèle TTS en mémoire.
        Pour Piper : vérifie la présence du modèle et du binaire.
        Pour system : initialise pyttsx3.
        """
        if self._mode == "piper":
            self._verify_piper()
        elif self._mode == "system":
            self._init_pyttsx3()
        elif self._mode == "openai":
            if not self._openai_api_key:
                logger.warning("Clé API OpenAI non configurée pour TTS")
        logger.info("TTS prêt (mode=%s, lang=%s)", self._mode, self._language)

    def _verify_piper(self) -> None:
        """Vérifie que le binaire piper et le modèle .onnx sont disponibles."""
        if not self._piper_bin or not self._piper_bin.exists():
            logger.warning(
                "Binaire piper introuvable. Installer depuis https://github.com/rhasspy/piper"
            )
            return

        model_path = self._get_piper_model_path()
        if not model_path or not model_path.exists():
            logger.warning(
                "Modèle Piper pour '%s' introuvable dans %s", self._language, self._models_dir
            )

    def _init_pyttsx3(self) -> None:
        """Initialise le moteur pyttsx3 (TTS système)."""
        try:
            import pyttsx3
            self._system_engine = pyttsx3.init()
            self._system_engine.setProperty("rate", int(200 * self._speed))
            logger.info("pyttsx3 initialisé")
        except Exception as e:
            logger.error("Impossible d'initialiser pyttsx3 : %s", e)

    # ── Synthèse vocale ───────────────────────────────────────────────────────

    def synthesize(self, text: str) -> AudioData:
        """
        Synthétise le texte en audio.

        Args:
            text: Texte à synthétiser dans la langue configurée.

        Returns:
            AudioData avec les samples float32 et le taux d'échantillonnage.
        """
        if not text.strip():
            return AudioData(samples=np.array([], dtype=np.float32), sample_rate=DEFAULT_SAMPLE_RATE)

        t0 = time.time()

        if self._mode == "piper":
            result = self._synthesize_piper(text)
        elif self._mode == "openai":
            result = self._synthesize_openai(text)
        else:
            result = self._synthesize_system(text)

        elapsed = int((time.time() - t0) * 1000)
        logger.info("TTS [%s] '%s...' → %d samples (%dms)", self._language, text[:40], len(result.samples), elapsed)
        return result

    def _synthesize_piper(self, text: str) -> AudioData:
        """Synthèse via le binaire Piper TTS (subprocess)."""
        model_path = self._get_piper_model_path()

        if not model_path or not model_path.exists():
            logger.warning("Modèle Piper absent — fallback système")
            return self._synthesize_system(text)

        if not self._piper_bin or not self._piper_bin.exists():
            logger.warning("Binaire piper absent — fallback système")
            return self._synthesize_system(text)

        try:
            cmd = [
                str(self._piper_bin),
                "--model", str(model_path),
                "--output_raw",
                "--length_scale", str(1.0 / self._speed),
            ]
            result = subprocess.run(
                cmd,
                input=text.encode("utf-8"),
                capture_output=True,
                timeout=10,
            )

            if result.returncode != 0:
                logger.error("piper erreur : %s", result.stderr.decode(errors="replace"))
                return self._synthesize_system(text)

            # Piper produit du PCM int16 raw
            audio_int16 = np.frombuffer(result.stdout, dtype=np.int16)
            audio_float = audio_int16.astype(np.float32) / 32768.0

            sample_rate = self._get_piper_sample_rate()
            return AudioData(samples=audio_float, sample_rate=sample_rate)

        except subprocess.TimeoutExpired:
            logger.error("piper timeout — fallback système")
            return self._synthesize_system(text)
        except Exception as e:
            logger.error("Erreur piper : %s", e)
            return self._synthesize_system(text)

    def _synthesize_openai(self, text: str) -> AudioData:
        """Synthèse via OpenAI TTS API."""
        try:
            import openai
            from config.language_registry import LANGUAGE_REGISTRY

            client = openai.OpenAI(api_key=self._openai_api_key)
            voice = self._voice_id or LANGUAGE_REGISTRY.get(self._language, {}).get("openai_voice", "nova")

            response = client.audio.speech.create(
                model="tts-1",
                voice=voice,
                input=text,
                speed=self._speed,
                response_format="pcm",  # PCM 24kHz int16
            )

            audio_bytes = response.content
            audio_int16 = np.frombuffer(audio_bytes, dtype=np.int16)
            audio_float = audio_int16.astype(np.float32) / 32768.0

            return AudioData(samples=audio_float, sample_rate=24000)

        except Exception as e:
            logger.error("OpenAI TTS échoué : %s — fallback système", e)
            return self._synthesize_system(text)

    def _synthesize_system(self, text: str) -> AudioData:
        """Synthèse via pyttsx3 (voix OS, fallback d'urgence)."""
        try:
            import pyttsx3
            import wave
            import tempfile

            if self._system_engine is None:
                self._init_pyttsx3()

            if self._system_engine is None:
                logger.error("pyttsx3 non disponible")
                return AudioData(samples=np.array([], dtype=np.float32), sample_rate=DEFAULT_SAMPLE_RATE)

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp_path = tmp.name

            self._system_engine.save_to_file(text, tmp_path)
            self._system_engine.runAndWait()

            # Lire le WAV produit
            with wave.open(tmp_path, "rb") as wf:
                sr = wf.getframerate()
                raw = wf.readframes(wf.getnframes())

            import os
            os.unlink(tmp_path)

            audio_int16 = np.frombuffer(raw, dtype=np.int16)
            audio_float = audio_int16.astype(np.float32) / 32768.0
            return AudioData(samples=audio_float, sample_rate=sr)

        except Exception as e:
            logger.error("pyttsx3 échoué : %s", e)
            return AudioData(samples=np.array([], dtype=np.float32), sample_rate=DEFAULT_SAMPLE_RATE)

    # ── Voix disponibles ──────────────────────────────────────────────────────

    def list_voices(self, language: str) -> list[VoiceInfo]:
        """Liste les voix disponibles pour une langue."""
        voices = []

        # Voix Piper
        if self._models_dir:
            for onnx_file in Path(self._models_dir).glob(f"{language}_*.onnx"):
                voices.append(VoiceInfo(
                    voice_id=onnx_file.stem,
                    name=onnx_file.stem,
                    language=language,
                    engine="piper",
                ))

        # Voix système (pyttsx3)
        try:
            import pyttsx3
            engine = pyttsx3.init()
            for v in engine.getProperty("voices"):
                if language.lower() in v.languages[0].lower() if v.languages else False:
                    voices.append(VoiceInfo(
                        voice_id=v.id,
                        name=v.name,
                        language=language,
                        engine="system",
                    ))
            engine.stop()
        except Exception:
            pass

        return voices

    # ── Helpers privés ────────────────────────────────────────────────────────

    def _get_piper_model_path(self) -> Optional[Path]:
        """Retourne le chemin du modèle Piper pour la langue actuelle."""
        if not self._models_dir:
            return None

        from config.language_registry import get_piper_model
        model_name = self._voice_id or get_piper_model(self._language)
        if not model_name:
            return None

        path = Path(self._models_dir) / f"{model_name}.onnx"
        return path

    def _get_piper_sample_rate(self) -> int:
        """Retourne le taux d'échantillonnage du modèle Piper actuel."""
        from config.language_registry import LANGUAGE_REGISTRY
        return LANGUAGE_REGISTRY.get(self._language, {}).get("piper_sample_rate", DEFAULT_SAMPLE_RATE)

    @staticmethod
    def _find_piper_bin(custom_path: Optional[Path]) -> Optional[Path]:
        """Cherche le binaire piper dans les emplacements standards."""
        if custom_path and Path(custom_path).exists():
            return Path(custom_path)

        import shutil
        found = shutil.which("piper")
        if found:
            return Path(found)

        # Emplacements courants
        candidates = [
            Path.home() / ".local" / "bin" / "piper",
            Path("C:/Program Files/piper/piper.exe"),
            Path("/usr/local/bin/piper"),
        ]
        for c in candidates:
            if c.exists():
                return c

        return None

    # ── Configuration dynamique ───────────────────────────────────────────────

    def set_language(self, language: str) -> None:
        """Change la langue cible TTS."""
        self._language = language

    def set_speed(self, speed: float) -> None:
        """Change la vitesse de parole."""
        self._speed = max(0.5, min(2.0, speed))
        if self._system_engine:
            self._system_engine.setProperty("rate", int(200 * self._speed))

    def set_mode(self, mode: Literal["piper", "openai", "system"]) -> None:
        """Change le moteur TTS."""
        self._mode = mode

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def language(self) -> str:
        return self._language

    def __repr__(self) -> str:
        return f"TTSEngine(mode={self._mode}, lang={self._language}, speed={self._speed}x)"
