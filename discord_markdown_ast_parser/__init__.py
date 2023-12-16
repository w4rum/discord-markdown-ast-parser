from typing import Any, Dict, List, Optional

from .lexer import lex, Lexing
from .parser import Node, parse_tokens


def lexing_list_convert(lexing: Lexing) -> List[Lexing]:
    if not isinstance(lexing, list):
        lexing = [lexing]
    return [Lexing(item) if isinstance(item, str) else item for item in lexing]


def parse(text, custom: Dict[str, List[Lexing]] = None) -> List[Node]:
    """
    Parses the text and returns an AST, using this package's internal Node
    representation.
    See parse_to_dict for a more generic string representation.
    """
    custom = custom if custom is not None else {}
    custom = {k: lexing_list_convert(v) for k, v in custom.items()}
    tokens = list(lex(text, custom))
    return parse_tokens(tokens, custom)


def parse_to_dict(text, custom: Dict[str, List[Lexing]] = None) -> List[Dict[str, Any]]:
    """
    Parses the text and returns an AST, represented as a dict.
    See the README for information on the structure of this dict.
    """
    return [node.to_dict() for node in parse(text, custom)]
