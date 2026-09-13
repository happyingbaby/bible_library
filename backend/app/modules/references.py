import html
import re
from markdown_it import MarkdownIt

# Stable canonical IDs; aliases are extensible without changing stored references.
BOOK_ROWS = '''Gen|创世记,创世纪,创,創世記,創|50
Exod|出埃及记,出,出埃及記|40
Lev|利未记,利,利未記|27
Num|民数记,民,民數記|36
Deut|申命记,申,申命記|34
Josh|约书亚记,书,約書亞記,書|24
Judg|士师记,士,士師記|21
Ruth|路得记,得,路得記|4
1Sam|撒母耳记上,撒上,撒母耳記上|31
2Sam|撒母耳记下,撒下,撒母耳記下|24
1Kgs|列王纪上,王上,列王紀上|22
2Kgs|列王纪下,王下,列王紀下|25
1Chr|历代志上,代上,歷代志上|29
2Chr|历代志下,代下,歷代志下|36
Ezra|以斯拉记,拉,以斯拉記|10
Neh|尼希米记,尼,尼希米記|13
Esth|以斯帖记,斯,以斯帖記|10
Job|约伯记,伯,約伯記|42
Ps|诗篇,诗,詩篇,詩|150
Prov|箴言,箴|31
Eccl|传道书,传,傳道書,傳|12
Song|雅歌,歌|8
Isa|以赛亚书,赛,以賽亞書,賽|66
Jer|耶利米书,耶,耶利米書|52
Lam|耶利米哀歌,哀|5
Ezek|以西结书,结,以西結書,結|48
Dan|但以理书,但,但以理書|12
Hos|何西阿书,何,何西阿書|14
Joel|约珥书,珥,約珥書|3
Amos|阿摩司书,摩,阿摩司書|9
Obad|俄巴底亚书,俄,俄巴底亞書|1
Jonah|约拿书,拿,約拿書|4
Mic|弥迦书,弥,彌迦書,彌|7
Nah|那鸿书,鸿,那鴻書,鴻|3
Hab|哈巴谷书,哈,哈巴谷書|3
Zeph|西番雅书,番,西番雅書|3
Hag|哈该书,该,哈該書,該|2
Zech|撒迦利亚书,亚,撒迦利亞書,亞|14
Mal|玛拉基书,玛,瑪拉基書,瑪|4
Matt|马太福音,太,馬太福音|28
Mark|马可福音,可,馬可福音|16
Luke|路加福音,路|24
John|约翰福音,约,約翰福音,約|21
Acts|使徒行传,徒,使徒行傳|28
Rom|罗马书,罗,羅馬書,羅|16
1Cor|哥林多前书,林前,哥林多前書|16
2Cor|哥林多后书,林后,哥林多後書,林後|13
Gal|加拉太书,加,加拉太書|6
Eph|以弗所书,弗,以弗所書|6
Phil|腓立比书,腓,腓立比書|4
Col|歌罗西书,西,歌羅西書|4
1Thess|帖撒罗尼迦前书,帖前,帖撒羅尼迦前書|5
2Thess|帖撒罗尼迦后书,帖后,帖撒羅尼迦後書,帖後|3
1Tim|提摩太前书,提前,提摩太前書|6
2Tim|提摩太后书,提后,提摩太後書,提後|4
Titus|提多书,多,提多書|3
Phlm|腓利门书,门,腓利門書,門|1
Heb|希伯来书,来,希伯來書,來|13
Jas|雅各书,雅,雅各書|5
1Pet|彼得前书,彼前,彼得前書|5
2Pet|彼得后书,彼后,彼得後書,彼後|3
1John|约翰一书,约一,約翰一書,約一|5
2John|约翰二书,约二,約翰二書,約二|1
3John|约翰三书,约三,約翰三書,約三|1
Jude|犹大书,犹,猶大書,猶|1
Rev|启示录,启,啟示錄,啟|22'''
BOOKS = {}
ALIASES = {}
for row in BOOK_ROWS.splitlines():
    code, names, chapters = row.split('|')
    BOOKS[code] = {'code': code, 'name': names.split(',')[0], 'chapters': int(chapters)}
    for alias in [code, *names.split(',')]:
        ALIASES[alias.lower()] = code

BRACKET = re.compile(r'【[^【】\n]{1,80}】|（[^（）\n]{1,80}）|\([^()\n]{1,80}\)|\[[^\[\]\n]{1,80}\]')
PATTERN = re.compile(r'^(.+?)\s*(\d{1,3})\s*[:：]\s*(\d{1,3})(?:\s*[-－–—]\s*(\d{1,3}))?\s*([上下abAB])?$')


def parse_reference(raw):
    inside = raw[1:-1].strip()
    if not re.search(r'\d\s*[:：]', inside):
        return None
    match = PATTERN.fullmatch(inside)
    result = {'raw': raw, 'status': 'invalid', 'message': '暂不支持此引用格式'}
    if not match:
        return result
    name, chapter, start, end, part = match.groups()
    book = ALIASES.get(name.strip().lower())
    if not book:
        return {**result, 'message': '无法识别书卷名称'}
    chapter, start, end = int(chapter), int(start), int(end or start)
    result.update(book=book, book_name=BOOKS[book]['name'], chapter=chapter, start=start, end=end, part=part or '')
    if not (1 <= chapter <= BOOKS[book]['chapters'] and 1 <= start <= end <= 176):
        return {**result, 'message': '章节或经节范围错误'}
    return {**result, 'status': 'valid', 'message': ''}


def render(markdown):
    md = MarkdownIt('commonmark', {'html': False, 'breaks': True})
    refs = []
    def text_rule(tokens, idx, options, env):
        token = tokens[idx]
        # Link labels, image labels and code are never transformed.
        if env.get('in_link'):
            return html.escape(token.content)
        content = token.content
        output, pos = [], 0
        for match in BRACKET.finditer(content):
            ref = parse_reference(match.group())
            if not ref:
                continue
            output.append(html.escape(content[pos:match.start()]))
            ref.update(ordinal=len(refs), text_offset=match.start(), inline_index=env.get('inline_index', 0))
            refs.append(ref)
            output.append(f'<button class="verse-ref {ref["status"]}" data-ref="{ref["ordinal"]}" title="{html.escape(ref["message"], quote=True)}">{html.escape(ref["raw"])}</button>')
            pos = match.end()
        output.append(html.escape(content[pos:]))
        return ''.join(output)
    original_open = md.renderer.rules.get('link_open')
    def link_open(tokens, idx, options, env):
        env['in_link'] = True
        return md.renderer.renderToken(tokens, idx, options, env)
    def link_close(tokens, idx, options, env):
        env['in_link'] = False
        return md.renderer.renderToken(tokens, idx, options, env)
    md.renderer.rules['text'] = text_rule
    md.renderer.rules['link_open'] = link_open
    md.renderer.rules['link_close'] = link_close
    # Offline first: imported image URLs are not fetched.
    md.renderer.rules['image'] = lambda tokens, idx, options, env: '<span class="unsupported">[图片：' + html.escape(tokens[idx].content) + ']</span>'
    tokens = md.parse(markdown)
    # Inline positions are stable per Markdown block, including repeated references.
    for block_index, token in enumerate(tokens):
        if token.type == 'inline':
            for child in token.children or []:
                child.meta['block_index'] = block_index
    base_text = md.renderer.rules['text']
    def positioned(tokens, idx, options, env):
        env['inline_index'] = tokens[idx].meta.get('block_index', 0)
        return base_text(tokens, idx, options, env)
    md.renderer.rules['text'] = positioned
    return {'html': md.renderer.render(tokens, md.options, {}), 'references': refs}
