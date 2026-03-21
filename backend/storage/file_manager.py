from pathlib import Path


def generate_recording_path(recordings_dir: str, session_id: str) -> str:
    path = Path(recordings_dir)
    path.mkdir(parents=True, exist_ok=True)
    return str(path / f"{session_id}.wav")


def delete_file_if_exists(file_path: str) -> None:
    path = Path(file_path)
    if path.exists() and path.is_file():
        path.unlink(missing_ok=True)
