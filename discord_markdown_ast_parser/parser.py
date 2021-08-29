import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Generator, Any

from discord_markdown_ast_parser.lexer import Token, TokenType


class NodeType(Enum):
    TEXT = 0
    QUOTE_BLOCK = 1
    CODE_BLOCK = 2
    CODE_INLINE = 3
    ITALIC = 4
    BOLD = 5
    UNDERLINE = 6
    STRIKETHROUGH = 7
    SPOILER = 8
    USER = 9
    ROLE = 10
    CHANNEL = 11
    EMOJI_CUSTOM = 12
    EMOJI_UNICODE_ENCODED = 13
    URL_WITH_PREVIEW = 14
    URL_WITHOUT_PREVIEW = 15


@dataclass
class Node:
    node_type: NodeType

    # only set on TEXT type
    text_content: Optional[str] = None

    discord_id: Optional[int] = None
    emoji_name: Optional[str] = None
    code_lang: Optional[str] = None
    url: Optional[str] = None

    # set on everything but TEXT type
    # some node types always have exactly one child
    children: Optional[tuple["Node", ...]] = None

    def to_dict(self) -> dict[str, Any]:
        # copy all properties that are not None
        self_dict = {k: v for k, v in self.__dict__.items() if v is not None}

        # convert NodeType to string
        self_dict["node_type"] = self.node_type.name

        # recursively convert children to dict
        if self.children is not None:
            self_dict["children"] = tuple([node.to_dict() for node in self.children])

        return self_dict


def parse_tokens(tokens: tuple[Token, ...]) -> tuple[Node, ...]:
    return compress_text_nodes(tuple(parse_tokens_generator(tokens)))


def compress_text_nodes(subtree: tuple[Node, ...]) -> tuple[Node, ...]:
    compressed_tree = []
    prev_text_node = None
    for node in subtree:
        if node.node_type == NodeType.TEXT:
            if prev_text_node is None:
                prev_text_node = node
            else:
                prev_text_node.text_content += node.text_content
                continue  # don't store this node
        else:
            prev_text_node = None

        if node.children is not None:
            node.children = compress_text_nodes(node.children)

        compressed_tree.append(node)

    return tuple(compressed_tree)


def parse_tokens_generator(
        tokens: tuple[Token, ...], in_quote=False
) -> Generator[Node, None, None]:
    i = 0
    while i < len(tokens):
        current_token = tokens[i]
        # print(i, current_token)

        if current_token.token_type == TokenType.QUOTE_LINE_PREFIX:
            print()

        # === simple node types without children
        # just continue once any of them match

        # text
        if current_token.token_type == TokenType.TEXT_INLINE:
            yield Node(NodeType.TEXT, text_content=current_token.value)
            i += 1
            continue

        # user mentions
        if current_token.token_type == TokenType.USER_MENTION:
            yield Node(NodeType.USER, discord_id=int(current_token.groups[0]))
            i += 1
            continue

        # role mentions
        if current_token.token_type == TokenType.ROLE_MENTION:
            yield Node(NodeType.ROLE, discord_id=int(current_token.groups[0]))
            i += 1
            continue

        # channel mentions
        if current_token.token_type == TokenType.CHANNEL_MENTION:
            yield Node(NodeType.CHANNEL, discord_id=int(current_token.groups[0]))
            i += 1
            continue

        # custom emoji
        if current_token.token_type == TokenType.EMOJI_CUSTOM:
            yield Node(
                NodeType.EMOJI_CUSTOM,
                discord_id=int(current_token.groups[1]),
                emoji_name=current_token.groups[0],
            )
            i += 1
            continue

        # unicode emoji (when it's encoded as :name: and not just written as unicode)
        if current_token.token_type == TokenType.EMOJI_UNICODE_ENCODED:
            yield Node(
                NodeType.EMOJI_UNICODE_ENCODED,
                emoji_name=current_token.groups[0],
            )
            i += 1
            continue

        # URL with preview
        if current_token.token_type == TokenType.URL_WITH_PREVIEW:
            yield Node(NodeType.URL_WITH_PREVIEW, url=current_token.value)
            i += 1
            continue

        # URL without preview
        if current_token.token_type == TokenType.URL_WITHOUT_PREVIEW:
            yield Node(NodeType.URL_WITHOUT_PREVIEW, url=current_token.value[1:-1])
            i += 1
            continue

        # === text modifiers
        # these just modify the look of the text (bold, italic, inline code, ...),
        # can appear everywhere (outside of code blocks) and can span all other
        # elements (including code blocks) and can span across newlines.
        # they must have at least one child token.
        # note, however, that text modifiers (and all other nodes with children),
        # can not overlap partially:
        #   strikethrough is completely inside italic, works:
        #     *a~~b~~c*d = <it>a<s>b</s>c</it>d
        #   strikethrough only partially overlaps italic, strikethrough is ignored
        #     *a~~bc*d~~ = <it>a~~bc</it>~~d
        #
        # known issue:
        # we don't account for the fact that spoilers can't wrap code blocks

        # format: delimiter, type
        text_modifiers = [
            ((TokenType.STAR, TokenType.STAR), NodeType.BOLD),
            ((TokenType.UNDERSCORE, TokenType.UNDERSCORE), NodeType.UNDERLINE),
            ((TokenType.TILDE, TokenType.TILDE), NodeType.STRIKETHROUGH),
            ((TokenType.STAR,), NodeType.ITALIC),
            ((TokenType.UNDERSCORE,), NodeType.ITALIC),
            ((TokenType.SPOILER_DELIMITER,), NodeType.SPOILER),
            ((TokenType.CODE_INLINE_DELIMITER,), NodeType.CODE_INLINE),
        ]

        parse_try = None
        for delimiter, node_type in text_modifiers:
            parse_try = try_parse_node_with_children(
                tokens[i:], delimiter, delimiter, node_type, in_quote
            )
            if parse_try is not None:
                break

        if parse_try is not None:
            node, amount_consumed_tokens = parse_try
            i += amount_consumed_tokens
            yield node
            continue

        # === code blocks
        # these are similar to text modifiers but have some additional twists
        # - code blocks only contain inline text, all other markdown rules are disabled
        #   inside code blocks
        # - the first line can be a language specifier for syntax highlighting.
        #   - the LS starts immediately after the code block delimiter and is
        #     immediately followed by a newline, otherwise it is treated as normal
        #     text content of the code block.
        #   - if the language specifier is omitted completely, i.e., the code block
        #     delimiter is immediately followed by a newline, then that newline is
        #     removed:
        #       ```
        #       test
        #       ```
        #       is, in HTML, <code-block>test<br /></code-block>
        #       and not <code-block><br />test<br /></code-block>

        if current_token.token_type == TokenType.CODE_BLOCK_DELIMITER:
            search = search_for_closer(
                tokens[i + 1:], (TokenType.CODE_BLOCK_DELIMITER,)
            )
            if search is not None:
                children_token, amount_consumed_tokens = search
                children_content = ""
                # treat all children token as inline text
                for child_token in children_token:
                    children_content += child_token.value

                # check for a language specifier
                lines = children_content.split("\n")
                # there must be at least one other non-empty line
                # (the content doesn't matter, there just has to be one)
                non_empty_line_found = False
                lang = None
                for line_index in range(1, len(lines)):
                    if len(lines[line_index]) > 0:
                        non_empty_line_found = True
                        break
                if non_empty_line_found:
                    match = re.fullmatch(r"([a-zA-Z0-9-]*)(.*)", lines[0])
                    # if there is any behind the lang spec, then it is normal text
                    # otherwise, it is either a lang spec (gets removed from the
                    # displayed text) or it is empty (newline gets removed)
                    if len(match[2]) == 0:
                        lines = lines[1:]  # remove first line from code block
                        if len(match[1]) > 0:
                            lang = match[1]

                children_content = "\n".join(lines)
                child_node = Node(NodeType.TEXT, text_content=children_content)
                yield Node(NodeType.CODE_BLOCK, code_lang=lang, children=(child_node,))
                i += 1 + amount_consumed_tokens
                continue

        # === quote blocks
        # these are a bit trickier. essentially, quote blocks are also
        # "just another text modifier" but with a few more complicated rules
        # - quote blocks always have "> " at the very beginning of every line
        # - quote blocks can span multiple lines, meaning that if multiple consecutive
        #   lines start with "> ", then they belong to the same quote block
        # - quote blocks can't be nested. any quote delimiters inside a quote block
        #   are just inline text. all other elements can appear inside a quote block
        # - text modifiers
        children_token_in_quote_block = []
        # note that in_quote won't change during the while-loop, we're just reducing
        # the level of indentation here by including it in the condition instead of
        # making an additional if statement around the while loop
        while not in_quote and tokens[i].token_type == TokenType.QUOTE_LINE_PREFIX:
            # scan until next newline
            for j in range(i, len(tokens)):
                if tokens[j].token_type == TokenType.NEWLINE:
                    # add everything from the quote line prefix (non-inclusive)
                    # to the newline (inclusive) as children token
                    children_token_in_quote_block.extend(tokens[i + 1: j + 1])
                    i = j + 1  # move to the token after the newline
                    break
            else:
                # this is the last line,
                # all remaining tokens are part of the quote block
                children_token_in_quote_block.extend(tokens[i + 1:])
                i = len(tokens)  # move to the end
                break

        if len(children_token_in_quote_block) > 0:
            # tell the inner parse function that it's now inside a quote block
            children_nodes = tuple(
                parse_tokens_generator(
                    tuple(children_token_in_quote_block), in_quote=True
                )
            )
            yield Node(NodeType.QUOTE_BLOCK, children=children_nodes)
            continue

        # if we get all the way here, than whatever token we're currently sitting on
        # is not an inline text token but also failed to match any of our parsing rules.
        # this happens when a special character, such as ">" or "*" is used as part of
        # normal text.
        # in this case, we just treat it as normal text.
        #
        # TODO:
        # note that we don't combine multiple text nodes here.
        # we *could* do it similar to what we do in the lexer but
        # - remembering inline text into future loop iterations would require adding
        #   a check to every yield-continue combo in this function, which would be quite
        #   ugly
        # - we can't change previous segments without dropping the generator
        #   functionality (even though that *is* the current workaround)
        # - we can't look ahead without simulating this entire function on future tokens
        # if you know how to do this *without adding ugly code*: help is appreciated.
        # until then, this is a case of "we'll cross that bridge when we get there",
        # i.e., we'll fix it if anyone comes along that actually needs it
        yield Node(NodeType.TEXT, current_token.value)
        i += 1


def try_parse_node_with_children(
        tokens: list[Token],
        opener: tuple[TokenType, ...],
        closer: tuple[TokenType, ...],
        node_type: NodeType,
        in_quote: bool,
) -> Optional[tuple[Node, int]]:
    # if there aren't enough tokens to match this node type, abort immediately
    # +1 because there needs to be at least one child token
    if len(tokens) < len(opener) + 1 + len(closer):
        return None

    # check if the opener matches
    for opener_index in range(len(opener)):
        if tokens[opener_index].token_type != opener[opener_index]:
            return None

    # try finding the matching closer and consume as few tokens as possible
    # (skip the first token as that has to be a child token)
    # TODO: edge case ***bold and italic*** doesn't work
    search = search_for_closer(tokens[len(opener) + 1:], closer)

    if search is None:
        # closer not found, abort trying to parse as the selected node type
        return None

    children_token, amount_consumed_tokens = search

    # put first child token back in
    children_token = (tokens[len(opener)], *children_token)
    amount_consumed_tokens += len(opener) + 1

    return (
        Node(
            node_type,
            children=tuple(parse_tokens_generator(children_token, in_quote)),
        ),
        amount_consumed_tokens,
    )


def search_for_closer(
        tokens: list[Token], closer: tuple[TokenType, ...]
) -> Optional[tuple[tuple[Token, ...], int]]:
    # iterate over tokens
    for token_index in range(len(tokens) - len(closer) + 1):
        # try matching the closer to the current position by iterating over the closer
        for closer_index in range(len(closer)):
            if tokens[token_index + closer_index].token_type != closer[closer_index]:
                break
        else:
            # closer matched
            return tokens[:token_index], token_index + len(closer)
        # closer didn't match, try next token_index

    # closer was not found
    return None
