#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VoxShield — Module de capture audio.
Capture microphone (Pipeline A) et loopback système (Pipeline B).
Utilise sounddevice (cross-platform) et PyAudioWPatch (loopback Windows).
"""

import sys
import threading
import time
from typing import Callable, Optional

import numpy as np
import sounddevice as sd

from utils.logger import get_logger

logger = get_logger("AUDIO")

# Nombre de tentatives de reconnexion automatique
MAX_RETRIES = 3
RETRY_DELAY_S = 0.5


class AudioCapture:
    """
    Capture audio depuis un périphérique d'entrée (microphone ou loopback).

    Le callback reçoit des bytes PCM bruts int16 mono 16000 Hz,
    en chunks de chunk_ms millisecondes.
    """

    def __init__(
        self,
        device_index: Optional[int],
        sample_rate: int = 16000,
        channels: int = 1,
        chunk_ms: int = 30,
        loopback: bool = False,
    ) -> None:
        """
        Args:
            device_index: Index sounddevice du périphérique. None = défaut système.
            sample_rate: Taux d'échantillonnage en Hz (16000 recommandé pour Whisper).
            channels: Nombre de canaux (1 = mono).
            chunk_ms: Durée de chaque chunk en millisecondes (10/20/30 pour webrtcvad).
            loopback: True pour activer la capture loopback (Windows WASAPI).
        """
        self._device_index = device_index
        self._sample_rate = sample_rate
        self._channels = channels
        self._chunk_ms = chunk_ms
        self._loopback = loopback

        self._chunk_frames = int(sample_rate * chunk_ms / 1000)
        self._callback: Optional[Callable[[bytes], None]] = None
        self._stream = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._lock = threading.Lock()

        # Actual rate used by the open stream (may differ from _sample_rate)
        self._native_rate: int = sample_rate
        self._native_chunk_frames: int = self._chunk_frames

    # ── Méthodes statiques de découverte ─────────────────────────────────────

    @staticmethod
    def list_input_devices() -> list[dict]:
        """
        Liste tous les périphériques d'entrée audio disponibles.

        Returns:
            Liste de dicts avec 'index', 'name', 'max_input_channels', 'default_samplerate'.
        """
        devices = []
        try:
            for i, dev in enumerate(sd.query_devices()):
                if dev.get("max_input_channels", 0) > 0:
                    devices.append({
                        "index": i,
                        "name": dev["name"],
                        "max_input_channels": dev["max_input_channels"],
                        "default_samplerate": int(dev["default_samplerate"]),
                    })
        except Exception as e:
            logger.error("Erreur lors de la liste des périphériques : %s", e)
        return devices

    @staticmethod
    def list_loopback_devices() -> list[dict]:
        """
        Liste les périphériques loopback disponibles.
        Sur Windows : utilise PyAudioWPatch si disponible.
        Sur macOS/Linux : filtre par nom (BlackHole, Soundflower, monitor...).

        Returns:
            Liste de dicts avec 'index', 'name', 'api'.
        """
        devices = []

        if sys.platform == "win32":
            devices = _list_loopback_windows()
        else:
            # macOS / Linux : filtrer les devices avec des noms de loopback connus
            patterns = ["blackhole", "soundflower", "monitor", "loopback"]
            try:
                for i, dev in enumerate(sd.query_devices()):
                    name_lower = dev.get("name", "").lower()
                    if dev.get("max_input_channels", 0) > 0:
                        if any(p in name_lower for p in patterns):
                            devices.append({
                                "index": i,
                                "name": dev["name"],
                                "api": "sounddevice",
                            })
            except Exception as e:
                logger.error("Erreur liste loopback : %s", e)

        return devices

    # ── Contrôle de la capture ────────────────────────────────────────────────

    def start(self, callback: Callable[[bytes], None]) -> None:
        """
        Démarre la capture audio dans un thread dédié.

        Args:
            callback: Fonction appelée pour chaque chunk audio (bytes PCM).
        """
        with self._lock:
            if self._running:
                logger.warning("AudioCapture déjà en cours")
                return
            self._callback = callback
            self._running = True

        self._thread = threading.Thread(
            target=self._capture_loop,
            name="AudioCapture",
            daemon=True,
        )
        self._thread.start()
        logger.info(
            "Capture démarrée — device=%s, %dHz, %dch, %dms chunks, loopback=%s",
            self._device_index, self._sample_rate, self._channels,
            self._chunk_ms, self._loopback,
        )

    def stop(self) -> None:
        """Arrête la capture audio."""
        with self._lock:
            self._running = False

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)

        self._close_stream()
        logger.info("Capture arrêtée")

    def is_running(self) -> bool:
        """Retourne True si la capture est active."""
        return self._running

    # ── Boucle interne ────────────────────────────────────────────────────────

    def _capture_loop(self) -> None:
        """Boucle principale de capture avec retry automatique."""
        retries = 0
        while self._running:
            try:
                self._open_stream()
                retries = 0  # Reset si succès
                self._stream.start()

                while self._running:
                    raw_data, overflowed = self._stream.read(self._native_chunk_frames)
                    if overflowed:
                        logger.debug("Overflow audio détecté")
                    if self._callback and self._running:
                        pcm = bytes(raw_data)
                        if self._native_rate != self._sample_rate:
                            pcm = _resample_pcm(pcm, self._native_rate, self._sample_rate)
                        self._callback(pcm)

            except sd.PortAudioError as e:
                logger.error("Erreur PortAudio : %s", e)
                self._close_stream()
                retries += 1
                if retries >= MAX_RETRIES:
                    logger.error("Trop d'erreurs consécutives — capture arrêtée")
                    self._running = False
                    break
                logger.info("Nouvelle tentative %d/%d dans %.1fs...", retries, MAX_RETRIES, RETRY_DELAY_S)
                time.sleep(RETRY_DELAY_S)

            except Exception as e:
                logger.error("Erreur inattendue dans la capture : %s", e)
                self._close_stream()
                self._running = False
                break

    def _open_stream(self) -> None:
        """Ouvre le stream audio selon la configuration."""
        if self._loopback and sys.platform == "win32":
            # For loopback: PyAudioWPatch detects its own native rate internally
            stream, native_rate = _open_wasapi_loopback(
                device_index=self._device_index,
                chunk_ms=self._chunk_ms,
            )
            self._stream = stream
            self._native_rate = native_rate
            self._native_chunk_frames = int(native_rate * self._chunk_ms / 1000)
            if native_rate != self._sample_rate:
                logger.info(
                    "Loopback natif a %dHz, cible %dHz — rééchantillonnage actif",
                    native_rate, self._sample_rate,
                )
        else:
            # For mic: detect native rate, open at native rate, fall back if WDM-KS
            native_rate = _get_device_native_rate(self._device_index, self._sample_rate)
            self._native_rate = native_rate
            self._native_chunk_frames = int(native_rate * self._chunk_ms / 1000)

            if native_rate != self._sample_rate:
                logger.info(
                    "Periph natif a %dHz, cible %dHz — rééchantillonnage actif",
                    native_rate, self._sample_rate,
                )

            try:
                self._stream = sd.RawInputStream(
                    device=self._device_index,
                    samplerate=self._native_rate,
                    channels=self._channels,
                    dtype="int16",
                    blocksize=self._native_chunk_frames,
                )
            except sd.PortAudioError as e:
                # WDM-KS doesn't support blocking reads — try WASAPI default input
                if "-9999" in str(e) or "WDM-KS" in str(e) or "Blocking" in str(e):
                    logger.warning(
                        "WDM-KS non supporté (device=%s) — fallback WASAPI par défaut",
                        self._device_index,
                    )
                    wasapi_dev = _find_wasapi_default_input()
                    self._native_rate = _get_device_native_rate(wasapi_dev, self._sample_rate)
                    self._native_chunk_frames = int(self._native_rate * self._chunk_ms / 1000)
                    if self._native_rate != self._sample_rate:
                        logger.info(
                            "WASAPI natif a %dHz, cible %dHz — rééchantillonnage actif",
                            self._native_rate, self._sample_rate,
                        )
                    self._stream = sd.RawInputStream(
                        device=wasapi_dev,
                        samplerate=self._native_rate,
                        channels=self._channels,
                        dtype="int16",
                        blocksize=self._native_chunk_frames,
                    )
                else:
                    raise

    def _close_stream(self) -> None:
        """Ferme le stream audio proprement."""
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception as e:
                logger.debug("Erreur à la fermeture du stream : %s", e)
            finally:
                self._stream = None

    @property
    def device_index(self) -> Optional[int]:
        return self._device_index

    @device_index.setter
    def device_index(self, index: Optional[int]) -> None:
        """Change le périphérique (prend effet au prochain start)."""
        self._device_index = index


# ── Helpers audio ─────────────────────────────────────────────────────────────

def _get_device_native_rate(device_index: Optional[int], fallback: int) -> int:
    """Retourne le taux d'échantillonnage natif d'un périphérique sounddevice."""
    try:
        if device_index is not None:
            dev_info = sd.query_devices(device_index)
        else:
            dev_info = sd.query_devices(kind="input")
        return int(dev_info.get("default_samplerate", fallback))
    except Exception as e:
        logger.warning("Impossible de détecter le taux natif : %s", e)
        return fallback


def _find_wasapi_default_input() -> Optional[int]:
    """
    Trouve le périphérique d'entrée par défaut sur l'API WASAPI.
    Retourne None si WASAPI n'est pas disponible (fallback sur le défaut système).
    """
    try:
        hostapis = sd.query_hostapis()
        wasapi_idx = next(
            (i for i, api in enumerate(hostapis) if "WASAPI" in api.get("name", "")),
            None,
        )
        if wasapi_idx is None:
            return None

        wasapi_api = hostapis[wasapi_idx]
        default_input = wasapi_api.get("default_input_device", -1)
        if default_input >= 0:
            return default_input

        # Parcourir les devices et trouver le premier input WASAPI
        for i, dev in enumerate(sd.query_devices()):
            if dev.get("hostapi") == wasapi_idx and dev.get("max_input_channels", 0) > 0:
                return i
    except Exception as e:
        logger.warning("Impossible de trouver le device WASAPI : %s", e)
    return None


def _resample_pcm(pcm_bytes: bytes, orig_rate: int, target_rate: int) -> bytes:
    """Rééchantillonne des données PCM int16 de orig_rate vers target_rate."""
    if orig_rate == target_rate:
        return pcm_bytes
    try:
        from math import gcd
        from scipy.signal import resample_poly
        audio = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32)
        g = gcd(orig_rate, target_rate)
        resampled = resample_poly(audio, target_rate // g, orig_rate // g)
        return resampled.astype(np.int16).tobytes()
    except Exception as e:
        logger.warning("Rééchantillonnage échoué : %s — données brutes transmises", e)
        return pcm_bytes


# ── Fonctions privées Windows (loopback WASAPI) ───────────────────────────────

def _list_loopback_windows() -> list[dict]:
    """Liste les périphériques loopback via PyAudioWPatch (Windows uniquement)."""
    try:
        import pyaudiowpatch as pyaudio
        pa = pyaudio.PyAudio()
        devices = []
        try:
            wasapi_info = pa.get_host_api_info_by_type(pyaudio.paWASAPI)
            for i in range(wasapi_info["deviceCount"]):
                dev_info = pa.get_device_info_by_host_api_device_index(
                    wasapi_info["index"], i
                )
                if dev_info.get("isLoopbackDevice", False):
                    devices.append({
                        "index": dev_info["index"],
                        "name": dev_info["name"],
                        "api": "PyAudioWPatch/WASAPI",
                    })
        finally:
            pa.terminate()
        return devices
    except ImportError:
        logger.warning("PyAudioWPatch non installé — loopback Windows indisponible")
        return []
    except Exception as e:
        logger.error("Erreur loopback Windows : %s", e)
        return []


def _open_wasapi_loopback(
    device_index: Optional[int],
    chunk_ms: int,
) -> tuple:
    """
    Ouvre un stream loopback WASAPI via PyAudioWPatch.

    Returns:
        (stream, actual_sample_rate) — stream compatible read()/start()/stop()/close()
        et le taux d'échantillonnage réellement utilisé.
    """
    try:
        import pyaudiowpatch as pyaudio
        stream = _PyAudioWPatchStream(device_index, chunk_ms, pyaudio)
        return stream, stream.actual_sample_rate
    except ImportError:
        logger.warning("PyAudioWPatch absent — fallback sur sounddevice standard")
        native_rate = _get_device_native_rate(device_index, 44100)
        chunk_frames = int(native_rate * chunk_ms / 1000)
        stream = sd.RawInputStream(
            device=device_index,
            samplerate=native_rate,
            channels=1,
            dtype="int16",
            blocksize=chunk_frames,
        )
        return stream, native_rate


class _PyAudioWPatchStream:
    """Adaptateur PyAudioWPatch avec interface compatible sounddevice.RawInputStream."""

    def __init__(
        self,
        device_index: Optional[int],
        chunk_ms: int,
        pyaudio_module,
    ) -> None:
        self._pa = pyaudio_module.PyAudio()
        self._stream = None

        wasapi_info = self._pa.get_host_api_info_by_type(pyaudio_module.paWASAPI)

        if device_index is None:
            # Utiliser le périphérique de sortie par défaut en mode loopback
            default_out = self._pa.get_default_output_device_info()
            device_index = default_out["index"]

        dev_info = self._pa.get_device_info_by_index(device_index)
        if not dev_info.get("isLoopbackDevice", False):
            # Chercher la version loopback correspondante
            for i in range(wasapi_info["deviceCount"]):
                d = self._pa.get_device_info_by_host_api_device_index(
                    wasapi_info["index"], i
                )
                if d.get("isLoopbackDevice") and d["name"].startswith(dev_info["name"][:10]):
                    device_index = d["index"]
                    dev_info = d
                    break

        # Use the device's actual native sample rate
        self.actual_sample_rate = int(dev_info.get("defaultSampleRate", 44100))
        chunk_frames = int(self.actual_sample_rate * chunk_ms / 1000)
        self._chunk_frames = chunk_frames

        logger.info(
            "PyAudioWPatch loopback : '%s' @ %dHz",
            dev_info.get("name", "?"), self.actual_sample_rate,
        )

        self._stream = self._pa.open(
            format=pyaudio_module.paInt16,
            channels=1,
            rate=self.actual_sample_rate,
            input=True,
            input_device_index=device_index,
            frames_per_buffer=chunk_frames,
        )

    def start(self) -> None:
        pass  # PyAudio démarre au open()

    def read(self, frames: int) -> tuple[bytes, bool]:
        data = self._stream.read(frames, exception_on_overflow=False)
        return data, False

    def stop(self) -> None:
        if self._stream:
            self._stream.stop_stream()

    def close(self) -> None:
        if self._stream:
            self._stream.close()
        self._pa.terminate()
