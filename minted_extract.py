# based on https://tex.stackexchange.com/a/130755
import argparse
import fnmatch

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("file")
    parser.add_argument("patterns")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    with open(args.file) as f:
        lines = f.readlines()

    patterns = args.patterns.split(",")
    pattern = None
    started = False

    print(r"\begin{minted}{python}")

    for pattern in patterns:
        while lines:
            line = lines.pop(0)
            if started:
                print(line, end="")

            if fnmatch.fnmatchcase(line.strip(), pattern):
                if not started:
                    print(line, end="")
                started = True
                break

    if not started:
        print(f"Pattern {pattern!r} not found")

    print(r"\end{minted}")


if __name__ == "__main__":
    main()
