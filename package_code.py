import sys
import enum
import pathlib
import subprocess
import dataclasses
import zipfile
import shutil
from typing import Annotated

import rich

import minted_extract
import typer

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent


class Error(Exception):
    pass


@dataclasses.dataclass
class ProcessedFile:
    filename: pathlib.Path
    contents: str


class TrainingType(enum.Enum):
    LONG = "long"
    SHORT = "short"


EXCLUDE = [
    pathlib.Path("code", "requirements-dev.txt"),
]
SHORT_EXCLUDE = [
    # FIXME can we exclude more?
    pathlib.Path("code", "mocking"),
]


def get_code_files(use_git: bool = True) -> list[pathlib.Path]:
    if not use_git:
        code_path = REPO_ROOT / "code"
        assert code_path.is_dir(), code_path
        return [f for f in code_path.rglob("*") if f.is_file()]

    assert (REPO_ROOT / ".git").exists(), REPO_ROOT
    proc = subprocess.run(
        ["git", "ls-files", "code"],
        capture_output=True,
        text=True,
        check=True,
        cwd=REPO_ROOT,
    )
    assert not proc.stderr, proc.stderr
    return [pathlib.Path(p) for p in proc.stdout.splitlines()]


def filter_files(
    files: list[pathlib.Path],
    type: TrainingType,
    exclude: list[pathlib.Path],
    tox: bool,
    yaml: bool,
) -> list[pathlib.Path]:
    for f in files:
        assert (REPO_ROOT / f).is_file(), f

    exclude.extend(EXCLUDE)
    if type == TrainingType.SHORT:
        exclude.extend(SHORT_EXCLUDE)

    if not tox:
        exclude.append(pathlib.Path("code", "tox"))
    if not yaml:
        exclude.append(pathlib.Path("code", "hooks", "yaml"))

    for e in exclude:
        assert (REPO_ROOT / e).exists(), e

    return [f for f in files if not any(f.is_relative_to(e) for e in exclude)]


def process_line(line: str, lineno: int, solution: bool) -> str:
    parsed = minted_extract.parse_line(line.rstrip(), lineno)
    if isinstance(parsed, minted_extract.ExerciseMarkerLine) and solution:
        return parsed.to_solution()
    return parsed.code


def process_file(
    file: pathlib.Path, output_type: minted_extract.OutputType
) -> ProcessedFile | None:
    solution = output_type == minted_extract.OutputType.SOLUTION
    cleaned_lines = []
    has_solution = False

    code = minted_extract.read_code(REPO_ROOT / file, output_type=output_type)
    for parsed in minted_extract.parse_lines(code):
        if isinstance(parsed, minted_extract.ExerciseMarkerLine) and solution:
            cleaned_lines.append(parsed.to_solution())
            has_solution = True
        else:
            cleaned_lines.append(parsed.code)

    if solution and not has_solution:
        # skip files without solution markers
        # FIXME what about e.g. pytest.ini?
        return None

    contents = "\n".join(cleaned_lines) + "\n"
    return ProcessedFile(filename=file, contents=contents)


def make_zip(
    files: list[ProcessedFile],
    filename: pathlib.Path,
    output_type: minted_extract.OutputType,
) -> None:
    root_subdir = output_type.value
    with zipfile.ZipFile(filename, "w") as zipf:
        for file in files:
            zip_path = root_subdir / file.filename.relative_to("code")
            zipname = str(zip_path)
            rich.print(zipname)
            zipf.writestr(zipname, file.contents)


def output_to_dir(
    files: list[ProcessedFile],
    output_path: pathlib.Path,
    quiet: bool = False,
    demo: bool = False,
) -> None:
    for file in files:
        if demo:  # We want a code/ subdir as we have other stuff too
            rel_path = file.filename
        else:
            rel_path = file.filename.relative_to("code")
        if not quiet:
            rich.print(rel_path)
        file_path = output_path / rel_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(file.contents)


def dir_has_markers(path: pathlib.Path, markers: set[str]) -> bool:
    return path.is_dir() and all((path / marker).exists() for marker in markers)


def prepare_output_dir(output_path: pathlib.Path, *, force: bool) -> None:
    assert not output_path.suffix, output_path
    if output_path.exists():
        if force:
            if dir_has_markers(
                output_path, {"pytest.ini", "rpncalc"}
            ) or dir_has_markers(
                output_path, {".git", "code", "dayX.ipynb", "start_demos.sh"}
            ):
                shutil.rmtree(output_path)
            else:
                raise Error(f"Refusing to delete unknown {output_path}")
        else:
            raise Error(f"Output directory {output_path} already exists")


def create_git_repo(output_path: pathlib.Path) -> None:
    git_proc = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
        cwd=REPO_ROOT,
    )
    assert not git_proc.stderr, git_proc.stderr
    commit_hash = git_proc.stdout.strip()

    subprocess.run(["git", "init", "-q"], check=True, cwd=output_path)
    subprocess.run(["git", "add", "."], check=True, cwd=output_path)
    subprocess.run(
        ["git", "commit", "-qm", f"Initialize code based on {commit_hash}"],
        check=True,
        cwd=output_path,
    )
    rich.print(f"Created git repository in {output_path}")


def copy_demo_files(output_path: pathlib.Path) -> None:
    demo_files = [
        REPO_ROOT / "scripts" / "start_demos.sh",
        REPO_ROOT / "other" / "dayX.ipynb",
    ]
    for path in demo_files:
        shutil.copy(path, output_path)
    rich.print("Copied demo files to output directory")


def create_venv(output_path: pathlib.Path) -> None:
    gitignore_file = output_path / ".gitignore"
    gitignore_file.write_text(".venv/")  # FIXME more?

    subprocess.run(["uv", "venv"], check=True, cwd=output_path)
    subprocess.run(
        [
            "uv",
            "pip",
            "install",
            "-r",
            REPO_ROOT / "code" / "requirements.txt",
            "-r",
            REPO_ROOT / "code" / "requirements-dev.txt",
        ],
        check=True,
        cwd=output_path,
    )


def process_all(
    code_files: list[pathlib.Path], output_type: minted_extract.OutputType
) -> list[ProcessedFile]:
    return [
        processed
        for file in code_files
        if (processed := process_file(file, output_type=output_type)) is not None
    ]


def get_output_type(solutions: bool, selftest: bool) -> minted_extract.OutputType:
    if solutions:
        return minted_extract.OutputType.SOLUTION
    elif selftest:
        return minted_extract.OutputType.SELFTEST
    else:
        return minted_extract.OutputType.CODE


def main(
    type: Annotated[TrainingType, typer.Argument(help="Type of training")],
    output: Annotated[pathlib.Path, typer.Argument(help="Output dir/.zip file")],
    no_git: Annotated[
        bool, typer.Option("--no-git", help="Get files in code/ without git")
    ] = False,
    demo: Annotated[
        bool,
        typer.Option(
            "--demo", help="Create directory with additional files for live demos"
        ),
    ] = False,
    solutions: Annotated[
        bool, typer.Option("-s", "--solutions", help="Package solutions")
    ] = False,
    selftest: Annotated[
        bool, typer.Option("-t", "--selftest", help="Package selftests")
    ] = False,
    tox: Annotated[bool, typer.Option("--tox", help="Include tox exercises")] = False,
    yaml: Annotated[
        bool, typer.Option("--yaml", help="Include YAML exercises")
    ] = False,
    exclude: Annotated[
        list[pathlib.Path] | None, typer.Option("-e", "--exclude", help="Exclude files")
    ] = None,
    force: Annotated[
        bool, typer.Option("-f", "--force", help="Overwrite output directory")
    ] = False,
) -> None:
    if output.suffix and output.suffix != ".zip":
        raise Error("Output filename must be directory or have .zip extension")

    output_type = get_output_type(solutions=solutions, selftest=selftest)

    code_files = filter_files(
        get_code_files(use_git=not no_git),
        type=type,
        exclude=exclude or [],
        tox=tox,
        yaml=yaml,
    )
    processed = process_all(code_files, output_type=output_type)
    if output.suffix == ".zip":
        if demo:
            raise Error("Can't use --demo with zip output")
        make_zip(processed, output, output_type=output_type)
    else:
        prepare_output_dir(output, force=force)
        output_to_dir(processed, output, demo=demo)
        if demo:
            if no_git:
                raise Error("Cannot create git repo without using git")
            create_git_repo(output)
            copy_demo_files(output)
            create_venv(output)


if __name__ == "__main__":
    try:
        typer.run(main)
    except Error as e:
        rich.print(f"[red]Error:[/] {e}")
        sys.exit(1)
