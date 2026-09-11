import pytest
from app.collectors.lxfyt import BASE, BOOKS, parse_books, parse_chapters, parse_verses, source_url, write_chapter, crawl


def chapter_html(count=31):
    return '<title>创世记_Genesis_第1章_圣经在线阅读</title><ul id="song_list">'+''.join(f'<li><span>{n}</span><p>测试正文 {n} &amp; 文字<br></p></li>' for n in range(1,count+1))+'</ul>'


def index_html():
    return ''.join(f'<a href="book-{i}_{i}.html"><span>简称</span>{b["name"]}</a>' for i,b in enumerate(BOOKS.values(),1))


def test_parsers_and_bad_pages():
    assert len(parse_books(index_html()))==66
    html='<ul class="zhangList">'+''.join(f'<a href="book-1_1_{n}.html">{n}</a>' for n in range(1,51))+'</ul>'
    assert len(parse_chapters(html,'Gen',BASE+'book-1_1.html'))==50
    assert parse_verses(chapter_html(),'Gen',1)[1]=='测试正文 1 & 文字'
    for broken in [chapter_html().removesuffix('</ul>'),chapter_html(30),chapter_html().replace('<span>2</span>','<span>1</span>'),chapter_html().replace('第1章','第2章'),'<h1>登录</h1>']:
        with pytest.raises(ValueError):parse_verses(broken,'Gen',1)
    with pytest.raises(ValueError):source_url('https://example.com/page')
    with pytest.raises(ValueError):parse_books('<a href="genesis_1.html">创世记</a>')


def test_crawler_writes_and_resumes(client,admin,tmp_path):
    tid=client.post('/api/translations',json={'code':'crawl-test','name':'采集测试','language':'zh'}).json()['id']
    class FakeSource:
        def get(self,url):
            if url==BASE+'index.html':return index_html()
            if url==BASE+'book-1_1.html':return '<ul class="zhangList">'+''.join(f'<a href="book-1_1_{n}.html">{n}</a>' for n in range(1,51))+'</ul>'
            assert url==BASE+'book-1_1_1.html'
            return chapter_html()
    report=crawl(FakeSource(),tmp_path,['Gen'],1,client,tid)
    assert not report['failed']
    assert report['chapters'][0]['written']==31
    report=crawl(FakeSource(),tmp_path,['Gen'],1,client,tid)
    assert report['chapters'][0]['written']==0
    path=f'/api/bible/translations/{tid}/Gen/1'
    before=client.get(path).json()
    with pytest.raises(ValueError):write_chapter(client,tid,'Gen',1,{1:'不同正文',32:'新增'})
    assert client.get(path).json()==before
    assert write_chapter(client,tid,'Gen',1,{1:'不同正文'},True)==1
    assert len(client.get(path).json()['verses'])==31


def test_malformed_source_does_not_write(client,admin,tmp_path):
    tid=client.post('/api/translations',json={'code':'bad-crawl','name':'测试','language':'zh'}).json()['id']
    with pytest.raises(ValueError):parse_verses(chapter_html().replace('测试正文 2 &amp; 文字',''),'Gen',1)
    assert client.get(f'/api/bible/translations/{tid}/Gen/1').json()['verses']==[]
