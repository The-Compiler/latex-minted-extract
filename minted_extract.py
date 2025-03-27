# SPDX-FileCopyrightText: 2024 Florian Bruhin <me@the-compiler.org>
#
# SPDX-License-Identifier: MIT

# Originally inspired by https://tex.stackexchange.com/a/130755
from __future__ import annotations

import re  # <- imports-[12]
import shlex
import dataclasses
import collections
import argparse
import pathlib  # !! imports-1
import enum # !! imports-2
import sys
from typing import Iterator  # -> imports-[12]


class Token(enum.Enum):
    START = "<-"
    END = "->"
    HL = "!!"
    HL_START = "<!"
    HL_END = "!>"
    HL_INLINE = "||"
    INLINE_REPLACE = "s/"
    JINJA = "%%"


_TokenList = list[tuple[int, Token, list[str]]]


TOKEN_PAT = r"|".join(re.escape(token.value) for token in Token)
COMMENT_RE = re.compile(rf"(?P<code>.*) *# (?P<comment>({TOKEN_PAT}) .*)")
EX_MARKER_RE = re.compile(r"\s*# exercise: \[(?P<label>.*)\]")


class Error(Exception):
    pass


class OutputType(enum.Enum):
    #: The distributed code.zip
    CODE = "code"
    #: The solution zip
    SOLUTION = "solution"
    #: Shown on the slides
    SLIDE = "slide"
    #: Where pytest runs without errors
    SELFTEST = "selftests"


@dataclasses.dataclass
class ParsedLine:
    lineno: int  # only for debugging
    code: str  # for non-TokenLine, the whole line


@dataclasses.dataclass
class TokenLine(ParsedLine):
    comment: str


@dataclasses.dataclass
class ExerciseMarkerLine(ParsedLine):
    label: str

    def to_solution(self) -> str:
        return self.code.replace("exercise:", "solution:")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--minted-lang", help="Language for minted", default="python")
    parser.add_argument("--minted-opts", help="Options for minted", default="")
    parser.add_argument(
        "--prefix",
        help="Directory prefix for code files",
        type=pathlib.Path,
        default=pathlib.Path(),
    )
    parser.add_argument(
        "--show-name",
        help="Also show file name",
        choices=["false", "true", "phantom"],
    )
    parser.add_argument(
        "--output-type",
        help="Which version of the code to output",
        choices=[t.value for t in OutputType],
        default=OutputType.SLIDE.value,
    )
    parser.add_argument("file", help="Source file to read", type=pathlib.Path)
    parser.add_argument("snippet", help="Snippet name to extract")
    return parser.parse_args()


def shlex_split(s: str) -> list[str]:
    """Reimplementation of shlex.split without backslash escaping."""
    assert s is not None
    lexer = shlex.shlex(s, posix=True)  # default for shlex.split
    lexer.whitespace_split = True
    lexer.escape = ""
    return list(lexer)


def format_token_list(tokens: _TokenList) -> str:
    return "\n".join(
        f"{lineno}: {token.value} {', '.join(token_args)}"
        for lineno, token, token_args in tokens
    )


def tokens_to_minted_opts(tokens: _TokenList, snippet: str) -> Iterator[str]:
    hl_start = None
    hl_ranges = []
    has_start = False
    has_end = False

    for lineno, token, token_args in tokens:
        if token == Token.START:
            if has_start:
                raise Error(
                    f"Multiple start tokens for {snippet} in:\n"
                    f"{format_token_list(tokens)}"
                )
            has_start = True
            yield f"firstline={lineno}"
        elif token == Token.END:
            if has_end:
                raise Error(
                    f"Multiple end tokens for {snippet} in:\n"
                    f"{format_token_list(tokens)}"
                )
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
        elif token in [Token.HL_INLINE, Token.INLINE_REPLACE]:
            yield "escapeinside=||"
        else:
            raise Error(f"Unknown token for minted opts: {token}")

    if hl_ranges:
        value = ",".join(hl_ranges)
        yield "highlightlines={%s}" % value

    if not has_start or not has_end:
        missing = []
        if not has_start:
            missing.append("start")
        if not has_end:
            missing.append("end")
        raise Error(
            f"Missing {'/'.join(missing)} token for {snippet} in:\n"
            f"{format_token_list(tokens)}"
        )


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


def parse_line(line: str, lineno: int) -> ParsedLine:
    if (match := COMMENT_RE.match(line)) is not None:
        code = match.group("code").rstrip(" ")
        comment = match.group("comment")
        return TokenLine(code=code, comment=comment, lineno=lineno)
    elif (match := EX_MARKER_RE.match(line)) is not None:
        label = match.group("label")
        return ExerciseMarkerLine(code=line, lineno=lineno, label=label)
    else:
        # Normal code line without special comment
        return ParsedLine(code=line, lineno=lineno)


def search_replace_code(code: str, search: str, replace: str, lineno: int) -> str:
    not_found_msg = f"Failed to find {search!r} in {code!r} (line {lineno})"

    if search.startswith("/") and search.endswith("/"):
        try:
            pattern = re.compile(search[1:-1])
            if not pattern.search(code):
                raise Error(not_found_msg)
            return pattern.sub(replace.replace("\\", "\\\\"), code)
        except re.error as e:
            raise Error(f"{search!r}: {e}")

    if search not in code:
        raise Error(not_found_msg)
    return code.replace(search, replace)


def transform_code(lines: list[str], tokens: _TokenList) -> Iterator[str]:
    code_tokens = collections.defaultdict(list)
    for lineno, token, token_args in tokens:
        if token in [Token.HL_INLINE, Token.INLINE_REPLACE]:
            code_tokens[lineno].append((token, token_args))

    for lineno, line in enumerate(lines, start=1):
        parsed = parse_line(line, lineno)
        code = parsed.code
        for token, token_args in code_tokens[lineno]:
            if token is Token.HL_INLINE:
                [search] = token_args
                replace = r"|\highlightbox{%s}|" % totex(search)
                code = search_replace_code(code, search, replace, lineno)
            elif token is Token.INLINE_REPLACE:
                search, replace = token_args
                code = search_replace_code(code, search, replace, lineno)
            else:
                assert False, token

        yield code


def totex(value: str) -> str:
    # https://stackoverflow.com/q/16259923
    replacements = {
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\^{}",
        "\\": r"\textbackslash{}",
        "\n": "\\\\",
    }
    return "".join(replacements.get(c, c) for c in value)


def use_jinja(path: pathlib.Path) -> bool:
    return path.suffix in [".py", ".ini"]  # FIXME what about others?


def jinja_prepare(code: str) -> str | None:
    """Prepare the code for jinja if jinja comments are used."""
    jinja_comment = f"# {Token.JINJA.value} "
    output = []
    uses_jinja = False
    for lineno, line in enumerate(code.splitlines(), start=1):
        has_jinja_syntax = any(marker in line for marker in ["{{", "{%"])
        if line.strip().startswith(jinja_comment):
            uses_jinja = True
            output.append(line.replace(jinja_comment, ""))
        elif line.strip().startswith("#") and has_jinja_syntax:
            raise Error(f"Stray jinja syntax on line {lineno}: {line}")
        else:
            output.append(line)

    return "\n".join(output) if uses_jinja else None


def jinja_render(contents: str, output_type: OutputType) -> str:
    import jinja2

    return jinja2.Template(contents, trim_blocks=True, lstrip_blocks=True).render(
        # FIXME should SELFTEST always imply SOLUTION too?
        solution=output_type in [OutputType.SOLUTION, OutputType.SELFTEST],
        selftest=output_type == OutputType.SELFTEST,
        slide=output_type == OutputType.SLIDE,
    )


def read_code(file: pathlib.Path, output_type: OutputType) -> str:
    code = file.read_text()
    # Jinja needs to happen before going through the lines, as line numbers could shift.
    # To avoid issues with leftovers "# %%" with trim_blocks=True, we cut those
    # out first, before anything gets to Jinja. We also avoid using jinja if
    # there are no "# %%" comments in the file, because importing jinja has a
    # non-negligible time cost.
    if use_jinja(file):
        jinja_code = jinja_prepare(code)
        if jinja_code is not None:
            return jinja_render(jinja_code, output_type=output_type)
    return code


def parse_lines(code: str) -> Iterator[ParsedLine]:
    for lineno, line in enumerate(code.splitlines(), start=1):
        yield parse_line(line, lineno)


def main() -> None:
    args = parse_args()

    minted_opts = args.minted_opts.split(",") if args.minted_opts else []

    # Mapping snippet name to list of (lineno, token, *args)
    tokens: dict[str, _TokenList] = collections.defaultdict(list)

    path = args.prefix / args.file
    try:
        code = read_code(path, output_type=OutputType(args.output_type))
    except IOError as e:
        raise Error(f"Failed to read file: {e}")

    for parsed in parse_lines(code):
        if not isinstance(parsed, TokenLine):
            continue

        for part in parsed.comment.split(";"):
            token_str, snippet_pat, *token_args = shlex_split(part.strip())
            try:
                token = Token(token_str)
            except ValueError:
                raise Error(f"Unknown token: {token_str}")

            if token == Token.INLINE_REPLACE:
                arg_count = 2
            elif token == Token.HL_INLINE:
                arg_count = 1
            else:
                arg_count = 0

            if len(token_args) != arg_count:
                raise Error(
                    f"Expected {arg_count} arguments for {token}, "
                    f"but got {len(token_args)}: {token_args} (line {parsed.lineno})"
                )

            for snippet in expand_snippet_name(snippet_pat):
                tokens[snippet].append((parsed.lineno, token, token_args))

    # print(dict(tokens))

    if args.snippet:  # empty arg: full file
        minted_opts += list(tokens_to_minted_opts(tokens[args.snippet], args.snippet))

    if args.show_name == "true":
        print(r"\filenameheader{%s}" % args.file)
    elif args.show_name == "phantom":
        print(r"\vphantom{\filenameheader{%s}}" % args.file)

    minted_code = "\n".join(transform_code(code.splitlines(), tokens[args.snippet]))

    minted_opts_str = ",".join(minted_opts)
    print(r"\begin{minted}[%s]{%s}" % (minted_opts_str, args.minted_lang))
    print(minted_code)
    print(r"\ end{minted}".replace(" ", ""))  # hack so LaTeX can read this file as example...


if __name__ == "__main__":
    try:
        main()
    except Error as e:
        print(r"\errmessage{%s}" % e)
        sys.exit(str(e))
