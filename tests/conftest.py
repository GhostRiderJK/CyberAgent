import hashlib
import os
import pytest
from pathlib import Path


def get_file_hash(filepath):
    """Calculate SHA-256 hash of a file."""
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


@pytest.fixture(autouse=True, scope="session")
def check_artifact_integrity():
    """Fixture to ensure no files in data/processed or results/tables are modified during test session."""
    # Directories to monitor
    monitor_dirs = [
        Path("data/processed"),
        Path("results/tables")
    ]

    # Store initial state
    initial_state = {}

    # Record initial hashes for all files in monitored directories
    for monitor_dir in monitor_dirs:
        if monitor_dir.exists():
            for file_path in monitor_dir.rglob("*"):
                if file_path.is_file():
                    # Use the file path as key
                    initial_state[str(file_path)] = get_file_hash(file_path)

    yield  # Run the tests

    # Check for changes after tests
    changed_files = []
    new_files = []
    deleted_files = []

    # Check for modified or deleted files
    for file_path_str, initial_hash in initial_state.items():
        file_path = Path(file_path_str)
        if file_path.exists():
            current_hash = get_file_hash(file_path)
            if current_hash != initial_hash:
                changed_files.append(file_path_str)
        else:
            deleted_files.append(file_path_str)

    # Check for new files
    for monitor_dir in monitor_dirs:
        if monitor_dir.exists():
            for file_path in monitor_dir.rglob("*"):
                if file_path.is_file():
                    file_path_str = str(file_path)
                    if file_path_str not in initial_state:
                        new_files.append(file_path_str)

    # Fail if any changes detected
    if changed_files or new_files or deleted_files:
        error_msg = ["Artifact integrity check failed:"]
        if changed_files:
            error_msg.append(f"  Modified files: {changed_files}")
        if new_files:
            error_msg.append(f"  New files: {new_files}")
        if deleted_files:
            error_msg.append(f"  Deleted files: {deleted_files}")
        error_msg.append("Tests must not modify files in data/processed or results/tables.")
        pytest.fail("\n".join(error_msg))