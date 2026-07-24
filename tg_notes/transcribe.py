"""Local, pluggable audio transcription for tg-notes (media Phase 2).

Best-effort speech-to-text for audio note files, so a dictated voice note becomes
searchable caption text without a manual ``--caption``. Everything runs **locally**, via one
of three pluggable backends, detected on demand in this order:

1. a configured whisper CLI (``cfg.whisper_cmd``),
2. a whisper CLI found on ``PATH`` (``whisper-cli`` / ``whisper`` / ``main`` — whisper.cpp
   or openai-whisper), or
3. the :mod:`faster_whisper` Python package (imported lazily, only when used).

No engine is a hard dependency: :func:`available_transcriber` returns ``None`` when nothing
is installed, and the caller treats transcription as best-effort — a missing or failing
engine never loses the upload, it just skips the caption.

This module is pure compute + subprocess; it does **no** Telegram I/O (that stays in
:mod:`tg_notes.telegram`), and the CLI handler passes the returned text on as the caption.
"""
from __future__ import annotations

import shutil

# Safe: the transcriber binary is resolved via shutil.which / an existing path, invoked with
# a fixed argument list and no shell, and never interpolates untrusted input (see below).
import subprocess  # nosec B404
import tempfile
from pathlib import Path

#: Audio file extensions we attempt to transcribe (lower-case, dot-prefixed).
AUDIO_EXTS = frozenset(
    {".ogg", ".oga", ".opus", ".mp3", ".m4a", ".wav", ".flac", ".aac", ".webm"}
)

#: whisper-style CLI binaries tried on PATH, in order (whisper.cpp first, then openai-whisper).
_WHISPER_CLIS = ("whisper-cli", "whisper", "main")

#: Label returned/used for the pure-Python faster-whisper backend.
_FASTER_WHISPER = "faster-whisper"

#: How long (seconds) a CLI transcription may run before we give up.
_CLI_TIMEOUT = 900

#: Default whisper model when the config does not name one.
_DEFAULT_MODEL = "base"


class TranscriptionUnavailable(Exception):
    """Raised when no local transcription engine is available."""


class TranscriptionError(Exception):
    """Raised when a transcription engine ran but failed to produce a transcript."""


def is_audio(path: str | Path) -> bool:
    """Return ``True`` when ``path``'s suffix is a known audio extension (case-insensitive)."""
    return Path(path).suffix.lower() in AUDIO_EXTS


def _resolve_cmd(cmd: str | None) -> str | None:
    """Resolve ``cmd`` to an executable path — a ``PATH`` lookup or an existing file — else None."""
    if not cmd:
        return None
    found = shutil.which(cmd)
    if found:
        return found
    path = Path(cmd)
    return str(path) if path.exists() else None


def _cli_backend(cfg: object | None) -> str | None:
    """Return the whisper CLI to use: the configured one first, then one found on ``PATH``."""
    configured = _resolve_cmd(getattr(cfg, "whisper_cmd", None)) if cfg is not None else None
    if configured:
        return configured
    for name in _WHISPER_CLIS:
        found = shutil.which(name)
        if found:
            return found
    return None


def _faster_whisper_available() -> bool:
    """Return ``True`` when :mod:`faster_whisper` can be imported (checked lazily)."""
    try:
        import faster_whisper  # noqa: F401
    except Exception:  # noqa: BLE001 - any import/native-load failure means "not available"
        return False
    return True


def available_transcriber(cfg: object | None = None) -> str | None:
    """Return a label for the first usable local transcriber, or ``None``.

    The label is the resolved CLI path for a whisper binary (configured or found on
    ``PATH``), or :data:`_FASTER_WHISPER` for the :mod:`faster_whisper` backend. Detection
    order: configured ``cfg.whisper_cmd`` → a whisper CLI on ``PATH`` → ``faster_whisper``.
    """
    cli = _cli_backend(cfg)
    if cli:
        return cli
    if _faster_whisper_available():
        return _FASTER_WHISPER
    return None


def transcribe(path: str | Path, cfg: object | None = None) -> str:
    """Transcribe an audio file to text using the first available local backend.

    Raises:
        TranscriptionUnavailable: if no local engine is available.
        TranscriptionError: if the chosen engine ran but failed.
    """
    backend = available_transcriber(cfg)
    if backend is None:
        raise TranscriptionUnavailable(
            "no local transcription engine — install faster-whisper "
            "(`pipx inject tg-notes faster-whisper`) or set whisper_cmd to a whisper CLI"
        )
    if backend == _FASTER_WHISPER:
        return _transcribe_faster_whisper(path, cfg)
    return _transcribe_cli(backend, path, cfg)


def _model_name(cfg: object | None) -> str:
    """Return the configured whisper model, or the default."""
    return (getattr(cfg, "whisper_model", None) if cfg is not None else None) or _DEFAULT_MODEL


def _transcribe_faster_whisper(path: str | Path, cfg: object | None) -> str:
    """Transcribe via the :mod:`faster_whisper` package; join segment texts, stripped."""
    try:
        from faster_whisper import WhisperModel
    except Exception as exc:  # pragma: no cover - guarded by availability check
        raise TranscriptionUnavailable("faster-whisper is not importable") from exc
    try:
        model = WhisperModel(_model_name(cfg))
        segments, _info = model.transcribe(str(path))
        parts = [seg.text.strip() for seg in segments if getattr(seg, "text", "").strip()]
    except Exception as exc:  # surface any engine failure as TranscriptionError
        raise TranscriptionError(f"faster-whisper failed: {exc}") from exc
    return " ".join(parts).strip()


def _transcribe_cli(cmd: str, path: str | Path, cfg: object | None) -> str:
    """Transcribe via a whisper CLI, writing the transcript into a temp dir and reading it.

    The binary basename selects the argument template:

    - openai-whisper (basename ``whisper``):
      ``<cmd> <path> --model <m> --output_format txt --output_dir <tmp>`` → ``<stem>.txt``;
    - whisper.cpp (``whisper-cli`` / ``main``):
      ``<cmd> -f <path> -otxt -of <tmp>/<stem>`` → ``<tmp>/<stem>.txt``.
    """
    name = Path(cmd).name
    # openai-whisper's CLI is named exactly `whisper`; whisper.cpp ships `whisper-cli`/`main`.
    openai_style = name in ("whisper", "whisper.exe")
    stem = Path(path).stem
    with tempfile.TemporaryDirectory(prefix="tg-notes-transcribe-") as tmp:
        tmpdir = Path(tmp)
        txt_path = tmpdir / f"{stem}.txt"
        if openai_style:
            argv = [
                cmd,
                str(path),
                "--model",
                _model_name(cfg),
                "--output_format",
                "txt",
                "--output_dir",
                str(tmpdir),
            ]
        else:
            argv = [cmd, "-f", str(path), "-otxt", "-of", str(tmpdir / stem)]
        try:
            # Safe: fixed argv (no shell), binary resolved earlier via which/existing path;
            # only file paths we control are interpolated. capture_output keeps it quiet.
            proc = subprocess.run(  # nosec B603
                argv, capture_output=True, text=True, timeout=_CLI_TIMEOUT, check=False
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise TranscriptionError(f"{name} failed to run: {exc}") from exc
        if proc.returncode != 0:
            tail = (proc.stderr or proc.stdout or "").strip()[-500:]
            raise TranscriptionError(f"{name} exited {proc.returncode}: {tail}")
        try:
            return txt_path.read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise TranscriptionError(
                f"{name} produced no transcript at {txt_path.name}: {exc}"
            ) from exc
