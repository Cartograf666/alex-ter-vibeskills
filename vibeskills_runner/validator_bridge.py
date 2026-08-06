import os
import re
import site
import stat
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from typing import Any, Dict, List, Sequence, Set

import yaml

from .errors import ValidationError

DEFAULT_MAX_STREAM_BYTES = 1024 * 1024  # 1 MiB stream limit
SHA256_REGEX = re.compile(r"^[0-9a-f]{64}$")


def get_site_packages_dir() -> str:
    """Find a runtime dependency root without consulting import state or sys.path."""
    candidates = [site.getusersitepackages(), *site.getsitepackages()]
    for candidate in candidates:
        root = Path(candidate).resolve()
        jsonschema_init = root / "jsonschema" / "__init__.py"
        yaml_init = root / "yaml" / "__init__.py"
        if root.is_dir() and jsonschema_init.is_file() and yaml_init.is_file():
            return str(root)
    raise ValidationError(
        "Could not locate trusted runtime dependencies (jsonschema and yaml) in site-packages."
    )


def get_isolated_env(
    allowed_keys: Set[str], trusted_import_dirs: Sequence[Path] = ()
) -> Dict[str, str]:
    """Build a sanitized environment based on a strict allowlist.

    ``trusted_import_dirs`` are appended to PYTHONPATH so trusted scripts can
    import their siblings. PYTHONSAFEPATH strips the script's own directory
    from sys.path on Python 3.11+, so a validator that relies on sibling
    imports needs its directory granted explicitly rather than implicitly.
    """
    env = {}
    base_allow = {
        "PATH",
        # locales
        "LANG",
        "LC_ALL",
        "LC_COLLATE",
        "LC_CTYPE",
        "LC_MESSAGES",
        "LC_MONETARY",
        "LC_NUMERIC",
        "LC_TIME",
        # temp directories
        "TMPDIR",
        "TEMP",
        "TMP",
        # Windows systemroot
        "SYSTEMROOT",
        "COMSPEC",
    }
    for k, v in os.environ.items():
        if k in base_allow or k in allowed_keys:
            env[k] = v

    # Add Python isolation variables
    env["PYTHONNOUSERSITE"] = "1"
    env["PYTHONSAFEPATH"] = "1"
    env["PYTHONDONTWRITEBYTECODE"] = "1"

    # Set PYTHONPATH strictly to site-packages plus explicitly trusted directories.
    # site-packages stays first so a trusted script directory cannot shadow
    # jsonschema or yaml.
    path_entries = [get_site_packages_dir()]
    for directory in trusted_import_dirs:
        path_entries.append(str(Path(directory).resolve()))
    env["PYTHONPATH"] = os.pathsep.join(path_entries)

    return env


def check_trusted_file(file_path: Path, trusted_root: Path) -> None:
    """Ensure trusted file exists, is not a symlink, is a regular file, and resides within trusted_root."""
    abs_root = trusted_root.resolve()

    # Check symlink via lstat directly on path before resolve
    if file_path.is_symlink() or os.path.islink(str(file_path)):
        raise ValidationError(f"Security error: File '{file_path}' is a symbolic link.")

    try:
        st = os.lstat(str(file_path))
    except OSError as e:
        raise ValidationError(f"Trusted file not found or inaccessible: {file_path}") from e

    if not stat.S_ISREG(st.st_mode):
        raise ValidationError(f"Security error: File '{file_path}' is not a regular file.")

    abs_file = file_path.resolve()
    try:
        abs_file.relative_to(abs_root)
    except ValueError as exc:
        raise ValidationError(
            f"Security error: File '{abs_file}' escapes trusted root '{abs_root}'"
        ) from exc


def check_trusted_script(script_path: Path, trusted_root: Path) -> None:
    """Ensure script is a regular file, not a symlink, and resides within TRUSTED_ROOT."""
    check_trusted_file(script_path, trusted_root)


class IsolatedProcessResult:
    """Holds stdout, stderr, and exit code from isolated subprocess execution."""

    def __init__(self, returncode: int, stdout: str, stderr: str):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def run_isolated_python(
    command: List[str],
    *,
    cwd: Path,
    env: Dict[str, str],
    timeout_seconds: float = 10.0,
    max_stdout_bytes: int = DEFAULT_MAX_STREAM_BYTES,
    max_stderr_bytes: int = DEFAULT_MAX_STREAM_BYTES,
) -> IsolatedProcessResult:
    """Execute Python subprocess with bounded execution time, pipe draining, and stream limits."""
    if not command or command[0] != sys.executable:
        raise ValidationError("Isolated subprocess must run using sys.executable")

    try:
        proc = subprocess.Popen(
            command,
            cwd=str(cwd),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
        )
    except Exception as exc:
        raise ValidationError(f"Failed to launch isolated subprocess: {exc}") from exc

    stdout_chunks: List[bytes] = []
    stderr_chunks: List[bytes] = []
    overflow_occurred = threading.Event()
    overflow_stream = [""]

    def read_stream(stream, chunks: List[bytes], max_bytes: int, stream_name: str):
        bytes_read = 0
        try:
            while True:
                chunk = stream.read(4096)
                if not chunk:
                    break
                bytes_read += len(chunk)
                if bytes_read > max_bytes:
                    overflow_stream[0] = stream_name
                    overflow_occurred.set()
                    try:
                        proc.kill()
                    except OSError:
                        pass
                    break
                chunks.append(chunk)
        except Exception:
            pass

    t_out = threading.Thread(
        target=read_stream,
        args=(proc.stdout, stdout_chunks, max_stdout_bytes, "stdout"),
        daemon=True,
    )
    t_err = threading.Thread(
        target=read_stream,
        args=(proc.stderr, stderr_chunks, max_stderr_bytes, "stderr"),
        daemon=True,
    )
    t_out.start()
    t_err.start()

    timed_out = False
    try:
        proc.wait(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        timed_out = True
        try:
            proc.kill()
        except OSError:
            pass
        proc.wait()

    t_out.join(timeout=1.0)
    t_err.join(timeout=1.0)

    if proc.stdout:
        try:
            proc.stdout.close()
        except OSError:
            pass
    if proc.stderr:
        try:
            proc.stderr.close()
        except OSError:
            pass

    if timed_out:
        raise ValidationError(f"Subprocess execution timed out after {timeout_seconds} seconds")

    if overflow_occurred.is_set():
        raise ValidationError(
            f"Subprocess {overflow_stream[0]} output overflow (exceeded stream byte limit)"
        )

    stdout_str = b"".join(stdout_chunks).decode("utf-8", errors="replace")
    stderr_str = b"".join(stderr_chunks).decode("utf-8", errors="replace")

    return IsolatedProcessResult(proc.returncode, stdout_str, stderr_str)


def run_validate_semantics(
    contract_data: Dict[str, Any],
    repository: Path,
    trusted_scripts_dir: Path,
    trusted_schemas_dir: Path,
) -> List[str]:
    """Execute contract semantics validation within an isolated subprocess."""
    trusted_root = trusted_scripts_dir.parent
    validator_script = trusted_scripts_dir / "validate_contract.py"
    check_trusted_script(validator_script, trusted_root)

    schema_path = trusted_schemas_dir / "development-contract.schema.json"
    check_trusted_file(schema_path, trusted_root)

    with tempfile.NamedTemporaryFile(
        suffix=".yaml", mode="w", encoding="utf-8", delete=False
    ) as f:
        yaml.safe_dump(contract_data, f, allow_unicode=True)
        temp_path = Path(f.name)

    try:
        allowed_keys = {"VIBESKILLS_APPROVAL_HMAC_KEY", "VIBESKILLS_APPROVAL_HMAC_KEYS"}
        env = get_isolated_env(allowed_keys, trusted_import_dirs=(trusted_scripts_dir,))

        cmd = [
            sys.executable,
            str(validator_script),
            str(temp_path),
            "--schema",
            str(schema_path),
            "--repository",
            str(repository),
        ]

        res = run_isolated_python(cmd, cwd=trusted_root, env=env, timeout_seconds=10.0)

        errors = []
        output = res.stderr or ""
        for line in output.splitlines():
            line = line.strip()
            if line.startswith("ERROR:"):
                errors.append(line[6:].strip())
            elif line:
                errors.append(line)

        if not errors and res.returncode != 0:
            errors.append(res.stderr.strip() or f"Subprocess returned {res.returncode}")

        return errors

    finally:
        if temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass


def run_contract_payload_sha256(
    contract_data: Dict[str, Any], trusted_scripts_dir: Path
) -> str:
    """Execute contract payload hashing via an isolated helper worker."""
    trusted_root = trusted_scripts_dir.parent
    worker_script = Path(__file__).resolve().parent / "contract_hash_worker.py"
    check_trusted_script(worker_script, trusted_root)

    with tempfile.NamedTemporaryFile(
        suffix=".yaml", mode="w", encoding="utf-8", delete=False
    ) as f:
        yaml.safe_dump(contract_data, f, allow_unicode=True)
        temp_path = Path(f.name)

    try:
        # Hashing worker does not receive any HMAC secrets
        env = get_isolated_env(set())

        cmd = [
            sys.executable,
            str(worker_script),
            str(temp_path),
            str(trusted_scripts_dir),
        ]

        res = run_isolated_python(cmd, cwd=trusted_root, env=env, timeout_seconds=10.0)

        if res.returncode != 0:
            raise ValidationError(f"Contract hashing worker failed: {res.stderr.strip()}")

        out_lines = [line.strip() for line in res.stdout.splitlines() if line.strip()]
        if len(out_lines) != 1:
            raise ValidationError(f"Contract hashing worker output contains unexpected extra lines: '{res.stdout}'")
        out = out_lines[0]
        if not SHA256_REGEX.match(out):
            raise ValidationError(f"Contract hashing worker output invalid: '{out}'")

        return out

    finally:
        if temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass


def run_validator_subprocess(
    run_record_path: Path,
    contract_path: Path,
    repo_root: Path,
    trusted_root: Path,
    trusted_scripts_dir: Path,
    trusted_schemas_dir: Path,
) -> IsolatedProcessResult:
    """Execute the validate_run_record subprocess with an isolated environment."""
    validator_script = trusted_scripts_dir / "validate_run_record.py"
    check_trusted_script(validator_script, trusted_root)

    run_record_schema = trusted_schemas_dir / "run-record.schema.json"
    contract_schema = trusted_schemas_dir / "development-contract.schema.json"
    check_trusted_file(run_record_schema, trusted_root)
    check_trusted_file(contract_schema, trusted_root)

    allowed_keys = {
        "VIBESKILLS_APPROVAL_HMAC_KEY",
        "VIBESKILLS_APPROVAL_HMAC_KEYS",
        "VIBESKILLS_RUN_HMAC_KEY",
        "VIBESKILLS_RUN_HMAC_KEYS",
    }
    env = get_isolated_env(allowed_keys, trusted_import_dirs=(trusted_scripts_dir,))

    cmd = [
        sys.executable,
        str(validator_script),
        str(run_record_path),
        "--contract",
        str(contract_path),
        "--repository",
        str(repo_root),
        "--schema",
        str(run_record_schema),
        "--contract-schema",
        str(contract_schema),
    ]

    return run_isolated_python(cmd, cwd=trusted_root, env=env, timeout_seconds=10.0)
