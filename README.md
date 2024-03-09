# LaTeX Minted extract

This project lets you use comment annotations inside code files, in order to
select snippets to use for [minted](https://github.com/gpoore/minted).

It also lets you use such annotations to select lines to be highlighted. The end
result is having snippets controlled by code comments, rather than needing to
provide line numbers to minted.

The following comments are currently recognized:

- `# <- NAME`: Start a snippet named `NAME`
- `# -> NAME`: End a snippet named `NAME`
- `# <! NAME`: Start highlighting for a snippet named `NAME`
- `# !> NAME`: End highlighting for a snippet named `NAME`
- `# !! NAME`: Highlight this line for a snippet named `NAME`

Those directives can be combined by `;`, e.g. `# <- part-2; !! part-2` to start
a snippet with the first line highlighted.

Snippet names can contain `[...]` patterns, e.g. `# -> part-[123]` ends
`part-1`, `part-2` and `part-3`. Note that ranges (`part[1-3]`) are not
supported, though a PR to add support would be appreciated!

To integrate this into your LaTeX project, add something like this to the
preamble:

```latex
\usepackage{keycommand}
\newkeycommand{\inputmintedex}[opts=,lang=python,bool showname=false][2]{%
    \input|"python scripts/minted_extract.py --minted-opts '\commandkey{opts}' --minted-lang '\commandkey{lang}' --show-name '\commandkey{showname}' '#1' '#2'"%
}
```

You will also need to define a `\filenameheader` command to specify how filenames should get printed when using `showname`, e.g.:

```latex
\newcommand{\filenameheader}[1]{\texttt{\detokenize{#1}:}}
```

then finally, to include a snippet from a file, use:

```latex
\inputmintedex[...]{code/example.py}{part-1}
```

with the following options available inside `[...]`:

- `opts={...}`: Options passed on to minted, e.g. `opts={gobble=4}`
- `lang=...`: The language to use for highlighting
- `showname=true`: Add a `\filenameheader` command to show the filename
