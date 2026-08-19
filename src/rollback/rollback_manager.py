"""
Rollback Manager — Safe Migration with Undo

Provides atomic migration rollback capabilities:
1. Creates full snapshots of the output directory before each migration phase
2. Supports rolling back to any previous phase
3. Maintains a transaction log for auditability
"""
import json
import os
import shutil
import time
from typing import List, Optional
from dataclasses import dataclass, field


@dataclass
class RollbackPoint:
    """A saved state that can be restored."""
    phase_name: str
    timestamp: float
    snapshot_path: str
    file_count: int
    description: str


class RollbackManager:
    """
    Manages migration rollback points for safe, undoable migrations.
    """

    def __init__(self, rollback_dir: str = ".refactor_rollbacks"):
        self.rollback_dir = rollback_dir
        self._points: List[RollbackPoint] = []
        self._log_path = os.path.join(rollback_dir, "transaction_log.jsonl")
        os.makedirs(rollback_dir, exist_ok=True)

    def create_rollback_point(self, phase_name: str, source_dir: str, description: str = "") -> RollbackPoint:
        """Snapshot the current state of the output directory."""
        timestamp = time.time()
        snapshot_name = f"{phase_name}_{int(timestamp)}"
        snapshot_path = os.path.join(self.rollback_dir, snapshot_name)

        if os.path.exists(source_dir):
            shutil.copytree(source_dir, snapshot_path, dirs_exist_ok=True)
            file_count = sum(len(files) for _, _, files in os.walk(snapshot_path))
        else:
            os.makedirs(snapshot_path, exist_ok=True)
            file_count = 0

        point = RollbackPoint(
            phase_name=phase_name,
            timestamp=timestamp,
            snapshot_path=snapshot_path,
            file_count=file_count,
            description=description or f"Snapshot before {phase_name}",
        )
        self._points.append(point)
        self._log_transaction("CREATE_ROLLBACK", phase_name, snapshot_path)
        return point

    def rollback_to(self, phase_name: str, target_dir: str) -> bool:
        """Restore the output directory to a previous rollback point."""
        point = next((p for p in reversed(self._points) if p.phase_name == phase_name), None)
        if not point:
            return False

        # Clear current output
        if os.path.exists(target_dir):
            shutil.rmtree(target_dir)

        # Restore snapshot
        shutil.copytree(point.snapshot_path, target_dir)
        self._log_transaction("ROLLBACK", phase_name, target_dir)
        return True

    def list_points(self) -> List[RollbackPoint]:
        """List all available rollback points."""
        return list(self._points)

    def cleanup_old_points(self, keep_latest: int = 3):
        """Remove old rollback snapshots, keeping only the N most recent."""
        while len(self._points) > keep_latest:
            oldest = self._points.pop(0)
            if os.path.exists(oldest.snapshot_path):
                shutil.rmtree(oldest.snapshot_path, ignore_errors=True)
            self._log_transaction("CLEANUP", oldest.phase_name, oldest.snapshot_path)

    def _log_transaction(self, action: str, phase: str, path: str):
        """Append to the transaction log."""
        entry = {"action": action, "phase": phase, "path": path, "timestamp": time.time()}
        with open(self._log_path, "a") as f:
            f.write(json.dumps(entry) + "\n")
