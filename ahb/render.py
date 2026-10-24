"""Pure, escaped static rendering shared by previews and exported websites."""
from __future__ import annotations

from datetime import date
from html import escape
import json
from pathlib import Path
import xml.etree.ElementTree as ET

LABELS = {
    'en': {'about': 'About', 'news': 'News', 'publications': 'Publications', 'projects': 'Projects',
           'internships': 'Experience', 'education': 'Education', 'honors': 'Honors', 'contact': 'Contact',
           'email': 'Email', 'cv': 'Curriculum vitae', 'interests': 'Research interests', 'hobbies': 'Beyond research',
           'review': 'Needs review', 'example': 'Fictional demo · All people and achievements on this page are illustrative.',
           'theme': 'Change color theme', 'skip': 'Skip to content', 'name': 'Your name', 'visit': 'View project',
           'updated': 'Personal academic website', 'legend': '* Equal contribution; † Corresponding author.'},
    'zh': {'about': '关于我', 'news': '动态', 'publications': '论文', 'projects': '项目',
           'internships': '经历', 'education': '教育', 'honors': '荣誉', 'contact': '联系',
           'email': '邮箱', 'cv': '个人简历', 'interests': '研究方向', 'hobbies': '研究之外',
           'review': '待核对', 'example': '虚构演示 · 本页人物与成果仅用于展示排版。',
           'theme': '切换明暗主题', 'skip': '跳至正文', 'name': '你的姓名', 'visit': '查看项目',
           'updated': '个人学术主页', 'legend': '* 同等贡献；† 通讯作者。'},
}
ORDER = ('news', 'publications', 'projects', 'internships', 'education', 'honors')
ICON_PATHS = {
    'about': '<circle cx="12" cy="8" r="3"/><path d="M5 21v-3a7 7 0 0 1 14 0v3"/>',
    'news': '<path d="M4 6h12v14H4zM16 9h4v10a1 1 0 0 1-1 1h-3M7 10h6M7 14h6M7 17h4"/>',
    'publications': '<path d="M4 4h7a3 3 0 0 1 3 3v14a4 4 0 0 0-4-2H4zM14 7a3 3 0 0 1 3-3h3v15h-3a3 3 0 0 0-3 2"/>',
    'projects': '<path d="m8 5-6 7 6 7M16 5l6 7-6 7M14 3l-4 18"/>',
    'internships': '<rect x="3" y="7" width="18" height="14" rx="3"/><path d="M8 7V3h8v4M3 12a19 19 0 0 0 18 0M10 13h4"/>',
    'education': '<path d="m2 9 10-6 10 6-10 6zM6 12v6c4 3 8 3 12 0v-6M22 9v8"/>',
    'honors': '<path d="M8 3h8v7a4 4 0 0 1-8 0zM8 5H3v3a5 5 0 0 0 5 5M16 5h5v3a5 5 0 0 1-5 5M12 14v5M7 21h10"/>',
    'contact': '<rect x="2" y="5" width="20" height="14" rx="3"/><path d="m3 6 9 7 9-7"/>',
}


def text(value, lang):
    return value.get(lang, '') if isinstance(value, dict) else ''


def esc(value):
    return escape(str(value or ''), quote=True)


def paragraphs(value):
    return ''.join('<p>' + esc(p).replace('\n', '<br>') + '</p>' for p in value.split('\n\n') if p.strip())


def icon(key):
    return f'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{ICON_PATHS.get(key, ICON_PATHS["about"])}</svg>'


def link(url, label, cls=''):
    return f'<a class="{cls}" href="{esc(url)}" target="_blank" rel="noopener noreferrer">{label}<span class="external" aria-hidden="true">↗</span></a>'


def page_paths(data):
    return {lang: 'index.html' if lang == data['default_language'] else f'{lang}/index.html' for lang in data['languages']}


def render_site(site) -> dict[str, bytes]:
    from .models import Site
    data = (site if isinstance(site, Site) else Site.model_validate(site)).model_dump()
    result = {}
    assets = Path(__file__).with_name('site_assets')
    for filename in ('site.css', 'site.js', 'favicon.svg'):
        result['assets/' + filename] = (assets / filename).read_bytes()
    paths = page_paths(data)
    for lang, path in paths.items():
        result[path] = render_page(data, lang, paths).encode('utf-8')
    origin = data.get('site_url', '').rstrip('/')
    if origin:
        namespace = 'http://www.sitemaps.org/schemas/sitemap/0.9'
        ET.register_namespace('', namespace)
        sitemap = ET.Element('{' + namespace + '}urlset')
        for lang in data['languages']:
            node = ET.SubElement(sitemap, '{' + namespace + '}url')
            ET.SubElement(node, '{' + namespace + '}loc').text = origin + ('/' if lang == data['default_language'] else f'/{lang}/')
        result['sitemap.xml'] = ET.tostring(sitemap, encoding='utf-8', xml_declaration=True)
        result['robots.txt'] = f'User-agent: *\nAllow: /\n\nSitemap: {origin}/sitemap.xml\n'.encode()
    return result


def render_page(data, lang, paths):
    labels = LABELS[lang]
    prefix = '' if paths[lang] == 'index.html' else '../'
    p = data['profile']
    name = text(p['name'], lang) or labels['name']
    hidden = set(data['hidden_sections'])
    active = {key: [entry for entry in data['sections'].get(key, []) if entry.get('enabled', True) and any(text(entry.get(f, {}), lang).strip() for f in ('title', 'subtitle', 'description', 'status'))] for key in ORDER if key not in hidden}
    active = {key: items for key, items in active.items() if items}
    bio, interests = text(p['bio'], lang), text(p['interests'], lang)
    contact, hobbies = text(data['contact'], lang), text(data['hobbies'], lang)
    sections = []
    nav_keys = []

    def section(key, body):
        nav_keys.append(key)
        return f'<section id="{key}" class="section section-{key}" aria-labelledby="{key}-title"><header class="section-title"><span class="section-icon">{icon(key)}</span><h2 id="{key}-title">{labels[key]}</h2></header>{body}</section>'

    if 'about' not in hidden and (bio or interests):
        interest_html = f'<div class="research-interests"><span>{labels["interests"]}</span><p>{esc(interests).replace(chr(10), " · ")}</p></div>' if interests else ''
        sections.append(section('about', f'<div class="bio">{paragraphs(bio)}</div>{interest_html}'))
    for key, items in active.items():
        cards = []
        for entry in items:
            title = text(entry['title'], lang)
            title_html = link(entry['url'], esc(title)) if entry['url'] else esc(title)
            subtitle, desc, status = (text(entry[field], lang) for field in ('subtitle', 'description', 'status'))
            image = f'<div class="entry-image"><img src="{prefix}{esc(entry["image"])}" alt="{esc(title)}" loading="lazy"></div>' if entry['image'] else ''
            review = f'<span class="review-badge">{labels["review"]}</span>' if not entry['confirmed'] else ''
            metadata = ''.join(f'<p class="{cls}">{esc(value)}</p>' for cls, value in [('entry-subtitle', subtitle), ('entry-authors', entry['authors']), ('entry-status', status)] if value)
            date_html = f'<span class="entry-date">{esc(entry["date"])}</span>' if entry['date'] else ''
            links_html = '<div class="entry-links">' + ''.join(link(item['url'], esc(item['label']), 'resource-link') for item in entry['links']) + '</div>' if entry['links'] else ''
            description_html = f'<div class="entry-description">{paragraphs(desc)}</div>' if desc else ''
            cards.append(f'<article class="entry">{image}<div class="entry-content"><div class="entry-top">{date_html}{review}</div><h3>{title_html}</h3>{metadata}{description_html}{links_html}</div></article>')
        legend = f'<p class="publication-legend">{labels["legend"]}</p>' if key == 'publications' else ''
        sections.append(section(key, legend + '<div class="entries">' + ''.join(cards) + '</div>'))
    if 'contact' not in hidden and (contact or p['email'] or hobbies):
        email = f'<a class="contact-email" href="mailto:{esc(p["email"])}">{icon("contact")}{esc(p["email"])}</a>' if p['email'] else ''
        interests_html = f'<div class="hobbies"><span>{labels["hobbies"]}</span><p>{esc(hobbies).replace(chr(10), " · ")}</p></div>' if hobbies else ''
        sections.append(section('contact', paragraphs(contact) + email + interests_html))

    avatar = f'<img class="portrait" src="{prefix}{esc(p["portrait"])}" alt="{esc(name)}">' if p['portrait'] else f'<div class="portrait monogram" aria-hidden="true">{esc("".join(word[0] for word in name.split()[:2]).upper()[:2])}</div>'
    social = ''.join('<li>' + link(item['url'], esc(item['label'])) + '</li>' for item in p['links'])
    if p['email']:
        social = f'<li><a href="mailto:{esc(p["email"])}">{labels["email"]}<span aria-hidden="true">↗</span></a></li>' + social
    if p['cv']:
        social += '<li>' + link(prefix + p['cv'], labels['cv']) + '</li>'
    headline = f'<p class="headline">{esc(text(p["headline"],lang))}</p>' if text(p['headline'],lang) else ''
    affiliation = f'<p class="affiliation">{esc(text(p["affiliation"],lang))}</p>' if text(p['affiliation'],lang) else ''
    hero = f'<aside class="hero">{avatar}<div class="identity"><h1>{esc(name)}</h1>{headline}{affiliation}<ul class="profile-links">{social}</ul></div></aside>'
    nav = ''.join(f'<a href="#{key}">{labels[key]}</a>' for key in nav_keys)
    switches = ''.join(f'<a class="language-switch" href="{prefix}{path}" lang="{other}" hreflang="{other}" aria-label="{"Switch to English" if other == "en" else "切换至中文"}">{"EN" if other == "en" else "中文"}</a>' for other,path in paths.items() if other != lang)
    example = f'<div class="demo-banner" role="note">{labels["example"]}</div>' if data['example'] else ''
    title = name + ' · ' + labels['updated']
    description = ' '.join((text(p['headline'],lang), text(p['affiliation'],lang), interests)).strip()[:260]
    seo = ''
    origin = data.get('site_url', '').rstrip('/')
    if origin:
        urls = {key: origin + ('/' if key == data['default_language'] else f'/{key}/') for key in paths}
        alternates = ''.join(f'<link rel="alternate" hreflang="{"zh-CN" if key == "zh" else key}" href="{esc(url)}">' for key,url in urls.items())
        person = {'@type':'Person', '@id':origin+'/#person', 'name':name, 'url':origin+'/', 'description':description}
        other_names = [value for key,value in p['name'].items() if key != lang and key in data['languages'] and value]
        if other_names: person['alternateName'] = other_names
        if p['links']: person['sameAs'] = [item['url'] for item in p['links']]
        # A supplied avatar may still be a placeholder. Never claim it is a real person's image.
        structured = json.dumps({'@context':'https://schema.org','@type':'ProfilePage','url':urls[lang],'mainEntity':person},ensure_ascii=False).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
        seo = f'<link rel="canonical" href="{esc(urls[lang])}">{alternates}<link rel="alternate" hreflang="x-default" href="{esc(urls[data["default_language"]])}"><script type="application/ld+json">{structured}</script>'
    html = f'''<!doctype html>
<html lang="{'zh-CN' if lang=='zh' else 'en'}" data-theme="{data['theme']}" data-template="{data['template']}" data-font="{data['font']}">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="light dark"><meta name="description" content="{esc(description)}"><title>{esc(title)}</title>{seo}<link rel="icon" href="{prefix}assets/favicon.svg" type="image/svg+xml"><link rel="stylesheet" href="{prefix}assets/site.css"><style>:root{{--accent:{data['accent']}}}</style><script src="{prefix}assets/site.js" defer></script></head>
<body><a class="skip-link" href="#main">{labels['skip']}</a>{example}<header class="site-header"><div class="header-inner"><a class="wordmark" href="#">{esc(name)}</a><nav aria-label="{'Main navigation' if lang=='en' else '主导航'}">{nav}</nav><div class="header-tools">{switches}<button type="button" class="theme-button" aria-label="{labels['theme']}" title="{labels['theme']}"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" aria-hidden="true"><path d="M20 14A8 8 0 0 1 10 4a8 8 0 1 0 10 10Z"/></svg></button></div></div></header><div class="page">{hero}<main id="main">{''.join(sections)}</main></div><footer class="site-footer"><span>© {date.today().year} {esc(name)}</span><span>{labels['updated']}</span></footer></body></html>'''
    return html
