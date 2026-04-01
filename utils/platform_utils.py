#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VoxShield — Utilitaires de détection de plateforme.
Détecte l'OS, la présence de Virtual Cable et du loopback audio.
"""

import platform
import sys
from typing import Optional

from utils.logger import get_logger

logger = get_logger("PLATFORM")


def get_os() -> str:
    """Retourne 'Windows', 'Darwin' (macOS) ou 'Linux'."""
    return platform.system()


def is_windows() -> bool:
    return sys.platform == "win32"


def is_macos() -> bool:
    return sys.platform == "darwin"


def is_linux() -> bool:
    return sys.platform.startswith("linux")


def detect_virtual_cable() -> Optional[int]:
    """
    Cherche un périphérique Virtual Cable dans la liste des sorties audio.
    Retourne l'index du device ou None si non trouvé.
    """
    import sounddevice as sd
    from config.default_settings import VIRTUAL_CABLE_PATTERNS

    os_name = get_os()
    patterns = VIRTUAL_CABLE_PATTERNS.get(os_name, [])

    try:
        devices = sd.query_devices()
        for i, device in enumerate(devices):
            name: str = device.get("name", "")
            if device.get("max_output_channels", 0) > 0:
                for pattern in patterns:
                    if pattern.lower() in name.lower():
                        logger.info("Virtual Cable détecté : '%s' (index %d)", name, i)
                        return i
    except Exception as e:
        logger.error("Erreur lors de la détection du Virtual Cable : %s", e)

    logger.warning("Aucun Virtual Cable détecté sur %s", os_name)
    return None


def detect_loopback_device() -> Optional[int]:
    """
    Cherche un périphérique loopback (capture audio système).
    Sur Windows : utilise PyAudioWPatch si disponible.
    Retourne l'index du device ou None si non trouvé.
    """
    import sounddevice as sd
    from config.default_settings import LOOPBACK_PATTERNS

    os_name = get_os()
    patterns = LOOPBACK_PATTERNS.get(os_name, [])

    try:
        devices = sd.query_devices()
        for i, device in enumerate(devices):
            name: str = device.get("name", "")
            if device.get("max_input_channels", 0) > 0:
                for pattern in patterns:
                    if pattern.lower() in name.lower():
                        logger.info("Loopback détecté : '%s' (index %d)", name, i)
                        return i
    except Exception as e:
        logger.error("Erreur lors de la détection loopback : %s", e)

    logger.warning("Aucun périphérique loopback détecté sur %s", os_name)
    return None


def get_virtual_cable_install_info() -> dict:
    """Retourne les informations d'installation du Virtual Cable selon l'OS."""
    if is_windows():
        return {
            "name": "VB-Audio Virtual Cable",
            "url": "https://vb-audio.com/Cable/",
            "instructions": [
                "1. Télécharger VB-Audio Virtual Cable sur vb-audio.com/Cable",
                "2. Exécuter l'installeur en tant qu'administrateur",
                "3. Redémarrer Windows",
                "4. Dans votre app de visioconférence, sélectionner 'CABLE Input' comme microphone",
            ],
        }
    elif is_macos():
        return {
            "name": "BlackHole 2ch",
            "url": "https://existential.audio/blackhole/",
            "instructions": [
                "1. Télécharger BlackHole 2ch sur existential.audio/blackhole",
                "2. Installer le package .pkg",
                "3. Dans votre app de visioconférence, sélectionner 'BlackHole 2ch' comme microphone",
            ],
        }
    else:
        return {
            "name": "PulseAudio virtual sink",
            "url": "https://www.freedesktop.org/wiki/Software/PulseAudio/",
            "instructions": [
                "pactl load-module module-null-sink sink_name=voxshield",
                "Sélectionner 'voxshield' comme source dans votre app de visioconférence",
            ],
        }


def check_python_version() -> bool:
    """Vérifie que Python 3.10+ est utilisé."""
    return sys.version_info >= (3, 10)


def get_system_info() -> dict:
    """Retourne un dict avec les informations système."""
    return {
        "os": get_os(),
        "os_version": platform.version(),
        "python_version": platform.python_version(),
        "architecture": platform.machine(),
        "processor": platform.processor(),
    }
