#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VoxShield — Gestionnaire de configuration persistante.
Stocke la config en JSON dans le dossier utilisateur standard.
Les clés API sont stockées dans le gestionnaire de mots de passe OS (keyring).
"""

import copy
import json
import logging
from pathlib import Path
from typing import Any, Optional

import keyring
import platformdirs

from config.default_settings import DEFAULT_SETTINGS

logger = logging.getLogger(__name__)

APP_NAME = "VoxShield"
APP_AUTHOR = "MSIASystems"
KEYRING_SERVICE = "voxshield"


class SettingsManager:
    """
    Gère la lecture/écriture de la configuration JSON de l'application.
    Les clés API sensibles sont déléguées au gestionnaire de mots de passe OS.
    """

    def __init__(self) -> None:
        self._config_dir = Path(
            platformdirs.user_config_dir(APP_NAME, APP_AUTHOR)
        )
        self._config_file = self._config_dir / "settings.json"
        self._settings: dict = {}
        self._load()

    # ── Chemins ──────────────────────────────────────────────────────────────

    @property
    def config_dir(self) -> Path:
        """Dossier de configuration de l'application."""
        return self._config_dir

    @property
    def models_dir(self) -> Path:
        """Dossier de stockage des modèles IA."""
        d = self._config_dir / "models"
        d.mkdir(parents=True, exist_ok=True)
        return d

    @property
    def whisper_models_dir(self) -> Path:
        d = self.models_dir / "whisper"
        d.mkdir(parents=True, exist_ok=True)
        return d

    @property
    def piper_models_dir(self) -> Path:
        d = self.models_dir / "piper"
        d.mkdir(parents=True, exist_ok=True)
        return d

    @property
    def argos_models_dir(self) -> Path:
        d = self.models_dir / "argos"
        d.mkdir(parents=True, exist_ok=True)
        return d

    @property
    def logs_dir(self) -> Path:
        d = self._config_dir / "logs"
        d.mkdir(parents=True, exist_ok=True)
        return d

    # ── Chargement / Sauvegarde ───────────────────────────────────────────────

    def _load(self) -> None:
        """Charge la configuration depuis le fichier JSON, avec fusion des défauts."""
        self._config_dir.mkdir(parents=True, exist_ok=True)
        self._settings = copy.deepcopy(DEFAULT_SETTINGS)

        if self._config_file.exists():
            try:
                with open(self._config_file, encoding="utf-8") as f:
                    stored = json.load(f)
                self._deep_merge(self._settings, stored)
                logger.debug("Configuration chargée depuis %s", self._config_file)
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("Impossible de lire la config (%s) — défauts utilisés", e)
        else:
            logger.info("Première utilisation — config par défaut créée")
            self.save()

    def save(self) -> None:
        """Persiste la configuration actuelle sur disque."""
        try:
            self._config_dir.mkdir(parents=True, exist_ok=True)
            with open(self._config_file, "w", encoding="utf-8") as f:
                json.dump(self._settings, f, indent=2, ensure_ascii=False)
            logger.debug("Configuration sauvegardée")
        except OSError as e:
            logger.error("Impossible de sauvegarder la config : %s", e)

    @staticmethod
    def _deep_merge(base: dict, override: dict) -> None:
        """Fusionne override dans base récursivement (in-place)."""
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                SettingsManager._deep_merge(base[key], value)
            else:
                base[key] = value

    # ── Accès générique ───────────────────────────────────────────────────────

    def get(self, section: str, key: str, default: Any = None) -> Any:
        """Retourne une valeur de configuration."""
        return self._settings.get(section, {}).get(key, default)

    def set(self, section: str, key: str, value: Any) -> None:
        """Modifie une valeur et sauvegarde immédiatement."""
        if section not in self._settings:
            self._settings[section] = {}
        self._settings[section][key] = value
        self.save()

    def get_section(self, section: str) -> dict:
        """Retourne une section complète de la configuration."""
        return copy.deepcopy(self._settings.get(section, {}))

    def update_section(self, section: str, values: dict) -> None:
        """Met à jour plusieurs clés d'une section et sauvegarde."""
        if section not in self._settings:
            self._settings[section] = {}
        self._settings[section].update(values)
        self.save()

    # ── Raccourcis typés ──────────────────────────────────────────────────────

    @property
    def user_lang(self) -> str:
        return self.get("languages", "user_lang", "fr")

    @user_lang.setter
    def user_lang(self, code: str) -> None:
        self.set("languages", "user_lang", code)

    @property
    def remote_lang(self) -> str:
        return self.get("languages", "remote_lang", "en")

    @remote_lang.setter
    def remote_lang(self, code: str) -> None:
        self.set("languages", "remote_lang", code)

    @property
    def stt_mode(self) -> str:
        return self.get("stt", "mode", "local")

    @property
    def stt_model_size(self) -> str:
        return self.get("stt", "model_size", "base")

    @property
    def translation_mode(self) -> str:
        return self.get("translation", "mode", "local")

    @property
    def tts_mode(self) -> str:
        return self.get("tts", "mode", "piper")

    @property
    def tts_speed(self) -> float:
        return float(self.get("tts", "speed", 1.0))

    @property
    def pipeline_a_enabled(self) -> bool:
        return bool(self.get("pipelines", "pipeline_a_enabled", True))

    @pipeline_a_enabled.setter
    def pipeline_a_enabled(self, value: bool) -> None:
        self.set("pipelines", "pipeline_a_enabled", value)

    @property
    def pipeline_b_enabled(self) -> bool:
        return bool(self.get("pipelines", "pipeline_b_enabled", True))

    @pipeline_b_enabled.setter
    def pipeline_b_enabled(self, value: bool) -> None:
        self.set("pipelines", "pipeline_b_enabled", value)

    @property
    def local_tts_output(self) -> bool:
        return bool(self.get("pipelines", "local_tts_output", False))

    @property
    def first_launch(self) -> bool:
        return bool(self._settings.get("first_launch", True))

    def mark_first_launch_done(self) -> None:
        """Marque que le wizard de premier lancement a été complété."""
        self._settings["first_launch"] = False
        self.save()

    # ── Clés API (keyring) ────────────────────────────────────────────────────

    def set_api_key(self, service: str, key: str) -> None:
        """
        Stocke une clé API dans le gestionnaire de mots de passe OS.
        Met à jour uniquement le flag booléen dans le JSON.
        """
        try:
            keyring.set_password(KEYRING_SERVICE, service, key)
            # Marquer la présence dans la config sans exposer la clé
            section_map = {
                "openai": ("stt", "openai_api_key_set"),
                "deepl": ("translation", "deepl_api_key_set"),
                "openai_tts": ("tts", "openai_api_key_set"),
            }
            if service in section_map:
                section, flag = section_map[service]
                self.set(section, flag, True)
            logger.info("Clé API '%s' stockée dans le gestionnaire OS", service)
        except keyring.errors.KeyringError as e:
            logger.error("Impossible de stocker la clé API '%s' : %s", service, e)

    def get_api_key(self, service: str) -> Optional[str]:
        """Récupère une clé API depuis le gestionnaire de mots de passe OS."""
        try:
            return keyring.get_password(KEYRING_SERVICE, service)
        except keyring.errors.KeyringError as e:
            logger.error("Impossible de lire la clé API '%s' : %s", service, e)
            return None

    def delete_api_key(self, service: str) -> None:
        """Supprime une clé API du gestionnaire de mots de passe OS."""
        try:
            keyring.delete_password(KEYRING_SERVICE, service)
            section_map = {
                "openai": ("stt", "openai_api_key_set"),
                "deepl": ("translation", "deepl_api_key_set"),
                "openai_tts": ("tts", "openai_api_key_set"),
            }
            if service in section_map:
                section, flag = section_map[service]
                self.set(section, flag, False)
        except keyring.errors.KeyringError as e:
            logger.warning("Impossible de supprimer la clé API '%s' : %s", service, e)

    def has_api_key(self, service: str) -> bool:
        """Vérifie si une clé API est configurée."""
        return self.get_api_key(service) is not None

    # ── Hotkeys ───────────────────────────────────────────────────────────────

    def get_hotkey(self, action: str) -> str:
        """Retourne le raccourci clavier pour une action."""
        defaults = DEFAULT_SETTINGS.get("hotkeys", {})
        return self._settings.get("hotkeys", {}).get(action, defaults.get(action, ""))

    def set_hotkey(self, action: str, shortcut: str) -> None:
        """Définit un raccourci clavier pour une action."""
        if "hotkeys" not in self._settings:
            self._settings["hotkeys"] = {}
        self._settings["hotkeys"][action] = shortcut
        self.save()

    # ── Audio ─────────────────────────────────────────────────────────────────

    @property
    def input_device_index(self) -> Optional[int]:
        v = self.get("audio", "input_device_index")
        return int(v) if v is not None else None

    @input_device_index.setter
    def input_device_index(self, index: Optional[int]) -> None:
        self.set("audio", "input_device_index", index)

    @property
    def loopback_device_index(self) -> Optional[int]:
        v = self.get("audio", "loopback_device_index")
        return int(v) if v is not None else None

    @loopback_device_index.setter
    def loopback_device_index(self, index: Optional[int]) -> None:
        self.set("audio", "loopback_device_index", index)

    @property
    def virtual_cable_index(self) -> Optional[int]:
        v = self.get("audio", "virtual_cable_index")
        return int(v) if v is not None else None

    @virtual_cable_index.setter
    def virtual_cable_index(self, index: Optional[int]) -> None:
        self.set("audio", "virtual_cable_index", index)

    @property
    def sample_rate(self) -> int:
        return int(self.get("audio", "sample_rate", 16000))

    @property
    def chunk_ms(self) -> int:
        return int(self.get("audio", "chunk_ms", 30))

    @property
    def vad_mode(self) -> int:
        return int(self.get("audio", "vad_mode", 2))

    @property
    def vad_silence_ms(self) -> int:
        return int(self.get("audio", "vad_silence_ms", 800))

    @property
    def vad_min_speech_ms(self) -> int:
        return int(self.get("audio", "vad_min_speech_ms", 250))

    # ── UI ────────────────────────────────────────────────────────────────────

    @property
    def overlay_opacity(self) -> float:
        return float(self.get("ui", "overlay_opacity", 0.75))

    @property
    def overlay_font_size(self) -> int:
        return int(self.get("ui", "overlay_font_size", 16))

    @property
    def overlay_duration_ms(self) -> int:
        return int(self.get("ui", "overlay_duration_ms", 5000))

    @property
    def overlay_position(self) -> list:
        return self.get("ui", "overlay_position", ["center", "bottom"])

    def __repr__(self) -> str:
        return (
            f"SettingsManager(config={self._config_file}, "
            f"user_lang={self.user_lang}, remote_lang={self.remote_lang})"
        )
