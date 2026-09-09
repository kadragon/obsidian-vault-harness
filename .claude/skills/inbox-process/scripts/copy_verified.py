#!/usr/bin/env python3
"""Copy an Inbox attachment into the vault and prove the final link is safe.

This is deliberately small and dependency-free.  It never removes the source
and never overwrites an existing destination.  Callers must choose the durable
destination directory (for example ``_Sources/_Assets/{domain}`` or an action
note's attachment folder) after discovering it from vault conventions.

The ``copy`` command returns JSON containing the actual destination.  The
``verify-link`` command is the cleanup gate: it checks that the note contains
the exact vault-relative wikilink and that source and durable copy have the
same SHA-256 digest.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import sys
from dataclasses import asdict, dataclass
from pathlib import Path


CHUNK_SIZE = 1024 * 1024


class CopyError(RuntimeError):
    """A source copy or cleanup-gate invariant could not be proved."""


@dataclass(frozen=True)
class CopyResult:
    source: str
    destination: str
    relative_destination: str
    wikilink: str
    status: str
    verified: bool
    bytes: int
    sha256: str
    source_preserved: bool = True


def _regular(path: Path, label: str) -> None:
    try:
        mode = os.lstat(path).st_mode
    except FileNotFoundError as exc:
        raise CopyError(f"{label} not found: {path}") from exc
    except OSError as exc:
        raise CopyError(f"cannot inspect {label} {path}: {exc}") from exc
    if stat.S_ISLNK(mode):
        raise CopyError(f"refusing symlink {label}: {path}")
    if not stat.S_ISREG(mode):
        raise CopyError(f"{label} is not a regular file: {path}")


def _vault_root(vault: str | Path) -> Path:
    root = Path(vault).expanduser().resolve()
    if not root.is_dir():
        raise CopyError(f"vault directory not found: {root}")
    return root


def _inside(path: Path, root: Path, label: str) -> Path:
    """Resolve a path and reject lexical or symlink traversal outside root."""
    resolved = path.resolve(strict=False)
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise CopyError(f"{label} is outside vault: {path}") from exc
    return resolved


def _reject_symlink_below_vault(raw_path: Path, vault: Path) -> None:
    """Reject symlink components after the raw path reaches the vault root.

    The macOS ``/var`` alias may resolve to ``/private/var`` before the vault
    root, so walking raw parents all the way to ``/`` would reject an ordinary
    system path.  Find the lexical anchor whose resolved value is the vault,
    then inspect only components selected by the caller.
    """
    anchor = raw_path
    while anchor != anchor.parent:
        if anchor.resolve(strict=False) == vault:
            current = anchor
            try:
                parts = raw_path.relative_to(anchor).parts
            except ValueError:
                return
            for part in parts:
                current /= part
                if current.is_symlink():
                    raise CopyError(f"refusing symlink in destination path: {current}")
            return
        anchor = anchor.parent


def _destination_dir(vault: Path, value: str | Path, *, create: bool) -> Path:
    raw = Path(value).expanduser()
    raw_path = raw if raw.is_absolute() else vault / raw
    resolved = _inside(raw_path, vault, "destination directory")
    _reject_symlink_below_vault(raw_path, vault)

    if create and not raw_path.exists():
        try:
            raw_path.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise CopyError(f"cannot create destination directory {raw_path}: {exc}") from exc
    if create and (not raw_path.is_dir() or raw_path.is_symlink()):
        raise CopyError(f"destination is not a real directory: {raw_path}")
    if raw_path.exists() and (not raw_path.is_dir() or raw_path.is_symlink()):
        raise CopyError(f"destination is not a real directory: {raw_path}")
    if raw_path.exists() and raw_path.resolve() != resolved:
        raise CopyError(f"destination path changed during inspection: {raw_path}")
    return resolved


def _destination_path(vault: Path, value: str | Path) -> Path:
    raw = Path(value).expanduser()
    path = raw if raw.is_absolute() else vault / raw
    resolved = _inside(path, vault, "destination")
    _reject_symlink_below_vault(path, vault)
    return resolved


def _note_path(vault: Path, value: str | Path) -> Path:
    """Resolve the note like a destination: vault-relative unless absolute."""
    raw = Path(value).expanduser()
    path = raw if raw.is_absolute() else vault / raw
    resolved = _inside(path, vault, "note")
    _reject_symlink_below_vault(path, vault)
    return resolved


def _durable_destination(vault: Path, path: Path) -> Path:
    """Allow only the two vault locations that own durable attachments."""
    resolved = _inside(path, vault, "destination")
    relative = resolved.relative_to(vault)
    if not (
        relative.parts[:2] == ("_Sources", "_Assets")
        or relative.parts[:1] == ("10_Areas",)
    ):
        raise CopyError(
            "destination must be under _Sources/_Assets or 10_Areas; "
            f"refusing transient path: {path}"
        )
    return resolved


def _name(value: str | None, source: Path) -> str:
    name = value or source.name
    if not name or name in {".", ".."} or Path(name).name != name:
        raise CopyError(f"destination name must be a single filename: {name!r}")
    if "/" in name or "\\" in name:
        raise CopyError(f"destination name must be a single filename: {name!r}")
    # These characters have meaning in an Obsidian wikilink.  Refuse rather
    # than emitting a link that points at a heading, alias, or malformed path.
    if any(char in name for char in "#|[]\r\n"):
        raise CopyError(f"destination name is not representable in a wikilink: {name!r}")
    return name


def _collision_name(name: str, number: int) -> str:
    if number == 1:
        return name
    path = Path(name)
    return f"{path.stem}_{number}{path.suffix}"


def _sha256(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    try:
        with path.open("rb") as fh:
            while True:
                chunk = fh.read(CHUNK_SIZE)
                if not chunk:
                    break
                digest.update(chunk)
                size += len(chunk)
    except OSError as exc:
        raise CopyError(f"cannot hash {path}: {exc}") from exc
    return digest.hexdigest(), size


def _relative(vault: Path, path: Path) -> str:
    try:
        return path.resolve(strict=False).relative_to(vault).as_posix()
    except ValueError as exc:
        raise CopyError(f"path is outside vault: {path}") from exc


def _result(
    source: Path,
    destination: Path,
    vault: Path,
    status: str,
    verified: bool,
    digest: str,
    size: int,
) -> CopyResult:
    relative = _relative(vault, destination)
    return CopyResult(
        source=str(source),
        destination=str(destination),
        relative_destination=relative,
        wikilink=f"[[{relative}]]",
        status=status,
        verified=verified,
        bytes=size,
        sha256=digest,
    )


def copy_verified(
    source: str | Path,
    destination_dir: str | Path,
    vault: str | Path,
    *,
    destination_name: str | None = None,
    dry_run: bool = False,
) -> CopyResult:
    """Copy one source file to a durable vault directory and verify it.

    Existing byte-identical files are safely reused.  A different file gets a
    ``_2``/``_3`` suffix before any write.  Symlinks and paths outside the
    vault fail closed.  The source is never changed by this function.
    """
    source_path = Path(source).expanduser()
    _regular(source_path, "source")
    vault_path = _vault_root(vault)
    destination_path = _destination_dir(vault_path, destination_dir, create=not dry_run)
    destination_path = _durable_destination(vault_path, destination_path)
    base_name = _name(destination_name, source_path)
    source_digest, source_size = _sha256(source_path)

    number = 1
    while True:
        candidate = destination_path / _collision_name(base_name, number)
        # The parent was validated above.  Re-checking the candidate protects
        # against a caller passing an unusual filename on a case-folding FS.
        _inside(candidate, vault_path, "destination")
        try:
            mode = os.lstat(candidate).st_mode
        except FileNotFoundError:
            mode = None
        except OSError as exc:
            raise CopyError(f"cannot inspect destination {candidate}: {exc}") from exc

        if mode is not None:
            if stat.S_ISLNK(mode):
                raise CopyError(f"refusing symlink destination: {candidate}")
            if stat.S_ISREG(mode):
                try:
                    if os.path.samefile(source_path, candidate):
                        raise CopyError(
                            "source and destination are the same file; "
                            "Inbox cleanup requires a durable copy"
                        )
                except FileNotFoundError:
                    pass
                existing_digest, existing_size = _sha256(candidate)
                if existing_digest == source_digest and existing_size == source_size:
                    # Check the source once more before declaring a reused copy
                    # safe; this catches a source modified while it was read.
                    final_source_digest, final_source_size = _sha256(source_path)
                    if (final_source_digest, final_source_size) != (source_digest, source_size):
                        raise CopyError(
                            f"source changed while verifying existing copy: {source_path}"
                        )
                    return _result(
                        source_path,
                        candidate,
                        vault_path,
                        "reused" if not dry_run else "dry-run",
                        True,
                        source_digest,
                        source_size,
                    )
            number += 1
            continue

        if dry_run:
            return _result(
                source_path,
                candidate,
                vault_path,
                "dry-run",
                False,
                source_digest,
                source_size,
            )

        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        flags |= getattr(os, "O_NOFOLLOW", 0)
        flags |= getattr(os, "O_BINARY", 0)
        created = False
        try:
            fd = os.open(candidate, flags, 0o600)
            created = True
            with os.fdopen(fd, "wb") as out, source_path.open("rb") as inp:
                while True:
                    chunk = inp.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    out.write(chunk)
                out.flush()
                os.fsync(out.fileno())

            destination_digest, destination_size = _sha256(candidate)
            final_source_digest, final_source_size = _sha256(source_path)
            if (destination_digest, destination_size) != (source_digest, source_size):
                raise CopyError(f"destination verification failed: {candidate}")
            if (final_source_digest, final_source_size) != (source_digest, source_size):
                raise CopyError(f"source changed while copying: {source_path}")
            return _result(
                source_path,
                candidate,
                vault_path,
                "copied",
                True,
                destination_digest,
                destination_size,
            )
        except FileExistsError:
            # Another process won this candidate.  Never overwrite it; inspect
            # it on the next loop and either reuse it or choose the next suffix.
            if created:
                try:
                    candidate.unlink()
                except OSError:
                    pass
            number += 1
            continue
        except CopyError:
            if created:
                try:
                    candidate.unlink()
                except OSError:
                    pass
            raise
        except (OSError, ValueError) as exc:
            if created:
                try:
                    candidate.unlink()
                except OSError:
                    pass
            raise CopyError(f"copy failed; source preserved: {source_path}: {exc}") from exc


def verify_copy(
    source: str | Path,
    destination: str | Path,
    vault: str | Path,
) -> CopyResult:
    """Verify source and destination are regular, in-vault, byte-identical."""
    source_path = Path(source).expanduser()
    vault_path = _vault_root(vault)
    destination_path = _durable_destination(
        vault_path, _destination_path(vault_path, destination)
    )
    _regular(source_path, "source")
    _regular(destination_path, "destination")
    source_digest, source_size = _sha256(source_path)
    destination_digest, destination_size = _sha256(destination_path)
    if (source_digest, source_size) != (destination_digest, destination_size):
        raise CopyError(
            f"byte mismatch: source={source_path} destination={destination_path}"
        )
    return _result(
        source_path,
        destination_path,
        _vault_root(vault),
        "verified",
        True,
        destination_digest,
        destination_size,
    )


def verify_link(
    source: str | Path,
    note: str | Path,
    destination: str | Path,
    vault: str | Path,
) -> dict:
    """Verify byte identity and the exact final wikilink in a note."""
    vault_path = _vault_root(vault)
    note_path = _note_path(vault_path, note)
    _regular(note_path, "note")
    copy = verify_copy(source, destination, vault_path)
    try:
        note_text = note_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise CopyError(f"cannot read note for link verification: {note_path}: {exc}") from exc
    # Only a real Markdown wikilink counts.  Ignore fenced code, inline code,
    # and HTML comments so a copied example cannot authorize source deletion.
    note_text = re.sub(r"<!--.*?-->", "", note_text, flags=re.DOTALL)
    note_text = re.sub(r"`[^`]*`", "", note_text)
    visible_lines = []
    fenced = False
    for line in note_text.splitlines():
        marker = line.lstrip()
        if marker.startswith("```") or marker.startswith("~~~"):
            fenced = not fenced
            continue
        if not fenced:
            visible_lines.append(line)
    visible_text = "\n".join(visible_lines)
    link_pattern = rf"(?<!\!){re.escape(copy.wikilink)}"
    if not re.search(link_pattern, visible_text):
        raise CopyError(f"final wikilink missing from note: {copy.wikilink}")
    data = asdict(copy)
    data.update({"note": str(note_path), "link_present": True, "verified": True})
    return data


def _json(data: object) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    copy_parser = sub.add_parser("copy", help="copy and verify one source file")
    copy_parser.add_argument("source")
    copy_parser.add_argument("destination_dir")
    copy_parser.add_argument("--vault", default=".")
    copy_parser.add_argument("--name", dest="destination_name")
    copy_parser.add_argument("--dry-run", action="store_true")

    verify_parser = sub.add_parser("verify", help="verify source and durable copy")
    verify_parser.add_argument("source")
    verify_parser.add_argument("destination")
    verify_parser.add_argument("--vault", default=".")

    link_parser = sub.add_parser("verify-link", help="verify copy and exact note wikilink")
    link_parser.add_argument("source")
    link_parser.add_argument("note")
    link_parser.add_argument("destination")
    link_parser.add_argument("--vault", default=".")

    args = parser.parse_args(argv)
    try:
        if args.command == "copy":
            result = copy_verified(
                args.source,
                args.destination_dir,
                args.vault,
                destination_name=args.destination_name,
                dry_run=args.dry_run,
            )
            _json(asdict(result))
        elif args.command == "verify":
            _json(asdict(verify_copy(args.source, args.destination, args.vault)))
        else:
            _json(verify_link(args.source, args.note, args.destination, args.vault))
    except CopyError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
