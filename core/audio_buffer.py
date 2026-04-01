#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VoxShield — Buffer audio circulaire thread-safe.
Accumule les chunks audio en attendant le flush vers le STT.
"""

import threading
from collections import deque
from typing import Optional

from utils.logger import get_logger

logger = get_logger("AUDIO")

# Durée maximale accumulée avant flush forcé (sécurité anti-boucle infinie)
MAX_BUFFER_MS = 15_000


class AudioBuffer:
    """
    Buffer circulaire thread-safe pour accumuler les chunks audio PCM.

    Les chunks sont ajoutés depuis le thread de capture audio et
    consommés (flush) vers le thread STT.
    """

    def __init__(
        self,
        sample_rate: int = 16000,
        max_duration_ms: int = MAX_BUFFER_MS,
    ) -> None:
        """
        Args:
            sample_rate: Taux d'échantillonnage en Hz (pour calcul de durée).
            max_duration_ms: Durée maximale avant flush forcé automatique.
        """
        self._sample_rate = sample_rate
        self._max_duration_ms = max_duration_ms
        self._chunks: deque[bytes] = deque()
        self._total_bytes = 0
        self._lock = threading.Lock()

    @property
    def _bytes_per_ms(self) -> int:
        """Nombre de bytes PCM int16 mono par milliseconde."""
        return (self._sample_rate * 2) // 1000  # 2 = sizeof(int16)

    @property
    def _max_bytes(self) -> int:
        return self._max_duration_ms * self._bytes_per_ms

    def push(self, chunk: bytes) -> None:
        """
        Ajoute un chunk audio dans le buffer.

        Args:
            chunk: Données PCM brutes int16.
        """
        with self._lock:
            self._chunks.append(chunk)
            self._total_bytes += len(chunk)

    def flush(self) -> bytes:
        """
        Vide le buffer et retourne tous les bytes accumulés.

        Returns:
            Concaténation de tous les chunks depuis le dernier flush.
        """
        with self._lock:
            if not self._chunks:
                return b""
            data = b"".join(self._chunks)
            self._chunks.clear()
            self._total_bytes = 0
            return data

    def should_force_flush(self) -> bool:
        """Retourne True si le buffer dépasse la durée maximale (sécurité)."""
        with self._lock:
            return self._total_bytes >= self._max_bytes

    def duration_ms(self) -> int:
        """Retourne la durée accumulée dans le buffer en millisecondes."""
        with self._lock:
            if self._bytes_per_ms == 0:
                return 0
            return self._total_bytes // self._bytes_per_ms

    def size_bytes(self) -> int:
        """Retourne la taille totale du buffer en bytes."""
        with self._lock:
            return self._total_bytes

    def is_empty(self) -> bool:
        """Retourne True si le buffer est vide."""
        with self._lock:
            return self._total_bytes == 0

    def clear(self) -> None:
        """Vide le buffer sans retourner les données."""
        with self._lock:
            self._chunks.clear()
            self._total_bytes = 0

    def peek(self, last_ms: int) -> bytes:
        """
        Retourne les N dernières millisecondes du buffer sans les supprimer.
        Utile pour inclure le contexte pré-speech.

        Args:
            last_ms: Durée à retourner en millisecondes.

        Returns:
            Bytes PCM des N dernières ms.
        """
        with self._lock:
            target_bytes = last_ms * self._bytes_per_ms
            result = b""
            for chunk in reversed(self._chunks):
                result = chunk + result
                if len(result) >= target_bytes:
                    break
            return result[-target_bytes:] if len(result) > target_bytes else result

    def __len__(self) -> int:
        return self._total_bytes

    def __repr__(self) -> str:
        return f"AudioBuffer(duration={self.duration_ms()}ms, bytes={self._total_bytes})"
