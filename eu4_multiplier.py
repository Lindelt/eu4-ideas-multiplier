#!python3

import argparse
import json
import pathlib
import re
import tomllib
from collections.abc import Collection, Iterable, Mapping
from typing import TextIO

import paradox_parser as pdx

REGEX_ESTATE = re.compile(r"(?P<before>.*)<estate>(?P<after>.*)")
REGEX_FACTION = re.compile(r"(?P<before>.*)<faction>(?P<after>.*)")
REGEX_POWER = re.compile(
    r"(?P<before>.*)<government_power_type_id>(?P<after>.*)")
REGEX_TECH = re.compile(r"(?P<before>.*)<tech>(?P<after>.*)")

IGNORE_BLOCKS = {
    "ai_will_do",
    "ai",
    "allow",
    "can_end",
    "can_select",
    "can_start",
    "can_stop",
    "chance",
    "on_monthly",
    "potential",
    "progress",
    "target_province_weights",
    "trigger",
}

IGNORE_DIRS = {
    "ai_army",
    "ai_attitudes",
    "ai_personalities",
    "bookmarks",
    "cb_types",
    "client_states",
    "colonial_regions",
    "countries",
    "country_colors",
    "country_tags",
    "cultures",
    "custom_country_colors",
    "defines",
    "diplomatic_actions",
    "dynasty_colors",
    "estate_agendas",
    "estates_preload",
    "government_names",
    "governments",
    "imperial_incidents",
    "incidents",
    "insults",
    "natives",
    "new_diplomatic_actions",
    "on_actions",
    "opinion_modifiers",
    "parliament_bribes",
    "peace_treaties",
    "powerprojection",
    "prices",
    "province_names",
    "rebel_types",
    "region_colors",
    "religious_conversions",
    "revolt_triggers",
    "scripted_effects",
    "scripted_functions",
    "scripted_triggers",
    "subject_types",
    "timed_modifiers",
    "trade_companies",
    "tradenodes",
    "units_display",
    "units",
    "wargoal_types",
}


def load_estates(dirs: Iterable[str]) -> set[str]:
    print("Retrieving estates:")
    res = set[str]()
    for file in (f for d in dirs for f in pathlib.Path(d).iterdir()):
        print(f"  Parsing '{file}'.")
        with file.open(mode='r', encoding='Latin-1') as fd:
            for expression in pdx.parse_file(fd):
                assert isinstance(expression.rhs, pdx.Block)
                res.add(expression.lhs.value.removeprefix('estate_'))
    return res


def load_factions(dirs: Iterable[str], ignores: Collection[str]) -> set[str]:
    print("Retrieving factions:")
    res = set[str]()
    for file in (f for d in dirs for f in pathlib.Path(d).iterdir()):
        print(f"  Parsing '{file}'.")
        with file.open(mode='r', encoding='Latin-1') as fd:
            for expression in pdx.parse_file(fd):
                if expression.lhs.value in ignores:
                    continue
                assert isinstance(expression.rhs, pdx.Block)
                res.add(expression.lhs.value)
    return res


def load_powers(dirs: Iterable[str]) -> set[str]:
    print("Retrieving government power IDs:")
    res = set[str]()
    for file in (file for dir in dirs for file in pathlib.Path(dir).iterdir()):
        print(f"  Parsing '{file}'.")
        with file.open(mode='r', encoding='Latin-1') as fd:
            for top in pdx.parse_file(fd):
                assert isinstance(top.rhs, pdx.Block)
                for block in top.rhs.entries:
                    if block.lhs.value != "powers":
                        continue
                    assert isinstance(block.rhs, pdx.Block)
                    res.update(power.lhs.value for power in block.rhs.entries)
                    break
    return res


def load_modifiers(modifiers: TextIO,
                   multiplier: int | float,
                   ignores: Collection[str],
                   alternatives: Mapping[str, int | float],
                   tech_types: Iterable[str],
                   estates: Iterable[str],
                   factions: Iterable[str],
                   government_powers: Iterable[str]) -> dict[str, int | float]:
    res = dict[str, int | float]()
    for ident in (stripped for line in modifiers
                  if (stripped := line.rstrip()) not in ignores):
        if (match := REGEX_ESTATE.fullmatch(ident)) is not None:
            for estate in estates:
                key = f"{match.group('before')}{estate}{match.group('after')}"
                res[key] = alternatives.get(ident, multiplier)
        elif (match := REGEX_FACTION.fullmatch(ident)) is not None:
            for faction in factions:
                key = f"{match.group('before')}{faction}{match.group('after')}"
                res[key] = alternatives.get(ident, multiplier)
        elif (match := REGEX_POWER.fullmatch(ident)) is not None:
            for power in government_powers:
                key = f"{match.group('before')}{power}{match.group('after')}"
                res[key] = alternatives.get(ident, multiplier)
        elif (match := REGEX_TECH.fullmatch(ident)) is not None:
            for tech in tech_types:
                key = f"{match.group('before')}{tech}{match.group('after')}"
                res[key] = alternatives.get(ident, multiplier)
        else:
            res[ident] = alternatives.get(ident, multiplier)
    return res


def process_expression(expression: pdx.Expression,
                       modifiers: Mapping[str, int | float]) -> bool:
    if expression.lhs.value in IGNORE_BLOCKS:
        return False
    if isinstance(expression.rhs, pdx.Block):
        res = False
        for child_expression in expression.rhs.entries:
            res = process_expression(child_expression, modifiers) or res
        return res
    if (multiplier := modifiers.get(expression.lhs.value)) is not None:
        # Some modifier names may be used in other contexts
        # (e.g., merchants = yes in the diplomatic technology file).
        # Don't stop parsing, but make a note of them.
        if not isinstance(expression.rhs, pdx.Number):
            print(f"  {expression}")
            return False
        expression.rhs.value *= multiplier
        return True
    return False


def process_static_file(path: pathlib.Path,
                        modifiers: Mapping[str, int | float],
                        ignore: Collection[str]) -> list[pdx.Expression]:
    with path.open(mode='r', encoding='Latin-1') as file:
        tree = pdx.parse_file(file)
    changed = False
    for expression in tree:
        assert isinstance(expression.rhs, pdx.Block)
        if expression.lhs.value in ignore:
            continue
        for sub_expression in expression.rhs.entries:
            changed = process_expression(sub_expression, modifiers) or changed
    return tree if changed else []


def process_file(path: pathlib.Path,
                 modifiers: Mapping[str, int | float],
                 ignore_static: Collection[str]) -> list[pdx.Expression]:
    print(f"Processing '{path}':")
    if path.parent.name == "static_modifiers":
        return process_static_file(path=path, modifiers=modifiers,
                                   ignore=ignore_static)
    with path.open(mode='r', encoding='Latin-1') as file:
        tree = pdx.parse_file(file)
    changed = False
    for expression in tree:
        changed = process_expression(expression, modifiers) or changed
    return tree if changed else []


def process_target(source: pathlib.Path,
                   destination: pathlib.Path,
                   modifiers: Mapping[str, int | float],
                   ignore_static: Collection[str]):
    # Walk the source (target) directory, discovering eligible files.
    # Maintain a parallel destination path during the walk.
    stack = [(source, destination)]
    while stack:
        src, dst = stack.pop()
        if src.is_dir():
            for nxt in src.iterdir():
                if src.name == "common" and nxt.is_file():
                    continue
                if nxt.name in IGNORE_DIRS:
                    continue
                stack.append((nxt, dst.joinpath(nxt.name)))
        elif (tree := process_file(path=src, modifiers=modifiers,
                                   ignore_static=ignore_static)):
            if not dst.parent.exists():
                dst.parent.mkdir(parents=True)
            with dst.open(mode='w') as dst_fd:
                for exp in tree:
                    exp.print_pdx_script(file=dst_fd)
            print(f"  Changes written to '{dst}'.")
        else:
            print("  Skipping write, no changes made.")


def gen_modifiers(input: pathlib.Path, output: pathlib.Path,
                  config: pathlib.Path):
    with config.open(mode='rb') as fd_config:
        toml = tomllib.load(fd_config)
    estates = load_estates(toml['gen_modifiers']['estates'])
    factions = load_factions(toml['gen_modifiers']['factions'],
                             toml['gen_modifiers']['ignore_factions'])
    powers = load_powers(toml['gen_modifiers']['government_mechanics'])
    with input.open(mode='r') as fd:
        modifiers = load_modifiers(
            multiplier=toml['gen_modifiers']['multiplier'],
            ignores=toml['gen_modifiers']['ignores'],
            alternatives=toml['gen_modifiers']['alternatives'],
            tech_types=toml['gen_modifiers']['tech_types'],
            estates=estates, factions=factions,
            government_powers=powers, modifiers=fd,
        )
    with output.open(mode='w') as fd_output:
        fd_output.write(json.dumps(modifiers, indent=2))
    print(f"Modifiers written to '{output}'.")


def multiply(input: pathlib.Path, config: pathlib.Path):
    with config.open(mode='rb') as fd_config:
        toml = tomllib.load(fd_config)
    with input.open(mode='r') as fd_modifiers:
        modifiers: dict[str, int | float] = json.load(fd_modifiers)
    destination = pathlib.Path(toml['multiply']['destination'])
    ignore_static = set[str](toml['multiply']['ignore_static'])
    for target in toml['multiply']['targets']:
        process_target(source=pathlib.Path(target), destination=destination,
                       modifiers=modifiers, ignore_static=ignore_static)


def setup_argparse() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        suggest_on_error=True,
        description="Utility script for creating EU4 multiplier mods. "
                    "See subcommand documentation for further information.",
        epilog="Note: Given the irregularities which may be found in legal "
               "Paradox scripting structure, this utility implements a full "
               "parser for its file reading operations. While this approach "
               "results in less errors than a regex-based solution, it is "
               "also far less performant and requires files be fully loaded "
               "into memory before parsing.",
    )
    subs = parser.add_subparsers(dest="subcommand", required=True)
    gen_modifiers = subs.add_parser(
        'gen_modifiers', suggest_on_error=True,
        description="Generates a JSON table of modifier multipliers for use "
                    "by the 'multiply' subcommand. Generation behavior "
                    "is managed by the configuration file.",
    )
    gen_modifiers.add_argument(
        '-i', '--input', nargs=1, default="./modifiers.txt",
        type=pathlib.Path, required=False, metavar="INPUT_FILE",
        help="The file to read the raw modifiers from. "
             "Defaults to './modifiers.txt'.",
    )
    gen_modifiers.add_argument(
        '-o', '--output', nargs=1, default="./modifiers.json",
        type=pathlib.Path, required=False, metavar="OUTPUT_FILE",
        help="The file to write the modifier multipliers table to. "
             "Defaults to './modifiers.json'.",
    )
    gen_modifiers.add_argument(
        '-c', '--config', nargs=1, default="./config.toml",
        type=pathlib.Path, required=False, metavar="CONFIGURATION_FILE",
        help="The file to read configuration data from. "
             "Defaults to './config.toml'.",
    )
    multiply = subs.add_parser(
        'multiply', suggest_on_error=True,
        description="Recursively parses over a set of target 'common' "
                    "directories, multiplies the modifiers contained within, "
                    "and writes the results to a destination directory. "
                    "Parsing behavior is determined by the configuration "
                    "file.",
    )
    multiply.add_argument(
        '-i', '--input', nargs=1, default="./modifiers.json",
        type=pathlib.Path, required=False, metavar="MODIFIERS_FILE",
        help="JSON file containing a modifier multiplier table to be used "
             "during multiplication. Defaults to './modifiers.json'.",
    )
    multiply.add_argument(
        '-c', '--config', nargs=1, default="./config.toml",
        type=pathlib.Path, required=False, metavar="CONFIGURATION_FILE",
        help="The file to read configuration data from. "
             "Defaults to './config.toml'.",
    )
    return parser


if __name__ == "__main__":
    args = setup_argparse().parse_args()
    match args.subcommand:
        case "gen_modifiers":
            gen_modifiers(args.input, args.output, args.config)
        case "multiply":
            multiply(args.input, args.config)
