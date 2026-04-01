#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VoxShield — Fenêtre overlay de sous-titres flottants.
Fenêtre frameless, toujours au premier plan, semi-transparente,
avec animation fade-in/fade-out et drag-and-drop pour repositionnement.
"""

from PyQt6.QtCore import (
    Qt, QPropertyAnimation, QTimer, QPoint, pyqtProperty, pyqtSignal
)
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QFont
from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout, QApplication

from utils.logger import get_logger

logger = get_logger("UI")


class OverlayWindow(QWidget):
    """
    Fenêtre de sous-titres flottante, frameless, always-on-top.

    Caractéristiques :
    - Fond noir semi-transparent avec coins arrondis
    - Texte blanc, police Arial/Segoe UI 16pt
    - Fade-in 200ms / fade-out 500ms
    - Drag-and-drop pour repositionner
    - Badge langue source → cible
    - Disparition automatique après N secondes
    """

    # Signal émis quand l'overlay devient visible/invisible
    visibility_changed = pyqtSignal(bool)

    def __init__(
        self,
        screen_position: tuple = ("center", "bottom"),
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._position_hint = screen_position
        self._drag_offset = QPoint()
        self._is_dragging = False
        self._opacity_value = 0.0

        self._setup_window()
        self._setup_ui()
        self._setup_animations()
        self._setup_timer()

        # Positionner selon les préférences
        self._position_to_screen()

    # ── Configuration fenêtre ─────────────────────────────────────────────────

    def _setup_window(self) -> None:
        """Configure les propriétés de la fenêtre overlay."""
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setMinimumWidth(300)
        self.setMaximumWidth(900)

    def _setup_ui(self) -> None:
        """Crée les widgets internes."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(4)

        # Badge langue
        self._lang_badge = QLabel("")
        self._lang_badge.setObjectName("lang_badge")
        self._lang_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font_badge = QFont("Segoe UI", 9)
        self._lang_badge.setFont(font_badge)
        self._lang_badge.setStyleSheet(
            "color: rgba(200, 200, 200, 200);"
            "background: transparent;"
        )

        # Texte principal
        self._text_label = QLabel("")
        self._text_label.setObjectName("subtitle_text")
        self._text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._text_label.setWordWrap(True)
        font_text = QFont("Segoe UI", 16)
        font_text.setWeight(QFont.Weight.Medium)
        self._text_label.setFont(font_text)
        self._text_label.setStyleSheet(
            "color: white;"
            "background: transparent;"
        )

        layout.addWidget(self._lang_badge)
        layout.addWidget(self._text_label)

    def _setup_animations(self) -> None:
        """Configure les animations de fade-in et fade-out."""
        self._fade_in = QPropertyAnimation(self, b"windowOpacity")
        self._fade_in.setDuration(200)
        self._fade_in.setStartValue(0.0)
        self._fade_in.setEndValue(0.85)

        self._fade_out = QPropertyAnimation(self, b"windowOpacity")
        self._fade_out.setDuration(500)
        self._fade_out.setStartValue(0.85)
        self._fade_out.setEndValue(0.0)
        self._fade_out.finished.connect(self.hide)

    def _setup_timer(self) -> None:
        """Timer pour la disparition automatique."""
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self._start_fade_out)

    # ── API publique ──────────────────────────────────────────────────────────

    def show_subtitle(
        self,
        text: str,
        source_lang: str = "",
        target_lang: str = "",
        duration_ms: int = 5000,
    ) -> None:
        """
        Affiche un sous-titre avec animation fade-in.

        Args:
            text: Texte traduit à afficher.
            source_lang: Code ISO de la langue source (ex. 'fr').
            target_lang: Code ISO de la langue cible (ex. 'en').
            duration_ms: Durée d'affichage avant disparition.
        """
        self._hide_timer.stop()
        self._fade_out.stop()

        from config.language_registry import get_display_name
        if source_lang and target_lang:
            badge_text = f"{get_display_name(source_lang)} → {get_display_name(target_lang)}"
            self._lang_badge.setText(badge_text)
            self._lang_badge.setVisible(True)
        else:
            self._lang_badge.setVisible(False)

        self._text_label.setText(text)
        self.adjustSize()

        if not self.isVisible():
            self.setWindowOpacity(0.0)
            self.show()
            self._fade_in.start()
            self.visibility_changed.emit(True)
        else:
            self._fade_in.start()

        self._hide_timer.start(duration_ms)

    def clear(self) -> None:
        """Efface le texte et lance la disparition."""
        self._hide_timer.stop()
        self._start_fade_out()

    def set_position(self, x: int, y: int) -> None:
        """Déplace l'overlay à la position spécifiée (coordonnées écran)."""
        self.move(x, y)

    def set_opacity(self, opacity: float) -> None:
        """Définit l'opacité de fond (0.0 à 1.0)."""
        self._opacity_value = max(0.0, min(1.0, opacity))
        self.update()

    def set_font_size(self, size: int) -> None:
        """Change la taille de police du texte principal."""
        font = self._text_label.font()
        font.setPointSize(size)
        self._text_label.setFont(font)

    def toggle_visible(self) -> None:
        """Affiche ou cache l'overlay."""
        if self.isVisible():
            self._start_fade_out()
        else:
            self.show()

    # ── Peinture personnalisée ────────────────────────────────────────────────

    def paintEvent(self, event) -> None:
        """Dessine le fond arrondi semi-transparent."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        path = QPainterPath()
        path.addRoundedRect(
            0, 0, self.width(), self.height(),
            12, 12,
        )

        painter.fillPath(path, QColor(0, 0, 0, int(220 * self._opacity_value if self._opacity_value > 0 else 200)))
        painter.end()

    # ── Drag-and-drop ─────────────────────────────────────────────────────────

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._is_dragging = True
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event) -> None:
        if self._is_dragging and event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)

    def mouseReleaseEvent(self, event) -> None:
        self._is_dragging = False

    # ── Helpers privés ────────────────────────────────────────────────────────

    def _start_fade_out(self) -> None:
        """Lance l'animation de disparition."""
        self._fade_in.stop()
        self._fade_out.start()
        self.visibility_changed.emit(False)

    def _position_to_screen(self) -> None:
        """Positionne l'overlay selon la préférence (center/bottom par défaut)."""
        screen = QApplication.primaryScreen()
        if not screen:
            return

        geo = screen.availableGeometry()
        h_hint, v_hint = self._position_hint

        self.adjustSize()
        w, h = self.width() or 400, self.height() or 80

        if h_hint == "left":
            x = geo.left() + 20
        elif h_hint == "right":
            x = geo.right() - w - 20
        else:
            x = geo.left() + (geo.width() - w) // 2

        if v_hint == "top":
            y = geo.top() + 40
        elif v_hint == "center":
            y = geo.top() + (geo.height() - h) // 2
        else:
            y = geo.bottom() - h - 60

        self.move(x, y)
