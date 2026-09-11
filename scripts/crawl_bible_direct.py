#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
圣经爬虫（直写 MySQL 版）

从 https://live.lxfyt.cn/shengjing 抓取中文经文，直接写入 bible_library.verses。
遵循《圣经数据结构与爬虫接口.md》第 7 节“直接写库的约定”：

  1. 使用 utf88mb4；以规范书卷代码（Gen / John …）匹配已初始化的 bible_chapters，
     不创建重复目录、不猜测英文路径。
  2. 写入时在事务内对目标 translations 行加 SELECT ... FOR UPDATE 锁。
  3. 按四字段唯一键 (translation_id, book, chapter, verse) 新增或更新 verses；
     校验章号 / 节号 / 正文 / 长度。
  4. 凡发生新增或修改正文，同步递增 translations.revision（否则管理页无法感知变更）。
  5. 提交成功后计入进度；失败回滚。不触碰账户 / 讲义 / 会话表。

用法：
  # 仅解析创世记第 1 章，不写库（验证解析结果）
  python crawl_bible_direct.py --dry-run --book Gen --chapter 1

  # 把创世记整卷写入数据库
  python crawl_bible_direct.py --book Gen

  # 全本 66 卷写入（断点续跑：相同正文自动跳过）
  python crawl_bible_direct.py

数据库连接：优先读环境变量 BIBLE_DB_HOST/PORT/USER/PASS/NAME，也可用 --db-* 覆盖。
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

from bs4 import BeautifulSoup
import pymysql

# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------
SITE = "https://live.lxfyt.cn"
BASE = SITE + "/shengjing/"
UA = "Mozilla/5.0 (compatible; BibleCrawler/1.0; +respect-robots)"

VERSE_MAX = 176          # API 限制 1~176
TEXT_MAX = 10000         # API 限制 1~10000


# ---------------------------------------------------------------------------
# 网络
# ---------------------------------------------------------------------------
def fetch(url, delay, retries, robots):
    """抓取 URL，返回解码后的 HTML 字符串；404 返回 None；5xx/429 按 retries 退避。"""
    if not robots.allowed(url):
        print(f"  [robots] 被 robots.txt 禁止：{url}", file=sys.stderr)
        return None
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": UA, "Referer": BASE}
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if e.code in (429, 500, 502, 503, 504):
                wait = delay * attempt
                print(f"  [warn] {url} HTTP {e.code}，第 {attempt} 次重试，{wait:.0f}s 后",
                      file=sys.stderr)
                time.sleep(wait)
                continue
            raise
        except Exception as e:  # 超时 / 连接错误
            if attempt < retries:
                wait = delay * attempt
                print(f"  [warn] {url} 异常 {e}，第 {attempt} 次重试，{wait:.0f}s 后",
                      file=sys.stderr)
                time.sleep(wait)
                continue
            raise
    return None


class Robots:
    """极简 robots.txt 解析：仅支持 * 通配与 Disallow 前缀匹配。"""
    def __init__(self, base):
        self.allowed_paths = []
        self.loaded = False
        try:
            req = urllib.request.Request(base + "/robots.txt",
                                         headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=15) as r:
                for line in r.read().decode("utf-8", "replace").splitlines():
                    line = line.strip()
                    if line.lower().startswith("disallow:"):
                        path = line.split(":", 1)[1].strip()
                        if path:
                            self.allowed_paths.append(path)
            self.loaded = True
        except Exception:
            # 取不到 robots 不阻塞采集，仅给提示
            print("[info] 未能获取 robots.txt，按默认允许采集。", file=sys.stderr)

    def allowed(self, url):
        path = url[len(SITE):] if url.startswith(SITE) else url
        for p in self.allowed_paths:
            if p == "/" or path.startswith(p):
                return False
        return True


# ---------------------------------------------------------------------------
# 解析
# ---------------------------------------------------------------------------
def parse_index(html):
    """从总目录解析 66 卷：{testament, position, name, slug}。"""
    soup = BeautifulSoup(html, "html.parser")
    books = []
    for ul_id, testament in (("jiu", "OT"), ("xin", "NT")):
        ul = soup.find("ul", id=ul_id)
        if not ul:
            continue
        for li in ul.find_all("li", recursive=False):
            a = li.find("a")
            if not a:
                continue
            href = a.get("href", "")
            m = re.match(r"([a-zA-Z0-9\-]+)_(\d+)\.html$", href)
            if not m:
                continue
            slug = m.group(1)
            position = int(m.group(2))
            name_tag = a.find("span")
            name = name_tag.get_text(strip=True) if name_tag else a.get_text(strip=True)
            books.append({"testament": testament, "position": position,
                          "name": name, "slug": slug})
    return books


def parse_chapter(html):
    """从章节页解析 {节号(int): 正文(str)}。章节页结构：
       <ul class="jingRead" id="song_list">
         <li><span>1</span><p>正文<br></p></li>
    """
    soup = BeautifulSoup(html, "html.parser")
    ul = soup.find("ul", class_="jingRead", id="song_list")
    if ul is None:
        ul = soup.find("ul", class_="jingRead")
    verses = {}
    if ul is None:
        return verses
    for li in ul.find_all("li", recursive=False):
        span = li.find("span")
        if span is None:
            continue
        try:
            vn = int(span.get_text(strip=True))
        except ValueError:
            continue
        p = li.find("p")
        if p is not None:
            text = p.get_text(separator=" ", strip=True)
        else:
            text = li.get_text(separator=" ", strip=True)
        text = " ".join(text.split())  # 归一化空白（含 <br> 产生的换行）
        if not text:
            continue
        verses[vn] = text
    return verses


# ---------------------------------------------------------------------------
# 数据库
# ---------------------------------------------------------------------------
def load_catalog(conn):
    """从已初始化的目录表读取规范代码与章节集合（权威来源）。"""
    cur = conn.cursor()
    cur.execute("SELECT position, code, name, testament_code, chapter_count "
                "FROM bible_books")
    books_by_position = {}
    for position, code, name, tc, cc in cur.fetchall():
        books_by_position[position] = {
            "code": code, "name": name,
            "testament_code": tc, "chapter_count": cc,
        }
    cur.execute("SELECT book, number FROM bible_chapters")
    chapters_by_book = {}
    for book, number in cur.fetchall():
        chapters_by_book.setdefault(book, set()).add(number)
    cur.close()
    return books_by_position, chapters_by_book


def write_chapter(conn, translation_id, code, chapter, verses):
    """把一章解析结果写入 verses；返回 (changed, skipped)。

    相同正文跳过（不 bump revision）；发生新增/修改则整章在一个事务内提交，
    并对 translations 行加锁、revision +1。
    """
    cur = conn.cursor()
    cur.execute(
        "SELECT verse, text FROM verses "
        "WHERE translation_id=%s AND book=%s AND chapter=%s",
        (translation_id, code, chapter),
    )
    existing = {v: t for v, t in cur.fetchall()}

    to_write = []
    skipped = 0
    for vn, text in verses.items():
        if not (1 <= vn <= VERSE_MAX):
            print(f"    [skip] {code} {chapter}:{vn} 节号越界", file=sys.stderr)
            continue
        if len(text) > TEXT_MAX:
            text = text[:TEXT_MAX]
        if existing.get(vn) == text:
            skipped += 1
        else:
            to_write.append((translation_id, code, chapter, vn, text))

    changed = 0
    if to_write:
        try:
            cur.execute("SELECT id, revision FROM translations "
                        "WHERE id=%s FOR UPDATE", (translation_id,))
            cur.executemany(
                "INSERT INTO verses (translation_id, book, chapter, verse, text) "
                "VALUES (%s, %s, %s, %s, %s) "
                "ON DUPLICATE KEY UPDATE text=VALUES(text)",
                to_write,
            )
            cur.execute("UPDATE translations SET revision = revision + 1 "
                        "WHERE id=%s", (translation_id,))
            conn.commit()
            changed = len(to_write)
        except Exception:
            conn.rollback()
            raise
    cur.close()
    return changed, skipped


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="圣经爬虫（直写 MySQL）")
    ap.add_argument("--dry-run", action="store_true", help="只解析不写库")
    ap.add_argument("--book", help="只采集指定书卷代码，如 Gen / John（默认全部）")
    ap.add_argument("--testament", choices=["OT", "NT"], help="只采集某约")
    ap.add_argument("--chapter", type=int, help="只采集一章（需同时指定 --book）")
    ap.add_argument("--delay", type=float, default=1.0, help="请求间隔秒数（>=1）")
    ap.add_argument("--translation-id", type=int, default=1, help="目标译本 ID")
    ap.add_argument("--limit", type=int, help="最多采集多少章（调试用）")
    ap.add_argument("--report", default="crawl_report.json", help="报告输出路径")
    ap.add_argument("--db-host", default=os.getenv("BIBLE_DB_HOST", "39.102.143.118"))
    ap.add_argument("--db-port", type=int, default=int(os.getenv("BIBLE_DB_PORT", "3306")))
    ap.add_argument("--db-user", default=os.getenv("BIBLE_DB_USER", "bible_library"))
    ap.add_argument("--db-pass", default=os.getenv("BIBLE_DB_PASS", ""))
    ap.add_argument("--db-name", default=os.getenv("BIBLE_DB_NAME", "bible_library"))
    args = ap.parse_args()

    if args.delay < 1.0 and not args.dry_run:
        print("[warn] 请求间隔小于 1s，已按约定提升到 1s。", file=sys.stderr)
        args.delay = 1.0

    # 1) 取目录（网络）
    print(f"[1/5] 抓取总目录 {BASE}index.html ...")
    robots = Robots(SITE)
    idx_html = fetch(BASE + "index.html", args.delay, 3, robots)
    if not idx_html:
        print("[error] 无法获取总目录，终止。", file=sys.stderr)
        sys.exit(1)
    site_books = parse_index(idx_html)
    print(f"      站点解析到 {len(site_books)} 卷。")

    # 2) 连接数据库并加载规范目录
    print(f"[2/5] 连接数据库 {args.db_host}/{args.db_name} ...")
    conn = pymysql.connect(host=args.db_host, port=args.db_port, user=args.db_user,
                           password=args.db_pass, database=args.db_name,
                           charset="utf8mb4", autocommit=False, connect_timeout=20)
    books_by_position, chapters_by_book = load_catalog(conn)
    cur = conn.cursor()
    cur.execute("SELECT id, code, name, language, revision FROM translations "
                "WHERE id=%s", (args.translation_id,))
    tr = cur.fetchone()
    cur.close()
    if tr is None:
        print(f"[error] translations 中不存在 id={args.translation_id}，终止。",
              file=sys.stderr)
        conn.close()
        sys.exit(1)
    print(f"      译本 #{tr[0]} {tr[2]} ({tr[3]}) revision={tr[4]}")

    # 3) 把站点卷映射到规范代码（以 position 为关联键，禁止猜测英文路径）
    targets = []  # (code, slug, position, chapter)
    for b in site_books:
        meta = books_by_position.get(b["position"])
        if meta is None:
            print(f"    [warn] 站点卷 position={b['position']} {b['name']} "
                  f"在 bible_books 中无对应，跳过。", file=sys.stderr)
            continue
        code = meta["code"]
        if args.book and code != args.book:
            continue
        if args.testament and meta["testament_code"] != args.testament:
            continue
        all_chapters = sorted(chapters_by_book.get(code, set()))
        if args.chapter is not None:
            if args.chapter not in all_chapters:
                print(f"    [warn] {code} 无第 {args.chapter} 章（目录未收录），跳过。",
                      file=sys.stderr)
                continue
            chap_list = [args.chapter]
        else:
            chap_list = all_chapters
        for ch in chap_list:
            targets.append((code, b["slug"], b["position"], ch))
    # 按 position 稳定排序
    targets.sort(key=lambda t: t[2])
    print(f"[3/5] 计划采集 {len(targets)} 章。")

    if args.limit:
        targets = targets[:args.limit]

    # 4) 逐章采集
    print(f"[4/5] 开始{'演练' if args.dry_run else '采集'} ...")
    report = {"translation_id": args.translation_id, "chapters": [],
              "totals": {"chapters": 0, "verses": 0, "changed": 0,
                         "skipped": 0, "failed": 0}}
    t0 = time.time()
    for i, (code, slug, position, ch) in enumerate(targets, 1):
        url = f"{BASE}{slug}_{position}_{ch}.html"
        html = fetch(url, args.delay, 3, robots)
        rec = {"book": code, "chapter": ch, "url": url,
               "verses": 0, "changed": 0, "skipped": 0, "status": "ok"}
        if html is None:
            rec["status"] = "fetch_failed"
            report["totals"]["failed"] += 1
            print(f"  ({i}/{len(targets)}) {code} {ch}: 抓取失败")
        else:
            verses = parse_chapter(html)
            rec["verses"] = len(verses)
            if args.dry_run:
                rec["status"] = "dry_run"
                if i <= 3:  # 仅前 3 章打印样本，避免刷屏
                    sample = list(verses.items())[:3]
                    print(f"  ({i}/{len(targets)}) {code} {ch}: "
                          f"{len(verses)} 节 样本={sample}")
                else:
                    print(f"  ({i}/{len(targets)}) {code} {ch}: {len(verses)} 节")
            else:
                changed, skipped = write_chapter(
                    conn, args.translation_id, code, ch, verses)
                rec["changed"], rec["skipped"] = changed, skipped
                report["totals"]["changed"] += changed
                report["totals"]["skipped"] += skipped
                print(f"  ({i}/{len(targets)}) {code} {ch}: "
                      f"{len(verses)} 节 写入={changed} 跳过={skipped}")
        report["totals"]["verses"] += rec["verses"]
        report["chapters"].append(rec)
        if not args.dry_run:
            time.sleep(args.delay)

    # 5) 收尾
    report["totals"]["chapters"] = len(targets)
    report["elapsed_sec"] = round(time.time() - t0, 1)
    with open(args.report, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"[5/5] 完成。报告已写 {args.report}")
    print("  汇总:", json.dumps(report["totals"], ensure_ascii=False))
    conn.close()


if __name__ == "__main__":
    main()
