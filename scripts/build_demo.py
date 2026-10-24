"""Build the public, entirely fictional template gallery for Cloudflare Pages.

Run ``python scripts/build_demo.py`` from the repository. This command never
loads a user's site.json, uploads, resume, or local wizard session.
"""
from __future__ import annotations

import argparse
from importlib.resources import files as package_files
from pathlib import Path
import shutil
import sys
from tempfile import TemporaryDirectory
import uuid

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ahb.exporter import asset_references, check_directory, public_files
from ahb.models import Site

MARKER = '.ahb-demo-generated'
MARKER_TEXT = b'Academic Homepage Builder fictional gallery\n'
NOINDEX = '<meta name="robots" content="noindex,nofollow">'
TEMPLATES = (
    ('academic', '01', 'Academic two-column', '学术双栏', 'A familiar home for your research.', 'serif', '#426b87'),
    ('modern', '02', 'Modern minimal', '现代简洁', 'A clear, focused introduction.', 'sans', '#477c70'),
    ('visual', '03', 'Visual portfolio', '视觉作品', 'More room for projects and ideas.', 'sans', '#806a9b'),
)


def gallery_files() -> dict[str, bytes]:
    """Generate only the bundled fictional example, with no uploaded assets."""
    example = Site.model_validate_json(package_files('ahb').joinpath('demo.json').read_bytes())
    if not example.example or asset_references(example):
        raise ValueError('The gallery requires a fictional example without personal attachments.')
    output = {
        MARKER: MARKER_TEXT,
        'robots.txt': b'User-agent: *\nDisallow: /\n',
        '_headers': b'/*\n  X-Robots-Tag: noindex, nofollow\n  X-Content-Type-Options: nosniff\n  Referrer-Policy: strict-origin-when-cross-origin\n',
        'gallery.css': GALLERY_CSS.encode(),
    }
    cards = []
    for key, number, title, chinese, description, font, accent in TEMPLATES:
        data = example.model_dump(mode='json')
        data.update(template=key, font=font, accent=accent, theme='auto',
                    site_url='', languages=['en', 'zh'], default_language='en', example=True)
        site = Site.model_validate(data)
        for name, content in public_files(site, {}).items():
            if name.endswith('.html'):
                content = content.decode().replace('</head>', NOINDEX + '</head>', 1).encode()
            output[f'{key}/{name}'] = content
        cards.append(f'''<article class="template-card" id="{key}">
          <a class="thumbnail {key}" href="{key}/index.html" aria-label="Explore {title}">
            <div class="paper" aria-hidden="true"><div class="mock-nav"><b>A.</b><i></i><i></i><i></i></div>
              <div class="mock-body"><div class="mock-person"><span class="portrait">AM</span><b>Alex Morgan</b><i></i><i></i></div>
              <div class="mock-content"><b>About</b><i></i><i></i><i class="short"></i><b>Selected work</b>
                <div class="mock-grid"><div><em></em><i></i><i class="short"></i></div><div><em></em><i></i><i class="short"></i></div></div>
              </div></div></div><span class="open-label">Explore template ↗</span></a>
          <div class="card-copy"><div class="card-heading"><span>{number}</span><h2>{title}</h2></div>
            <p class="chinese" lang="zh-CN">{chinese}</p><p>{description}</p>
            <div class="card-links"><a href="{key}/index.html">English <span aria-hidden="true">↗</span></a><a href="{key}/zh/index.html" lang="zh-CN">中文 <span aria-hidden="true">↗</span></a></div>
          </div></article>''')
    output['index.html'] = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Academic Homepage Builder · Template gallery</title>{NOINDEX}
<meta name="description" content="Explore three academic homepage layouts using a fictional researcher profile.">
<link rel="icon" href="academic/assets/favicon.svg" type="image/svg+xml"><link rel="stylesheet" href="gallery.css"></head>
<body><header class="topbar"><a class="brand" href="index.html"><span class="brand-icon" aria-hidden="true">A</span>Academic Homepage Builder</a><span class="edition">Template gallery · v1</span></header>
<main><section class="intro"><p class="eyebrow">YOUR RESEARCH, YOUR SPACE</p><h1>A thoughtful home<br>for your academic work.</h1>
<p class="lede">Three layouts. One shared profile. Explore the same fictional researcher’s homepage in English and Chinese.</p>
<p class="intro-zh" lang="zh-CN">三种布局，同一份资料。为你的研究、项目与故事，找到合适的呈现方式。</p>
<div class="details"><span>Local fonts &amp; assets</span><span>Responsive layouts</span><span>Light &amp; dark themes</span></div>
<a class="get-builder" href="https://github.com/masktrump19-sudo/academic-homepage-builder" target="_blank" rel="noopener noreferrer">Get the local builder <span aria-hidden="true">↗</span></a></section>
<section class="gallery" aria-label="Choose a template">{''.join(cards)}</section>
<aside class="demo-note"><span class="note-dot" aria-hidden="true"></span><div><strong>Fictional content, real templates.</strong><p>All names, institutions and achievements shown here are illustrative. No user resumes or personal attachments are used in this gallery.</p><p lang="zh-CN">所有人物、机构与成果均为虚构演示，不包含使用者的简历或个人附件。</p></div></aside>
</main><footer><span>Academic Homepage Builder</span><span>Designed to keep the work yours.</span></footer></body></html>'''.encode()
    return output


def build_demo(output: Path) -> Path:
    """Atomically replace only an empty directory or our previous gallery."""
    output = output.absolute()
    if output.is_symlink():
        raise ValueError('The demo output must not be a symbolic link.')
    output = output.resolve()
    if output == Path(output.anchor) or output == Path.home().resolve() or ROOT.is_relative_to(output):
        raise ValueError('Choose a dedicated output directory outside the project source.')
    if output.exists():
        if not output.is_dir():
            raise ValueError('The demo output must be a directory.')
        marker = output / MARKER
        if any(output.iterdir()) and (marker.is_symlink() or not marker.is_file() or marker.read_bytes() != MARKER_TEXT):
            raise ValueError('The output contains unrelated files; choose an empty folder or a previous demo build.')
    files = gallery_files()
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix='.ahb-gallery-stage-', dir=output.parent) as temporary:
        stage = Path(temporary) / 'gallery'
        stage.mkdir()
        for name, content in files.items():
            path = stage / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        check_directory(stage)
        backup = output.parent / ('.ahb-gallery-old-' + uuid.uuid4().hex)
        if output.exists():
            output.rename(backup)
        try:
            stage.rename(output)
        except Exception:
            if backup.exists():
                backup.rename(output)
            raise
        if backup.exists():
            if backup.is_symlink() or backup.resolve().parent != output.parent:
                raise ValueError('Unexpected backup directory.')
            shutil.rmtree(backup)
    return output


GALLERY_CSS = '''
.get-builder{display:inline-flex;align-items:center;gap:24px;padding:13px 19px;margin-top:27px;border:1px solid #315e59;border-radius:8px;background:#315e59;color:white;font-size:12px;font-weight:600;box-shadow:0 6px 13px -8px #315e5966}.get-builder:hover{background:#254d48}.get-builder span{font-size:15px;color:#cbded2}
:root{font-family:Inter,-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;color:#24373b;background:#f7f8f5;font-synthesis:none}*{box-sizing:border-box}body{margin:0}a{color:inherit;text-decoration:none}a:focus-visible{outline:3px solid #4d8b82;outline-offset:5px}p,h1,h2{margin:0}.topbar,main,footer{max-width:1240px;margin:auto}.topbar{padding:30px 36px;display:flex;justify-content:space-between;align-items:center;gap:20px;border-bottom:1px solid #dde4df}.brand{display:flex;gap:12px;align-items:center;font-size:15px;font-weight:650;letter-spacing:-.3px}.brand-icon{background:#315e59;color:white;font:700 20px Georgia,serif;padding:8px 12px;border-radius:11px}.edition{font-size:11px;color:#7b8885;letter-spacing:.03em}main{padding:0 36px}.intro{padding:68px 0 48px;max-width:760px}.eyebrow{color:#557b72;font-size:10px;letter-spacing:.17em;font-weight:700;margin-bottom:19px}h1{font-family:Georgia,"Times New Roman",serif;font-weight:500;font-size:clamp(37px,5vw,64px);line-height:1.1;letter-spacing:-2px;color:#293d3a}.lede{font-size:16px;line-height:1.8;max-width:600px;margin-top:24px;color:#62716e}.intro-zh{font-size:13px;line-height:1.8;color:#7a8782;margin-top:10px}.details{display:flex;flex-wrap:wrap;gap:10px 23px;margin-top:24px;color:#65796f;font-size:10px}.details span:before{content:'✓';color:#47836f;margin-right:7px}.gallery{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:24px}.template-card{min-width:0;background:#fff;border:1px solid #dde5df;border-radius:15px;overflow:hidden;box-shadow:0 2px 4px #16322904,0 16px 32px -26px #1a433955}.thumbnail{display:block;background:#e8eee9;padding:32px 25px 40px;position:relative;height:275px;overflow:hidden}.paper{background:#fff;box-shadow:0 12px 25px -10px #294e3d33;border-radius:4px;padding:17px;transform:rotate(-2deg);height:215px;transition:transform .25s}.thumbnail:hover .paper{transform:rotate(0deg) translateY(-4px)}.mock-nav{display:flex;gap:13px;align-items:center;border-bottom:1px solid #e6ece8;padding-bottom:10px}.mock-nav>b{font:700 9px Georgia,serif;margin-right:auto}.paper i{display:block;border-radius:2px;height:3px;background:#e4e9e6;margin:5px 0;width:100%}.mock-nav i{width:20px;height:2px;background:#b6c8c0}.mock-body{display:grid;grid-template-columns:58px minmax(0,1fr);gap:17px;margin-top:20px}.mock-person .portrait{display:grid;place-items:center;width:31px;height:31px;border-radius:8px;background:#eef2ee;color:#5b7c70;font:700 12px Georgia,serif;margin-bottom:10px}.mock-person b{font:700 7px Georgia,serif}.mock-person i{height:2px;width:90%}.mock-content>b{font:700 8px Georgia,serif;display:block;margin-bottom:8px}.mock-content>b:not(:first-child){margin-top:17px}.paper .short{width:70%}.mock-grid{display:grid;grid-template-columns:1fr 1fr;gap:7px}.mock-grid>div{border:1px solid #e3eae4;border-radius:3px;padding:8px}.mock-grid em{display:block;height:20px;background:#edf2ed;border-radius:2px;margin-bottom:6px}.open-label{position:absolute;bottom:13px;left:25px;font-size:10px;font-weight:600;color:#4f7163}.modern{background:#eeeae3}.modern .paper{transform:rotate(2deg)}.modern .mock-body{display:block;margin-top:15px}.modern .mock-person{display:flex;align-items:center;gap:12px;flex-direction:row-reverse;justify-content:space-between;border-bottom:1px solid #e8e7e1;padding-bottom:12px}.modern .mock-person .portrait{border-radius:50%;margin:0;background:#f0ede5}.modern .mock-person b{font:700 14px sans-serif}.modern .mock-person i{display:none}.modern .mock-content{margin-top:13px}.modern .mock-content>b:not(:first-child){margin-top:12px}.modern .mock-grid em{display:none}.modern .open-label{color:#857051}.visual{background:#ede9f0}.visual .paper{transform:rotate(-1deg)}.visual .mock-body{display:block;margin-top:8px}.visual .mock-person{text-align:center}.visual .mock-person .portrait{margin:0 auto 5px;width:22px;height:22px;font-size:8px;background:#efedf4}.visual .mock-person b{font-size:11px}.visual .mock-person i{display:none}.visual .mock-content{margin-top:10px}.visual .mock-content>i,.visual .mock-content>b:first-child{display:none}.visual .mock-content>b:not(:first-child){margin-top:8px}.visual .mock-grid em{height:40px;background:linear-gradient(130deg,#ddd9e7,#eeeaf5);border-radius:4px}.visual .open-label{color:#7b678f}.card-copy{padding:23px 24px 24px}.card-heading{display:flex;align-items:center;gap:9px}.card-heading>span{font-size:10px;color:#98a89f;font-weight:600}.card-heading h2{font-family:Georgia,serif;font-weight:500;font-size:23px;letter-spacing:-.5px}.card-copy>p{font-size:12px;line-height:1.7;color:#77847c;margin-top:10px}.card-copy>.chinese{font-size:11px;color:#89968d;margin-top:5px}.card-links{display:flex;gap:24px;border-top:1px solid #e7ece7;padding-top:15px;margin-top:20px;font-size:11px;font-weight:600}.card-links a{display:flex;gap:18px}.card-links a:hover{text-decoration:underline;text-underline-offset:4px}.card-links span{color:#91a49a}.demo-note{margin:40px 0 55px;padding:22px 24px;background:#edf2ec;border:1px solid #e2e9e0;border-radius:11px;display:flex;gap:14px}.note-dot{flex:0 0 7px;height:7px;border-radius:50%;background:#8aa186;margin-top:5px}.demo-note strong{font-size:11px;font-weight:600}.demo-note p{font-size:11px;line-height:1.8;color:#788875;margin-top:5px}footer{padding:23px 36px 32px;border-top:1px solid #dde4df;display:flex;justify-content:space-between;gap:15px;font-size:10px;color:#8a968c}@media(max-width:1000px){.gallery{gap:16px}.thumbnail{padding:28px 17px 40px;height:250px}.paper{padding:12px;height:195px}.mock-body{gap:10px;grid-template-columns:45px minmax(0,1fr)}.card-copy{padding:20px 17px}.card-heading h2{font-size:20px}.mock-grid>div{padding:5px}}@media(max-width:760px){.topbar{padding:22px}.edition{display:none}main{padding:0 22px}.intro{padding:45px 0 35px}h1{letter-spacing:-1.2px}.lede{font-size:14px}.gallery{grid-template-columns:1fr;gap:25px;max-width:480px;margin:auto}.thumbnail{height:260px;padding:28px 45px 40px}.paper{height:215px;padding:18px}.card-copy{padding:22px 25px}.card-heading h2{font-size:24px}.mock-body{gap:20px;grid-template-columns:60px minmax(0,1fr)}.card-copy>p{font-size:13px}.demo-note{margin-bottom:35px}footer{padding:23px 22px;flex-direction:column}}@media(prefers-reduced-motion:reduce){*{transition:none!important}}
'''


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'demo-dist', help='Dedicated gallery output directory (default: demo-dist).')
    args = parser.parse_args()
    output = build_demo(args.output)
    print(f'Fictional template gallery built: {output}')


if __name__ == '__main__':
    main()
