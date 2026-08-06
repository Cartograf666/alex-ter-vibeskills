import argparse
import sys
from pathlib import Path

from .errors import RunnerError
from .run_service import init_run, get_status, resume_run, verify_run


def main(args_list=None) -> int:
    parser = argparse.ArgumentParser(
        description="vibeskills-runner: Executable development run controller kernel."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # init
    init_parser = subparsers.add_parser("init", help="Initialize a new development run.")
    init_parser.add_argument("--contract", required=True, help="Path to development contract.")
    init_parser.add_argument("--run-id", required=True, help="Unique run identifier.")
    init_parser.add_argument("--manager-provider", required=True, help="Manager AI provider.")
    init_parser.add_argument("--manager-model", required=True, help="Manager model name.")
    init_parser.add_argument("--manager-model-version", required=True, help="Exact version of the manager model.")
    init_parser.add_argument("--manager-context-id", required=True, help="Manager runtime context identifier.")
    init_parser.add_argument("--repository", type=Path, default=Path.cwd(), help="Path to repository root.")

    # status
    status_parser = subparsers.add_parser("status", help="Get status of an existing run.")
    status_parser.add_argument("--run-id", required=True, help="Run identifier.")
    status_parser.add_argument("--json", action="store_true", help="Output status in JSON format.")
    status_parser.add_argument("--repository", type=Path, default=Path.cwd(), help="Path to repository root.")

    # resume
    resume_parser = subparsers.add_parser("resume", help="Resume a run after interruption.")
    resume_parser.add_argument("--run-id", required=True, help="Run identifier.")
    resume_parser.add_argument("--repository", type=Path, default=Path.cwd(), help="Path to repository root.")

    # verify
    verify_parser = subparsers.add_parser("verify", help="Verify run record against contract.")
    verify_parser.add_argument("--run-id", required=True, help="Run identifier.")
    verify_parser.add_argument("--contract", required=True, help="Path to development contract.")
    verify_parser.add_argument("--repository", type=Path, default=Path.cwd(), help="Path to repository root.")

    parsed = parser.parse_args(args_list)

    try:
        if parsed.command == "init":
            init_run(
                repository_path=parsed.repository,
                contract_rel_path=parsed.contract,
                run_id=parsed.run_id,
                manager_provider=parsed.manager_provider,
                manager_model=parsed.manager_model,
                manager_model_version=parsed.manager_model_version,
                manager_context_id=parsed.manager_context_id,
            )
        elif parsed.command == "status":
            out = get_status(
                repository_path=parsed.repository,
                run_id=parsed.run_id,
                as_json=parsed.json,
            )
            if out:
                print(out)
        elif parsed.command == "resume":
            resume_run(
                repository_path=parsed.repository,
                run_id=parsed.run_id,
            )
        elif parsed.command == "verify":
            verify_run(
                repository_path=parsed.repository,
                run_id=parsed.run_id,
                contract_rel_path=parsed.contract,
            )
        return 0
    except RunnerError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        # Fallback traceback-free exit for all unexpected errors as required
        print(f"ERROR: Unexpected runner failure: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
