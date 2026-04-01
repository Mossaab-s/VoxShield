#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VoxShield — Fenêtre de paramètres (5 onglets).
"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QTabWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QComboBox, QPushButton, QLineEdit, QSlider,
    QCheckBox, QSpinBox, QDoubleSpinBox, QGroupBox,
    QDialogButtonBox, QFormLayout, QMessageBox,
)

from config.default_settings import WHISPER_MODEL_SIZES, STT_MODES, TRANSLATION_MODES, TTS_MODES
from config.settings_manager import SettingsManager
from utils.logger import get_logger

logger = get_logger("UI")


class SettingsWindow(QDialog):
    """Fenêtre de paramètres avec 5 onglets."""

    def __init__(self, settings: SettingsManager, parent=None) -> None:
        super().__init__(parent)
        self._settings = settings
        self._changed = False

        self.setWindowTitle("Paramètres — VoxShield")
        self.setFixedSize(520, 480)
        self.setModal(True)

        layout = QVBoxLayout(self)

        self._tabs = QTabWidget()
        self._tabs.addTab(self._build_audio_tab(), "Audio")
        self._tabs.addTab(self._build_translation_tab(), "Traduction")
        self._tabs.addTab(self._build_tts_tab(), "Synthèse vocale")
        self._tabs.addTab(self._build_ui_tab(), "Interface")
        self._tabs.addTab(self._build_hotkeys_tab(), "Raccourcis")

        layout.addWidget(self._tabs)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save_and_close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    # ── Onglet Audio ─────────────────────────────────────────────────────────

    def _build_audio_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setSpacing(10)

        # Modèle Whisper
        self._combo_model = QComboBox()
        for m in WHISPER_MODEL_SIZES:
            self._combo_model.addItem(m)
        self._combo_model.setCurrentText(self._settings.stt_model_size)
        form.addRow("Modèle Whisper :", self._combo_model)

        # Mode STT
        self._combo_stt_mode = QComboBox()
        for m in STT_MODES:
            self._combo_stt_mode.addItem(m)
        self._combo_stt_mode.setCurrentText(self._settings.stt_mode)
        form.addRow("Mode STT :", self._combo_stt_mode)

        # Agressivité VAD
        self._slider_vad = QSlider(Qt.Orientation.Horizontal)
        self._slider_vad.setRange(0, 3)
        self._slider_vad.setValue(self._settings.vad_mode)
        self._slider_vad.setTickPosition(QSlider.TickPosition.TicksBelow)
        self._lbl_vad = QLabel(f"Agressivité : {self._settings.vad_mode}")
        self._slider_vad.valueChanged.connect(
            lambda v: self._lbl_vad.setText(f"Agressivité : {v}")
        )
        form.addRow(self._lbl_vad, self._slider_vad)

        # Silence avant flush
        self._spin_silence = QSpinBox()
        self._spin_silence.setRange(200, 2000)
        self._spin_silence.setSingleStep(50)
        self._spin_silence.setSuffix(" ms")
        self._spin_silence.setValue(self._settings.vad_silence_ms)
        form.addRow("Silence avant flush :", self._spin_silence)

        return w

    # ── Onglet Traduction ─────────────────────────────────────────────────────

    def _build_translation_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setSpacing(10)

        # Mode traduction
        self._combo_trans_mode = QComboBox()
        for m in TRANSLATION_MODES:
            self._combo_trans_mode.addItem(m)
        self._combo_trans_mode.setCurrentText(self._settings.translation_mode)
        form.addRow("Mode traduction :", self._combo_trans_mode)

        # Clé DeepL
        self._edit_deepl_key = QLineEdit()
        self._edit_deepl_key.setEchoMode(QLineEdit.EchoMode.Password)
        self._edit_deepl_key.setPlaceholderText(
            "Clé API DeepL (stockée en sécurité dans le gestionnaire OS)"
        )
        existing = self._settings.get_api_key("deepl")
        if existing:
            self._edit_deepl_key.setPlaceholderText("●●●●●●●● (clé configurée)")
        form.addRow("Clé DeepL :", self._edit_deepl_key)

        # Bouton test DeepL
        btn_test = QPushButton("Tester la connexion DeepL")
        btn_test.clicked.connect(self._test_deepl)
        form.addRow("", btn_test)

        # Taille cache
        self._spin_cache = QSpinBox()
        self._spin_cache.setRange(50, 5000)
        self._spin_cache.setValue(self._settings.get("translation", "cache_size", 500))
        self._spin_cache.setSuffix(" entrées")
        form.addRow("Taille cache :", self._spin_cache)

        return w

    # ── Onglet TTS ────────────────────────────────────────────────────────────

    def _build_tts_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setSpacing(10)

        # Mode TTS
        self._combo_tts_mode = QComboBox()
        for m in TTS_MODES:
            self._combo_tts_mode.addItem(m)
        self._combo_tts_mode.setCurrentText(self._settings.tts_mode)
        form.addRow("Mode TTS :", self._combo_tts_mode)

        # Clé OpenAI
        self._edit_openai_key = QLineEdit()
        self._edit_openai_key.setEchoMode(QLineEdit.EchoMode.Password)
        self._edit_openai_key.setPlaceholderText("Clé API OpenAI (facultatif)")
        existing = self._settings.get_api_key("openai")
        if existing:
            self._edit_openai_key.setPlaceholderText("●●●●●●●● (clé configurée)")
        form.addRow("Clé OpenAI :", self._edit_openai_key)

        # Vitesse TTS
        self._spin_speed = QDoubleSpinBox()
        self._spin_speed.setRange(0.5, 2.0)
        self._spin_speed.setSingleStep(0.1)
        self._spin_speed.setSuffix("x")
        self._spin_speed.setValue(self._settings.tts_speed)
        form.addRow("Vitesse :", self._spin_speed)

        # Bouton test voix
        btn_test_voice = QPushButton("Tester la voix")
        btn_test_voice.clicked.connect(self._test_voice)
        form.addRow("", btn_test_voice)

        return w

    # ── Onglet Interface ──────────────────────────────────────────────────────

    def _build_ui_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setSpacing(10)

        # Position overlay
        pos = self._settings.overlay_position
        self._combo_overlay_h = QComboBox()
        for p in ["left", "center", "right"]:
            self._combo_overlay_h.addItem(p)
        self._combo_overlay_h.setCurrentText(pos[0] if pos else "center")
        form.addRow("Position overlay (H) :", self._combo_overlay_h)

        self._combo_overlay_v = QComboBox()
        for p in ["top", "center", "bottom"]:
            self._combo_overlay_v.addItem(p)
        self._combo_overlay_v.setCurrentText(pos[1] if len(pos) > 1 else "bottom")
        form.addRow("Position overlay (V) :", self._combo_overlay_v)

        # Opacité
        self._slider_opacity = QSlider(Qt.Orientation.Horizontal)
        self._slider_opacity.setRange(30, 100)
        self._slider_opacity.setValue(int(self._settings.overlay_opacity * 100))
        self._lbl_opacity = QLabel(f"Opacité : {int(self._settings.overlay_opacity * 100)}%")
        self._slider_opacity.valueChanged.connect(
            lambda v: self._lbl_opacity.setText(f"Opacité : {v}%")
        )
        form.addRow(self._lbl_opacity, self._slider_opacity)

        # Taille police
        self._spin_fontsize = QSpinBox()
        self._spin_fontsize.setRange(10, 24)
        self._spin_fontsize.setValue(self._settings.overlay_font_size)
        self._spin_fontsize.setSuffix(" pt")
        form.addRow("Taille police :", self._spin_fontsize)

        # Durée affichage
        self._spin_duration = QSpinBox()
        self._spin_duration.setRange(1000, 10000)
        self._spin_duration.setSingleStep(500)
        self._spin_duration.setSuffix(" ms")
        self._spin_duration.setValue(self._settings.overlay_duration_ms)
        form.addRow("Durée sous-titres :", self._spin_duration)

        return w

    # ── Onglet Raccourcis ─────────────────────────────────────────────────────

    def _build_hotkeys_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setSpacing(10)

        actions = {
            "start_stop": "Démarrer / Arrêter",
            "mute_mic": "Mute micro",
            "toggle_overlay": "Afficher/Masquer overlay",
            "swap_languages": "Inverser les langues",
            "show_hide": "Afficher/Masquer fenêtre",
        }

        self._hotkey_edits: dict[str, QLineEdit] = {}
        for action, label in actions.items():
            edit = QLineEdit(self._settings.get_hotkey(action))
            edit.setPlaceholderText("ex. ctrl+shift+t")
            self._hotkey_edits[action] = edit
            form.addRow(f"{label} :", edit)

        return w

    # ── Actions ───────────────────────────────────────────────────────────────

    def _test_deepl(self) -> None:
        key = self._edit_deepl_key.text().strip()
        if not key:
            key = self._settings.get_api_key("deepl")
        if not key:
            QMessageBox.warning(self, "DeepL", "Entrez d'abord une clé API DeepL.")
            return
        try:
            import deepl
            translator = deepl.Translator(key)
            usage = translator.get_usage()
            QMessageBox.information(
                self, "DeepL OK",
                f"Connexion réussie !\nCaractères utilisés : {usage.character.count:,}"
            )
        except Exception as e:
            QMessageBox.critical(self, "DeepL Erreur", str(e))

    def _test_voice(self) -> None:
        QMessageBox.information(self, "Test voix", "Test TTS non disponible en dehors d'une session active.")

    def _save_and_close(self) -> None:
        """Sauvegarde tous les paramètres et ferme la fenêtre."""
        s = self._settings

        # Audio
        s.set("stt", "model_size", self._combo_model.currentText())
        s.set("stt", "mode", self._combo_stt_mode.currentText())
        s.set("audio", "vad_mode", self._slider_vad.value())
        s.set("audio", "vad_silence_ms", self._spin_silence.value())

        # Traduction
        s.set("translation", "mode", self._combo_trans_mode.currentText())
        s.set("translation", "cache_size", self._spin_cache.value())
        deepl_key = self._edit_deepl_key.text().strip()
        if deepl_key:
            s.set_api_key("deepl", deepl_key)

        # TTS
        s.set("tts", "mode", self._combo_tts_mode.currentText())
        s.set("tts", "speed", self._spin_speed.value())
        openai_key = self._edit_openai_key.text().strip()
        if openai_key:
            s.set_api_key("openai", openai_key)
            s.set_api_key("openai_tts", openai_key)

        # UI
        s.set("ui", "overlay_position", [
            self._combo_overlay_h.currentText(),
            self._combo_overlay_v.currentText(),
        ])
        s.set("ui", "overlay_opacity", self._slider_opacity.value() / 100)
        s.set("ui", "overlay_font_size", self._spin_fontsize.value())
        s.set("ui", "overlay_duration_ms", self._spin_duration.value())

        # Hotkeys
        for action, edit in self._hotkey_edits.items():
            val = edit.text().strip()
            if val:
                s.set_hotkey(action, val)

        logger.info("Paramètres sauvegardés")
        self.accept()
