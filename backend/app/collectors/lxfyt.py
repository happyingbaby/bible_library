"""Collect the public lxfyt Chinese Bible through its actual directory links."""
import json
import re
import time
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser

import httpx
from app.modules.references import ALIASES, BOOKS

BASE = 'https://live.lxfyt.cn/shengjing/'
AGENT = 'BibleLibraryCollector/1.0'


class Node:
    def __init__(self, tag='', attrs=()):
        self.tag, self.attrs, self.children = tag, dict(attrs), []
        self.closed = False

    def text(self):
        return ''.join(c.text() if isinstance(c, Node) else c for c in self.children)

    def find(self, tag=None, **attrs):
        result = []
        if (tag is None or self.tag == tag) and all(
            value in self.attrs.get(key, '').split() if key == 'class' else self.attrs.get(key) == value
            for key, value in attrs.items()
        ):
            result.append(self)
        for child in self.children:
            if isinstance(child, Node):
                result.extend(child.find(tag, **attrs))
        return result


class Page(HTMLParser):
    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.root = Node()
        self.stack = [self.root]
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs)
        self.stack[-1].children.append(node)
        if tag == 'br':
            node.children.append('\n')
        if tag not in {'area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr'}:
            self.stack.append(node)

    def handle_endtag(self, tag):
        for i in range(len(self.stack)-1, 0, -1):
            if self.stack[i].tag == tag:
                self.stack[i].closed = True
                del self.stack[i:]
                break

    def handle_data(self, data):
        self.stack[-1].children.append(data)


def source_url(href, parent=BASE):
    url = urljoin(parent, href)
    parts = urlsplit(url)
    if parts.scheme != 'https' or parts.netloc != 'live.lxfyt.cn' or not parts.path.startswith('/shengjing/') or parts.query or parts.fragment:
        raise ValueError('目录包含非预期来源链接')
    return url


def parse_books(html):
    found = {}
    for a in Page(html).root.find('a'):
        href = a.attrs.get('href', '')
        if not re.fullmatch(r'[a-z0-9-]+_[0-9]+\.html', href):
            continue
        names = a.text().strip().split()
        code = next((ALIASES[n.lower()] for n in reversed(names) if n.lower() in ALIASES), None)
        if code is None:
            label = ''.join(names)
            code = next((b for b, info in BOOKS.items() if label.endswith(info['name'])), None)
        if not code:
            raise ValueError('无法识别书卷目录名称：' + a.text())
        url = source_url(href)
        if code in found and found[code] != url:
            raise ValueError('书卷目录重复冲突')
        found[code] = url
    if set(found) != set(BOOKS):
        raise ValueError('网站目录不完整：必须包含 66 卷')
    return {code: found[code] for code in BOOKS}


def parse_chapters(html, book, url):
    groups = Page(html).root.find('ul', **{'class':'zhangList'})
    if len(groups) != 1:
        raise ValueError('无法定位章节目录')
    found = {}
    for a in groups[0].find('a'):
        number = int(a.text().strip())
        target = source_url(a.attrs.get('href', ''), url)
        expected = url.removesuffix('.html') + f'_{number}.html'
        if target != expected or number in found:
            raise ValueError('章节链接或编号不一致')
        found[number] = target
    if set(found) != set(range(1, BOOKS[book]['chapters']+1)):
        raise ValueError('章节目录不完整或与规范目录不一致')
    return found


def parse_verses(html, book, chapter):
    root = Page(html).root
    title = root.find('title')
    if len(title) != 1 or not title[0].text().startswith(BOOKS[book]['name']+'_') or f'_第{chapter}章_' not in title[0].text():
        raise ValueError('正文页面书卷／章号不匹配')
    lists = root.find('ul', id='song_list')
    if len(lists) != 1 or not lists[0].closed:
        raise ValueError('找不到经文列表 song_list')
    rows = {}
    for li in lists[0].find('li'):
        spans, paragraphs = li.find('span'), li.find('p')
        if not li.closed or len(spans) != 1 or len(paragraphs) != 1 or not paragraphs[0].closed or paragraphs[0].find('script') or paragraphs[0].find('style'):
            raise ValueError('经节结构异常，拒绝写入')
        number = int(spans[0].text().strip())
        text = paragraphs[0].text().strip()
        if number in rows or not 1 <= number <= 176 or not text or len(text)>10000:
            raise ValueError('重复、空白或非法经节')
        rows[number] = text
    if not rows or list(rows) != list(range(1,len(rows)+1)):
        raise ValueError('经节编号不连续或页面为空')
    if book == 'Gen' and chapter == 1 and len(rows) != 31:
        raise ValueError('创世记第 1 章应为 31 节，拒绝不完整页面')
    return rows


class Source:
    def __init__(self, delay=1.0):
        self.delay = max(1.0, delay)
        self.last = 0.0
        self.client = httpx.Client(timeout=30, headers={'User-Agent':AGENT}, follow_redirects=False)
        self.robot = RobotFileParser()
        raw = self._get('https://live.lxfyt.cn/robots.txt', robots=True)
        self.robot.parse(raw.splitlines())

    def _get(self, url, robots=False):
        for attempt in range(3):
            time.sleep(max(0, self.last+self.delay-time.monotonic()))
            self.last = time.monotonic()
            try:
                with self.client.stream('GET', url) as response:
                    if robots and response.status_code == 404:
                        return 'User-agent: *\nAllow: /'
                    if response.status_code == 429 or response.status_code >= 500:
                        wait = response.headers.get('Retry-After', '')
                        if wait.isdigit():
                            self.last += min(int(wait), 60)
                        response.raise_for_status()
                    response.raise_for_status()
                    if response.is_redirect:
                        raise ValueError('来源页面重定向，停止采集并检查地址')
                    chunks, size = [], 0
                    for chunk in response.iter_bytes():
                        size += len(chunk)
                        if size > 2_000_000:
                            raise ValueError('来源页面过大')
                        chunks.append(chunk)
                    return b''.join(chunks).decode('utf-8-sig')
            except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError) as exc:
                if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code not in (429,500,502,503,504):
                    raise
                if attempt == 2:
                    raise
                self.last += 2**attempt
        raise RuntimeError('下载失败')

    def get(self, url):
        url = source_url(url)
        if not self.robot.can_fetch(AGENT,url):
            raise ValueError('robots.txt 不允许采集此地址')
        return self._get(url)

    def close(self):
        self.client.close()


def write_chapter(client, translation_id, book, chapter, rows, update_existing=False):
    """Use authenticated application API; no direct DB access or deletion.

    client accepts httpx.Client or FastAPI TestClient, with a root (not /api) base URL.
    The caller provides authentication headers. A stale revision stops the write.
    """
    path = f'/api/bible/translations/{translation_id}/{book}/{chapter}'
    response = client.get(path)
    response.raise_for_status()
    current = response.json()
    existing = {v['verse']:v['text'] for v in current['verses']}
    if not update_existing and any(n in existing and existing[n] != t for n,t in rows.items()):
        raise ValueError('数据库已有不同正文；本章未写入，核对后使用 --update-existing')
    revision, changed = current['revision'], 0
    for number, text in sorted(rows.items()):
        if existing.get(number) == text:
            continue
        response = client.put(f'{path}/{number}',json={'text':text,'revision':revision})
        response.raise_for_status()
        revision = response.json()['revision']
        changed += 1
    return changed


def crawl(source, cache_dir, books=None, chapter=None, client=None, translation_id=None, refresh=False, update_existing=False):
    """Fetch/validate chapters and optionally write through the existing API.

    A validated HTML cache supports restart; DB contents, never progress flags,
    decide which verses still need writing. Failure details stay in report.json.
    """
    directory = parse_books(source.get(BASE+'index.html'))
    chosen = books or list(directory)
    if any(book not in directory for book in chosen):
        raise ValueError('未知书卷代码')
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True,exist_ok=True)
    report = {'chapters':[], 'failed':[]}
    for book in chosen:
        try:
            chapters = parse_chapters(source.get(directory[book]),book,directory[book])
            if chapter is not None and chapter not in chapters:
                raise ValueError('该书卷没有指定章节')
        except (ValueError,httpx.HTTPError) as exc:
            report['failed'].append({'book':book,'error':str(exc)})
            continue
        for number,url in chapters.items():
            if chapter is not None and number != chapter:
                continue
            try:
                path = cache_dir/f'{book}-{number}.html'
                html = path.read_text(encoding='utf-8') if path.exists() and not refresh else source.get(url)
                rows = parse_verses(html,book,number)
                temporary = path.with_suffix('.tmp')
                temporary.write_text(html,encoding='utf-8')
                temporary.replace(path)
                changed = write_chapter(client,translation_id,book,number,rows,update_existing) if client is not None else 0
                report['chapters'].append({'book':book,'chapter':number,'source':url,'verses':len(rows),'written':changed})
                print(f'{book} {number}: {len(rows)} verses, {changed} written',flush=True)
            except (ValueError,httpx.HTTPError) as exc:
                report['failed'].append({'book':book,'chapter':number,'source':url,'error':str(exc)})
                print(f'{book} {number}: failed ({type(exc).__name__})',flush=True)
                # Stop on authentication, revision or API failures; avoid repeated unsafe writes.
                if isinstance(exc,httpx.HTTPStatusError) and client is not None and str(exc.request.url).startswith(str(client.base_url)):
                    break
        if report['failed']:
            break
    (cache_dir/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return report
