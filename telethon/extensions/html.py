"""
Simple HTML -> Telegram entity parser.
"""
import struct
from collections import deque
from html import escape
from html.parser import HTMLParser
from typing import Iterable, Optional, Tuple, List

from ..helpers import add_surrogate, del_surrogate, within_surrogate, strip_text
from ..tl import TLObject
from ..tl.types import (
    MessageEntityBold, MessageEntityItalic, MessageEntityCode,
    MessageEntityPre, MessageEntityEmail, MessageEntityUrl,
    MessageEntityTextUrl, MessageEntityMentionName,
    MessageEntityUnderline, MessageEntityStrike, MessageEntityBlockquote,
    TypeMessageEntity
)


class HTMLToTelegramParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text = ''
        self.entities = []
        self._building_entities = {}
        self._open_tags = deque()
        self._open_tags_meta = deque()

    def handle_starttag(self, tag, attrs):
        self._open_tags.appendleft(tag)
        self._open_tags_meta.appendleft(None)

        attrs = dict(attrs)
        EntityType = None
        args = {}
        if tag in ['strong', 'b']:
            EntityType = MessageEntityBold
        elif tag in ['em', 'i']:
            EntityType = MessageEntityItalic
        elif tag == 'u':
            EntityType = MessageEntityUnderline
        elif tag in ['del', 's']:
            EntityType = MessageEntityStrike
        elif tag == 'blockquote':
            EntityType = MessageEntityBlockquote
        elif tag == 'code':
            try:
                # If we're in the middle of a <pre> tag, this <code> tag is
                # probably intended for syntax highlighting.
                #
                # Syntax highlighting is set with
                #     <code class='language-...'>codeblock</code>
                # inside <pre> tags
                pre = self._building_entities['pre']
                try:
                    pre.language = attrs['class'][len('language-'):]
                except KeyError:
                    pass
            except KeyError:
                EntityType = MessageEntityCode
        elif tag == 'pre':
            EntityType = MessageEntityPre
            args['language'] = ''
        elif tag == 'a':
            try:
                url = attrs['href']
            except KeyError:
                return
            if url.startswith('mailto:'):
                url = url[len('mailto:'):]
                EntityType = MessageEntityEmail
            elif self.get_starttag_text() == url:
                EntityType = MessageEntityUrl
            else:
                EntityType = MessageEntityTextUrl
                args['url'] = del_surrogate(url)
                url = None
            self._open_tags_meta.popleft()
            self._open_tags_meta.appendleft(url)

        if EntityType and tag not in self._building_entities:
            self._building_entities[tag] = EntityType(
                offset=len(self.text),
                # The length will be determined when closing the tag.
                length=0,
                **args)

    def handle_data(self, text):
        previous_tag = self._open_tags[0] if len(self._open_tags) > 0 else ''
        if previous_tag == 'a':
            if url := self._open_tags_meta[0]:
                text = url

        for tag, entity in self._building_entities.items():
            entity.length += len(text)

        self.text += text

    def handle_endtag(self, tag):
        try:
            self._open_tags.popleft()
            self._open_tags_meta.popleft()
        except IndexError:
            pass
        if entity := self._building_entities.pop(tag, None):
            self.entities.append(entity)


def parse(html: str) -> Tuple[str, List[TypeMessageEntity]]:
    """
    Parses the given HTML message and returns its stripped representation
    plus a list of the MessageEntity's that were found.

    :param html: the message with HTML to be parsed.
    :return: a tuple consisting of (clean message, [message entities]).
    """
    if not html:
        return html, []

    parser = HTMLToTelegramParser()
    parser.feed(add_surrogate(html))
    text = strip_text(parser.text, parser.entities)
    parser.entities.reverse()
    parser.entities.sort(key=lambda entity: entity.offset)
    return del_surrogate(text), parser.entities


ENTITY_TO_FORMATTER = {
    MessageEntityBold: ('<strong>', '</strong>'),
    MessageEntityItalic: ('<em>', '</em>'),
    MessageEntityCode: ('<code>', '</code>'),
    MessageEntityUnderline: ('<u>', '</u>'),
    MessageEntityStrike: ('<del>', '</del>'),
    MessageEntityBlockquote: ('<blockquote>', '</blockquote>'),
    MessageEntityPre: lambda e, _: (
        f"<pre>\n    <code class='language-{e.language}'>\n        ",
        "{}\n" "    </code>\n" "</pre>",
    ),
    MessageEntityEmail: lambda _, t: (f'<a href="mailto:{t}">', '</a>'),
    MessageEntityUrl: lambda _, t: (f'<a href="{t}">', '</a>'),
    MessageEntityTextUrl: lambda e, _: (f'<a href="{escape(e.url)}">', '</a>'),
    MessageEntityMentionName: lambda e, _: (
        f'<a href="tg://user?id={e.user_id}">',
        '</a>',
    ),
}


def unparse(text: str, entities: Iterable[TypeMessageEntity]) -> str:
    """
    Performs the reverse operation to .parse(), effectively returning HTML
    given a normal text and its MessageEntity's.

    :param text: the text to be reconverted into HTML.
    :param entities: the MessageEntity's applied to the text.
    :return: a HTML representation of the combination of both inputs.
    """
    if not text:
        return text
    elif not entities:
        return escape(text)

    if isinstance(entities, TLObject):
        entities = (entities,)

    text = add_surrogate(text)
    insert_at = []
    for i, entity in enumerate(entities):
        s = entity.offset
        e = entity.offset + entity.length
        if delimiter := ENTITY_TO_FORMATTER.get(type(entity), None):
            if callable(delimiter):
                delimiter = delimiter(entity, text[s:e])
            insert_at.extend(((s, i, delimiter[0]), (e, -i, delimiter[1])))
    insert_at.sort(key=lambda t: (t[0], t[1]))
    next_escape_bound = len(text)
    while insert_at:
        # Same logic as markdown.py
        at, _, what = insert_at.pop()
        while within_surrogate(text, at):
            at += 1

        text = text[:at] + what + escape(text[at:next_escape_bound]) + text[next_escape_bound:]
        next_escape_bound = at

    text = escape(text[:next_escape_bound]) + text[next_escape_bound:]

    return del_surrogate(text)
