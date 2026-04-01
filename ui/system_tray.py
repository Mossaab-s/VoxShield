#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VoxShield — Icône systray et menu de contrôle rapide.
L'icône change selon l'état : gris (off), vert (actif), orange (erreur).
"""

from pathlib import Path
from typing import Callable, Optional

from PyQt6.QtGui import QIcon, QPixmap, QColor, QPainter
from PyQt6.QtCore import QSize
from PyQt6.QtWidgets import QSystemTrayIcon, QMenu, QApplication

from core.main_controller import ControllerState
from utils.logger import get_logger

logger = get_logger("TRAY")

STATE_COLORS = {
    ControllerState.STOPPED:  "#6C7086",
    ControllerState.STARTING: "#F9E2AF",
    ControllerState.RUNNING:  "#A6E3A1",
    ControllerState.STOPPING: "#F9E2AF",
    ControllerState.ERROR:    "#F38BA8",
}


def _make_icon(color_hex: str) -> QIcon:
    """Génère une icône circulaire colorée pour le systray."""
    pixmap = QPixmap(QSize(32, 32))
    pixmap.fill(QColor(0, 0, 0, 0))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor(color_hex))
    painter.setPen(QColor("#1E1E2E"))
    painter.drawEllipse(2, 2, 28, 28)
    painter.end()
    return QIcon(pixmap)


class SystemTray(QSystemTrayIcon):
    """
    Icône dans la zone de notification système avec menu contextuel.
    """

    def __init__(
        self,
        on_show: Optional[Callable] = None,
        on_toggle: Optional[Callable] = None,
        on_settings: Optional[Callable] = None,
        on_quit: Optional[Callable] = None,
        parent=None,
    ) -> None:
        super().__init__(parent)

        self._on_show = on_show
        self._on_toggle = on_toggle
        self._on_settings = on_settings
        self._on_quit = on_quit

        self._setup_icon()
        self._setup_menu()
        self._setup_interactions()

    def _setup_icon(self) -> None:
        # Essayer de charger une icône depuis assets/
        icon_path = Path(__file__).parent.parent / "assets" / "icons" / "voxshield.png"
        if icon_path.exists():
            self.setIcon(QIcon(str(icon_path)))
        else:
            self.setIcon(_make_icon(STATE_COLORS[ControllerState.STOPPED]))

        self.setToolTip("VoxShield — Traducteur vocal temps réel")

    def _setup_menu(self) -> None:
        menu = QMenu()

        self._action_show = menu.addAction("Afficher / Masquer")
        self._action_show.triggered.connect(lambda: self._on_show and self._on_show())

        menu.addSeparator()

        self._action_toggle = menu.addAction("▶ Démarrer")
        self._action_toggle.triggered.connect(lambda: self._on_toggle and self._on_toggle())

        menu.addSeparator()

        action_settings = menu.addAction("Paramètres")
        action_settings.triggered.connect(lambda: self._on_settings and self._on_settings())

        menu.addSeparator()

        action_about = menu.addAction("À propos")
        action_about.triggered.connect(self._show_about)

        menu.addSeparator()

        action_quit = menu.addAction("Quitter")
        action_quit.triggered.connect(lambda: self._on_quit and self._on_quit())

        self.setContextMenu(menu)

    def _setup_interactions(self) -> None:
        self.activated.connect(self._on_activated)

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            if self._on_show:
                self._on_show()

    def update_state(self, state: ControllerState) -> None:
        """Met à jour l'icône et le menu selon l'état du contrôleur."""
        color = STATE_COLORS.get(state, "#6C7086")
        self.setIcon(_make_icon(color))

        if state == ControllerState.RUNNING:
            self._action_toggle.setText("■ Arrêter")
            self.setToolTip("VoxShield — Actif")
        else:
            self._action_toggle.setText("▶ Démarrer")
            self.setToolTip("VoxShield — Arrêté")

    def _show_about(self) -> None:
        self.showMessage(
            "VoxShield v1.0",
            "Traducteur vocal temps réel\n© MSIA Systems — Mars 2026",
            QSystemTrayIcon.MessageIcon.Information,
            3000,
        )

    def notify(self, title: str, message: str) -> None:
        """Affiche une notification bulle systray."""
        self.showMessage(title, message, QSystemTrayIcon.MessageIcon.Information, 3000)
