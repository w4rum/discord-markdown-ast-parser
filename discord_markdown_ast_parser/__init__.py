from typing import Any, Dict, Tuple

from discord_markdown_ast_parser.lexer import lex
from discord_markdown_ast_parser.parser import Node, parse_tokens


def parse(text) -> Tuple[Node, ...]:
    """
    Parses the text and returns an AST, using this package's internal Node
    representation.
    See parse_to_dict for a more generic string representation.
    """
    tokens = tuple(lex(text))
    return parse_tokens(tokens)


def parse_to_dict(text) -> Tuple[Dict[str, Any], ...]:
    """
    Parses the text and returns an AST, represented as a dict.
    See the README for information on the structure of this dict.
    """
    node_ast = parse(text)
    return tuple([node.to_dict() for node in node_ast])
