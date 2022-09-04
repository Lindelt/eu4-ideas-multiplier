#! python3

import argparse
import glob
import os
import re
from io import TextIOWrapper

STEAM_DIR = "D:\\SteamLibrary\\"
EUROPA_PATH = "steamapps\\common\\Europa Universalis IV\\common\\"
ILLEGAL_MODIFIERS = ["factor", "max_level", "default", "female_advisor_chance"]


def _process_directory(inroot: str,
                       outroot: str,
                       dir: str,
                       mult: float) -> None:
    os.makedirs(f"{outroot}{dir}\\", exist_ok=True)
    files = glob.glob(f"{dir}\\*.txt", root_dir=inroot)
    for file in files:
        with open(f"{inroot}{file}", mode='r') as infile:
            with open(f"{outroot}{file}", mode='w') as outfile:
                _process_file(infile, outfile, mult)


def _process_file(infile: TextIOWrapper,
                  outfile: TextIOWrapper,
                  mult: float) -> None:
    lockvar = 0  # tracks brackets for unalterable blocks
    for line in infile:
        if re.match(r"\s+(?:ai_will_do|chance)\s+=\s+{", line) or lockvar > 0:
            lockvar += line.count('{') - line.count('}')
            outfile.write(line)
        else:
            outfile.write(
                re.sub(
                    r"(\S+)\s+=\s+(-?\d+\.?\d*)",
                    lambda x: _process_line(x, mult),
                    line
                )
            )


def _process_line(match: re.Match[str], mult: float) -> str:
    if re.fullmatch(r"level_cost_\d+", match.group(1)):
        return match.group(0)
    if match.group(1) in ILLEGAL_MODIFIERS:
        return match.group(0)
    return f"{match.group(1)} = {float(match.group(2)) * mult}"


def _setup_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Multiplies the effects of ideas and policies in EU4"
        + " source files."
    )
    parser.add_argument(
        '-m', '--multiplier',
        default=10,
        type=int
    )
    parser.add_argument(
        '-i', '--root_in',
        default=f"{STEAM_DIR}{EUROPA_PATH}",
        help="Root input directory from which source directories are detected."
    )
    parser.add_argument(
        '-o', '--root_out',
        default=".\\common\\",
        help="Root output directory to which modified directories are written to."
    )
    parser.add_argument(
        '-d', '--dirs',
        nargs='+',
        default=["custom_ideas", "ideas", "policies"],
        metavar="DIRECTORY",
        help="Directories to be modified."
    )
    return parser


if __name__ == '__main__':
    args = _setup_parser().parse_args()
    for dir in args.dirs:
        _process_directory(args.root_in, args.root_out, dir, args.multiplier)
