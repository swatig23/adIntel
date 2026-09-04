"""Persistence layer for AdIntel analyses.

Two backends behind one protocol:

* :class:`LocalJsonStore`  — writes JSON files to ``./data/analyses/``.
                              Always available; the default in dev.
* :class:`FirestoreStore`  — writes to Google Cloud Firestore. Activated
                              when ``GCP_PROJECT_ID`` is set in ``.env``.

Use :func:`get_store` to pick the right backend automatically.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from loguru import logger

from .config import get_settings
from .models import AnalysisReport


class ReportStore(Protocol):
    """The contract every storage backend implements."""

    def save(self, report: AnalysisReport) -> str: ...
    def load(self, report_id: str) -> AnalysisReport | None: ...
    def list_recent(self, limit: int = 20) -> list[dict]: ...


# ────────────────────────────────────────────────────────────────
# Local JSON backend — always works, zero setup
# ────────────────────────────────────────────────────────────────


class LocalJsonStore:
    """Fallback backend that writes JSON files to disk."""

    def __init__(self, base_dir: Path = Path("data/analyses")):
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save(self, report: AnalysisReport) -> str:
        report_id = uuid.uuid4().hex[:12]
        path = self.base_dir / f"{report_id}.json"
        payload = report.model_dump(mode="json")
        payload["_id"] = report_id
        payload["_saved_at"] = datetime.now(timezone.utc).isoformat()
        path.write_text(json.dumps(payload, indent=2, default=str))
        logger.info(f"[LocalJsonStore] saved report {report_id} -> {path}")
        return report_id

    def load(self, report_id: str) -> AnalysisReport | None:
        path = self.base_dir / f"{report_id}.json"
        if not path.exists():
            return None
        data = json.loads(path.read_text())
        data.pop("_id", None)
        data.pop("_saved_at", None)
        return AnalysisReport(**data)

    def list_recent(self, limit: int = 20) -> list[dict]:
        rows = []
        for p in sorted(self.base_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]:
            try:
                data = json.loads(p.read_text())
                rows.append(
                    {
                        "id": data.get("_id", p.stem),
                        "brand": data.get("request", {}).get("user_brand", "?"),
                        "competitors": data.get("request", {}).get("competitors", []),
                        "saved_at": data.get("_saved_at"),
                    }
                )
            except Exception as e:  # noqa: BLE001
                logger.warning(f"Could not read {p}: {e}")
        return rows


# ────────────────────────────────────────────────────────────────
# Firestore backend
# ────────────────────────────────────────────────────────────────


class FirestoreStore:
    """Google Cloud Firestore backend."""

    def __init__(self, project_id: str, collection: str = "adintel_analyses"):
        from google.cloud import firestore  # imported lazily

        self._client = firestore.Client(project=project_id)
        self._collection = collection
        self._firestore = firestore
        logger.info(f"[FirestoreStore] project={project_id} collection={collection}")

    def save(self, report: AnalysisReport) -> str:
        report_id = uuid.uuid4().hex[:12]
        payload = report.model_dump(mode="json")
        payload["_id"] = report_id
        payload["_saved_at"] = self._firestore.SERVER_TIMESTAMP
        self._client.collection(self._collection).document(report_id).set(payload)
        logger.info(f"[FirestoreStore] saved report {report_id}")
        return report_id

    def load(self, report_id: str) -> AnalysisReport | None:
        doc = self._client.collection(self._collection).document(report_id).get()
        if not doc.exists:
            return None
        data = doc.to_dict()
        data.pop("_id", None)
        data.pop("_saved_at", None)
        return AnalysisReport(**data)

    def list_recent(self, limit: int = 20) -> list[dict]:
        q = (
            self._client.collection(self._collection)
            .order_by("_saved_at", direction=self._firestore.Query.DESCENDING)
            .limit(limit)
        )
        rows = []
        for doc in q.stream():
            data = doc.to_dict()
            rows.append(
                {
                    "id": data.get("_id", doc.id),
                    "brand": data.get("request", {}).get("user_brand", "?"),
                    "competitors": data.get("request", {}).get("competitors", []),
                    "saved_at": str(data.get("_saved_at", "")),
                }
            )
        return rows


# ────────────────────────────────────────────────────────────────
# Factory
# ────────────────────────────────────────────────────────────────

_store: ReportStore | None = None


def get_store() -> ReportStore:
    """Returns the singleton store, choosing backend based on env."""
    global _store
    if _store is not None:
        return _store

    settings = get_settings()
    if settings.gcp_project_id:
        try:
            _store = FirestoreStore(
                project_id=settings.gcp_project_id,
                collection=settings.firestore_collection,
            )
            return _store
        except Exception as e:  # noqa: BLE001
            logger.warning(
                f"[storage] Firestore init failed ({e}); falling back to LocalJsonStore. "
                f"Set GOOGLE_APPLICATION_CREDENTIALS or run `gcloud auth application-default login`."
            )

    _store = LocalJsonStore()
    logger.info("[storage] using LocalJsonStore backend")
    return _store
