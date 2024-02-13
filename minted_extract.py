# based on https://tex.stackexchange.com/a/130755
import sys
import argparse
import fnmatch

PATTERN_SEP = "!"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--minted-lang", help="Language for minted")
    parser.add_argument("--minted-opts", help="Options for minted")
    parser.add_argument("file", help="Source file to read")
    parser.add_argument(
        "patterns", help=f"Patterns to match, separated by '{PATTERN_SEP}'"
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    with open(args.file) as f:
        lines = f.readlines()

    patterns = args.patterns.split(PATTERN_SEP)
    output = []
    started = False

    for pattern in patterns:
        while lines:
            line = lines.pop(0)
            if started:
                output.append(line)

            if fnmatch.fnmatchcase(line.strip(), pattern):
                if not started:
                    output.append(line)
                started = True
                break
        else:
            msg = f"Remains unmatched: {pattern}"
            print(r"\errmessage{%s}" % msg)
            sys.exit(msg)

    opts = f"[{args.minted_opts}]" if args.minted_opts else ""
    print(r"\begin{minted}%s{%s}" % (opts, args.minted_lang))
    print("".join(output))
    print(r"\end{minted}")


if __name__ == "__main__":
    main()
