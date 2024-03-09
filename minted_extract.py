# Originally inspired by https://tex.stackexchange.com/a/130755
from __future__ import annotations

import re
import collections
import argparse
import pathlib
import enum
import sys
from typing import Iterator


class Token(enum.Enum):
    START = "<-"
    END = "->"
    HL = "!!"
    HL_START = "<!"
    HL_END = "!>"


TOKEN_PAT = r"|".join(re.escape(token.value) for token in Token)
COMMENT_RE = re.compile(
    rf"(?P<code>.*) +# (?P<comment>({TOKEN_PAT}) .*)"
)


class Error(Exception):
    pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--minted-lang", help="Language for minted", default="python")
    parser.add_argument("--minted-opts", help="Options for minted", default="")
    parser.add_argument(  # somewhat awkard to make the LaTeX side easier
        "--show-name",
        help="Also show file name",
        type=lambda v: bool(int(v)),
        choices=[0, 1],
    )
    parser.add_argument("file", help="Source file to read", type=pathlib.Path)
    parser.add_argument("snippet", help="Snippet name to extract")
    return parser.parse_args()


def tokens_to_minted_opts(
    tokens: list[tuple[int, Token]], snippet: str
) -> Iterator[str]:
    hl_start = None
    hl_ranges = []
    has_start = False
    has_end = False

    for lineno, token in tokens:
        if token == Token.START:
            if has_start:
                raise Error(f"Multiple start tokens in {tokens} for {snippet}")
            has_start = True
            yield f"firstline={lineno}"
        elif token == Token.END:
            if has_end:
                raise Error(f"Multiple end tokens in {tokens} for {snippet}")
            has_end = True
            yield f"lastline={lineno}"
            if hl_start is not None:  # ending snippet ends highlight
                hl_ranges.append(f"{hl_start}-{lineno}")
                hl_start = None
        elif token == Token.HL:
            hl_ranges.append(str(lineno))
        elif token == Token.HL_START:
            if hl_start is not None:
                raise Error(f"Nested highlight start at line {lineno}")
            hl_start = lineno
        elif token == Token.HL_END:
            if hl_start is None:
                raise Error(f"Unmatched highlight end at line {lineno}")
            hl_ranges.append(f"{hl_start}-{lineno}")
            hl_start = None
        else:
            raise Error(f"Unknown token: {token}")

    if hl_ranges:
        value = ",".join(hl_ranges)
        yield "highlightlines={%s}" % value

    if not has_start or not has_end:
        raise Error(f"Missing start/end tokens in {tokens} for {snippet}")


def expand_snippet_name(snippet: str) -> Iterator[str]:
    """Handle snippet names like `code-changes-[345]`."""
    if "[" not in snippet:
        yield snippet
        return

    start_idx = snippet.index("[")
    end_idx = snippet.index("]")
    prefix = snippet[:start_idx]
    suffix = snippet[end_idx + 1 :]
    for part in snippet[start_idx + 1 : end_idx]:
        yield prefix + part + suffix


def split_line(line: str) -> tuple[str, str | None]:
    m = COMMENT_RE.match(line)
    if m is None:
        return line, None

    return m.group("code"), m.group("comment")


def main() -> None:
    args = parse_args()
    # print(r"\begin{minted}{python}")
    # for a in sys.argv:
    #    print(repr(a))
    # print(r"\end{minted}")

    with open(args.file) as f:
        lines = f.read().splitlines()

    clean_lines = []
    minted_opts = args.minted_opts.split(",") if args.minted_opts else []

    # Mapping snippet name to list of (lineno, token)
    tokens: dict[str, list[tuple[int, Token]]] = collections.defaultdict(list)

    for lineno, line in enumerate(lines, start=1):
        code, comment = split_line(line)
        clean_lines.append(code)
        if comment is None:
            continue

        for part in comment.split(";"):
            token_str, snippet_pat = part.strip().split(" ", 1)
            try:
                token = Token(token_str)
            except ValueError:
                raise Error(f"Unknown token: {token_str}")
            for snippet in expand_snippet_name(snippet_pat):
                tokens[snippet].append((lineno, token))

    # print(dict(tokens))

    if args.snippet:  # empty arg: full file
        minted_opts += list(tokens_to_minted_opts(tokens[args.snippet], args.snippet))

    if args.show_name:
        name = args.file.relative_to(pathlib.PurePath("code"))
        print(r"\filenameheader{%s}" % name)

    minted_opts_str = ",".join(minted_opts)
    print(r"\begin{minted}[%s]{%s}" % (minted_opts_str, args.minted_lang))
    print("\n".join(clean_lines))
    print(r"\end{minted}")


if __name__ == "__main__":
    try:
        main()
    except Error as e:
        print(r"\errmessage{%s}" % e)
        sys.exit(str(e))
