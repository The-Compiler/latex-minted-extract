import argparse
import pathlib
import subprocess
import dataclasses
import zipfile

import minted_extract


@dataclasses.dataclass
class ProcessedFile:

    filename: pathlib.Path
    contents: str


SHORT_EXCLUDE = [
    # FIXME can we exclude more?
    pathlib.Path("code", "hooks", "yaml"),
    pathlib.Path("code", "mocking"),
    pathlib.Path("code", "tox"),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Package code for participants")
    parser.add_argument("type", choices=["long", "short"], help="Type of training")
    parser.add_argument("filename", help="Output filename", type=pathlib.Path)
    args = parser.parse_args()
    if args.filename.suffix != ".zip":
        parser.error("Output filename must have .zip extension")
    return args


def get_code_files() -> list[pathlib.Path]:
    proc = subprocess.run(
        ["git", "ls-files", "code"], capture_output=True, text=True, check=True
    )
    assert not proc.stderr, proc.stderr
    return [pathlib.Path(p) for p in proc.stdout.splitlines()]


def filter_files(files: list[pathlib.Path], type: str) -> list[pathlib.Path]:
    for f in files:
        assert f.is_file(), f

    if type == "long":
        return files

    assert type == "short", type
    return [f for f in files if not any(f.is_relative_to(e) for e in SHORT_EXCLUDE)]


def process_file(file: pathlib.Path) -> None:
    cleaned_lines = []
    with file.open("r") as src:
        for line in src:
            cleaned, _comment = minted_extract.split_line(line.rstrip())
            cleaned_lines.append(cleaned)

    return ProcessedFile(filename=file, contents="\n".join(cleaned_lines))


def make_zip(files: list[ProcessedFile], filename: pathlib.Path) -> None:
    with zipfile.ZipFile(filename, "w") as zipf:
        for file in files:
            print(file.filename)
            zipf.writestr(str(file.filename), file.contents)


def main() -> None:
    args = parse_args()
    assert args.filename.suffix == ".zip", args.filename

    code_files = filter_files(get_code_files(), args.type)
    processed = [process_file(file) for file in code_files]
    make_zip(processed, args.filename)


if __name__ == "__main__":
    main()
