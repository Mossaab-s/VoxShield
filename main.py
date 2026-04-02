#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VoxShield — Traducteur vocal temps réel
Point d'entrée principal de l'application.
"""

import sys
import os


def _check_python_version() -> None:
    if sys.version_info < (3, 10):
        print(f"ERREUR : Python 3.10+ requis (version actuelle : {sys.version})")
        sys.exit(1)


def main() -> None:
    _check_python_version()

    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import Qt

    # Activer le DPI haute résolution
    os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR", "1")

    app = QApplication(sys.argv)
    app.setApplicationName("VoxShield")
    app.setApplicationVersion("1.0")
    app.setOrganizationName("MSIA Systems")
    app.setOrganizationDomain("msia-systems.com")

    # Initialiser le logger avec le dossier de config
    from config.settings_manager import SettingsManager
    settings = SettingsManager()

    from utils.logger import setup_logger
    import logging
    logger = setup_logger(
        log_dir=settings.logs_dir,
        level=logging.INFO,
        console=True,
    )
    logger.info("Démarrage VoxShield v1.0")
    logger.info("Config : %s", settings.config_dir)

    # Contrôleur principal
    from core.main_controller import MainController
    controller = MainController(settings)

    # Fenêtre principale
    from ui.main_window import MainWindow
    window = MainWindow(controller, settings)

    # System Tray
    from ui.system_tray import SystemTray
    tray = SystemTray(
        on_show=window.show,
        on_toggle=controller.toggle,
        on_settings=window.open_settings,
        on_quit=app.quit,
    )
    previous_status_callback = controller.on_status_change

    def _on_status_change(state) -> None:
        if previous_status_callback:
            previous_status_callback(state)
        tray.update_state(state)

    controller.on_status_change = _on_status_change
    tray.show()

    # Raccourcis clavier globaux
    from ui.hotkey_manager import HotkeyManager
    hotkeys = HotkeyManager(settings)
    hotkeys.register_all(
        on_start_stop=controller.toggle,
        on_mute=controller.toggle_mute,
        on_overlay=window.request_toggle_overlay,
        on_swap=window.request_swap_languages,
        on_show_hide=window.request_toggle_visibility,
    )

    # Wizard premier lancement
    if settings.first_launch:
        from ui.first_launch_wizard import FirstLaunchWizard
        wizard = FirstLaunchWizard(settings, controller, window)
        wizard.exec()

    window.show()

    ret = app.exec()

    # Nettoyage
    hotkeys.unregister_all()
    if controller.is_running:
        controller.stop()
    logger.info("VoxShield fermé")

    sys.exit(ret)


if __name__ == "__main__":
    main()
