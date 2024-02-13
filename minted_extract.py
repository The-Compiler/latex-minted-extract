# based on https://tex.stackexchange.com/a/130755
import argparse
import sys

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("codefile")
    parser.add_argument("delim1")
    parser.add_argument("delim2")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    with open(args.codefile) as f:
        code = f.read()

    print(r"\begin{minted}{python}")
    print(code.split(args.delim1, 1)[1].split(args.delim2, 1)[0])
    print(r"\end{minted}")


if __name__ == "__main__":
    main()
