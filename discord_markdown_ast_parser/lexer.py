import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional, List, Generator


class TokenType(Enum):
    TEXT_INLINE = 1
    NEWLINE = 2
    STAR = 3
    UNDERSCORE = 4
    TILDE = 5
    SPOILER_DELIMITER = 6
    USER_MENTION = 7
    ROLE_MENTION = 8
    CHANNEL_MENTION = 9
    EMOJI_CUSTOM = 10
    EMOJI_UNICODE_ENCODED = 11
    URL_WITH_PREVIEW = 12
    URL_WITHOUT_PREVIEW = 13
    QUOTE_LINE_PREFIX = 14
    CODE_INLINE_DELIMITER = 15
    CODE_BLOCK_DELIMITER = 16


@dataclass
class Token:
    token_type: TokenType
    value: str
    groups: Optional[List[str]] = None


@dataclass
class LexingRule:
    token_type: TokenType
    pattern: Optional[str] = None


def lex(input_text: str) -> Generator[Token, None, None]:
    """
    Scans the input text for sequences of characters (=tokens), identified by regular
    expressions, that have a special meaning in Discord's Markdown.

    This function takes care of identifying the low-level elements of the text such as
    markdown special characters. It also does pretty much all of the parsing work for
    simple structures such as user mentions that can be identified via regular
    expressions.

    Will output the tokens in the order that they appear in the input text.
    """
    # There will be cases when no specific lexing rules matches.
    #
    # This happens when what we're looking at is just simple text with no special
    # markdown meaning.
    #
    # Problem is: We're generally only trying to match our regex pattern against the
    # prefix of what we're looking at, so if we go through all of our rules and end up
    # noticing "Oh, that's just text", then we don't know how long that text segment
    # is going to be.
    #
    # So we're going to continue scanning until we arrive at something that is not just
    # text, at which point we're going to output all the text we've found as a single
    # text token.
    seen_simple_text = ""

    while True:
        if len(input_text) == 0:
            if len(seen_simple_text) > 0:
                yield Token(TokenType.TEXT_INLINE, seen_simple_text)
            return

        for rule in lexing_rules:
            match = re.match(rule.pattern, input_text)
            if match is not None:
                matching_rule = rule
                break
        else:
            seen_simple_text += input_text[0]
            input_text = input_text[1:]
            continue  # don't yield a token in this run

        # cut off matched part
        input_text = input_text[len(match[0]):]

        # yield inline text if we have some left
        if len(seen_simple_text) > 0:
            yield Token(TokenType.TEXT_INLINE, seen_simple_text)
            seen_simple_text = ""

        groups = None
        if len(match.groups()) > 0:
            groups = match.groups()

        yield Token(matching_rule.token_type, match[0], groups)


# stolen from https://www.urlregex.com/
URL_REGEX = (
    r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"
)

lexing_rules = [
    LexingRule(token_type=TokenType.USER_MENTION, pattern="<@!?([0-9]+)>"),
    LexingRule(token_type=TokenType.ROLE_MENTION, pattern="<@&([0-9]+)>"),
    LexingRule(token_type=TokenType.CHANNEL_MENTION, pattern="<#([0-9]+)>"),
    LexingRule(
        token_type=TokenType.EMOJI_CUSTOM, pattern="<:([a-zA-Z0-9_]{2,}):([0-9]+)>"
    ),
    LexingRule(token_type=TokenType.EMOJI_UNICODE_ENCODED, pattern=":([a-zA-Z0-9_]+):"),
    LexingRule(token_type=TokenType.URL_WITHOUT_PREVIEW, pattern=f"<{URL_REGEX}>"),
    LexingRule(token_type=TokenType.URL_WITH_PREVIEW, pattern=URL_REGEX),
    LexingRule(token_type=TokenType.QUOTE_LINE_PREFIX, pattern=r"(>>)?> "),
    LexingRule(token_type=TokenType.TILDE, pattern=r"~"),
    LexingRule(token_type=TokenType.STAR, pattern=r"\*"),
    LexingRule(token_type=TokenType.UNDERSCORE, pattern=r"_"),
    LexingRule(token_type=TokenType.SPOILER_DELIMITER, pattern=r"\|\|"),
    LexingRule(token_type=TokenType.CODE_BLOCK_DELIMITER, pattern=r"```"),
    LexingRule(token_type=TokenType.CODE_INLINE_DELIMITER, pattern=r"`"),
    LexingRule(token_type=TokenType.NEWLINE, pattern="\n"),
]
