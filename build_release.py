"""Сборка печатной книги и переносимого архива. Только стандартная библиотека."""
from html import escape
from pathlib import Path
import re
import zipfile

from core import ROOT, TITLES
from exercises import EXERCISES


def render_markdown(text):
    parts = []
    code = []
    paragraph = []
    in_code = False

    def flush():
        if paragraph:
            parts.append('<p>' + escape(' '.join(paragraph)) + '</p>')
            paragraph.clear()

    for line in text.splitlines():
        if line.startswith('```'):
            flush()
            if in_code:
                parts.append('<pre><code>' + escape('\n'.join(code)) + '</code></pre>')
                code = []
            in_code = not in_code
        elif in_code:
            code.append(line)
        elif line.startswith('# '):
            flush()
            parts.append('<h1>' + escape(line[2:]) + '</h1>')
        elif line.startswith('## '):
            flush()
            parts.append('<h2>' + escape(line[3:]) + '</h2>')
        elif not line:
            flush()
        elif re.match(r'^(- |\d+\. )', line):
            flush()
            parts.append('<p class="item">' + escape(line) + '</p>')
        else:
            paragraph.append(line)
    flush()
    return '\n'.join(parts)


def build():
    toc = '<nav><h2>Оглавление</h2>' + ''.join(f'<a href="#day-{i}">{i:02}. {escape(title)}</a>' for i, title in enumerate(TITLES, 1)) + '</nav>'
    sections = []
    for day in range(1, 31):
        content = render_markdown((ROOT / 'course' / f'{day:02}.md').read_text(encoding='utf-8'))
        tasks = '<h2>Задания с подсказками</h2>'
        for exercise in EXERCISES[day]:
            tasks += '<h3>' + escape(exercise['title']) + '</h3><p>' + escape(exercise['task']) + '</p>'
            tasks += '<pre>' + escape(exercise['starter']) + '</pre>'
            tasks += '<details><summary>Подсказка</summary><p>' + escape(exercise['hint']) + '</p></details>'
            tasks += '<details><summary>Решение</summary><pre>' + escape(exercise['solution']) + '</pre></details>'
        sections.append(f'<section id="day-{day}"><div class="chapter-number">ГЛАВА {day:02} / 30</div>{content}{tasks}<a href="#top">↑ К оглавлению</a></section>')
    html = '''<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Python с нуля — русская учебная книга</title><style>
:root{color-scheme:light}*{box-sizing:border-box}body{margin:0;background:#f6f3eb;color:#20332f;font:18px/1.75 system-ui,sans-serif}
header{padding:64px 28px;background:#20332f;color:#faf7f0}header>div,main{max-width:920px;margin:auto}header h1{font-size:44px;line-height:1.2;margin:16px 0}header p{max-width:680px;color:#c6dacb}
main{padding:32px 24px}nav{display:grid;grid-template-columns:1fr 1fr;gap:6px 20px;background:#eeece1;padding:26px;border-radius:12px}nav h2{grid-column:1/-1;margin:0 0 12px}
a{color:#236654;text-decoration-thickness:1px;text-underline-offset:3px}section{padding-top:64px;margin-bottom:36px}section h1{font-size:34px;line-height:1.3}h2{color:#236654;margin-top:40px;font-size:25px}h3{font-size:21px}
pre{background:#e9eee5;padding:20px;border-radius:8px;overflow:auto;font:15px/1.65 ui-monospace,Consolas,monospace;white-space:pre-wrap;overflow-wrap:anywhere}details{background:#eeece1;padding:12px 18px;margin:10px 0;border-radius:8px}summary{cursor:pointer;color:#236654;font-weight:600}.item{padding-left:12px}.chapter-number{letter-spacing:2px;font-size:13px;color:#61746a}button{padding:10px 18px;border:0;border-radius:6px;cursor:pointer;font-size:16px;background:#d1e6cd;color:#20332f}
@media(max-width:600px){nav{grid-template-columns:1fr}header h1{font-size:34px}main{padding:20px 16px}section h1{font-size:29px}}
@media print{body{background:white;font-size:11pt}header{background:white;color:#20332f;padding:20px}header p{color:#20332f}button{display:none}nav{display:block;columns:2}nav a{display:block}section{break-before:page;padding-top:0}pre{font-size:9pt;break-inside:avoid}details{display:block}details>*{display:block!important}a{color:inherit}main{max-width:none;padding:0}}
</style><header id="top"><div><div>УЧЕБНАЯ АДАПТАЦИЯ · 30 ТЕМ</div><h1>Python с нуля.<br>В своём темпе.</h1><p>Понятные объяснения, примеры и упражнения на русском. На основе 30 Days Of Python Асабенеха Йетайеха. Это адаптация, а не полный построчный перевод оригинала.</p><button onclick="window.print()">Печатать / сохранить в PDF</button></div></header><main>'''
    html += toc + ''.join(sections) + '<footer><p>Источник: <a href="https://github.com/Asabeneh/30-Days-Of-Python">Asabeneh / 30 Days Of Python</a>. Точная версия указана в original/SOURCE.json.</p></footer></main></html>'
    (ROOT / 'Книга.html').write_text(html, encoding='utf-8')
    (ROOT / 'Книга.md').write_text('# Python с нуля\n\nУчебная адаптация всех 30 тем, не полный построчный перевод.\n\n' + '\n\n---\n\n'.join((ROOT / 'course' / f'{day:02}.md').read_text(encoding='utf-8') for day in range(1, 31)), encoding='utf-8')
    output = ROOT.parent / 'library-files' / 'python-book-ru.zip'
    output.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(ROOT.rglob('*')):
            if path.is_file() and '__pycache__' not in path.parts and '.git' not in path.parts and path.suffix != '.pyc':
                archive.write(path, Path('Python-Book-RU') / path.relative_to(ROOT))
    print(f'Архив: {output} ({output.stat().st_size:,} байт)')


if __name__ == '__main__':
    build()
