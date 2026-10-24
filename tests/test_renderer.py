from html.parser import HTMLParser
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest
from pydantic import ValidationError

from ahb.models import Site, Entry, Link
from ahb.render import render_site


def basic():
    site = Site()
    site.profile.name = {'en': 'Example Researcher', 'zh': '示例研究者'}
    site.profile.bio = {'en': 'Research and collaboration.', 'zh': '研究与合作。'}
    return site


class Document(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []
        self.anchors = []
        self.references = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if 'id' in attrs:
            self.ids.append(attrs['id'])
        for key in ('href', 'src'):
            if key in attrs:
                self.references.append(attrs[key])
                if attrs[key].startswith('#') and len(attrs[key]) > 1:
                    self.anchors.append(attrs[key][1:])


@pytest.mark.parametrize('template', ['academic', 'modern', 'visual'])
@pytest.mark.parametrize('languages,default', [(['en'], 'en'), (['zh'], 'zh'), (['en', 'zh'], 'en'), (['en', 'zh'], 'zh')])
def test_templates_languages_and_resources(template, languages, default):
    site = basic()
    # Assign both language properties as one validated model operation.
    site = Site.model_validate({**site.model_dump(), 'template': template, 'languages': languages, 'default_language': default})
    files = render_site(site)
    assert 'index.html' in files
    assert len([key for key in files if key.endswith('.html')]) == len(languages)
    for path, raw in files.items():
        if not path.endswith('.html'):
            continue
        html = raw.decode()
        assert f'data-template="{template}"' in html
        doc = Document()
        doc.feed(html)
        assert len(doc.ids) == len(set(doc.ids))
        assert set(doc.anchors).issubset(set(doc.ids))
        for ref in doc.references:
            if ref.startswith('#') or ':' in ref:
                continue
            base = Path(path).parent
            # normpath avoids relying on actual filesystem paths for virtual output.
            import posixpath
            target = posixpath.normpath((base / ref).as_posix())
            assert target in files


def test_minimal_no_empty_sections_or_contact():
    site = Site()
    site.profile.name = {'en': 'Example Researcher'}
    html = render_site(site)['index.html'].decode()
    assert '<h1>Example Researcher</h1>' in html
    for section in ('news', 'publications', 'projects', 'internships', 'education', 'honors', 'contact'):
        assert f'id="{section}"' not in html
    assert 'mailto:' not in html


def test_escaped_content_cannot_execute_in_body_or_jsonld():
    site = basic()
    site.profile.name = {'en': '<img src=x onerror=alert(1)>'}
    site.profile.bio = {'en': '</script><script>alert("x")</script>'}
    site.site_url = 'https://example.org/'
    html = render_site(site)['index.html'].decode()
    assert '<img src=x' not in html
    assert '<script>alert' not in html
    assert '&lt;script&gt;' in html
    structured = html.split('<script type="application/ld+json">')[1].split('</script>')[0]
    assert '<' not in structured
    assert json.loads(structured)['mainEntity']['name'].startswith('<img')


def test_disabled_entries_and_hidden_sections_are_absent():
    site = basic()
    site.sections['projects'] = [Entry(title={'en': 'Visible'}, confirmed=True), Entry(title={'en': 'Hidden entry'}, enabled=False)]
    site.sections['education'] = [Entry(title={'en': 'Hidden education'}, confirmed=True)]
    site.hidden_sections = ['education']
    html = render_site(site)['index.html'].decode()
    assert 'Visible' in html
    assert 'Hidden entry' not in html
    assert 'Hidden education' not in html
    assert 'href="#education"' not in html


def test_no_translation_fallback_or_inactive_alternate_name():
    site = basic()
    site.site_url = 'https://example.org/'
    site.profile.bio = {'zh': '这段只有中文'}
    html = render_site(site)['index.html'].decode()
    assert '这段只有中文' not in html
    assert '示例研究者' not in html


def test_seo_only_after_real_origin_is_supplied():
    site = basic()
    files = render_site(site)
    assert 'sitemap.xml' not in files
    assert 'rel="canonical"' not in files['index.html'].decode()
    site.languages = ['en', 'zh']
    site.site_url = 'https://example.org/'
    files = render_site(site)
    locations = [node.text for node in ET.fromstring(files['sitemap.xml']).iter() if node.tag.endswith('loc')]
    assert locations == ['https://example.org/', 'https://example.org/zh/']
    assert b'Sitemap: https://example.org/sitemap.xml' in files['robots.txt']
    assert 'href="https://example.org/zh/"' in files['zh/index.html'].decode()


def test_publication_metadata_multiple_entries_and_attachments():
    site = basic()
    site.sections['publications'] = [Entry(title={'en': 'Sample study'}, authors='A. Example, B. Example', status={'en': 'Under review'}, image='assets/uploads/figure.png', links=[Link(label='Code', url='https://example.org/code')], confirmed=True)]
    site.sections['education'] = [Entry(title={'en': 'School A'}, confirmed=True), Entry(title={'en': 'School B'}, confirmed=True)]
    html = render_site(site)['index.html'].decode()
    assert 'Under review' in html
    assert 'Equal contribution' in html
    assert 'School A' in html and 'School B' in html
    assert 'src="assets/uploads/figure.png"' in html
    assert 'href="https://example.org/code"' in html
    assert 'Needs review' not in html


def test_fictional_demo_and_unconfirmed_badge_are_visible():
    site = basic()
    site.example = True
    site.sections['projects'] = [Entry(title={'en': 'Draft example'})]
    html = render_site(site)['index.html'].decode()
    assert 'Fictional demo' in html
    assert 'Needs review' in html


def test_dangerous_link_or_remote_image_rejected_before_preview():
    site = basic().model_dump()
    site['profile']['links'] = [{'label': 'unsafe', 'url': 'javascript:alert(1)'}]
    with pytest.raises(ValidationError):
        render_site(site)
    site['profile']['links'] = []
    site['profile']['portrait'] = 'https://tracking.example.org/image.png'
    with pytest.raises(ValidationError):
        render_site(site)
