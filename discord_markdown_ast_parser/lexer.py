import re
from dataclasses import dataclass, InitVar, field
from enum import Enum
from typing import Optional, List, Generator, Dict
import itertools


class Lexing:
    def __init__(self, pattern: Optional[str] = None, flags: re.RegexFlag = re.NOFLAG):
        self.regex = re.compile(pattern, flags=flags) if pattern else None
        
    def __call__(self, text: str):
        return self.regex and self.regex.match(text)
    
    def __repr__(self):
        return f"{self.__class__.__name__}({self.regex and self.regex.pattern!r})"

# stolen from https://www.urlregex.com/
URL_REGEX = (
    r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"
)

class LexingRule(Lexing, Enum):
    USER_MENTION = r"<@!?(\d{15,20})>"
    ROLE_MENTION = r"<@&(\d{15,20})>"
    SLASH_COMMAND_MENTION  = r"</([a-zA-Z0-9_ ]{2,}):(\d{15,20})>"
    CHANNEL_MENTION = r"<#(\d{15,20})>"
    TIMESTAMP = r"<t:(-?\d+)(?::([tTdDfFR]))?>"
    EMOJI_CUSTOM = r"<:([a-zA-Z0-9_]{2,}):(\d{15,20})>"
    EMOJI_CUSTOM_ANIMATED = r"<a:([a-zA-Z0-9_]{2,}):(\d{15,20})>"
    EMOJI_UNICODE = r"(\u00a9|\u00ae|[\u2000-\u3300]|\ud83c[\ud000-\udfff]|\ud83d[\ud000-\udfff]|\ud83e[\ud000-\udfff])"
    EMOJI_UNICODE_ENCODED = r":([a-zA-Z0-9_]+):"
    URL_WITHOUT_PREVIEW_EMBEDDED = f"\[([^\]]+)\]\(<({URL_REGEX})>\)"
    URL_WITH_PREVIEW_EMBEDDED =    f"\[([^\]]+)\]\(({URL_REGEX})\)"
    URL_WITHOUT_PREVIEW = f"<{URL_REGEX}>"
    URL_WITH_PREVIEW = URL_REGEX
    QUOTE_LINE_PREFIX = r"(>>)?> "
    TILDE = r"~"
    STAR = r"\*"
    UNDERSCORE = r"_"
    SPOILER_DELIMITER = r"\|\|"
    CODE_BLOCK_DELIMITER = r"```"
    CODE_INLINE_DELIMITER = r"`"
    NEWLINE = r"\n"
    TEXT_INLINE = ""


@dataclass
class Token:
    value: str = ""
    lexing_rule: Lexing = LexingRule.TEXT_INLINE
    groups: List[str] = field(default_factory=list)
    
    def __contains__(self, rule: Lexing):
        return self.lexing_rule == rule



def lex(input_text: str, custom: Optional[Dict[str, List[Lexing]]] = None) -> Generator[Token, None, None]:
    """Lexes the input text and returns a generator of tokens.
    The generator will yield a token for each lexing rule that matches the input text.

    Args:
        input_text (str): String to lex

    Yields:
        Generator[Token, None, None]: Generator of tokens
    """
    seen_simple_text = ""
    custom = custom or {}
    
    while input_text:
        for rule in itertools.chain(*custom.values(), LexingRule):
            match = rule(input_text)
            if match is not None:
                matching_rule = rule
                break
        else:
            seen_simple_text += input_text[0]
            input_text = input_text[1:]
            continue  # don't yield a token in this run

        # cut off matched part
        input_text = input_text[len(match[0]) :]

        # yield inline text if we have some left
        if len(seen_simple_text) > 0:
            yield Token(seen_simple_text)
            seen_simple_text = ""

        yield Token(match[0], matching_rule, match.groups())

    if len(seen_simple_text) > 0:
        yield Token(seen_simple_text)
