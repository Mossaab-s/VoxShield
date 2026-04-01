#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VoxShield — Routage audio vers le Virtual Cable.
Injecte l'audio TTS dans le peripherique virtuel pour qu'il soit
capturé par l'application de visioconférence.
"""

import time
from typing import Optional

import numpy as np
import sounddevice as sd

from utils.logger import get_logger
from utils.platform_utils import get_os, get_virtual_cable_install_info

logger = get_logger("ROUTE")


class VirtualAudioRouter:
    """
    Route l'audio synthétisé vers un peripherique Virtual Cable.

    Sur Windows : VB-Audio Virtual Cable (CABLE Input)
    Sur macOS   : BlackHole 2ch
    """

    def __init__(self, device_name_pattern: str = "CABLE Input") -> None:
        """
        Args:
            device_name_pattern: Motif de nom du peripherique virtuel à utiliser.
        """
        self._device_name_pattern = device_name_pattern
        self._device_index: Optional[int] = None
        self._device_info: Optional[dict] = None
        self._detect()

    # ── Détection ─────────────────────────────────────────────────────────────

    def _detect(self) -> None:
        """Détecte le Virtual Cable dans la liste des peripheriques audio."""
        from config.default_settings import VIRTUAL_CABLE_PATTERNS
        os_name = get_os()
        patterns = VIRTUAL_CABLE_PATTERNS.get(os_name, [self._device_name_pattern])

        try:
            for i, dev in enumerate(sd.query_devices()):
                name: str = dev.get("name", "")
                max_out = dev.get("max_output_channels", 0)
                if max_out > 0:
                    for pattern in patterns:
                        if pattern.lower() in name.lower():
                            self._device_index = i
                            self._device_info = dev
                            logger.info(
                                "Virtual Cable detecte : '%s' (index=%d, %d canaux out)",
                                name, i, max_out,
                            )
                            return
        except Exception as e:
            logger.error("Erreur detection Virtual Cable : %s", e)

        logger.warning("Aucun Virtual Cable introuvable — Pipeline A désactivé")

    def detect_virtual_cable(self) -> Optional[int]:
        """
        Relance la detection et retourne l'index du peripherique ou None.
        Utile après installation du Virtual Cable.
        """
        self._detect()
        return self._device_index

    def is_available(self) -> bool:
        """Retourne True si un Virtual Cable est disponible."""
        return self._device_index is not None

    def list_virtual_devices(self) -> list[dict]:
        """Liste tous les peripheriques de sortie pouvant servir de Virtual Cable."""
        from config.default_settings import VIRTUAL_CABLE_PATTERNS
        os_name = get_os()
        patterns = VIRTUAL_CABLE_PATTERNS.get(os_name, [])

        devices = []
        try:
            for i, dev in enumerate(sd.query_devices()):
                name: str = dev.get("name", "")
                if dev.get("max_output_channels", 0) > 0:
                    for pattern in patterns:
                        if pattern.lower() in name.lower():
                            devices.append({
                                "index": i,
                                "name": name,
                                "max_output_channels": dev["max_output_channels"],
                                "default_samplerate": int(dev["default_samplerate"]),
                            })
                            break
        except Exception as e:
            logger.error("Erreur liste Virtual Devices : %s", e)
        return devices

    # ── Routage audio ─────────────────────────────────────────────────────────

    def route_audio(self, audio_data: np.ndarray, sample_rate: int) -> None:
        """
        Joue l'audio sur le Virtual Cable (l'application de visio le capturera comme micro).

        Args:
            audio_data: Tableau float32 normalisé [-1.0, 1.0].
            sample_rate: Taux d'échantillonnage de l'audio.
        """
        if not self.is_available():
            logger.warning("Virtual Cable indisponible — audio non routé")
            return

        if len(audio_data) == 0:
            return

        try:
            # Assurer que l'audio est float32 et clipé proprement
            audio = np.clip(audio_data.astype(np.float32), -1.0, 1.0)

            # S'assurer que l'audio est mono (1D)
            if audio.ndim > 1:
                audio = audio.mean(axis=1)

            # Rééchantillonner si nécessaire
            dev_sr = int(self._device_info.get("default_samplerate", sample_rate))
            if sample_rate != dev_sr:
                audio = _resample(audio, sample_rate, dev_sr)
                sample_rate = dev_sr

            sd.play(
                audio,
                samplerate=sample_rate,
                device=self._device_index,
                blocking=False,  # Non bloquant pour ne pas geler le pipeline
            )
            logger.debug(
                "Audio routé vers '%s' — %.2fs @ %dHz",
                self._device_info.get("name", "?"),
                len(audio) / sample_rate,
                sample_rate,
            )

        except sd.PortAudioError as e:
            logger.error("Erreur PortAudio lors du routage : %s", e)
        except Exception as e:
            logger.error("Erreur routage audio : %s", e)

    def wait_until_done(self, timeout_s: float = 30.0) -> None:
        """Attend que la lecture en cours soit terminée."""
        sd.wait()

    # ── Test ──────────────────────────────────────────────────────────────────

    def test_routing(self) -> bool:
        """
        Joue un bip de test sur le Virtual Cable pour vérifier le routage.

        Returns:
            True si le test a réussi.
        """
        if not self.is_available():
            logger.warning("Impossible de tester : Virtual Cable non disponible")
            return False

        try:
            # Générer un bip 440 Hz (La) d'une durée de 0.3 secondes
            sample_rate = 22050
            duration = 0.3
            t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
            bip = (0.3 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)

            # Envelope fade-in/out pour éviter les clics
            fade = int(sample_rate * 0.02)
            bip[:fade] *= np.linspace(0, 1, fade)
            bip[-fade:] *= np.linspace(1, 0, fade)

            self.route_audio(bip, sample_rate)
            time.sleep(duration + 0.1)
            logger.info("Test routage Virtual Cable : OK")
            return True

        except Exception as e:
            logger.error("Test routage échoué : %s", e)
            return False

    # ── Infos ─────────────────────────────────────────────────────────────────

    def get_install_guide(self) -> dict:
        """Retourne le guide d'installation du Virtual Cable pour l'OS actuel."""
        return get_virtual_cable_install_info()

    def set_device_by_index(self, index: int) -> None:
        """Change manuellement le peripherique de sortie Virtual Cable."""
        try:
            dev = sd.query_devices(index)
            if dev.get("max_output_channels", 0) > 0:
                self._device_index = index
                self._device_info = dev
                logger.info("Virtual Cable manuel : '%s' (index=%d)", dev["name"], index)
            else:
                logger.warning("Le peripherique %d n'a pas de canaux de sortie", index)
        except Exception as e:
            logger.error("Périphérique %d invalide : %s", index, e)

    @property
    def device_index(self) -> Optional[int]:
        return self._device_index

    @property
    def device_name(self) -> Optional[str]:
        if self._device_info:
            return self._device_info.get("name")
        return None

    def __repr__(self) -> str:
        return (
            f"VirtualAudioRouter(device='{self.device_name}', "
            f"index={self._device_index}, available={self.is_available()})"
        )


# ── Utilitaires privés ────────────────────────────────────────────────────────

def _resample(audio: np.ndarray, orig_rate: int, target_rate: int) -> np.ndarray:
    """Rééchantillonne un signal audio."""
    if orig_rate == target_rate:
        return audio
    try:
        from scipy.signal import resample_poly
        from math import gcd
        g = gcd(orig_rate, target_rate)
        return resample_poly(audio, target_rate // g, orig_rate // g).astype(np.float32)
    except Exception as e:
        logger.warning("Rééchantillonnage échoué : %s", e)
        return audio
