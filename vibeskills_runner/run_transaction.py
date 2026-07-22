import datetime as dt
import hashlib
import os
import re
import secrets
import shutil
import tempfile
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, Optional

import yaml

from .errors import PersistenceError, ValidationError

SHA256_REGEX = re.compile(r"^[0-9a-f]{64}$")


class TransactionPhase(str, Enum):
    STAGED = "STAGED"
    DIRECTORY_PROMOTED = "DIRECTORY_PROMOTED"
    RECORD_PROMOTED = "RECORD_PROMOTED"
    COMPLETE = "COMPLETE"


class RecoveryMode(str, Enum):
    COMPLETE_IF_POSSIBLE = "COMPLETE_IF_POSSIBLE"
    ROLLBACK_ONLY_IF_UNPUBLISHED = "ROLLBACK_ONLY_IF_UNPUBLISHED"


def compute_file_sha256(path: Path) -> str:
    """Compute SHA-256 of the given file path after checking for symlinks."""
    if path.is_symlink() or os.path.islink(str(path)):
        raise ValidationError(f"Security breach: File '{path}' is a symbolic link.")
    if not path.is_file():
        raise ValidationError(f"File not found for hashing: {path}")
    h = hashlib.sha256()
    try:
        h.update(path.read_bytes())
    except OSError as e:
        raise PersistenceError(f"Failed to read file for hashing: {path}: {e}") from e
    return h.hexdigest()


class RunLock:
    """Acquires a concurrency lock for a specific run ID using a context manager."""

    def __init__(self, repo_root: Path, run_id: str):
        self.repo_root = Path(repo_root)
        self.run_id = run_id
        self.lock_path = self.repo_root / f".ai/runs/{run_id}.lock"
        self.acquired = False
        self.nonce: Optional[str] = None

    def _verify_lock_path_safety(self) -> None:
        ai_dir = self.repo_root / ".ai"
        runs_dir = ai_dir / "runs"
        if ai_dir.is_symlink() or os.path.islink(str(ai_dir)):
            raise ValidationError(f"Security breach: '{ai_dir}' is a symbolic link.")
        if runs_dir.is_symlink() or os.path.islink(str(runs_dir)):
            raise ValidationError(f"Security breach: '{runs_dir}' is a symbolic link.")
        if self.lock_path.is_symlink() or os.path.islink(str(self.lock_path)):
            raise ValidationError(f"Security breach: Lock path '{self.lock_path}' is a symbolic link.")

        try:
            rel_parts = self.lock_path.relative_to(self.repo_root).parts
            check_path = self.repo_root
            for part in rel_parts:
                check_path = check_path / part
                if check_path.is_symlink() or os.path.islink(str(check_path)):
                    raise ValidationError(f"Security breach: Path component '{check_path}' is a symbolic link.")
        except ValueError as exc:
            raise ValidationError(
                f"Security breach attempt: lock path '{self.lock_path}' escapes repository root."
            ) from exc

        try:
            self.lock_path.resolve().relative_to(runs_dir.resolve())
        except ValueError as exc:
            raise ValidationError(
                f"Security breach attempt: lock path '{self.lock_path}' escapes runs directory."
            ) from exc

    def acquire(self) -> None:
        self._verify_lock_path_safety()
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        nonce = secrets.token_hex(16)
        created_at = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        lock_data = {
            "run_id": self.run_id,
            "pid": os.getpid(),
            "created_at": created_at,
            "nonce": nonce,
        }
        try:
            fd = os.open(str(self.lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                yaml.safe_dump(lock_data, f, sort_keys=False, allow_unicode=True)
            self.nonce = nonce
            self.acquired = True
        except FileExistsError:
            raise ValidationError(
                f"Another operation is already running on run '{self.run_id}'. "
                f"Lock file exists: {self.lock_path}"
            )
        except OSError as e:
            raise ValidationError(f"Failed to acquire run lock: {e}")

    def release(self) -> None:
        if not self.acquired:
            return
        self._verify_lock_path_safety()
        if not self.lock_path.exists():
            raise ValidationError("Lock ownership check failed: lock file disappeared before release.")

        try:
            content = self.lock_path.read_text(encoding="utf-8")
            data = yaml.safe_load(content)
        except Exception as e:
            raise ValidationError(f"Failed to read lock file during release: {e}") from e

        if (
            not isinstance(data, dict)
            or data.get("run_id") != self.run_id
            or data.get("nonce") != self.nonce
        ):
            raise ValidationError("Lock ownership check failed: file modified or owned by another process.")

        try:
            self.lock_path.unlink()
            self.acquired = False
        except OSError as e:
            raise PersistenceError(f"Failed to release lock file '{self.lock_path}': {e}") from e

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.acquired:
            try:
                self.release()
            except Exception as rel_err:
                if exc_val is not None:
                    raise rel_err from exc_val
                raise rel_err


class RunTransaction:
    """Manages multi-stage atomic promotion transactions and verification-driven recovery."""

    def __init__(self, repo_root: Path, run_id: str):
        self.repo_root = Path(repo_root)
        self.run_id = run_id

        # Lexical paths inside runs directory
        self.final_record_path = self.repo_root / f".ai/runs/{run_id}.yaml"
        self.final_dir_path = self.repo_root / f".ai/runs/{run_id}"
        self.stage_record_path = self.repo_root / f".ai/runs/{run_id}.yaml.stage"
        self.stage_dir_path = self.repo_root / f".ai/runs/{run_id}.stage"
        self.marker_path = self.repo_root / f".ai/runs/{run_id}.transaction.yaml"

    def verify_path_confinement(self, path: Path) -> None:
        """Verify that path lies strictly within .ai/runs/ and contains no symlinks."""
        ai_dir = self.repo_root / ".ai"
        runs_dir = ai_dir / "runs"
        if ai_dir.is_symlink() or os.path.islink(str(ai_dir)):
            raise ValidationError(f"Security breach: '{ai_dir}' is a symbolic link.")
        if runs_dir.is_symlink() or os.path.islink(str(runs_dir)):
            raise ValidationError(f"Security breach: '{runs_dir}' is a symbolic link.")
        if path.is_symlink() or os.path.islink(str(path)):
            raise ValidationError(f"Security breach: Path '{path}' is a symbolic link.")

        try:
            rel_parts = path.relative_to(self.repo_root).parts
            check_path = self.repo_root
            for part in rel_parts:
                check_path = check_path / part
                if check_path.is_symlink() or os.path.islink(str(check_path)):
                    raise ValidationError(f"Security breach: Path component '{check_path}' is a symbolic link.")
        except ValueError as exc:
            raise ValidationError(
                f"Security breach attempt: path '{path}' escapes repository root."
            ) from exc

        try:
            path.resolve().relative_to(runs_dir.resolve())
        except ValueError as exc:
            raise ValidationError(
                f"Security breach attempt: path '{path}' escapes runs directory."
            ) from exc

    def _validate_hashes(self, hashes: Dict[str, str]) -> None:
        """Validate the immutable file hashes stored in a transaction marker."""
        if not isinstance(hashes, dict):
            raise ValidationError("Transaction marker hashes must be a mapping.")
        for key in ["record", "journal", "metadata"]:
            value = hashes.get(key)
            if not isinstance(value, str) or not SHA256_REGEX.match(value):
                raise ValidationError(f"Invalid SHA-256 hash for '{key}': '{value}'")

    def write_marker(self, phase: TransactionPhase, hashes: Dict[str, str]) -> None:
        """Atomically write the transaction marker."""
        if not isinstance(phase, TransactionPhase):
            raise ValidationError("Transaction phase must be a TransactionPhase value.")
        self._validate_hashes(hashes)

        self.verify_path_confinement(self.marker_path)
        marker_data = {
            "run_id": self.run_id,
            "phase": phase.value,
            "stage_record_path": str(self.stage_record_path),
            "stage_dir_path": str(self.stage_dir_path),
            "final_record_path": str(self.final_record_path),
            "final_dir_path": str(self.final_dir_path),
            "hashes": hashes,
        }
        temp_fd, temp_path = tempfile.mkstemp(dir=str(self.marker_path.parent), suffix=".tmp")
        try:
            with os.fdopen(temp_fd, "w", encoding="utf-8") as f:
                yaml.safe_dump(marker_data, f, sort_keys=False, allow_unicode=True)
            os.replace(temp_path, self.marker_path)
        except Exception as exc:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass
            raise PersistenceError(f"Failed to write transaction marker: {exc}") from exc

    def promote_directory(self) -> None:
        """Rename staging directory to final directory."""
        try:
            self.stage_dir_path.rename(self.final_dir_path)
        except OSError as e:
            raise PersistenceError(f"Failed to promote run directory: {e}") from e

    def promote_record(self) -> None:
        """Rename staging record to final record."""
        try:
            self.stage_record_path.rename(self.final_record_path)
        except OSError as e:
            raise PersistenceError(f"Failed to promote run record: {e}") from e

    def write_transaction_phase(
        self, phase: TransactionPhase, hashes: Dict[str, str]
    ) -> None:
        """Write the transaction phase marker."""
        self.write_marker(phase, hashes)

    def _load_marker(self) -> tuple[TransactionPhase, Dict[str, str]]:
        """Load a marker only when it names this transaction and canonical paths."""
        if self.marker_path.is_symlink() or os.path.islink(str(self.marker_path)):
            raise ValidationError(f"Security breach: Transaction marker is a symbolic link: {self.marker_path}")
        if not self.marker_path.is_file():
            raise ValidationError(f"Transaction marker is missing: {self.marker_path}")
        try:
            marker_data = yaml.safe_load(self.marker_path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise ValidationError(f"Transaction marker is corrupted: {exc}") from exc
        if not isinstance(marker_data, dict):
            raise ValidationError("Transaction marker content is not a mapping.")
        try:
            phase = TransactionPhase(marker_data.get("phase"))
        except (TypeError, ValueError) as exc:
            raise ValidationError(
                f"Transaction marker phase is invalid or missing: '{marker_data.get('phase')}'"
            ) from exc
        if marker_data.get("run_id") != self.run_id:
            raise ValidationError("Transaction marker run_id mismatch.")
        if (
            marker_data.get("stage_record_path") != str(self.stage_record_path)
            or marker_data.get("stage_dir_path") != str(self.stage_dir_path)
            or marker_data.get("final_record_path") != str(self.final_record_path)
            or marker_data.get("final_dir_path") != str(self.final_dir_path)
        ):
            raise ValidationError("Path mismatch detected in transaction marker file.")
        hashes = marker_data.get("hashes")
        self._validate_hashes(hashes)
        return phase, hashes

    def verify_final_integrity(self, hashes: Dict[str, str]) -> None:
        """Require the published topology to match the immutable staging hashes."""
        if not self.verify_record_integrity(self.final_record_path, hashes):
            raise ValidationError("Final record integrity check failed.")
        if not self.verify_dir_integrity(self.final_dir_path, hashes):
            raise ValidationError("Final directory integrity check failed.")

    def cleanup_transaction(self) -> None:
        """Remove recovery evidence only from a verified COMPLETE transaction."""
        phase, hashes = self._load_marker()
        if phase is not TransactionPhase.COMPLETE:
            raise ValidationError("Controlled cleanup requires a COMPLETE transaction marker.")
        if (
            not self.final_record_path.is_file()
            or not self.final_dir_path.is_dir()
            or self.stage_record_path.exists()
            or self.stage_dir_path.exists()
        ):
            raise ValidationError("Controlled cleanup requires the exact COMPLETE filesystem topology.")
        self.verify_final_integrity(hashes)
        if self.final_dir_path.exists():
            stage_marker = self.final_dir_path / ".stage_marker"
            if stage_marker.is_symlink() or os.path.islink(str(stage_marker)):
                raise ValidationError(f"Security breach: .stage_marker is a symbolic link: {stage_marker}")
            if stage_marker.is_file():
                try:
                    stage_marker.unlink()
                except OSError as e:
                    raise PersistenceError(f"Failed to cleanup stage marker: {e}") from e

        try:
            self.marker_path.unlink()
        except OSError as e:
            raise PersistenceError(f"Failed to delete transaction marker: {e}") from e

    def cleanup_unpublished_staging(self, hashes: Dict[str, str]) -> None:
        """Clean only verified artifacts created by this still-running unpublished operation."""
        if self.marker_path.exists() or self.final_record_path.exists() or self.final_dir_path.exists():
            raise ValidationError("Cannot clean unpublished staging after marker or final artifacts exist.")
        if not self.stage_record_path.is_file() or not self.stage_dir_path.is_dir():
            raise ValidationError("Cannot clean incomplete unpublished staging artifacts.")
        if not self.verify_stage_marker(self.stage_dir_path):
            raise ValidationError("Cannot clean staging without a matching stage marker.")
        if not self.verify_record_integrity(self.stage_record_path, hashes):
            raise ValidationError("Cannot clean modified staging record.")
        if not self.verify_dir_integrity(self.stage_dir_path, hashes):
            raise ValidationError("Cannot clean modified staging directory.")
        try:
            shutil.rmtree(self.stage_dir_path)
            self.stage_record_path.unlink()
        except OSError as exc:
            raise PersistenceError(f"Failed to clean unpublished staging artifacts: {exc}") from exc

    def execute_promotion(
        self, hashes: Dict[str, str], validate_published: Callable[[], None]
    ) -> None:
        """Promote staging files to final destination following exact transaction phases."""
        if not callable(validate_published):
            raise ValidationError("Published-run validation callback is required for promotion.")
        try:
            self.write_transaction_phase(TransactionPhase.STAGED, hashes)
        except Exception:
            self.cleanup_unpublished_staging(hashes)
            raise
        self.promote_directory()
        self.write_transaction_phase(TransactionPhase.DIRECTORY_PROMOTED, hashes)
        self.promote_record()
        self.write_transaction_phase(TransactionPhase.RECORD_PROMOTED, hashes)
        self.complete_promotion(hashes, validate_published)

    def verify_dir_integrity(self, path: Path, hashes: Dict[str, str]) -> bool:
        """Check events and metadata hashes inside the directory."""
        try:
            j_hash = compute_file_sha256(path / "events.jsonl")
            m_hash = compute_file_sha256(path / "metadata.yaml")
            return j_hash == hashes.get("journal") and m_hash == hashes.get("metadata")
        except Exception:
            return False

    def verify_record_integrity(self, path: Path, hashes: Dict[str, str]) -> bool:
        """Check run record hash."""
        try:
            r_hash = compute_file_sha256(path)
            return r_hash == hashes.get("record")
        except Exception:
            return False

    def verify_stage_marker(self, dir_path: Path) -> bool:
        """Verify .stage_marker file exists and matches run_id."""
        marker = dir_path / ".stage_marker"
        if marker.is_symlink() or os.path.islink(str(marker)):
            raise ValidationError(f"Security breach: .stage_marker is a symbolic link: {marker}")
        if not marker.is_file():
            return False
        try:
            data = yaml.safe_load(marker.read_text(encoding="utf-8"))
            return isinstance(data, dict) and data.get("run_id") == self.run_id
        except Exception:
            return False

    def complete_promotion(self, hashes: Dict[str, str], validate_published: Callable[[], None]) -> None:
        """Bind final bytes and semantic validation before recording COMPLETE."""
        if not callable(validate_published):
            raise ValidationError("Published-run validation callback is required for completion.")
        self.verify_final_integrity(hashes)
        validate_published()
        self.write_transaction_phase(TransactionPhase.COMPLETE, hashes)
        self.cleanup_transaction()

    def recover(
        self,
        mode: RecoveryMode,
        validate_published: Callable[[], None],
    ) -> None:
        """Perform verification-driven recovery or rollback based on mode, marker and topology."""
        self.verify_path_confinement(self.final_record_path)
        self.verify_path_confinement(self.final_dir_path)
        self.verify_path_confinement(self.stage_record_path)
        self.verify_path_confinement(self.stage_dir_path)
        self.verify_path_confinement(self.marker_path)

        # Check existing stage files for symlinks
        for path in [
            self.stage_record_path,
            self.stage_dir_path,
            self.final_record_path,
            self.final_dir_path,
            self.marker_path,
        ]:
            if path.is_symlink() or os.path.islink(str(path)):
                raise ValidationError(f"Security breach: Path '{path}' is a symbolic link.")

        # Case 1: No transaction marker
        if not self.marker_path.exists():
            # If stage files exist without a transaction marker -> fail closed!
            if self.stage_record_path.exists() or self.stage_dir_path.exists():
                raise ValidationError(
                    f"Unmanaged staging files exist for run '{self.run_id}' without transaction marker."
                )
            return

        if not callable(validate_published):
            raise ValidationError("Published-run validation callback is required for recovery.")
        phase, hashes = self._load_marker()

        # Check topology
        stage_rec = self.stage_record_path.exists()
        stage_dir = self.stage_dir_path.exists()
        final_rec = self.final_record_path.exists()
        final_dir = self.final_dir_path.exists()

        if phase is TransactionPhase.STAGED:
            if stage_rec and stage_dir and not final_rec and not final_dir:
                if not self.verify_stage_marker(self.stage_dir_path):
                    raise ValidationError("Stage marker missing or run_id mismatch in stage directory.")

                if mode == RecoveryMode.ROLLBACK_ONLY_IF_UNPUBLISHED:
                    self.rollback(hashes)
                else:
                    self.promote_from_staged(hashes, validate_published)
            elif stage_rec and final_dir and not stage_dir and not final_rec:
                # Directory rename completed, phase write failed
                if not self.verify_stage_marker(self.final_dir_path):
                    raise ValidationError("Stage marker missing or run_id mismatch in promoted directory.")
                self.promote_from_directory_promoted(hashes, validate_published)
            else:
                raise ValidationError("Marker phase 'STAGED' is ahead of or incompatible with filesystem topology.")

        elif phase is TransactionPhase.DIRECTORY_PROMOTED:
            if stage_rec and final_dir and not stage_dir and not final_rec:
                if not self.verify_stage_marker(self.final_dir_path):
                    raise ValidationError("Stage marker missing or run_id mismatch in promoted directory.")
                self.promote_from_directory_promoted(hashes, validate_published)
            elif final_rec and final_dir and not stage_rec and not stage_dir:
                # Record rename completed, phase write failed
                self.promote_from_record_promoted(hashes, validate_published)
            else:
                raise ValidationError("Marker phase 'DIRECTORY_PROMOTED' is incompatible with filesystem topology.")

        elif phase is TransactionPhase.RECORD_PROMOTED:
            if final_rec and final_dir and not stage_rec and not stage_dir:
                self.promote_from_record_promoted(hashes, validate_published)
            else:
                raise ValidationError("Marker phase 'RECORD_PROMOTED' is incompatible with filesystem topology.")

        elif phase is TransactionPhase.COMPLETE:
            if final_rec and final_dir and not stage_rec and not stage_dir:
                self.complete_promotion(hashes, validate_published)
            else:
                raise ValidationError("Marker phase 'COMPLETE' is incompatible with filesystem topology.")

        else:
            raise ValidationError(f"Unknown transaction phase '{phase}'.")

    def promote_from_staged(
        self, hashes: Dict[str, str], validate_published: Callable[[], None]
    ) -> None:
        if not self.verify_record_integrity(self.stage_record_path, hashes):
            raise ValidationError("Staged record integrity check failed during recovery.")
        if not self.verify_dir_integrity(self.stage_dir_path, hashes):
            raise ValidationError("Staged directory integrity check failed during recovery.")

        self.promote_directory()
        self.write_transaction_phase(TransactionPhase.DIRECTORY_PROMOTED, hashes)
        self.promote_record()
        self.write_transaction_phase(TransactionPhase.RECORD_PROMOTED, hashes)

        self.complete_promotion(hashes, validate_published)

    def promote_from_directory_promoted(
        self, hashes: Dict[str, str], validate_published: Callable[[], None]
    ) -> None:
        if not self.verify_dir_integrity(self.final_dir_path, hashes):
            raise ValidationError("Final directory integrity check failed during recovery.")
        if not self.verify_record_integrity(self.stage_record_path, hashes):
            raise ValidationError("Staged record integrity check failed during recovery.")

        self.promote_record()
        self.write_transaction_phase(TransactionPhase.RECORD_PROMOTED, hashes)

        self.complete_promotion(hashes, validate_published)

    def promote_from_record_promoted(
        self, hashes: Dict[str, str], validate_published: Callable[[], None]
    ) -> None:
        if not self.verify_dir_integrity(self.final_dir_path, hashes):
            raise ValidationError("Final directory integrity check failed during recovery.")
        if not self.verify_record_integrity(self.final_record_path, hashes):
            raise ValidationError("Final record integrity check failed during recovery.")

        self.complete_promotion(hashes, validate_published)

    def rollback(self, hashes: Dict[str, str]) -> None:
        """Roll back transaction strictly when topology is STAGED and un-promoted."""
        if self.stage_record_path.exists():
            if self.verify_record_integrity(self.stage_record_path, hashes):
                try:
                    self.stage_record_path.unlink()
                except OSError as e:
                    raise PersistenceError(f"Failed to delete staging record: {e}") from e
            else:
                raise ValidationError("Cannot rollback: staging record is modified or corrupted.")

        if self.stage_dir_path.exists():
            if self.verify_dir_integrity(self.stage_dir_path, hashes):
                try:
                    shutil.rmtree(self.stage_dir_path)
                except OSError as e:
                    raise PersistenceError(f"Failed to delete staging directory: {e}") from e
            else:
                raise ValidationError("Cannot rollback: staging directory is modified or corrupted.")

        try:
            if self.marker_path.exists():
                self.marker_path.unlink()
        except OSError as e:
            raise PersistenceError(f"Failed to delete transaction marker: {e}") from e

    def clean_stale_stage_files(self) -> None:
        """Markerless cleanup is disabled (fails closed if stage files exist without marker)."""
        if self.stage_record_path.exists() or self.stage_dir_path.exists():
            raise ValidationError(
                f"Unmanaged staging files exist for run '{self.run_id}' without transaction marker."
            )
