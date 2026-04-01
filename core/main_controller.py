#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VoxShield — Orchestrateur central des pipelines audio.

Pipeline A (LOCAL → DISTANT) :
  Micro → VAD → STT → Traduction → TTS → Virtual Cable

Pipeline B (DISTANT → LOCAL) :
  Loopback système → VAD → STT → Traduction → Overlay + TTS optionnel

Toutes les communications entre threads passent par queue.Queue.
Aucun état partagé mutable sans verrou explicite.
"""

import queue
import threading
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Callable, Optional

from config.settings_manager import SettingsManager
from core.audio_capture import AudioCapture
from core.audio_buffer import AudioBuffer
from core.vad_engine import VADEngine
from core.stt_engine import STTEngine, STTResult
from core.translation_engine import TranslationEngine, TranslationResult
from core.tts_engine import TTSEngine, AudioData
from core.virtual_audio import VirtualAudioRouter
from utils.logger import get_logger

logger = get_logger("CTRL")

QUEUE_MAX = 10  # Taille maximale des queues inter-threads


class ControllerState(Enum):
    STOPPED = auto()
    STARTING = auto()
    RUNNING = auto()
    STOPPING = auto()
    ERROR = auto()


@dataclass
class TranslationEvent:
    """Événement émis après traduction (affiché dans l'UI et les logs)."""
    original_text: str
    translated_text: str
    source_lang: str
    target_lang: str
    pipeline: str           # 'A' ou 'B'
    timestamp: float = field(default_factory=time.time)
    engine_used: str = ""
    latency_ms: int = 0


class MainController:
    """
    Orchestre les deux pipelines audio en threads parallèles.

    Callbacks disponibles :
    - on_translation : appelé à chaque traduction complète
    - on_status_change : appelé quand l'état du contrôleur change
    - on_error : appelé en cas d'erreur non-fatale
    - on_latency_update : appelé avec la latence mesurée
    """

    def __init__(self, settings: SettingsManager) -> None:
        self._settings = settings
        self._state = ControllerState.STOPPED
        self._state_lock = threading.Lock()

        # Callbacks UI
        self.on_translation: Optional[Callable[[TranslationEvent], None]] = None
        self.on_status_change: Optional[Callable[[ControllerState], None]] = None
        self.on_error: Optional[Callable[[str], None]] = None
        self.on_latency_update: Optional[Callable[[int], None]] = None

        # Composants (initialisés au start)
        self._capture_a: Optional[AudioCapture] = None
        self._capture_b: Optional[AudioCapture] = None
        self._vad_a: Optional[VADEngine] = None
        self._vad_b: Optional[VADEngine] = None
        self._stt_a: Optional[STTEngine] = None
        self._stt_b: Optional[STTEngine] = None
        self._translation_a: Optional[TranslationEngine] = None
        self._translation_b: Optional[TranslationEngine] = None
        self._tts_a: Optional[TTSEngine] = None
        self._tts_b: Optional[TTSEngine] = None
        self._router: Optional[VirtualAudioRouter] = None

        # Queues inter-threads
        self._q_stt_a: queue.Queue[bytes] = queue.Queue(maxsize=QUEUE_MAX)
        self._q_stt_b: queue.Queue[bytes] = queue.Queue(maxsize=QUEUE_MAX)
        self._q_trans_a: queue.Queue[STTResult] = queue.Queue(maxsize=QUEUE_MAX)
        self._q_trans_b: queue.Queue[STTResult] = queue.Queue(maxsize=QUEUE_MAX)
        self._q_tts_a: queue.Queue[TranslationResult] = queue.Queue(maxsize=QUEUE_MAX)
        self._q_tts_b: queue.Queue[TranslationResult] = queue.Queue(maxsize=QUEUE_MAX)

        # Threads
        self._threads: list[threading.Thread] = []
        self._stop_event = threading.Event()

        # Métriques
        self._last_latency_ms = 0

        # Mute micro (Pipeline A pausé)
        self._mic_muted = False
        self._mic_muted_lock = threading.Lock()

    # ── Démarrage / Arrêt ─────────────────────────────────────────────────────

    def start(self) -> None:
        """Démarre les deux pipelines audio."""
        with self._state_lock:
            if self._state == ControllerState.RUNNING:
                logger.warning("Contrôleur déjà en cours")
                return
            self._set_state(ControllerState.STARTING)

        try:
            self._stop_event.clear()
            self._init_components()
            self._start_threads()
            self._set_state(ControllerState.RUNNING)
            logger.info("VoxShield démarré")

        except Exception as e:
            logger.error("Erreur au démarrage : %s", e)
            self._set_state(ControllerState.ERROR)
            self._emit_error(str(e))
            raise

    def stop(self) -> None:
        """Arrête tous les pipelines proprement."""
        with self._state_lock:
            if self._state == ControllerState.STOPPED:
                return
            self._set_state(ControllerState.STOPPING)

        logger.info("Arrêt en cours...")
        self._stop_event.set()

        # Arrêter les captures audio en premier
        if self._capture_a:
            self._capture_a.stop()
        if self._capture_b:
            self._capture_b.stop()

        # Vider les queues pour débloquer les threads en attente
        for q in [self._q_stt_a, self._q_stt_b, self._q_trans_a,
                  self._q_trans_b, self._q_tts_a, self._q_tts_b]:
            try:
                while not q.empty():
                    q.get_nowait()
            except Exception:
                pass

        # Attendre la fin des threads
        for t in self._threads:
            t.join(timeout=5.0)
        self._threads.clear()

        self._set_state(ControllerState.STOPPED)
        logger.info("VoxShield arrêté")

    def toggle(self) -> None:
        """Démarre si arrêté, arrête si en cours."""
        if self._state == ControllerState.RUNNING:
            self.stop()
        else:
            self.start()

    # ── Contrôles rapides ─────────────────────────────────────────────────────

    def mute_mic(self, muted: bool) -> None:
        """Active/désactive le mute du microphone (Pipeline A)."""
        with self._mic_muted_lock:
            self._mic_muted = muted
        logger.info("Micro %s", "muet" if muted else "actif")

    def toggle_mute(self) -> None:
        with self._mic_muted_lock:
            self._mic_muted = not self._mic_muted

    def swap_languages(self) -> None:
        """Inverse les langues source/cible en temps réel."""
        src = self._settings.user_lang
        tgt = self._settings.remote_lang
        self._settings.user_lang = tgt
        self._settings.remote_lang = src

        if self._translation_a:
            self._translation_a.swap_languages()
        if self._translation_b:
            self._translation_b.swap_languages()
        if self._tts_a:
            self._tts_a.set_language(self._settings.remote_lang)
        if self._tts_b:
            self._tts_b.set_language(self._settings.user_lang)

        logger.info("Langues inversées : %s ↔ %s", src, tgt)

    # ── Initialisation des composants ──────────────────────────────────────────

    def _init_components(self) -> None:
        """Initialise tous les composants audio et IA."""
        s = self._settings
        user_lang = s.user_lang
        remote_lang = s.remote_lang

        # --- Virtual Cable (Pipeline A) ---
        self._router = VirtualAudioRouter()
        if not self._router.is_available() and s.pipeline_a_enabled:
            logger.warning("Virtual Cable absent — Pipeline A désactivé automatiquement")
            self._settings.pipeline_a_enabled = False
            self._emit_error(
                "Virtual Cable non détecté. Installez VB-Audio Cable et relancez l'application."
            )

        # --- Pipeline A : Micro → STT → Traduction → TTS → Virtual Cable ---
        if s.pipeline_a_enabled:
            self._capture_a = AudioCapture(
                device_index=s.input_device_index,
                sample_rate=s.sample_rate,
                chunk_ms=s.chunk_ms,
            )
            self._vad_a = VADEngine(
                mode=s.vad_mode,
                sample_rate=s.sample_rate,
                chunk_ms=s.chunk_ms,
                min_speech_ms=s.vad_min_speech_ms,
                max_silence_ms=s.vad_silence_ms,
            )
            self._stt_a = STTEngine(
                mode=s.stt_mode,
                model_size=s.stt_model_size,
                language=user_lang,
            )
            self._translation_a = TranslationEngine(
                mode=s.translation_mode,
                source_lang=user_lang,
                target_lang=remote_lang,
                deepl_api_key=s.get_api_key("deepl"),
                cache_size=s.get("translation", "cache_size", 500),
            )
            self._tts_a = TTSEngine(
                mode=s.tts_mode,
                language=remote_lang,
                speed=s.tts_speed,
                openai_api_key=s.get_api_key("openai_tts"),
                models_dir=s.piper_models_dir,
            )

        # --- Pipeline B : Loopback → STT → Traduction → Overlay ---
        if s.pipeline_b_enabled:
            self._capture_b = AudioCapture(
                device_index=s.loopback_device_index,
                sample_rate=s.sample_rate,
                chunk_ms=s.chunk_ms,
                loopback=True,
            )
            self._vad_b = VADEngine(
                mode=s.vad_mode,
                sample_rate=s.sample_rate,
                chunk_ms=s.chunk_ms,
                min_speech_ms=s.vad_min_speech_ms,
                max_silence_ms=s.vad_silence_ms,
            )
            self._stt_b = STTEngine(
                mode=s.stt_mode,
                model_size=s.stt_model_size,
                language=remote_lang,
            )
            self._translation_b = TranslationEngine(
                mode=s.translation_mode,
                source_lang=remote_lang,
                target_lang=user_lang,
                deepl_api_key=s.get_api_key("deepl"),
                cache_size=s.get("translation", "cache_size", 500),
            )
            if s.local_tts_output:
                self._tts_b = TTSEngine(
                    mode=s.tts_mode,
                    language=user_lang,
                    speed=s.tts_speed,
                    openai_api_key=s.get_api_key("openai_tts"),
                    models_dir=s.piper_models_dir,
                )

        # Précharger les modèles dans des threads dédiés
        self._preload_models()

    def _preload_models(self) -> None:
        """Précharge les modèles IA dans des threads dédiés."""
        def _load(engine, name: str):
            try:
                logger.info("Chargement modèle %s...", name)
                # STTEngine expose load_model(), TTSEngine expose preload_model()
                if hasattr(engine, "load_model"):
                    engine.load_model()
                elif hasattr(engine, "preload_model"):
                    engine.preload_model()
                logger.info("Modèle %s prêt", name)
            except Exception as e:
                logger.error("Erreur chargement %s : %s", name, e)
                self._emit_error(f"Impossible de charger le modèle {name}: {e}")

        preload_tasks = []
        if self._stt_a:
            preload_tasks.append((self._stt_a, "STT-A"))
        if self._stt_b and self._stt_b is not self._stt_a:
            preload_tasks.append((self._stt_b, "STT-B"))
        if self._tts_a:
            preload_tasks.append((self._tts_a, "TTS-A"))
        if self._tts_b:
            preload_tasks.append((self._tts_b, "TTS-B"))

        load_threads = []
        for engine, name in preload_tasks:
            t = threading.Thread(target=_load, args=(engine, name), daemon=True)
            t.start()
            load_threads.append(t)

        # Attendre le chargement de tous les modèles avant de démarrer les pipelines
        for t in load_threads:
            t.join(timeout=120)

    # ── Démarrage des threads ─────────────────────────────────────────────────

    def _start_threads(self) -> None:
        """Lance tous les threads de traitement."""
        thread_defs = []

        if self._settings.pipeline_a_enabled:
            thread_defs += [
                ("VAD-A", self._vad_loop_a),
                ("STT-A", self._stt_loop, (self._q_stt_a, self._q_trans_a, self._stt_a, "A")),
                ("TRANS-A", self._translation_loop, (self._q_trans_a, self._q_tts_a, self._translation_a, "A")),
                ("TTS-A", self._tts_loop_a),
            ]

        if self._settings.pipeline_b_enabled:
            thread_defs += [
                ("VAD-B", self._vad_loop_b),
                ("STT-B", self._stt_loop, (self._q_stt_b, self._q_trans_b, self._stt_b, "B")),
                ("TRANS-B", self._translation_loop, (self._q_trans_b, self._q_tts_b, self._translation_b, "B")),
                ("TTS-B", self._tts_loop_b),
            ]

        for item in thread_defs:
            if len(item) == 2:
                name, target = item
                args = ()
            else:
                name, target, args = item

            t = threading.Thread(
                target=target,
                args=args,
                name=name,
                daemon=True,
            )
            t.start()
            self._threads.append(t)

        # Démarrer les captures en dernier (elles alimentent tout le reste)
        if self._capture_a:
            self._capture_a.start(self._on_audio_a)
        if self._capture_b:
            self._capture_b.start(self._on_audio_b)

    # ── Callbacks audio ───────────────────────────────────────────────────────

    def _on_audio_a(self, chunk: bytes) -> None:
        """Callback appelé par AudioCapture A pour chaque chunk."""
        with self._mic_muted_lock:
            if self._mic_muted:
                return
        if self._vad_a:
            result = self._vad_a.process_chunk(chunk)
            if result.should_flush and result.audio_segment:
                try:
                    self._q_stt_a.put_nowait(result.audio_segment)
                except queue.Full:
                    logger.warning("Queue STT-A pleine — chunk ignoré")

    def _on_audio_b(self, chunk: bytes) -> None:
        """Callback appelé par AudioCapture B pour chaque chunk (loopback)."""
        if self._vad_b:
            result = self._vad_b.process_chunk(chunk)
            if result.should_flush and result.audio_segment:
                try:
                    self._q_stt_b.put_nowait(result.audio_segment)
                except queue.Full:
                    logger.warning("Queue STT-B pleine — chunk ignoré")

    # ── Boucles de traitement ─────────────────────────────────────────────────

    def _vad_loop_a(self) -> None:
        """Boucle VAD Pipeline A (gérée via callback, thread factice pour structure)."""
        # La capture est démarrée avec callback _on_audio_a — ce thread n'est pas utilisé
        pass

    def _vad_loop_b(self) -> None:
        """Boucle VAD Pipeline B."""
        pass

    def _stt_loop(
        self,
        q_in: queue.Queue,
        q_out: queue.Queue,
        stt: STTEngine,
        pipeline: str,
    ) -> None:
        """Thread STT : reçoit des segments audio, transcrit, envoie le résultat."""
        logger.info("Thread STT-%s démarré", pipeline)
        while not self._stop_event.is_set():
            try:
                audio_bytes = q_in.get(timeout=1.0)
            except queue.Empty:
                continue

            try:
                result = stt.transcribe(audio_bytes)
                if result.text.strip():
                    q_out.put(result, timeout=2.0)
                else:
                    logger.debug("STT-%s : texte vide ignoré", pipeline)
            except queue.Full:
                logger.warning("Queue TRANS-%s pleine — résultat ignoré", pipeline)
            except Exception as e:
                logger.error("Erreur STT-%s : %s", pipeline, e)

        logger.info("Thread STT-%s arrêté", pipeline)

    def _translation_loop(
        self,
        q_in: queue.Queue,
        q_out: queue.Queue,
        translator: TranslationEngine,
        pipeline: str,
    ) -> None:
        """Thread Traduction : reçoit STTResult, traduit, envoie TranslationResult."""
        logger.info("Thread TRANS-%s démarré", pipeline)
        while not self._stop_event.is_set():
            try:
                stt_result = q_in.get(timeout=1.0)
            except queue.Empty:
                continue

            try:
                translation = translator.translate(stt_result.text)
                q_out.put((stt_result, translation), timeout=2.0)
            except queue.Full:
                logger.warning("Queue TTS-%s pleine — traduction ignorée", pipeline)
            except Exception as e:
                logger.error("Erreur TRANS-%s : %s", pipeline, e)

        logger.info("Thread TRANS-%s arrêté", pipeline)

    def _tts_loop_a(self) -> None:
        """Thread TTS Pipeline A : synthèse + injection Virtual Cable."""
        logger.info("Thread TTS-A démarré")
        while not self._stop_event.is_set():
            try:
                stt_result, translation = self._q_tts_a.get(timeout=1.0)
            except queue.Empty:
                continue

            try:
                t_start = time.time()
                audio = self._tts_a.synthesize(translation.translated_text)

                if len(audio.samples) > 0 and self._router:
                    self._router.route_audio(audio.samples, audio.sample_rate)

                latency = int((time.time() - t_start) * 1000)
                self._last_latency_ms = latency

                event = TranslationEvent(
                    original_text=stt_result.text,
                    translated_text=translation.translated_text,
                    source_lang=translation.source_lang,
                    target_lang=translation.target_lang,
                    pipeline="A",
                    engine_used=translation.engine_used,
                    latency_ms=latency,
                )
                self._emit_translation(event)

                if self.on_latency_update:
                    self.on_latency_update(latency)

            except Exception as e:
                logger.error("Erreur TTS-A : %s", e)

        logger.info("Thread TTS-A arrêté")

    def _tts_loop_b(self) -> None:
        """Thread TTS Pipeline B : affichage overlay + TTS local optionnel."""
        logger.info("Thread TTS-B démarré")
        while not self._stop_event.is_set():
            try:
                stt_result, translation = self._q_tts_b.get(timeout=1.0)
            except queue.Empty:
                continue

            try:
                event = TranslationEvent(
                    original_text=stt_result.text,
                    translated_text=translation.translated_text,
                    source_lang=translation.source_lang,
                    target_lang=translation.target_lang,
                    pipeline="B",
                    engine_used=translation.engine_used,
                )
                self._emit_translation(event)

                # TTS local optionnel (lire la traduction)
                if self._settings.local_tts_output and self._tts_b:
                    audio = self._tts_b.synthesize(translation.translated_text)
                    if len(audio.samples) > 0:
                        import sounddevice as sd
                        sd.play(audio.samples, samplerate=audio.sample_rate, blocking=False)

            except Exception as e:
                logger.error("Erreur TTS-B : %s", e)

        logger.info("Thread TTS-B arrêté")

    # ── Émetteurs d'événements ────────────────────────────────────────────────

    def _emit_translation(self, event: TranslationEvent) -> None:
        if self.on_translation:
            try:
                self.on_translation(event)
            except Exception as e:
                logger.error("Erreur callback on_translation : %s", e)

    def _emit_error(self, message: str) -> None:
        if self.on_error:
            try:
                self.on_error(message)
            except Exception as e:
                logger.error("Erreur callback on_error : %s", e)

    def _set_state(self, state: ControllerState) -> None:
        self._state = state
        if self.on_status_change:
            try:
                self.on_status_change(state)
            except Exception as e:
                logger.error("Erreur callback on_status_change : %s", e)

    # ── Propriétés ────────────────────────────────────────────────────────────

    @property
    def state(self) -> ControllerState:
        return self._state

    @property
    def is_running(self) -> bool:
        return self._state == ControllerState.RUNNING

    @property
    def virtual_cable_available(self) -> bool:
        return self._router is not None and self._router.is_available()

    @property
    def last_latency_ms(self) -> int:
        return self._last_latency_ms

    @property
    def mic_muted(self) -> bool:
        with self._mic_muted_lock:
            return self._mic_muted

    def __repr__(self) -> str:
        return f"MainController(state={self._state.name})"
