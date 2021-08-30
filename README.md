# Discord Markdown AST Parser
#### Markdown Parser for Discord messages that creates an abstract syntax tree

This package provides a parser that can be used to translate a Discord message into an abstract syntax tree (AST) that represents how the message should be rendered according to Discord's markdown rules.

### Example
Check the following example on how this parser will translate a Discord message:

![image](https://user-images.githubusercontent.com/1405498/131235730-94ba8100-2b42-492f-9479-bbce80c592f0.png)

```python
(
    {'node_type': 'ITALIC',
     'children': (
      {'node_type': 'TEXT', 'text_content': 'italic star single'},
    )},
    
    {'node_type': 'TEXT', 'text_content': '\n'},
    
    {'node_type': 'ITALIC',
     'children': (
        {'node_type': 'TEXT', 'text_content': 'italic underscore single'},
    )},
    
    {'node_type': 'TEXT', 'text_content': '\n'},
    
    {'node_type': 'BOLD',
     'children': (
        {'node_type': 'TEXT', 'text_content': 'bold single'},
    )},
    
    {'node_type': 'TEXT', 'text_content': '\n'},
    
    {'node_type': 'UNDERLINE',
     'children': (
        {'node_type': 'TEXT', 'text_content': 'underline single'},
    )},
    
    {'node_type': 'TEXT', 'text_content': '\n'},
    
    {'node_type': 'STRIKETHROUGH',
     'children': (
        {'node_type': 'TEXT', 'text_content': 'strikethrough single'},
    )},
    
    {'node_type': 'TEXT', 'text_content': '\n\n'},
    
    {'node_type': 'QUOTE_BLOCK',
     'children': (
        {'node_type': 'TEXT', 'text_content': 'quote\nblock\n'},
    )},
    
    {'node_type': 'TEXT', 'text_content': '\n'},
    
    {'node_type': 'CODE_INLINE',
     'children': (
        {'node_type': 'TEXT', 'text_content': 'inline code'},
    )},
    
    {'node_type': 'TEXT', 'text_content': '\n\n'},
    
    {'node_type': 'QUOTE_BLOCK',
     'children': (
        {'node_type': 'CODE_BLOCK',
         'code_lang': 'python',
         'children': (
            {'node_type': 'TEXT', 
             'text_content': 'code\nblock\nwith\npython\nhighlighting\n'},),
        },
    )},
)
```

### Installation
You can install this package from PyPI:
```
pip install discord-markdown-ast-parser
```

### Usage
Pass the message's content to `parse_to_dict` to get the AST represented as a `dict`.
Alternatively, use `parse` to get the AST using this package's internal `Node` type instead of a string-based `dict`:
```python
# string-based dict
ast_dict = parse_to_dict(message_content)
# tuple of Node objects
ast_tuple_of_nodes = parse(message_content)
```

### Node Types
These are the types of nodes the parser will output:
```
TEXT
- fields: "text_content"
- Just standard text, no additional formatting
- No child nodes

ITALIC, BOLD, UNDERLINE, STRIKETHROUGH, SPOILER, CODE_INLINE
- fields: "children"
- self-explanatory

QUOTE_BLOCK
- fields: "children"
- represents a single, uninterrupted code block (no gaps in Discord's client)
- can not contain another quote block (Discord has no nested quotes)

CODE_BLOCK
- fields: "children", "code_lang"
- can only contain a single TEXT node, all other markdown syntax inside the code block
  is ignored
- may or may not have a language specifier
- first newline is stripped according to the same rules that the Discord client uses

USER, ROLE, CHANNEL
- fields: "discord_id"
- user, role, or channel mention
- there is no way to retrieve the user/role/channel name, color or channel type
  (text/voice/stage) from just the message, so you'll have to use the API
  (or discord.py) to query that

URL_WITH_PREVIEW, URL_WITHOUT_PREVIEW
- fields: "url"
- a HTTP URL
- this is only recognized if the link actually contains "http". this is the same for the
  Discord client, with the exception that the Discord client also scan for invite links
  that don't start with http, e.g., "discord.gg/pxa"
- the WITHOUT_PREVIEW variant appears when the message contains the URL in the <URL>
  form, which causes the Discord client to suppress the preview
  
EMOJI_CUSTOM
- fields: "emoji_name", "emoji_id"
- you can get the custom emoji's image by querying to
  https://cdn.discordapp.com/emojis/EMOJI_ID.png
  
EMOJI_UNICODE_ENCODED
- fields: "emoji_name"
- this will appear very rarely. unicode emojis are usually just posted as unicode  
  characters and thus end up in a TEXT node it is, however, possible to send a message
  from a bot that uses, e.g., :red_car: instead of the actual red_car unicode emoji.
  the Discord client will properly translate that to the correct unicode emoji.
  this package does not do that because Discord has not published the list of names they
  use for the emojis. so this package will simply relay the emoji's name
```

### Known Issues
While this parser should work in pretty much every realistic scenario, there are some
very specific edge cases in which this parser will produce an output that doesn't align
with how it's rendered in the Discord client:
- `***bold and italic***` will be detected as bold-only with extra stars.
  This only happens when the italic and bold stars are right next to each other.
  This does not happen when mixing bold stars with italic underscores.
- `*italic with whitespace before star closer *`
  will be detected as italic even though the Discord client won't.
  Note that Discord doesn't have this weird requirement for `_underscore italic_`.
- ````
  ||spoilers around
  ```
  code blocks
  ```
  ||
  ````
  will be detected as spoilers spanning the code segments, although the Discord the
  client will only show spoiler bars before and after the code segment, but not on top
  of it.
  
