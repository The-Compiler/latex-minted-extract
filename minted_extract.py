# Originally inspired by https://tex.stackexchange.com/a/130755
import collections
import argparse
import enum
import re
from typing import Iterator


COMMENT = "#@ "


class Token(enum.Enum):
    START = "<"
    END = ">"
    HL = "!"
    HL_START = "!<"
    HL_END = "!>"
    CONTEXT = "..."


# e.g.: def func():  #@ ! slide-1
# ->                       def func():    #@        !                slide-1
COMMENT_RE = re.compile(rf"(?P<code>.*)\s*{COMMENT}(?P<token>[^ ]*) (?P<snippet>.*)")


class Error(Exception):
    pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--minted-lang", help="Language for minted")
    parser.add_argument("--minted-opts", help="Options for minted", default="")
    parser.add_argument(  # somewhat awkard to make the LaTeX side easier
        "--show-name",
        help="Also show file name",
        type=lambda v: bool(int(v)),
        choices=[0, 1],
    )
    parser.add_argument("file", help="Source file to read")
    parser.add_argument("snippet", help="Snippet name to extract")
    return parser.parse_args()


def tokens_to_minted_opts(tokens: list[tuple[int, Token]]) -> Iterator[str]:
    hl_start = None
    hl_ranges = []

    for lineno, token in tokens:
        if token == Token.START:
            yield f"firstline={lineno}"
        elif token == Token.END:
            yield f"lastline={lineno}"
        elif token == Token.HL:
            hl_ranges.append(str(lineno))
        elif token == Token.HL_START:
            hl_start = lineno
        elif token == Token.HL_END:
            assert hl_start is not None
            hl_ranges.append(f"{hl_start}-{lineno}")
            hl_start = None
        elif token == Token.CONTEXT:
            raise Error("Context not supported yet")
        else:
            raise Error(f"Unknown token: {token}")

    if hl_ranges:
        yield f"highlightlines={','.join(hl_ranges)}"


def main() -> None:
    args = parse_args()
    # print(r"\begin{minted}{python}")
    # for a in sys.argv:
    #    print(repr(a))
    # print(r"\end{minted}")

    with open(args.file) as f:
        lines = f.read().splitlines()

    clean_lines = []
    minted_opts = args.minted_opts.split(",")

    # Mapping snippet name to list of (lineno, token)
    tokens: dict[str, list[tuple[int, Token]]] = collections.defaultdict(list)

    for lineno, line in enumerate(lines, start=1):
        if COMMENT not in line:
            clean_lines.append(line)
            continue

        match = COMMENT_RE.match(line)
        assert match is not None, match

        clean_lines.append(match.group("code"))
        token = Token(match.group("token"))
        tokens[match.group("snippet")].append((lineno, token))

    minted_opts += list(tokens_to_minted_opts(tokens[args.snippets]))

    if args.show_name:
        print(r"\mintinline{python}{# %s}" % args.file)

    minted_opts_str = ','.join(minted_opts)
    print(r"\begin{minted}[%s]{%s}" % (minted_opts_str, args.minted_lang))
    print("\n".join(clean_lines))
    print(r"\end{minted}")


if __name__ == "__main__":
    main()
