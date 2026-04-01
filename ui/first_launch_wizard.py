#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VoxShield — Assistant de premier lancement (5 étapes).
Guidage de l'utilisateur pour la configuration initiale.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QStackedWidget, QWidget, QGroupBox, QTextEdit,
    QDialogButtonBox, QMessageBox,
)

from config.language_registry import LANGUAGE_REGISTRY
from config.settings_manager import SettingsManager
from core.main_controller import MainController
from utils.logger import get_logger

logger = get_logger("WIZARD")


class FirstLaunchWizard(QDialog):
    """
    Wizard en 5 étapes pour le premier démarrage.
    Étape 1 : Vérification Virtual Cable
    Étape 2 : Sélection des langues
    Étape 3 : Sélection microphone
    Étape 4 : Configuration visioconférence
    Étape 5 : Test bout-en-bout
    """

    def __init__(
        self,
        settings: SettingsManager,
        controller: MainController,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._settings = settings
        self._controller = controller
        self._current_step = 0

        self.setWindowTitle("Bienvenue dans VoxShield")
        self.setFixedSize(500, 420)
        self.setModal(True)

        self._build_ui()
        self._show_step(0)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Titre de l'étape
        self._lbl_step = QLabel()
        self._lbl_step.setStyleSheet("font-size: 16px; font-weight: bold; color: #2E75B6;")
        layout.addWidget(self._lbl_step)

        # Contenu (pages empilées)
        self._stack = QStackedWidget()
        self._stack.addWidget(self._build_step1())
        self._stack.addWidget(self._build_step2())
        self._stack.addWidget(self._build_step3())
        self._stack.addWidget(self._build_step4())
        self._stack.addWidget(self._build_step5())
        layout.addWidget(self._stack, stretch=1)

        # Navigation
        nav = QHBoxLayout()
        self._btn_prev = QPushButton("← Précédent")
        self._btn_prev.clicked.connect(self._prev_step)
        self._btn_prev.setEnabled(False)

        self._btn_next = QPushButton("Suivant →")
        self._btn_next.clicked.connect(self._next_step)

        self._btn_finish = QPushButton("Terminer ✓")
        self._btn_finish.clicked.connect(self._finish)
        self._btn_finish.hide()

        nav.addWidget(self._btn_prev)
        nav.addStretch()
        nav.addWidget(self._btn_next)
        nav.addWidget(self._btn_finish)
        layout.addLayout(nav)

    # ── Pages ─────────────────────────────────────────────────────────────────

    def _build_step1(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.addWidget(QLabel(
            "VoxShield nécessite un <b>Virtual Cable audio</b> pour injecter "
            "la voix traduite dans votre visioconférence."
        ))
        from core.virtual_audio import VirtualAudioRouter
        router = VirtualAudioRouter()
        if router.is_available():
            status = QLabel(f"✅ Virtual Cable détecté : <b>{router.device_name}</b>")
            status.setStyleSheet("color: #A6E3A1; font-size: 14px;")
        else:
            status = QLabel("❌ Virtual Cable non détecté")
            status.setStyleSheet("color: #F38BA8; font-size: 14px;")

            from utils.platform_utils import get_virtual_cable_install_info
            info = get_virtual_cable_install_info()
            instructions = QTextEdit()
            instructions.setReadOnly(True)
            instructions.setPlainText(
                f"Télécharger : {info['url']}\n\n" +
                "\n".join(info["instructions"])
            )
            instructions.setMaximumHeight(120)
            layout.addWidget(instructions)

        layout.addWidget(status)
        layout.addStretch()
        return w

    def _build_step2(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.addWidget(QLabel("Sélectionnez vos langues de travail :"))

        row_user = QHBoxLayout()
        row_user.addWidget(QLabel("Ma langue :"))
        self._combo_user = QComboBox()
        for code, meta in LANGUAGE_REGISTRY.items():
            self._combo_user.addItem(f"{meta['flag']} {meta['native_name']}", code)
        self._select_combo(self._combo_user, self._settings.user_lang)
        row_user.addWidget(self._combo_user)
        layout.addLayout(row_user)

        row_remote = QHBoxLayout()
        row_remote.addWidget(QLabel("Langue distante :"))
        self._combo_remote = QComboBox()
        for code, meta in LANGUAGE_REGISTRY.items():
            self._combo_remote.addItem(f"{meta['flag']} {meta['native_name']}", code)
        self._select_combo(self._combo_remote, self._settings.remote_lang)
        row_remote.addWidget(self._combo_remote)
        layout.addLayout(row_remote)

        layout.addStretch()
        return w

    def _build_step3(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.addWidget(QLabel("Sélectionnez votre microphone :"))

        from core.audio_capture import AudioCapture
        self._combo_mic_wizard = QComboBox()
        self._combo_mic_wizard.addItem("(Défaut système)", None)
        for dev in AudioCapture.list_input_devices():
            self._combo_mic_wizard.addItem(dev["name"], dev["index"])

        layout.addWidget(self._combo_mic_wizard)
        layout.addWidget(QLabel("⚠️ N'utilisez PAS CABLE Output comme microphone ici."))
        layout.addStretch()
        return w

    def _build_step4(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.addWidget(QLabel(
            "<b>Configuration dans votre application de visioconférence :</b>"
        ))
        instructions = QTextEdit()
        instructions.setReadOnly(True)
        instructions.setHtml("""
<ul>
<li><b>Google Meet</b> : ⚙️ Paramètres → Audio → Microphone → <i>CABLE Input (VB-Audio)</i></li>
<li><b>Zoom</b> : ⚙️ Paramètres → Audio → Microphone → <i>CABLE Input</i></li>
<li><b>Teams</b> : ⚙️ Paramètres → Périphériques → Micro → <i>CABLE Input</i></li>
<li><b>Webex</b> : ⚙️ Paramètres → Audio → Microphone → <i>CABLE Input</i></li>
<li><b>Discord</b> : ⚙️ Paramètres → Voix → Périphérique → <i>CABLE Input</i></li>
</ul>
<p><b>Votre interlocuteur entendra alors votre voix traduite.</b></p>
""")
        layout.addWidget(instructions)
        layout.addStretch()
        return w

    def _build_step5(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.addWidget(QLabel(
            "Configuration terminée ! Cliquez <b>Terminer</b> pour démarrer l'application."
        ))
        layout.addWidget(QLabel(
            "\n📝 Raccourcis par défaut :\n"
            "• Ctrl+Shift+T : Démarrer / Arrêter\n"
            "• Ctrl+Shift+M : Mute micro\n"
            "• Ctrl+Shift+S : Afficher/Masquer sous-titres\n"
            "• Ctrl+Shift+I : Inverser les langues"
        ))
        layout.addStretch()
        return w

    # ── Navigation ────────────────────────────────────────────────────────────

    def _show_step(self, step: int) -> None:
        titles = [
            "Étape 1/5 — Virtual Cable",
            "Étape 2/5 — Langues",
            "Étape 3/5 — Microphone",
            "Étape 4/5 — Visioconférence",
            "Étape 5/5 — Prêt !",
        ]
        self._current_step = step
        self._stack.setCurrentIndex(step)
        self._lbl_step.setText(titles[step])
        self._btn_prev.setEnabled(step > 0)
        is_last = step == 4
        self._btn_next.setVisible(not is_last)
        self._btn_finish.setVisible(is_last)

    def _next_step(self) -> None:
        self._save_step(self._current_step)
        if self._current_step < 4:
            self._show_step(self._current_step + 1)

    def _prev_step(self) -> None:
        if self._current_step > 0:
            self._show_step(self._current_step - 1)

    def _save_step(self, step: int) -> None:
        if step == 1:
            self._settings.user_lang = self._combo_user.currentData()
            self._settings.remote_lang = self._combo_remote.currentData()
        elif step == 2:
            idx = self._combo_mic_wizard.currentData()
            self._settings.input_device_index = idx

    def _finish(self) -> None:
        self._save_step(1)
        self._save_step(2)
        self._settings.mark_first_launch_done()
        self.accept()

    @staticmethod
    def _select_combo(combo: QComboBox, value: str) -> None:
        for i in range(combo.count()):
            if combo.itemData(i) == value:
                combo.setCurrentIndex(i)
                return
