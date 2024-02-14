# based on https://tex.stackexchange.com/a/130755
import sys
import argparse
import fnmatch

PATTERN_SEP = "!"
HIGHLIGHT_SEP = "!!"


class Error(Exception):
    pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--minted-lang", help="Language for minted")
    parser.add_argument("--minted-opts", help="Options for minted", default="")
    parser.add_argument("--highlight", help="Patterns to highlight")
    parser.add_argument(  # somewhat awkard to make the LaTeX side easier
        "--show-name", help="Also show file name", type=bool, choices=[0, 1]
    )
    parser.add_argument("file", help="Source file to read")
    parser.add_argument(
        "patterns", help=f"Patterns to match, separated by '{PATTERN_SEP}'"
    )
    return parser.parse_args()


def match_patterns(lines: list[str], patterns: list[str]) -> tuple[int, int]:
    num_lines = list(enumerate(lines, start=1))
    n = None
    start = None

    for pattern in patterns:
        while num_lines:
            n, line = num_lines.pop(0)

            if fnmatch.fnmatchcase(line.strip(), pattern) or (
                not pattern and not line.strip()
            ):
                if start is None:
                    start = n
                break
        else:
            raise Error(f"Remains unmatched: {pattern}")

    assert start is not None
    assert n is not None
    return start, n


def main() -> None:
    args = parse_args()
    # print(r"\begin{minted}{python}")
    # for a in sys.argv:
    #    print(repr(a))
    # print(r"\end{minted}")

    with open(args.file) as f:
        lines = f.read().splitlines()

    patterns = args.patterns.split(PATTERN_SEP)
    highlight_patterns = args.highlight.split(HIGHLIGHT_SEP)
    minted_opts = args.minted_opts.split(",")

    start, end = match_patterns(lines, patterns)
    output = lines[start - 1 : end]

    highlight_pairs = [
        match_patterns(output, patterns.split(PATTERN_SEP))
        for patterns in highlight_patterns
    ]
    if highlight_pairs:
        val = ",".join(f"{start}-{end}" for start, end in highlight_pairs)
        minted_opts.append("highlightlines={%s}" % val)

    if args.show_name:
        print(r"\mintinline{python}{# %s}" % args.file)

    opts = f"[{','.join(minted_opts)}]" if minted_opts else ""
    print(r"\begin{minted}%s{%s}" % (opts, args.minted_lang))
    print("\n".join(output))
    print(r"\end{minted}")


if __name__ == "__main__":
    main()
