import importlib.machinery
import importlib.util
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List

from .errors import ValidationError

UNTRUSTED_KEYS = [
    "validate_contract", "contract_lib", "validate_run_record",
    "architecture_lib", "validate_architecture", "design_system_lib",
    "validate_design_system", "finding_fingerprint"
]


def load_trusted_module(module_name: str, file_path: Path) -> Any:
    """Dynamically load a python module by absolute path, avoiding sys.modules caching and verifying __file__."""
    abs_path = file_path.resolve()
    if not abs_path.is_file():
        raise ValidationError(f"Trusted module file not found: {abs_path}")

    unique_name = f"trusted_bridge_{module_name}_{abs_path.stat().st_mtime_ns}"

    loader = importlib.machinery.SourceFileLoader(unique_name, str(abs_path))
    spec = importlib.util.spec_from_loader(unique_name, loader)
    if spec is None or spec.loader is None:
        raise ValidationError(f"Failed to create spec for module load: {abs_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[unique_name] = module

    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        if unique_name in sys.modules:
            del sys.modules[unique_name]
        raise ValidationError(f"Failed to execute trusted module '{abs_path}': {exc}") from exc

    loaded_file = getattr(module, "__file__", None)
    if loaded_file is None or Path(loaded_file).resolve() != abs_path:
        raise ValidationError(
            f"Security Error: Loaded module __file__ '{loaded_file}' does not match expected '{abs_path}'"
        )

    return module


def get_sanitized_sys_path(sys_path_list: List[str], trusted_scripts_dir: Path, repository: Path) -> List[str]:
    """Sanitize original sys.path list to exclude any target repository paths, while retaining standard libraries."""
    sanitized = [str(trusted_scripts_dir)]
    repo_resolved = repository.resolve()
    for p in sys_path_list:
        if not p:
            continue
        try:
            p_path = Path(p).resolve()
        except Exception:
            continue
        # Exclude current directory, repo root, and anything inside the repo
        if p_path == Path(".").resolve() or p_path == repo_resolved or repo_resolved in p_path.parents:
            continue
        if p_path == trusted_scripts_dir.resolve():
            continue
        sanitized.append(p)
    return sanitized


def run_validate_semantics(contract: Dict[str, Any], repository: Path, trusted_scripts_dir: Path) -> List[str]:
    """Execute contract semantics validation within a strict sys.path and sys.modules sandbox."""
    original_path = sys.path.copy()
    saved_modules = {}

    # Calculate sanitized path before clearing sys.path
    sanitized = get_sanitized_sys_path(original_path, trusted_scripts_dir, repository)

    # Isolate and sanitize sys.path
    sys.path.clear()
    sys.path.extend(sanitized)

    # Temporarily remove untrusted name collisions
    for key in UNTRUSTED_KEYS:
        if key in sys.modules:
            saved_modules[key] = sys.modules.pop(key)

    try:
        val_mod = load_trusted_module("validate_contract", trusted_scripts_dir / "validate_contract.py")
        return val_mod.validate_semantics(contract, repository)
    finally:
        sys.path.clear()
        sys.path.extend(original_path)
        for key, mod in saved_modules.items():
            sys.modules[key] = mod


def run_contract_payload_sha256(contract: Dict[str, Any], trusted_scripts_dir: Path) -> str:
    """Execute contract payload hashing within a strict sys.path and sys.modules sandbox."""
    original_path = sys.path.copy()
    saved_modules = {}

    # Calculate sanitized path before clearing sys.path
    sanitized = get_sanitized_sys_path(original_path, trusted_scripts_dir, trusted_scripts_dir.parent)

    # Isolate and sanitize sys.path
    sys.path.clear()
    sys.path.extend(sanitized)

    for key in UNTRUSTED_KEYS:
        if key in sys.modules:
            saved_modules[key] = sys.modules.pop(key)

    try:
        lib_mod = load_trusted_module("contract_lib", trusted_scripts_dir / "contract_lib.py")
        return lib_mod.contract_payload_sha256(contract)
    finally:
        sys.path.clear()
        sys.path.extend(original_path)
        for key, mod in saved_modules.items():
            sys.modules[key] = mod


def run_validator_subprocess(
    run_record_path: Path,
    contract_path: Path,
    repo_root: Path,
    trusted_root: Path,
    trusted_scripts_dir: Path,
    trusted_schemas_dir: Path
) -> subprocess.CompletedProcess:
    """Execute the validate_run_record subprocess with isolated environment and secure working directory."""
    env = os.environ.copy()
    # Clear PYTHONPATH or restrict to trusted scripts directory
    env["PYTHONPATH"] = str(trusted_scripts_dir)

    validator_script = trusted_scripts_dir / "validate_run_record.py"
    if not validator_script.is_file():
        raise ValidationError(f"Trusted validation script not found: {validator_script}")

    cmd = [
        sys.executable,
        str(validator_script),
        str(run_record_path),
        "--contract",
        str(contract_path),
        "--repository",
        str(repo_root),
        "--schema",
        str(trusted_schemas_dir / "run-record.schema.json"),
        "--contract-schema",
        str(trusted_schemas_dir / "development-contract.schema.json"),
    ]

    return subprocess.run(
        cmd,
        cwd=str(trusted_root),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False
    )
