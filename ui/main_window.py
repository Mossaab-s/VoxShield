#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VoxShield — Fenêtre principale de l'application.
480×620px, thème sombre, PyQt6.
"""

import time
from datetime import datetime

from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread, pyqtSlot
from PyQt6.QtGui import QColor, QFont, QIcon
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QComboBox, QTextEdit,
    QGroupBox, QProgressBar, QSizePolicy, QFrame,
    QMessageBox, QSlider,
)

from config.language_registry import LANGUAGE_REGISTRY, get_display_name
from config.settings_manager import SettingsManager
from core.main_controller import MainController, ControllerState, TranslationEvent
from ui.overlay_window import OverlayWindow
from utils.logger import get_logger

logger = get_logger("UI")

DARK_STYLE = """
QMainWindow, QWidget {
    background-color: #1E1E2E;
    color: #CDD6F4;
    font-family: "Segoe UI", Arial, sans-serif;
    font-size: 13px;
}
QGroupBox {
    border: 1px solid #313244;
    border-radius: 6px;
    margin-top: 8px;
    padding-top: 8px;
    color: #CDD6F4;
    font-weight: bold;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
}
QComboBox {
    background-color: #313244;
    border: 1px solid #45475A;
    border-radius: 4px;
    padding: 4px 8px;
    color: #CDD6F4;
    min-height: 28px;
}
QComboBox::drop-down { border: none; }
QComboBox:hover { border-color: #2E75B6; }
QComboBox QAbstractItemView {
    background-color: #313244;
    color: #CDD6F4;
    selection-background-color: #2E75B6;
}
QPushButton {
    background-color: #313244;
    border: 1px solid #45475A;
    border-radius: 6px;
    padding: 6px 16px;
    color: #CDD6F4;
    min-height: 32px;
}
QPushButton:hover { background-color: #45475A; border-color: #2E75B6; }
QPushButton:pressed { background-color: #2E75B6; }
QPushButton#btn_start {
    background-color: #2E75B6;
    font-size: 16px;
    font-weight: bold;
    min-height: 50px;
    border-radius: 8px;
    border: none;
}
QPushButton#btn_start:hover { background-color: #3484C9; }
QPushButton#btn_start[running="true"] {
    background-color: #E53E3E;
}
QPushButton#btn_start[running="true"]:hover { background-color: #FC5252; }
QTextEdit {
    background-color: #11111B;
    border: 1px solid #313244;
    border-radius: 4px;
    color: #CDD6F4;
    font-family: "Consolas", monospace;
    font-size: 12px;
}
QLabel#status_dot {
    border-radius: 6px;
    min-width: 12px;
    min-height: 12px;
    max-width: 12px;
    max-height: 12px;
}
QFrame#separator {
    background-color: #313244;
    max-height: 1px;
}
"""

STATUS_COLORS = {
    ControllerState.STOPPED:  "#6C7086",  # Gris
    ControllerState.STARTING: "#F9E2AF",  # Jaune
    ControllerState.RUNNING:  "#A6E3A1",  # Vert
    ControllerState.STOPPING: "#F9E2AF",  # Jaune
    ControllerState.ERROR:    "#F38BA8",  # Rouge
}
STATUS_LABELS = {
    ControllerState.STOPPED:  "Arrêté",
    ControllerState.STARTING: "Démarrage...",
    ControllerState.RUNNING:  "Actif",
    ControllerState.STOPPING: "Arrêt...",
    ControllerState.ERROR:    "Erreur",
}


class MainWindow(QMainWindow):
    """Fenêtre principale de VoxShield."""

    # Signaux pour thread-safety (les callbacks contrôleur viennent d'autres threads)
    _sig_translation = pyqtSignal(object)
    _sig_status = pyqtSignal(object)
    _sig_error = pyqtSignal(str)
    _sig_latency = pyqtSignal(int)
    _sig_request_swap = pyqtSignal()
    _sig_request_toggle_overlay = pyqtSignal()
    _sig_request_toggle_visibility = pyqtSignal()

    def __init__(self, controller: MainController, settings: SettingsManager) -> None:
        super().__init__()
        self._controller = controller
        self._settings = settings

        # Brancher les callbacks du contrôleur sur les signaux Qt (thread-safe)
        self._controller.on_translation = lambda e: self._sig_translation.emit(e)
        self._controller.on_status_change = lambda s: self._sig_status.emit(s)
        self._controller.on_error = lambda m: self._sig_error.emit(m)
        self._controller.on_latency_update = lambda l: self._sig_latency.emit(l)

        self._sig_translation.connect(self._on_translation)
        self._sig_status.connect(self._on_status_change)
        self._sig_error.connect(self._on_error)
        self._sig_latency.connect(self._on_latency)
        self._sig_request_swap.connect(self._on_swap_languages)
        self._sig_request_toggle_overlay.connect(self._toggle_overlay)
        self._sig_request_toggle_visibility.connect(self._toggle_visibility)

        # Overlay sous-titres
        self._overlay = OverlayWindow(
            screen_position=tuple(settings.overlay_position)
        )
        self._overlay.set_opacity(settings.overlay_opacity)
        self._overlay.set_font_size(settings.overlay_font_size)

        self._setup_window()
        self._setup_ui()
        self._populate_devices()
        self._populate_languages()
        self._apply_settings()

    # ── Configuration fenêtre ─────────────────────────────────────────────────

    def _setup_window(self) -> None:
        self.setWindowTitle("VoxShield v1.0")
        self.setFixedSize(480, 640)
        self.setStyleSheet(DARK_STYLE)
        # Centrer sur l'écran
        from PyQt6.QtWidgets import QApplication
        screen = QApplication.primaryScreen().availableGeometry()
        self.move(
            screen.center().x() - 240,
            screen.center().y() - 320,
        )

    # ── Construction de l'interface ───────────────────────────────────────────

    def _setup_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setSpacing(8)
        main_layout.setContentsMargins(12, 12, 12, 12)

        main_layout.addWidget(self._build_header())
        main_layout.addWidget(self._separator())
        main_layout.addWidget(self._build_languages_section())
        main_layout.addWidget(self._build_audio_section())
        main_layout.addWidget(self._build_controls_section())
        main_layout.addWidget(self._build_start_button())
        main_layout.addWidget(self._build_logs_section(), stretch=1)

    def _build_header(self) -> QWidget:
        w = QWidget()
        layout = QHBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)

        # Logo / Titre
        title = QLabel("🌐 VoxShield")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #2E75B6;")
        layout.addWidget(title)

        layout.addStretch()

        # Latence
        self._lbl_latency = QLabel("-- ms")
        self._lbl_latency.setStyleSheet("color: #6C7086; font-size: 11px;")
        layout.addWidget(self._lbl_latency)

        layout.addSpacing(8)

        # Point de statut
        self._status_dot = QLabel()
        self._status_dot.setObjectName("status_dot")
        self._status_dot.setFixedSize(12, 12)
        self._update_status_dot(ControllerState.STOPPED)
        layout.addWidget(self._status_dot)

        self._lbl_status = QLabel("Arrêté")
        self._lbl_status.setStyleSheet("font-size: 12px;")
        layout.addWidget(self._lbl_status)

        return w

    def _build_languages_section(self) -> QGroupBox:
        group = QGroupBox("Langues")
        layout = QHBoxLayout(group)
        layout.setSpacing(8)

        self._combo_user_lang = QComboBox()
        self._combo_user_lang.setToolTip("Ma langue (je parle)")

        btn_swap = QPushButton("⇄")
        btn_swap.setFixedWidth(36)
        btn_swap.setToolTip("Inverser les langues")
        btn_swap.clicked.connect(self._on_swap_languages)

        self._combo_remote_lang = QComboBox()
        self._combo_remote_lang.setToolTip("Langue de l'interlocuteur")

        layout.addWidget(QLabel("Ma langue :"))
        layout.addWidget(self._combo_user_lang, stretch=1)
        layout.addWidget(btn_swap)
        layout.addWidget(QLabel("Distant :"))
        layout.addWidget(self._combo_remote_lang, stretch=1)

        return group

    def _build_audio_section(self) -> QGroupBox:
        group = QGroupBox("Audio")
        layout = QVBoxLayout(group)
        layout.setSpacing(6)

        # Microphone
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Microphone :"))
        self._combo_mic = QComboBox()
        row1.addWidget(self._combo_mic, stretch=1)
        btn_test_mic = QPushButton("Test")
        btn_test_mic.setFixedWidth(50)
        btn_test_mic.clicked.connect(self._test_mic)
        row1.addWidget(btn_test_mic)
        layout.addLayout(row1)

        # Loopback
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Loopback :"))
        self._combo_loopback = QComboBox()
        row2.addWidget(self._combo_loopback, stretch=1)
        layout.addLayout(row2)

        # Virtual Cable
        row3 = QHBoxLayout()
        row3.addWidget(QLabel("Virtual Cable :"))
        self._combo_vcable = QComboBox()
        row3.addWidget(self._combo_vcable, stretch=1)
        self._lbl_vcable_status = QLabel("?")
        row3.addWidget(self._lbl_vcable_status)
        layout.addLayout(row3)

        # VU-mètre (simulé)
        vu_row = QHBoxLayout()
        vu_row.addWidget(QLabel("Niveau :"))
        self._vu_meter = QProgressBar()
        self._vu_meter.setMaximum(100)
        self._vu_meter.setValue(0)
        self._vu_meter.setTextVisible(False)
        self._vu_meter.setMaximumHeight(8)
        self._vu_meter.setStyleSheet(
            "QProgressBar { background: #313244; border-radius: 4px; }"
            "QProgressBar::chunk { background: #2E75B6; border-radius: 4px; }"
        )
        vu_row.addWidget(self._vu_meter, stretch=1)
        layout.addLayout(vu_row)

        return group

    def _build_controls_section(self) -> QGroupBox:
        group = QGroupBox("Pipelines")
        layout = QHBoxLayout(group)

        self._btn_pipe_a = QPushButton("Pipeline A ✓")
        self._btn_pipe_a.setCheckable(True)
        self._btn_pipe_a.setChecked(True)
        self._btn_pipe_a.setToolTip("Toi → Interlocuteur (votre micro traduit)")
        self._btn_pipe_a.toggled.connect(
            lambda v: self._settings.set("pipelines", "pipeline_a_enabled", v)
        )

        self._btn_pipe_b = QPushButton("Pipeline B ✓")
        self._btn_pipe_b.setCheckable(True)
        self._btn_pipe_b.setChecked(True)
        self._btn_pipe_b.setToolTip("Interlocuteur → Toi (sous-titres)")
        self._btn_pipe_b.toggled.connect(
            lambda v: self._settings.set("pipelines", "pipeline_b_enabled", v)
        )

        self._btn_local_tts = QPushButton("TTS Local")
        self._btn_local_tts.setCheckable(True)
        self._btn_local_tts.setChecked(False)
        self._btn_local_tts.setToolTip("Lire la traduction à voix haute localement")
        self._btn_local_tts.toggled.connect(
            lambda v: self._settings.set("pipelines", "local_tts_output", v)
        )

        layout.addWidget(self._btn_pipe_a)
        layout.addWidget(self._btn_pipe_b)
        layout.addWidget(self._btn_local_tts)

        return group

    def _build_start_button(self) -> QPushButton:
        self._btn_start = QPushButton("▶  DÉMARRER")
        self._btn_start.setObjectName("btn_start")
        self._btn_start.setProperty("running", False)
        self._btn_start.clicked.connect(self._on_toggle_start)
        return self._btn_start

    def _build_logs_section(self) -> QGroupBox:
        group = QGroupBox("Transcriptions & Traductions")
        layout = QVBoxLayout(group)

        self._log_view = QTextEdit()
        self._log_view.setReadOnly(True)
        self._log_view.document().setMaximumBlockCount(200)
        layout.addWidget(self._log_view)

        btn_clear = QPushButton("Vider les logs")
        btn_clear.setFixedHeight(28)
        btn_clear.clicked.connect(self._log_view.clear)
        layout.addWidget(btn_clear)

        return group

    def _separator(self) -> QFrame:
        sep = QFrame()
        sep.setObjectName("separator")
        sep.setFrameShape(QFrame.Shape.HLine)
        return sep

    # ── Populations des listes déroulantes ────────────────────────────────────

    def _populate_languages(self) -> None:
        """Remplit les combobox de langues."""
        for code, meta in LANGUAGE_REGISTRY.items():
            label = f"{meta['flag']} {meta['native_name']}"
            self._combo_user_lang.addItem(label, code)
            self._combo_remote_lang.addItem(label, code)

        # Sélectionner les valeurs sauvegardées
        self._select_combo(self._combo_user_lang, self._settings.user_lang)
        self._select_combo(self._combo_remote_lang, self._settings.remote_lang)

        self._combo_user_lang.currentIndexChanged.connect(self._on_user_lang_changed)
        self._combo_remote_lang.currentIndexChanged.connect(self._on_remote_lang_changed)

    def _populate_devices(self) -> None:
        """Remplit les combobox de périphériques audio."""
        from core.audio_capture import AudioCapture
        from core.virtual_audio import VirtualAudioRouter

        self._combo_mic.addItem("(Défaut système)", None)
        for dev in AudioCapture.list_input_devices():
            self._combo_mic.addItem(dev["name"], dev["index"])

        self._combo_loopback.addItem("(Défaut loopback)", None)
        for dev in AudioCapture.list_loopback_devices():
            self._combo_loopback.addItem(dev["name"], dev["index"])

        router = VirtualAudioRouter()
        self._combo_vcable.addItem("(Auto-détection)", None)
        for dev in router.list_virtual_devices():
            self._combo_vcable.addItem(dev["name"], dev["index"])

        if router.is_available():
            self._lbl_vcable_status.setText("✓")
            self._lbl_vcable_status.setStyleSheet("color: #A6E3A1;")
        else:
            self._lbl_vcable_status.setText("✗")
            self._lbl_vcable_status.setStyleSheet("color: #F38BA8;")

        self._combo_mic.currentIndexChanged.connect(
            lambda: self._settings.__setattr__("input_device_index", self._combo_mic.currentData())
        )
        self._combo_loopback.currentIndexChanged.connect(
            lambda: self._settings.__setattr__("loopback_device_index", self._combo_loopback.currentData())
        )
        self._combo_vcable.currentIndexChanged.connect(
            lambda: self._settings.__setattr__("virtual_cable_index", self._combo_vcable.currentData())
        )

    def _apply_settings(self) -> None:
        """Applique les paramètres sauvegardés à l'UI."""
        self._select_combo(self._combo_mic, self._settings.input_device_index)
        self._select_combo(self._combo_loopback, self._settings.loopback_device_index)
        self._select_combo(self._combo_vcable, self._settings.virtual_cable_index)
        self._btn_pipe_a.setChecked(self._settings.pipeline_a_enabled)
        self._btn_pipe_b.setChecked(self._settings.pipeline_b_enabled)
        self._btn_local_tts.setChecked(self._settings.local_tts_output)

    # ── Slots UI ──────────────────────────────────────────────────────────────

    def _on_toggle_start(self) -> None:
        if self._controller.is_running:
            self._controller.stop()
        else:
            try:
                self._controller.start()
            except Exception as e:
                self._show_error(str(e))

    def _on_swap_languages(self) -> None:
        user_idx = self._combo_user_lang.currentIndex()
        remote_idx = self._combo_remote_lang.currentIndex()
        self._combo_user_lang.setCurrentIndex(remote_idx)
        self._combo_remote_lang.setCurrentIndex(user_idx)
        if self._controller.is_running:
            self._controller.swap_languages()

    def _on_user_lang_changed(self) -> None:
        self._settings.user_lang = self._combo_user_lang.currentData()

    def _on_remote_lang_changed(self) -> None:
        self._settings.remote_lang = self._combo_remote_lang.currentData()

    def _test_mic(self) -> None:
        """Test rapide du microphone."""
        QMessageBox.information(self, "Test micro", "Parlez... (test non implémenté en preview)")

    # ── Slots signaux contrôleur (thread-safe via Qt signals) ─────────────────

    @pyqtSlot(object)
    def _on_translation(self, event: TranslationEvent) -> None:
        """Reçoit un événement de traduction et met à jour l'UI."""
        ts = datetime.fromtimestamp(event.timestamp).strftime("%H:%M:%S")
        color = "#F38BA8" if event.pipeline == "A" else "#89B4FA"
        line = (
            f'<span style="color:#6C7086;">[{ts}]</span> '
            f'<span style="color:{color};">[{event.source_lang}→{event.target_lang}]</span> '
            f'<span style="color:#CDD6F4;">{event.original_text}</span> '
            f'<span style="color:#6C7086;">→</span> '
            f'<span style="color:#A6E3A1;">{event.translated_text}</span>'
        )
        self._log_view.append(line)

        # Afficher l'overlay pour Pipeline B
        if event.pipeline == "B":
            self._overlay.show_subtitle(
                event.translated_text,
                source_lang=event.source_lang,
                target_lang=event.target_lang,
                duration_ms=self._settings.overlay_duration_ms,
            )

    @pyqtSlot(object)
    def _on_status_change(self, state: ControllerState) -> None:
        self._update_status_dot(state)
        self._lbl_status.setText(STATUS_LABELS.get(state, ""))

        is_running = state == ControllerState.RUNNING
        self._btn_start.setProperty("running", is_running)
        self._btn_start.setText("■  ARRÊTER" if is_running else "▶  DÉMARRER")
        self._btn_start.style().unpolish(self._btn_start)
        self._btn_start.style().polish(self._btn_start)

    @pyqtSlot(str)
    def _on_error(self, message: str) -> None:
        self._show_error(message)

    @pyqtSlot(int)
    def _on_latency(self, latency_ms: int) -> None:
        color = "#A6E3A1" if latency_ms < 2000 else "#F9E2AF" if latency_ms < 3000 else "#F38BA8"
        self._lbl_latency.setText(f"{latency_ms} ms")
        self._lbl_latency.setStyleSheet(f"color: {color}; font-size: 11px;")

    @pyqtSlot()
    def _toggle_overlay(self) -> None:
        self._overlay.toggle_visible()

    @pyqtSlot()
    def _toggle_visibility(self) -> None:
        self.show() if self.isHidden() else self.hide()

    def request_swap_languages(self) -> None:
        self._sig_request_swap.emit()

    def request_toggle_overlay(self) -> None:
        self._sig_request_toggle_overlay.emit()

    def request_toggle_visibility(self) -> None:
        self._sig_request_toggle_visibility.emit()

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _update_status_dot(self, state: ControllerState) -> None:
        color = STATUS_COLORS.get(state, "#6C7086")
        self._status_dot.setStyleSheet(
            f"background-color: {color}; border-radius: 6px;"
            f" min-width: 12px; min-height: 12px; max-width: 12px; max-height: 12px;"
        )

    def _show_error(self, message: str) -> None:
        logger.error("UI Error : %s", message)
        QMessageBox.critical(self, "Erreur VoxShield", message)

    @staticmethod
    def _select_combo(combo: QComboBox, value: str) -> None:
        """Sélectionne l'item dont la data correspond à value."""
        for i in range(combo.count()):
            if combo.itemData(i) == value:
                combo.setCurrentIndex(i)
                return

    def closeEvent(self, event) -> None:
        """Arrête le contrôleur proprement à la fermeture."""
        if self._controller.is_running:
            self._controller.stop()
        self._overlay.close()
        event.accept()

    def open_settings(self) -> None:
        """Ouvre la fenêtre des paramètres."""
        from ui.settings_window import SettingsWindow
        dlg = SettingsWindow(self._settings, self)
        dlg.exec()
