"""Small OOXML-to-Markdown fallback for platforms without a Pandoc binary."""
from __future__ import annotations

import re
import zipfile
from xml.etree import ElementTree as ET

W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'


def _enabled(node: ET.Element | None) -> bool:
    if node is None:
        return False
    return node.get(W + 'val', 'true').lower() not in {'0', 'false', 'off', 'none'}


def _number_formats(archive: zipfile.ZipFile) -> dict[str, str]:
    try:
        root = ET.fromstring(archive.read('word/numbering.xml'))
    except (KeyError, ET.ParseError):
        return {}
    abstracts: dict[str, dict[str, str]] = {}
    for abstract in root.findall(W + 'abstractNum'):
        levels = {}
        for level in abstract.findall(W + 'lvl'):
            number_format = level.find(W + 'numFmt')
            if number_format is not None:
                levels[level.get(W + 'ilvl', '0')] = number_format.get(W + 'val', 'bullet')
        abstracts[abstract.get(W + 'abstractNumId', '')] = levels
    result = {}
    for number in root.findall(W + 'num'):
        abstract = number.find(W + 'abstractNumId')
        if abstract is not None:
            for level, number_format in abstracts.get(abstract.get(W + 'val', ''), {}).items():
                result[f'{number.get(W + "numId", "")}:{level}'] = number_format
    return result


def _run_text(run: ET.Element) -> str:
    parts = []
    for node in run.iter():
        if node.tag == W + 't':
            parts.append(node.text or '')
        elif node.tag == W + 'tab':
            parts.append('\t')
        elif node.tag in {W + 'br', W + 'cr'}:
            parts.append('  \n')
    return ''.join(parts)


def _paragraph_text(paragraph: ET.Element) -> str:
    segments: list[tuple[bool, bool, str]] = []
    for run in paragraph.iter(W + 'r'):
        text = _run_text(run)
        if not text:
            continue
        properties = run.find(W + 'rPr')
        bold = _enabled(properties.find(W + 'b')) if properties is not None else False
        italic = _enabled(properties.find(W + 'i')) if properties is not None else False
        if segments and segments[-1][:2] == (bold, italic):
            previous = segments[-1]
            segments[-1] = (bold, italic, previous[2] + text)
        else:
            segments.append((bold, italic, text))
    output = []
    for bold, italic, text in segments:
        if bold:
            text = f'**{text}**'
        if italic:
            text = f'*{text}*'
        output.append(text)
    return ''.join(output).strip()


def to_markdown(archive: zipfile.ZipFile) -> str:
    """Convert common Word paragraphs, headings, lists and emphasis to Markdown."""
    root = ET.fromstring(archive.read('word/document.xml'))
    formats = _number_formats(archive)
    blocks: list[tuple[str, str]] = []
    for paragraph in root.iter(W + 'p'):
        text = _paragraph_text(paragraph)
        if not text:
            continue
        properties = paragraph.find(W + 'pPr')
        style = properties.find(W + 'pStyle') if properties is not None else None
        style_name = style.get(W + 'val', '') if style is not None else ''
        heading = re.search(r'(?:heading|title)[ _-]?([1-6])$', style_name, re.IGNORECASE)
        if heading:
            blocks.append(('paragraph', '#' * int(heading.group(1)) + ' ' + text))
            continue
        numbering = properties.find(W + 'numPr') if properties is not None else None
        if numbering is not None:
            number_id_node = numbering.find(W + 'numId')
            level_node = numbering.find(W + 'ilvl')
            number_id = number_id_node.get(W + 'val', '') if number_id_node is not None else ''
            level = level_node.get(W + 'val', '0') if level_node is not None else '0'
            marker = '-' if formats.get(f'{number_id}:{level}', 'bullet') == 'bullet' else '1.'
            blocks.append(('list', f'{"  " * int(level)}{marker} {text}'))
        else:
            blocks.append(('paragraph', text))
    output = ''
    previous_kind = ''
    for kind, text in blocks:
        separator = '\n' if kind == previous_kind == 'list' else ('\n\n' if output else '')
        output += separator + text
        previous_kind = kind
    return output + ('\n' if output else '')
