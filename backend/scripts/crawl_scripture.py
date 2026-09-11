"""Crawl lxfyt chapters; --write explicitly enables the authenticated write API."""
import argparse
import getpass
import os
import sys
from pathlib import Path
from urllib.parse import urlsplit
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import httpx
from app.collectors.lxfyt import Source, crawl, BASE


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--book',action='append',help='规范书卷代码，如 Gen；可重复；省略则全部 66 卷')
    p.add_argument('--chapter',type=int,help='仅采集指定章，需同时选择一个书卷')
    p.add_argument('--cache-dir',type=Path,default=Path.home()/'Library/Caches/bible-library/lxfyt')
    p.add_argument('--delay',type=float,default=1.0,help='请求间隔秒数，最小 1 秒')
    p.add_argument('--refresh',action='store_true',help='重新下载已缓存章节')
    p.add_argument('--write',action='store_true',help='写入应用数据库；默认仅采集校验')
    p.add_argument('--update-existing',action='store_true',help='允许更新不同的已有正文，不删除经节')
    p.add_argument('--web-url',default='http://127.0.0.1:5173')
    p.add_argument('--username',default=os.environ.get('BIBLE_ADMIN_USER'))
    p.add_argument('--translation-code',default='lxfyt-zh')
    p.add_argument('--translation-name',default='lxfyt 网站中文经文（译本待核实）')
    args=p.parse_args()
    if args.chapter is not None and (not args.book or len(args.book)!=1 or args.chapter<1):
        p.error('--chapter 需要一个 --book，且章号必须大于零')
    parts=urlsplit(args.web_url)
    if parts.scheme!='http' or parts.hostname not in ('127.0.0.1','localhost','::1') or parts.path not in ('','/') or parts.username or parts.password or parts.query or parts.fragment:
        p.error('--web-url 只接受本机 HTTP 网页根地址')
    source=None
    client=None
    try:
        tid=None
        if args.write:
            client=httpx.Client(base_url=args.web_url.rstrip('/'),timeout=30,follow_redirects=False)
            response=client.get('/web-config.json');response.raise_for_status()
            client.headers['X-App-Key']=response.json()['key']
            username=args.username or input('管理员用户名：')
            password=os.environ.get('BIBLE_ADMIN_PASSWORD') or getpass.getpass('管理员密码：')
            response=client.post('/api/login',json={'username':username,'password':password});response.raise_for_status()
            session=response.json()
            if session['user']['role']!='admin' or session['user']['must_change_password']:
                raise ValueError('请使用已完成改密的管理员账户')
            client.headers['Authorization']='Bearer '+session['token']
            response=client.get('/api/translations');response.raise_for_status()
            existing=next((t for t in response.json() if t['code']==args.translation_code),None)
            if existing and (existing['source']!=BASE+'index.html' or existing['language']!='zh'):
                raise ValueError('已有译本来源或语言不匹配，请使用新的采集译本代码')
            if existing:
                tid=existing['id']
            else:
                response=client.post('/api/translations',json={'code':args.translation_code,'name':args.translation_name,'language':'zh','source':BASE+'index.html'})
                response.raise_for_status();tid=response.json()['id']
        source=Source(args.delay)
        report=crawl(source,args.cache_dir,args.book,args.chapter,client,tid,args.refresh,args.update_existing)
        print(f"完成 {len(report['chapters'])} 章，失败 {len(report['failed'])} 项；报告：{args.cache_dir/'report.json'}")
        return 1 if report['failed'] else 0
    except (ValueError,httpx.HTTPError,OSError) as exc:
        # Do not print request bodies, authentication headers or credentials.
        print(f'采集停止：{type(exc).__name__}；请检查连接、目录和账户。',file=sys.stderr)
        return 1
    finally:
        if source: source.close()
        if client: client.close()


if __name__=='__main__':
    raise SystemExit(main())
