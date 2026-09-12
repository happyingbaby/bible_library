#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
爬虫：从 prayers.github.io 中英双语 NIV 圣经抓取英文经文，写入 bible_library.verses。
目标译本 translation_id=2 (NIV 英文版)。

源站结构（每卷一页）：
  - 目录页 bible_content.html：<li><a href=".../%E5%88%9B%E4%B8%96%E8%AE%B0.html">1-创世记</a></li>
  - 详情页（整卷）：<h5 id="创11">创1:1</h5>
                     <blockquote><p>英文</p><p>中文</p></blockquote>
    注意：诗篇119章异常——中文、英文分别位于两个 <blockquote>（中文在前、英文在后），
          故以“包含拉丁字母的 blockquote 第一个 p”判定英文行，兼容两种结构。

写入遵循 bible_library 文档约定（与 crawl_bible_direct.py 一致）：
  - utf8mb4；按 (translation_id,book,chapter,verse) 唯一键幂等写入
  - 每章一个事务：SELECT revision FOR UPDATE → INSERT/UPDATE → 有变更则 revision+1
  - 仅写入 bible_chapters 已初始化的 (book,chapter)，避免外键冲突
  - 凭据通过环境变量 BIBLE_DB_PASS 传入（不硬编码）
"""
import re, sys, json, time, argparse, os, urllib.request, urllib.parse, urllib.error
from bs4 import BeautifulSoup
import pymysql

BASE = "https://prayers.github.io/learning/bible/"
DIR_URL = BASE + "bible_content.html"
TRANSLATION_ID = 2
REF_RE = re.compile(r"^(.+?)(\d+):(\d+)\s*$")
LATIN_RE = re.compile(r"[A-Za-z]")


def db_connect(passwd):
    return pymysql.connect(host="39.102.143.118", port=3306, user="bible_library",
                           password=passwd, database="bible_library",
                           charset="utf8mb4", autocommit=False, connect_timeout=20)


def load_catalog(conn):
    cur = conn.cursor()
    cur.execute("SELECT code, name, position, chapter_count FROM bible_books ORDER BY position")
    rows = cur.fetchall()
    name2code = {r[1]: r[0] for r in rows}
    cat = set()
    cur.execute("SELECT book, number FROM bible_chapters")
    for b, c in cur.fetchall():
        cat.add((b, c))
    cur.close()
    return name2code, cat


def http_get(url, retries=4, backoff=1.5):
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.read().decode("utf-8")
        except Exception as e:
            last = e
            if attempt < retries - 1:
                time.sleep(backoff * (attempt + 1))
    raise last


def parse_directory(html):
    soup = BeautifulSoup(html, "html.parser")
    books = []
    for li in soup.select("ul li a"):
        href = li.get("href", "")
        txt = li.get_text(strip=True)
        if ".html" not in href:
            continue
        m = re.match(r"^(\d+)[-\s]*(.+)$", txt)
        if not m:
            continue
        pos = int(m.group(1))
        name = m.group(2)
        url = href if href.startswith("http") else urllib.parse.urljoin(DIR_URL, href)
        books.append((pos, name, url))
    books.sort(key=lambda x: x[0])
    return books


def parse_book(html):
    """返回 {(chapter,verse): english_text} 与 warnings 列表。"""
    soup = BeautifulSoup(html, "html.parser")
    verses = {}
    warnings = []
    for h5 in soup.find_all("h5"):
        ref = h5.get_text(strip=True)
        m = REF_RE.match(ref)
        if not m:
            warnings.append(("bad_ref", ref))
            continue
        chapter = int(m.group(2))
        verse = int(m.group(3))
        # 扫描后续 blockquote 兄弟节点，取首个含拉丁字母的 p 作为英文
        english = None
        node = h5
        while True:
            node = node.find_next_sibling()
            if node is None or node.name == "h5":
                break
            if node.name == "blockquote":
                for p in node.find_all("p"):
                    t = p.get_text()
                    if LATIN_RE.search(t):
                        english = t
                        break
                if english is not None:
                    break
        if english is None:
            warnings.append(("no_english", ref))
            continue
        english = re.sub(r"\s+", " ", english).strip()
        verses[(chapter, verse)] = english
    return verses, warnings


def write_chapter(conn, code, chapter, cvs, cat, tid=TRANSLATION_ID):
    """cvs: list of (verse, text) 已按 verse 排序。返回 (inserted, updated, skipped)。"""
    if (code, chapter) not in cat:
        return ("skip_cat", 0, 0, 0)
    cur = conn.cursor()
    cur.execute("SELECT revision FROM translations WHERE id=%s FOR UPDATE", (tid,))
    cur.execute("SELECT verse, text FROM verses WHERE translation_id=%s AND book=%s AND chapter=%s",
                (tid, code, chapter))
    existing = {v: t for v, t in cur.fetchall()}
    ins, upd, skip = [], [], 0
    for verse, text in cvs:
        if verse in existing:
            if existing[verse] == text:
                skip += 1
            else:
                upd.append((text, tid, code, chapter, verse))
        else:
            ins.append((tid, code, chapter, verse, text))
    if ins or upd:
        if ins:
            cur.executemany(
                "INSERT INTO verses (translation_id,book,chapter,verse,text) VALUES (%s,%s,%s,%s,%s)", ins)
        if upd:
            cur.executemany(
                "UPDATE verses SET text=%s WHERE translation_id=%s AND book=%s AND chapter=%s AND verse=%s", upd)
        cur.execute("UPDATE translations SET revision=revision+1 WHERE id=%s", (tid,))
    conn.commit()
    cur.close()
    return ("ok", len(ins), len(upd), skip)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db-pass", default=os.environ.get("BIBLE_DB_PASS", ""))
    ap.add_argument("--translation-id", type=int, default=TRANSLATION_ID)
    ap.add_argument("--book", help="仅抓取指定书卷 code，如 Gen / Phlm")
    ap.add_argument("--delay", type=float, default=0.3, help="每卷抓取间隔(秒)")
    ap.add_argument("--dry-run", action="store_true", help="只解析不写库")
    ap.add_argument("--skip-existing", action="store_true", help="跳过译本2该卷已写满的卷")
    ap.add_argument("--report", help="写出 JSON 报告路径")
    args = ap.parse_args()

    if not args.db_pass:
        print("ERROR: 需通过 --db-pass 或环境变量 BIBLE_DB_PASS 提供数据库密码", file=sys.stderr)
        sys.exit(2)

    conn = db_connect(args.db_pass)
    name2code, cat = load_catalog(conn)

    print("解析目录页:", DIR_URL)
    dir_html = http_get(DIR_URL)
    books = parse_directory(dir_html)
    print(f"  目录解析到 {len(books)} 卷")

    # name -> (code, url)
    plan = []
    for pos, name, url in books:
        code = name2code.get(name)
        if not code:
            print(f"  [跳过] 目录书名 {name} 未在 bible_books 中找到对应 code")
            continue
        plan.append((pos, code, name, url))
    if args.book:
        plan = [p for p in plan if p[1] == args.book]
        if not plan:
            print(f"ERROR: 未找到书卷 {args.book}", file=sys.stderr)
            sys.exit(2)

    totals = {"books": len(plan), "chapters": 0, "inserted": 0, "updated": 0, "skipped": 0,
              "skipped_cat": 0, "no_english": 0, "bad_ref": 0, "warnings": []}
    if args.skip_existing:
        cur = conn.cursor()
        cur.execute("SELECT book, COUNT(*) FROM verses WHERE translation_id=%s GROUP BY book", (TRANSLATION_ID,))
        have = {b: c for b, c in cur.fetchall()}
        cur.close()
    else:
        have = {}

    for pos, code, name, url in plan:
        try:
            html = http_get(url)
        except Exception as e:
            msg = f"fetch_failed {code} {url}: {e}"
            print("  " + msg, file=sys.stderr)
            totals["warnings"].append(msg)
            continue
        verses, warns = parse_book(html)
        for kind, val in warns:
            if kind == "no_english":
                totals["no_english"] += 1
            elif kind == "bad_ref":
                totals["bad_ref"] += 1
            totals["warnings"].append(f"{code}:{kind}:{val}")

        if args.skip_existing and have.get(code, 0) >= sum(1 for (c, v) in verses):
            # 粗略跳过：该卷已写满（按 verse 数判断，非严谨）
            print(f"  [{pos:>2}] {code} {name}: 已存在，跳过")
            continue

        if args.dry_run:
            nchap = len(set(c for (c, v) in verses))
            nvv = len(verses)
            print(f"  [dry] [{pos:>2}] {code} {name}: {nchap} 章 / {nvv} 节")
            totals["chapters"] += nchap
            totals["skipped"] += nvv
            continue

        # 按章分组写入
        chapters = sorted(set(c for (c, v) in verses))
        for ch in chapters:
            cvs = sorted([(v, verses[(c, v)]) for (c, v) in verses if c == ch])
            status, ins, upd, skp = write_chapter(conn, code, ch, cvs, cat, tid=args.translation_id)
            totals["chapters"] += 1
            if status == "skip_cat":
                totals["skipped_cat"] += 1
                totals["warnings"].append(f"{code} {ch}: 不在 bible_chapters 目录，跳过")
            else:
                totals["inserted"] += ins
                totals["updated"] += upd
                totals["skipped"] += skp
        print(f"  [{pos:>2}] {code} {name}: {len(chapters)} 章, "
              f"新增 {totals['inserted']} / 更新 {totals['updated']} / 跳过 {totals['skipped']}")
        if args.delay:
            time.sleep(args.delay)

    conn.close()
    print("\n=== 总计 ===")
    print(json.dumps(totals, ensure_ascii=False))
    if args.report:
        with open(args.report, "w", encoding="utf-8") as f:
            json.dump(totals, f, ensure_ascii=False, indent=2)
        print("报告已写出:", args.report)


if __name__ == "__main__":
    main()
