import json
import typing
from dataclasses import dataclass
from sys import stdout

import pyparsing as pp


class ParadoxScriptSerializable(typing.Protocol):
    def print_pdx_script(self, depth: int = 0, /, *,
                         file: typing.TextIO = stdout):
        ...


@dataclass
class Identifier:
    value: str

    def print_pdx_script(self, depth: int = 0, /, *,
                         file: typing.TextIO = stdout):
        file.write(f"{self.value}")


@dataclass
class String:
    value: str

    def print_pdx_script(self, depth: int = 0, /, *,
                         file: typing.TextIO = stdout):
        file.write(f"{self.value}")


@dataclass
class Number:
    value: int | float

    def print_pdx_script(self, depth: int = 0, /, *,
                         file: typing.TextIO = stdout):
        file.write(f"{self.value}")


@dataclass
class Color:
    red: int
    green: int
    blue: int

    def print_pdx_script(self, depth: int = 0, /, *,
                         file: typing.TextIO = stdout):
        file.write(f"{{ {self.red} {self.green} {self.blue} }}")


@dataclass
class Listing:
    elements: list[Identifier | String]

    def print_pdx_script(self, depth: int = 0, /, *,
                         file: typing.TextIO = stdout):
        if len(self.elements) == 0:
            file.write("{ }")
        elif len(self.elements) == 1:
            file.write("{ ")
            self.elements[0].print_pdx_script(file=file)
            file.write(" }")
        else:
            file.write("{\n")
            for child in self.elements:
                file.write('\t' * (depth + 1))
                child.print_pdx_script(file=file)
                file.write('\n')
            file.write(f"{'\t' * depth}{'}'}")


@dataclass
class Block:
    entries: list['Expression']

    def print_pdx_script(self, depth: int = 0, /, *,
                         file: typing.TextIO = stdout):
        if len(self.entries) == 0:
            file.write("{ }")
        elif (
            len(self.entries) == 1
            and not isinstance((exp := self.entries[0]).rhs, Block | Listing)
        ):
            file.write('{ ')
            exp.lhs.print_pdx_script(file=file)
            file.write(' = ')
            exp.rhs.print_pdx_script(file=file)
            file.write(' }')
        else:
            file.write('{\n')
            for child in self.entries:
                child.print_pdx_script(depth + 1, file=file)
            file.write(f"{'\t' * depth}{'}'}")


@dataclass
class Expression:
    lhs: Identifier
    rhs: Identifier | String | Number | Color | Listing | Block

    def print_pdx_script(self, depth: int = 0, /, *,
                         file: typing.TextIO = stdout):
        file.write(f'\t' * depth)
        self.lhs.print_pdx_script(file=file)
        file.write(' = ')
        self.rhs.print_pdx_script(depth, file=file)
        file.write('\n')


JsonType = list['JsonValue'] | typing.Mapping[str, 'JsonValue']

JsonValue = str | int | float | None | JsonType


class ParadoxEncoder(json.JSONEncoder):
    @typing.override
    def default(self, obj: typing.Any) -> JsonValue:
        if isinstance(obj, list):
            return [self.default(child) for child in obj]
        if isinstance(obj, Block):
            return [self.default(child) for child in obj.entries]
        if (
            isinstance(obj, Identifier)
            or isinstance(obj, String)
            or isinstance(obj, Number)
        ):
            return obj.value
        if isinstance(obj, Color):
            return {
                "red": obj.red,
                "green": obj.green,
                "blue": obj.blue,
            }
        if isinstance(obj, Expression):
            return {
                "name": self.default(obj.lhs),
                "value": self.default(obj.rhs),
            }
        return super().default(obj)


_BLOCK = pp.Forward()

# Catch-all for flags, dates, and identifiers that don't fit any other
# pattern. Errors during initial testing reveal that identifier
# patterns cover more possibilities than is truly reasonable.
#
# Could probably separate things out into other categories, but that
# would likely come with unwanted performance penalties; it already
# takes two to three minutes to process the EU4 common directory.
_IDENTIFIER = pp.Word(f"{pp.alphanums}_-",
                      f"{pp.alphanums}_.:-").set_name("identifier")

_STRING = pp.QuotedString(
    '"', multiline=True, unquote_results=False).set_name("string")

_NUMBER = pp.Regex(r"[-+]?\d+\.?\d*").set_name("number")

_COLOR = (pp.Char('{').suppress() +
          pp.Word(pp.nums)[3] +
          pp.Char('}').suppress()).set_name("color")

_LISTING = (pp.Char('{').suppress() + pp.OneOrMore(_IDENTIFIER ^ _STRING) +
            pp.Char('}').suppress()).set_name("listing")

_LHS = _IDENTIFIER + pp.Literal('=').suppress()

_RHS = _NUMBER ^ _COLOR ^ _LISTING ^ _BLOCK ^ _IDENTIFIER ^ _STRING

_EXPRESSION = (_LHS + _RHS).set_name("expression")

_BLOCK <<= pp.nested_expr('{', '}', _EXPRESSION).set_name("block")

_PARSER = _EXPRESSION[...].ignore(pp.python_style_comment)


@_IDENTIFIER.set_parse_action
def _parse_identifier(results: pp.ParseResults) -> Identifier:
    return Identifier(results[0])


@_STRING.set_parse_action
def _parse_string(results: pp.ParseResults) -> String:
    return String(results[0])


@_NUMBER.set_parse_action
def _parse_number(results: pp.ParseResults) -> Number:
    return Number(float(results[0]) if '.' in results[0]
                  else int(results[0]))


@_COLOR.set_parse_action
def _parse_color(results: pp.ParseResults) -> Color:
    return Color(results[0], results[1], results[2])


@_LISTING.set_parse_action
def _parse_listing(results: pp.ParseResults) -> Listing:
    return Listing(results.as_list())


@_BLOCK.set_parse_action
def _parse_block(results: pp.ParseResults) -> Block:
    return Block(results[0].as_list())


@_EXPRESSION.set_parse_action
def _parse_expression(results: pp.ParseResults) -> Expression:
    return Expression(results[0], results[1])


def parse_file(file: typing.TextIO, *, parse_all=True) -> list[Expression]:
    return _PARSER.parse_file(file, parse_all=parse_all).as_list()


if __name__ == "__main__":
    with open('./test.txt', encoding='Latin-1') as fd:
        tree = parse_file(fd)
    for e in tree:
        e.print_pdx_script()
