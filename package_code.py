"""Example script to get code files for distribution.

This creates a .zip file from all files in code/ in the development repository
(i.e. where you'd also have your .tex files), but with all comments stripped
off.
"""

import argparse
import pathlib
import subprocess
import zipfile

import minted_extract


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Package code for participants")
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


def process_file(path: pathlib.Path) -> str:
    cleaned_lines = []
    with path.open("r") as src:
        for line in src:
            cleaned, _comment = minted_extract.split_line(line.rstrip())
            cleaned_lines.append(cleaned)

    return "\n".join(cleaned_lines)


def make_zip(files: dict[pathlib.Path, str], out_path: pathlib.Path) -> None:
    with zipfile.ZipFile(out_path, "w") as zipf:
        for file_path, contents in files.items():
            print(file_path)
            zipf.writestr(str(file_path), contents)


def main() -> None:
    args = parse_args()
    code_files = get_code_files()
    processed = {file: process_file(file) for file in code_files}
    make_zip(processed, args.filename)


if __name__ == "__main__":
    main()
