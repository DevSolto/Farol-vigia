"""Implementações de deduplicação por hashing."""

from .sha256_deduper import Sha256Deduper, build_deduper

__all__ = ["Sha256Deduper", "build_deduper"]
