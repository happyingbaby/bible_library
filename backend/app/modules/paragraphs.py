"""Content-based anchors. Ambiguous duplicate content is never guessed."""
import hashlib
from markdown_it import MarkdownIt


def mark_paragraphs(tokens):
    paragraphs = []
    for i, token in enumerate(tokens):
        if token.type not in ('paragraph_open', 'heading_open'):
            continue
        inline = tokens[i + 1]
        if inline.type != 'inline' or not inline.content.strip():
            continue
        quote = inline.content
        key = hashlib.sha256(quote.encode()).hexdigest()
        # Tight list paragraphs would otherwise have no DOM element.
        token.hidden = False
        if i + 2 < len(tokens):
            tokens[i + 2].hidden = False
        token.attrSet('data-paragraph', key)
        token.attrSet('data-paragraph-index', str(len(paragraphs)))
        token.attrSet('tabindex', '0')
        paragraphs.append(dict(key=key, quote=quote))
    return paragraphs


def paragraphs(markdown):
    return mark_paragraphs(MarkdownIt('commonmark').parse(markdown))
