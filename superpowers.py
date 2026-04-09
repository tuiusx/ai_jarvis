import argparse
import fnmatch
import subprocess
import sys
from pathlib import Path

from core.settings import get_setting, load_settings


REQUIRED_IGNORE_RULES = (
    "config/settings.local.yaml",
    "recordings/",
    "runs/",
    "faces/",
    "state/",
    "memory.json",
    "runs.zip",
    "yolov8*.pt",
    "face_recognizer.task",
    ".ultralytics/",
    "Ultralytics/",
    "PyAudio-*.whl",
)


def _normalize_path(path: str) -> str:
    return str(path).replace("\\", "/").lstrip("./")


def _match_pattern(path: str, pattern: str) -> bool:
    norm_path = _normalize_path(path)
    norm_pattern = _normalize_path(pattern)
    basename = Path(norm_path).name

    if norm_pattern.endswith("/"):
        return norm_path.startswith(norm_pattern)

    if any(token in norm_pattern for token in "*?[]"):
        return fnmatch.fnmatch(norm_path, norm_pattern) or fnmatch.fnmatch(basename, norm_pattern)

    if "/" in norm_pattern:
        return norm_path == norm_pattern

    return basename == norm_pattern


def find_sensitive_tracked_files(tracked_files):
    flagged = []
    for file_path in tracked_files:
        if any(_match_pattern(file_path, pattern) for pattern in REQUIRED_IGNORE_RULES):
            flagged.append(_normalize_path(file_path))
    return sorted(flagged)


def parse_ignore_rules(ignore_text: str):
    rules = set()
    for line in ignore_text.splitlines():
        candidate = line.strip()
        if not candidate or candidate.startswith("#"):
            continue
        rules.add(candidate)
    return rules


def find_missing_ignore_rules(ignore_rules):
    return [rule for rule in REQUIRED_IGNORE_RULES if rule not in ignore_rules]


def run_git_ls_files(cwd: Path):
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "Falha ao executar git ls-files.")
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def run_pytest(cwd: Path):
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q"],
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
    )
    return result.returncode == 0, result.stdout + result.stderr


def run_checks(cwd: Path, skip_tests: bool):
    ok = True
    messages = []

    ignore_file = cwd / ".gitignore"
    if not ignore_file.exists():
        ok = False
        messages.append("[FAIL] .gitignore nao encontrado.")
    else:
        ignore_rules = parse_ignore_rules(ignore_file.read_text(encoding="utf-8"))
        missing_rules = find_missing_ignore_rules(ignore_rules)
        if missing_rules:
            ok = False
            messages.append("[FAIL] Regras ausentes no .gitignore: " + ", ".join(missing_rules))
        else:
            messages.append("[OK] Regras criticas de privacidade presentes no .gitignore.")

    try:
        tracked_files = run_git_ls_files(cwd)
    except RuntimeError as exc:
        ok = False
        messages.append(f"[FAIL] Nao foi possivel listar arquivos rastreados: {exc}")
        tracked_files = []

    sensitive_tracked = find_sensitive_tracked_files(tracked_files)
    if sensitive_tracked:
        ok = False
        messages.append("[FAIL] Arquivos sensiveis rastreados: " + ", ".join(sensitive_tracked))
    else:
        messages.append("[OK] Nenhum artefato sensivel esta rastreado no Git.")

    if skip_tests:
        messages.append("[SKIP] Testes nao executados (flag --skip-tests).")
    else:
        tests_ok, tests_output = run_pytest(cwd)
        if tests_ok:
            messages.append("[OK] Testes passaram.")
        else:
            ok = False
            messages.append("[FAIL] Testes falharam.\n" + tests_output.strip())

    settings_file = cwd / "config" / "settings.yaml"
    settings_example = cwd / "config" / "settings.example.yaml"
    if not settings_example.exists():
        ok = False
        messages.append("[FAIL] config/settings.example.yaml nao encontrado.")
    else:
        messages.append("[OK] config/settings.example.yaml presente.")

    if settings_file.exists():
        settings_text = settings_file.read_text(encoding="utf-8", errors="ignore")
        for line in settings_text.splitlines():
            stripped = line.strip()
            if not stripped.startswith("api_key:"):
                continue
            value = stripped.split(":", 1)[1].strip().strip("\"'")
            if value and value.lower() not in {"null", "none"}:
                ok = False
                messages.append(
                    "[FAIL] config/settings.yaml contem api_key preenchida. "
                    "Prefira OPENAI_API_KEY por variavel de ambiente."
                )
                break
        else:
            messages.append("[OK] config/settings.yaml sem api_key fixa.")

        loaded = load_settings(str(cwd))
        mode = str(get_setting(loaded, "app.mode", "dev")).lower()
        long_memory_file = str(get_setting(loaded, "memory.long_term_file", "state/memory.json"))
        if not long_memory_file.startswith("state/"):
            ok = False
            messages.append("[FAIL] memory.long_term_file deve ficar em state/ para evitar commits acidentais.")
        else:
            messages.append("[OK] memory.long_term_file em pasta state/.")

        if mode == "prod" and not bool(get_setting(loaded, "security.enforce_env_secrets", False)):
            ok = False
            messages.append("[FAIL] Em modo prod, security.enforce_env_secrets deve estar true.")

    return ok, messages


def main():
    parser = argparse.ArgumentParser(description="Validador rapido de qualidade e privacidade do projeto.")
    parser.add_argument("--skip-tests", action="store_true", help="Nao executa pytest.")
    args = parser.parse_args()

    cwd = Path.cwd()
    ok, messages = run_checks(cwd=cwd, skip_tests=args.skip_tests)
    for message in messages:
        print(message)

    if ok:
        print("Resumo: projeto validado com sucesso.")
        return 0

    print("Resumo: foram encontrados problemas.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
