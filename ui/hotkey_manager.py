#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VoxShield — Gestionnaire de raccourcis clavier globaux.
Utilise le module 'keyboard' pour les hooks globaux (inter-applications).
"""

import threading
from typing import Callable, Optional

from config.settings_manager import SettingsManager
from utils.logger import get_logger

logger = get_logger("HOTKEY")


class HotkeyManager:
    """
    Enregistre et gère les raccourcis clavier globaux de l'application.
    Les raccourcis fonctionnent même quand la fenêtre n'a pas le focus.

    Note : Le module 'keyboard' requiert des droits administrateur sur certains systèmes.
    """

    def __init__(self, settings: SettingsManager) -> None:
        self._settings = settings
        self._registered: list[str] = []
        self._lock = threading.Lock()
        self._callbacks: dict[str, Callable] = {}

        # Vérifier la disponibilité du module
        self._available = self._check_keyboard_module()

    def _check_keyboard_module(self) -> bool:
        try:
            import keyboard  # noqa: F401
            return True
        except ImportError:
            logger.warning("Module 'keyboard' non installé — raccourcis globaux désactivés")
            return False
        except Exception as e:
            logger.warning("Module 'keyboard' non disponible : %s", e)
            return False

    # ── Enregistrement ────────────────────────────────────────────────────────

    def register(
        self,
        action: str,
        callback: Callable,
        hotkey: Optional[str] = None,
    ) -> bool:
        """
        Enregistre un raccourci global pour une action.

        Args:
            action: Identifiant de l'action (ex. 'start_stop').
            callback: Fonction à appeler lors du raccourci.
            hotkey: Raccourci personnalisé (ex. 'ctrl+shift+t'). Si None, utilise les settings.

        Returns:
            True si l'enregistrement a réussi.
        """
        if not self._available:
            return False

        hotkey = hotkey or self._settings.get_hotkey(action)
        if not hotkey:
            logger.warning("Pas de raccourci défini pour l'action '%s'", action)
            return False

        try:
            import keyboard
            keyboard.add_hotkey(hotkey, callback, suppress=False)
            with self._lock:
                self._registered.append(hotkey)
                self._callbacks[action] = callback
            logger.info("Raccourci enregistre : %s -> %s", hotkey, action)
            return True
        except Exception as e:
            logger.error("Impossible d'enregistrer le raccourci '%s' : %s", hotkey, e)
            return False

    def register_all(
        self,
        on_start_stop: Optional[Callable] = None,
        on_mute: Optional[Callable] = None,
        on_overlay: Optional[Callable] = None,
        on_swap: Optional[Callable] = None,
        on_show_hide: Optional[Callable] = None,
    ) -> None:
        """Enregistre tous les raccourcis par défaut en une fois."""
        if on_start_stop:
            self.register("start_stop", on_start_stop)
        if on_mute:
            self.register("mute_mic", on_mute)
        if on_overlay:
            self.register("toggle_overlay", on_overlay)
        if on_swap:
            self.register("swap_languages", on_swap)
        if on_show_hide:
            self.register("show_hide", on_show_hide)

    # ── Désenregistrement ─────────────────────────────────────────────────────

    def unregister_all(self) -> None:
        """Supprime tous les raccourcis enregistrés."""
        if not self._available:
            return
        try:
            import keyboard
            with self._lock:
                for hotkey in self._registered:
                    try:
                        keyboard.remove_hotkey(hotkey)
                    except Exception:
                        pass
                self._registered.clear()
                self._callbacks.clear()
            logger.info("Tous les raccourcis désactivés")
        except Exception as e:
            logger.error("Erreur désenregistrement raccourcis : %s", e)

    def update_hotkey(self, action: str, new_hotkey: str) -> bool:
        """
        Met à jour le raccourci d'une action et sauvegarde dans les settings.

        Args:
            action: Identifiant de l'action.
            new_hotkey: Nouveau raccourci (ex. 'ctrl+alt+t').

        Returns:
            True si la mise à jour a réussi.
        """
        if not self._available:
            return False

        callback = self._callbacks.get(action)
        if not callback:
            logger.warning("Action '%s' non enregistrée", action)
            return False

        # Supprimer l'ancien raccourci
        old_hotkey = self._settings.get_hotkey(action)
        if old_hotkey:
            try:
                import keyboard
                keyboard.remove_hotkey(old_hotkey)
                with self._lock:
                    if old_hotkey in self._registered:
                        self._registered.remove(old_hotkey)
            except Exception:
                pass

        # Enregistrer le nouveau
        self._settings.set_hotkey(action, new_hotkey)
        return self.register(action, callback, new_hotkey)

    @property
    def is_available(self) -> bool:
        return self._available

    def __del__(self) -> None:
        self.unregister_all()
