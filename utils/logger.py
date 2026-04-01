#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VoxShield — Logging centralisé.
Console en développement + fichier rotatif en production.
"""

import io
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

# Forcer UTF-8 sur la console Windows pour les caractères spéciaux
if sys.platform == "win32" and hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


def setup_logger(
    log_dir: Path | None = None,
    level: int = logging.INFO,
    console: bool = True,
) -> logging.Logger:
    """
    Configure et retourne le logger racine de l'application.

    Args:
        log_dir: Dossier de sortie du fichier log. Si None, log en console uniquement.
        level: Niveau de log minimum (ex. logging.DEBUG).
        console: Activer ou non la sortie console.

    Returns:
        Logger racine configuré.
    """
    root_logger = logging.getLogger("voxshield")
    root_logger.setLevel(level)

    # Éviter la duplication de handlers entre appels multiples
    if root_logger.handlers:
        return root_logger

    fmt = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    if console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(fmt)
        console_handler.setLevel(level)
        root_logger.addHandler(console_handler)

    if log_dir is not None:
        log_dir = Path(log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "voxshield.log"
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=5 * 1024 * 1024,  # 5 MB
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setFormatter(fmt)
        file_handler.setLevel(level)
        root_logger.addHandler(file_handler)

    return root_logger


def get_logger(module_name: str) -> logging.Logger:
    """
    Retourne un logger préfixé pour un module spécifique.
    Usage : logger = get_logger("STT")
    """
    return logging.getLogger(f"voxshield.{module_name}")
