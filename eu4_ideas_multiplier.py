#!python3

import argparse
import re
import sys
from io import TextIOWrapper
from typing import Callable


def process_file(in_file: TextIOWrapper,
                 out_file: TextIOWrapper,
                 multiplier: float,
                 block_predicate: Callable[[list[str]], bool],
                 illegal_modifiers: list[str]) -> None:
    blocks = list[str]()
    for line in in_file:
        output_line = line
        if (match := re.fullmatch(r"\s*(\S+)\s+=\s+\{\s*(?:#.*)?", line)):
            blocks.append(match.group(1))
        elif re.fullmatch(r"\s*\}\s*(?:#.*)?", line):
            blocks.pop()
        elif block_predicate(blocks):
            output_line = re.sub(
                pattern=r"(\S+)\s+=\s+(-?\d+\.?\d*)",
                repl=lambda x: process_line(x, multiplier, illegal_modifiers),
                string=line
            )
        out_file.write(output_line)


def process_line(match: re.Match[str],
                 multiplier: float,
                 illegal_modifiers: list[str]) -> str:
    if any(
        re.fullmatch(illegal_modifier, match.group(1))
        for illegal_modifier in illegal_modifiers
    ):
        return match.group(0)
    return f"{match.group(1)} = {float(match.group(2)) * multiplier}"


def ideas_predicate(blocks: list[str]) -> bool:
    return not any(
        bad_block in blocks
        for bad_block in ['trigger', 'ai_will_do']
    )


def policies_predicate(blocks: list[str]) -> bool:
    return not any(
        bad_block in blocks
        for bad_block in ['potential', 'allow', 'ai_will_do']
    )


def custom_ideas_predicate(blocks: list[str]) -> bool:
    return not 'chance' in blocks


def setup_parser() -> argparse.ArgumentParser:
    EPILOG_MSG = """\
    This program assumes that input follows the formatting specified by the
    CWTools VSCode extension. Each statement should occupy its own line,
    including block declarations and closings. Patterns such as
    BLOCK = { MODIFIER = VALUE } may result in some modifiers not being
    processed properly.
    """

    parser = argparse.ArgumentParser(
        description="Multiplies the effects of modifiers in EU4 source files.",
        epilog=EPILOG_MSG
    )
    parser.add_argument(
        'source_type',
        choices=['ideas', 'policies', 'custom_ideas'],
        help="Modifier source type."
    )
    parser.add_argument(
        '-i', '--input',
        nargs='?',
        type=argparse.FileType('r', encoding='utf-8'),
        default=sys.stdin,
        help="Input file to parse. Defaults to standard input."
    )
    parser.add_argument(
        '-o', '--output',
        nargs='?',
        type=argparse.FileType('w', encoding='utf-8'),
        default=sys.stdout,
        help="Output file to write to. Defaults to standard output."
    )
    parser.add_argument('-m', '--multiplier', default=10, type=int)
    return parser


if __name__ == '__main__':
    args = setup_parser().parse_args()
    block_predicate = {
        'ideas': ideas_predicate,
        'policies': policies_predicate,
        'custom_ideas': custom_ideas_predicate
    }[args.source_type]
    illegal_modifiers = {
        'ideas': [],
        'policies': [],
        'custom_ideas': [
            r"level_cost_\d+",
            r"max_level",
            r"chance",
            r"default"
        ]
    }[args.source_type]
    with args.input as input:
        with args.output as output:
            process_file(
                in_file=input,
                out_file=output,
                multiplier=args.multiplier,
                block_predicate=block_predicate,
                illegal_modifiers=illegal_modifiers
            )
