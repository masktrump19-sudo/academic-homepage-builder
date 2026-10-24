"""Conservative, offline resume text extraction.

Extraction is not a claim of factual correctness. Imported entries remain
unconfirmed and private fields such as postal addresses and ID numbers are not
mapped into the public model.
"""
from __future__ import annotations

from io import BytesIO
import re
from pathlib import PurePath
import zipfile

from .models import Entry, Link, Site, blank_site

MAX_FILE_BYTES = 20 * 1024 * 1024
MAX_TEXT_CHARS = 120000
MAX_PAGES = 60
MAX_DOCX_EXPANDED = 50 * 1024 * 1024


class ResumeError(ValueError):
    """An actionable input problem suitable for displaying in the local UI."""


HEADINGS = {
    "education": ("education", "educational background", "academic background", "教育经历", "教育背景", "学历", "教育"),
    "internships": ("experience", "work experience", "research experience", "internships", "internship", "professional experience", "工作经历", "实习经历", "科研经历", "研究经历"),
    "projects": ("projects", "selected projects", "research projects", "open-source projects", "项目经历", "项目经验", "科研项目", "开源项目", "项目"),
    "publications": ("publications", "selected publications", "papers", "论文", "发表论文", "学术论文", "研究成果"),
    "honors": ("honors", "awards", "honors and awards", "awards and honors", "荣誉", "获奖情况", "获奖经历", "奖项", "奖励荣誉"),
    "bio": ("about", "about me", "summary", "profile", "personal profile", "个人简介", "简介", "自我介绍"),
    "interests": ("research interests", "interests", "research areas", "研究兴趣", "研究方向"),
}
_HEADING_MAP = {name: section for section, names in HEADINGS.items() for name in names}
_UNMAPPED = {"skills", "technical skills", "languages", "references", "contact", "personal information", "技能", "专业技能", "语言能力", "联系方式", "个人信息", "基本信息"}
_DATE = re.compile(r"(?:19|20)\d{2}(?:[./年-]\d{1,2}(?:月)?)?(?:\s*(?:–|—|-|至|to)\s*(?:(?:19|20)\d{2}(?:[./年-]\d{1,2}(?:月)?)?|present|current|至今|现在))?", re.I)
_EMAIL = re.compile(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_URL = re.compile(r"https://[^\s<>\"'\u3000\uff0c\u3002]+")


def _language(text: str) -> str:
    chinese = len(re.findall(r"[\u3400-\u9fff]", text))
    return "zh" if chinese > 0 and chinese * 3 > len(text.strip()) else "en"


def _heading(line: str) -> str | None:
    cleaned = re.sub(r"^[#\s\d.、)]+", "", line).strip().rstrip(":：").strip().lower()
    return _HEADING_MAP.get(cleaned)


def _candidate_name(lines: list[str]) -> tuple[str, str] | None:
    excluded = {"curriculum vitae", "resume", "résumé", "cv", "简历", "个人简历", "undergraduate student", "graduate student", "research intern", "research assistant", "software engineer", "data scientist"}
    for line in lines[:8]:
        match = re.match(r"^(?:name|姓名)\s*[:：]\s*(.+)$", line, re.I)
        candidate = (match.group(1) if match else line).strip()
        if candidate.lower() in excluded or _heading(candidate) or len(candidate) > 60:
            continue
        if re.search(r"university|college|institute|school|大学|学院|研究所", candidate, re.I):
            continue
        if re.fullmatch(r"[\u3400-\u9fff]{2,5}", candidate):
            return "zh", candidate
        if re.fullmatch(r"[A-Za-zÀ-ž][A-Za-zÀ-ž'’-]*(?:\s+[A-Za-zÀ-ž][A-Za-zÀ-ž.'’-]*){1,4}", candidate):
            return "en", candidate
    return None


def parse_text(text: str) -> dict:
    if not isinstance(text, str):
        raise ResumeError("Paste plain text to import a resume.")
    if len(text) > MAX_TEXT_CHARS:
        raise ResumeError("Resume text is too long (maximum 120,000 characters). Import a shorter document.")
    text = text.replace("\r\n", "\n").replace("\r", "\n").lstrip("\ufeff")
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    if not text.strip():
        raise ResumeError("No readable text was found. For a scanned resume, paste its text or use a text-based PDF.")
    lang = _language(text)
    site = Site(languages=[lang], default_language=lang)
    warnings = ["Imported information is tentative. Review every field and each entry before publishing.",
                "Names, dates, author order, degrees, and publication status are not verified. Nothing is translated automatically."]
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    name = _candidate_name(lines)
    if name:
        site.profile.name[name[0]] = name[1]
    else:
        warnings.append("The name could not be identified reliably. Enter it manually.")
    emails = list(dict.fromkeys(_EMAIL.findall(text)))
    if emails:
        site.profile.email = emails[0]
        warnings.append("An email candidate was found. Confirm that it is suitable for public display.")
        if len(emails) > 1:
            warnings.append("Multiple email addresses were found; only the first is proposed.")
    for url in dict.fromkeys(_URL.findall(text)):
        url = url.rstrip(".,;:)")
        if re.match(r"https://(?:www\.)?github\.com/[^/?#]+/?$", url, re.I):
            label = "GitHub"
        elif re.match(r"https://(?:www\.)?linkedin\.com/in/[^/?#]+/?$", url, re.I):
            label = "LinkedIn"
        elif re.match(r"https://scholar\.google\.com/citations\?", url, re.I):
            label = "Google Scholar"
        else:
            continue
        try:
            site.profile.links.append(Link(label=label, url=url))
        except ValueError:
            pass
        if len(site.profile.links) == 10:
            break

    # Headings are the only structural signal used. A block is proposed as one
    # editable entry; ambiguous grouping stays visible instead of inventing facts.
    blocks: list[tuple[str, list[str]]] = []
    section = None
    body: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        heading = _heading(stripped) if stripped else None
        if heading or stripped.lower().rstrip(":：") in _UNMAPPED:
            if section and body:
                blocks.append((section, body))
            section, body = heading, []
        elif section:
            body.append(stripped)
    if section and body:
        blocks.append((section, body))
    for section, block in blocks:
        content = "\n".join(block).strip()
        if not content:
            continue
        if section in ("bio", "interests"):
            limit = 1000 if section == "interests" else 12000
            getattr(site.profile, section)[lang] = content[:limit]
            if len(content) > limit:
                warnings.append(f"The {section} candidate was shortened to fit the editor. The complete extracted text remains available for review.")
            continue
        groups = [g.strip() for g in re.split(r"\n\s*\n", content) if g.strip()]
        for group in groups[:100 - len(site.sections[section])]:
            pieces = group.splitlines()
            title = re.sub(r"^[•●\-*]\s*", "", pieces[0]).strip()
            description = "\n".join(pieces[1:])
            entry = Entry(title={lang: title[:2000]}, description={lang: description[:12000]}, confirmed=False)
            if len(title) > 2000 or len(description) > 12000:
                warnings.append("A long entry was shortened to fit the editor. Review the complete extracted text before publishing.")
            date = _DATE.search(group)
            if date:
                entry.date = date.group(0)
            site.sections[section].append(entry)
    if not blocks:
        warnings.append("No recognized section headings were found. Use the extracted text to fill the form, or choose optional AI assistance.")
    else:
        warnings.append("Section blocks may combine multiple items. Split or edit entries as needed; publication status and authors are deliberately left blank.")
    return {"text": text, "site": site.model_dump(), "warnings": warnings}


def _pdf_text(payload: bytes) -> str:
    if b"%PDF-" not in payload[:1024]:
        raise ResumeError("This file is not a valid PDF. Export it again or paste its text.")
    try:
        from pypdf import PdfReader
        reader = PdfReader(BytesIO(payload), strict=True)
        if reader.is_encrypted:
            raise ResumeError("This PDF is encrypted. Export an unlocked copy or paste its text.")
        if len(reader.pages) > MAX_PAGES:
            raise ResumeError("PDF resumes are limited to 60 pages. Import a shorter document.")
        parts, total = [], 0
        for page in reader.pages:
            part = page.extract_text() or ""
            total += len(part)
            if total > MAX_TEXT_CHARS:
                raise ResumeError("Extracted text exceeds 120,000 characters. Import a shorter document.")
            parts.append(part)
        result = "\n\n".join(parts)
        if not result.strip():
            raise ResumeError("This PDF contains no readable text and may be scanned. OCR is not included; paste text or upload a text-based PDF.")
        return result
    except ResumeError:
        raise
    except Exception as exc:
        raise ResumeError("The PDF could not be read. It may be damaged or unsupported; export it again or paste its text.") from exc


def _docx_text(payload: bytes) -> str:
    try:
        with zipfile.ZipFile(BytesIO(payload)) as archive:
            infos = archive.infolist()
            if len(infos) > 2000 or sum(i.file_size for i in infos) > MAX_DOCX_EXPANDED:
                raise ResumeError("This DOCX expands beyond the safe import limit. Export a simpler copy or paste its text.")
            names = {i.filename for i in infos}
            if len(names) != len(infos) or "word/document.xml" not in names or "[Content_Types].xml" not in names:
                raise ResumeError("This file is not a valid DOCX document.")
            for info in infos:
                if info.flag_bits & 1 or ".." in info.filename.split("/") or info.filename.startswith(("/", "\\")):
                    raise ResumeError("This DOCX contains unsafe or encrypted package entries.")
                if info.file_size > 5 * 1024 * 1024 and info.file_size > max(info.compress_size, 1) * 200:
                    raise ResumeError("This DOCX has an unsafe compression ratio. Export a simpler copy.")
                if info.filename.endswith(".xml"):
                    # DTD/entity declarations are not needed for ordinary DOCX.
                    data = archive.read(info)
                    if b"<!DOCTYPE" in data.upper() or b"<!ENTITY" in data.upper():
                        raise ResumeError("This DOCX contains unsupported XML declarations.")
        from docx import Document
        from docx.table import Table
        from docx.text.paragraph import Paragraph
        document = Document(BytesIO(payload))
        output: list[str] = []
        total = 0

        def collect(container, depth=0):
            nonlocal total
            if depth > 8:
                raise ResumeError("This DOCX contains excessively nested tables. Paste its text instead.")
            for item in container.iter_inner_content():
                if isinstance(item, Paragraph):
                    output.append(item.text)
                    total += len(item.text)
                elif isinstance(item, Table):
                    for row in item.rows:
                        seen = set()
                        for cell in row.cells:
                            # Merged cells can be exposed more than once.
                            if id(cell._tc) not in seen:
                                seen.add(id(cell._tc))
                                collect(cell, depth + 1)
                if total > MAX_TEXT_CHARS or len(output) > 10000:
                    raise ResumeError("Extracted text exceeds 120,000 characters. Import a shorter document.")
        collect(document)
        return "\n".join(output)
    except ResumeError:
        raise
    except Exception as exc:
        raise ResumeError("The DOCX could not be read. Export a standard .docx file or paste its text.") from exc


def parse_resume(filename: str, payload: bytes) -> dict:
    if not isinstance(payload, bytes) or not payload:
        raise ResumeError("Choose a nonempty resume file.")
    if len(payload) > MAX_FILE_BYTES:
        raise ResumeError("Resume files must be 20 MB or smaller.")
    suffix = PurePath(filename.replace("\\", "/")).suffix.lower()
    if suffix == ".pdf":
        text = _pdf_text(payload)
    elif suffix == ".docx":
        text = _docx_text(payload)
    elif suffix == ".txt":
        try:
            encoding = "utf-16" if payload.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig"
            text = payload.decode(encoding, errors="strict")
        except UnicodeError as exc:
            raise ResumeError("Save the text file as UTF-8, or paste the text into the editor.") from exc
    else:
        raise ResumeError("Supported resume formats are PDF, DOCX, and UTF-8 TXT.")
    return parse_text(text)
