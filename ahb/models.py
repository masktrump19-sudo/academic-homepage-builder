"""Versioned, plain-text public content shared by the editor and renderer.

There are deliberately no credential, original-resume, or private-address fields.
Validation happens before preview as well as before export.
"""
from __future__ import annotations

import re
from typing import Annotated, Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

Language = Literal["en", "zh"]
Text = Annotated[str, StringConstraints(max_length=12000)]
Localized = dict[Language, Text]
SECTION_KEYS = ("news", "publications", "projects", "internships", "education", "honors")
SectionKey = Literal["news", "publications", "projects", "internships", "education", "honors"]
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_ASSET = re.compile(r"assets/uploads/[A-Za-z0-9][A-Za-z0-9_.-]{0,160}\.(?:png|jpe?g|webp|pdf)\Z")


def localized() -> Localized:
    return {"en": "", "zh": ""}


def safe_url(value: str, *, optional: bool = True) -> str:
    """Accept only ordinary HTTPS links; never turn an input into a fetch."""
    value = value.strip()
    if not value and optional:
        return ""
    if not value or len(value) > 2048 or re.search(r"\s|[\x00-\x1f\x7f\\]", value):
        raise ValueError("Use a valid HTTPS URL without whitespace or backslashes.")
    try:
        parsed = urlsplit(value)
        port = parsed.port
        host = parsed.hostname
    except ValueError as exc:
        raise ValueError("Use a valid HTTPS URL.") from exc
    if parsed.scheme.lower() != "https" or not host or parsed.username is not None or parsed.password is not None:
        raise ValueError("Links must use HTTPS and must not contain login credentials.")
    if not re.fullmatch(r"[A-Za-z0-9.\-:\[\]\u0080-\uffff]+", host) or host.startswith("."):
        raise ValueError("The URL hostname is invalid.")
    if port is not None and not 1 <= port <= 65535:
        raise ValueError("The URL port is invalid.")
    return value


def asset_path(value: str, *, pdf: bool = False) -> str:
    if not value:
        return ""
    if not _ASSET.fullmatch(value) or ".." in value:
        raise ValueError("Select a local uploaded asset; external images and arbitrary paths are not accepted.")
    if pdf != value.lower().endswith(".pdf"):
        raise ValueError("Select a PDF for the public CV, or a PNG/JPEG/WebP for an image.")
    return value


class ContentModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    @model_validator(mode="before")
    @classmethod
    def reject_controls(cls, values):
        def visit(value):
            if isinstance(value, str) and _CONTROL.search(value):
                raise ValueError("Text must not contain control characters.")
            if isinstance(value, dict):
                for key, item in value.items():
                    visit(key)
                    visit(item)
            if isinstance(value, (tuple, list)):
                for item in value:
                    visit(item)
        visit(values)
        return values


class Link(ContentModel):
    label: str = Field(min_length=1, max_length=100)
    url: str = Field(min_length=1, max_length=2048)

    @field_validator("url")
    @classmethod
    def valid_url(cls, value):
        return safe_url(value, optional=False)

    @field_validator("label")
    @classmethod
    def valid_label(cls, value):
        if not value.strip():
            raise ValueError("Link label must not be empty.")
        return value.strip()


class Profile(ContentModel):
    name: Localized = Field(default_factory=localized)
    headline: Localized = Field(default_factory=localized)
    affiliation: Localized = Field(default_factory=localized)
    bio: Localized = Field(default_factory=localized)
    interests: Localized = Field(default_factory=localized)
    email: str = Field(default="", max_length=254)
    portrait: str = Field(default="", max_length=200)
    cv: str = Field(default="", max_length=200)
    links: list[Link] = Field(default_factory=list, max_length=20)

    @field_validator("name", "headline", "affiliation", "interests")
    @classmethod
    def bounded_short_text(cls, value):
        if any(len(text) > 1000 for text in value.values()):
            raise ValueError("Profile labels and interests must be at most 1,000 characters per language.")
        return value

    @field_validator("email")
    @classmethod
    def valid_email(cls, value):
        value = value.strip()
        if value and not re.fullmatch(r"[^\s<>@\x00-\x1f]+@[^\s<>@\x00-\x1f]+\.[^\s<>@\x00-\x1f]+", value):
            raise ValueError("Enter an email address without a display name or headers.")
        return value

    @field_validator("portrait")
    @classmethod
    def valid_portrait(cls, value):
        return asset_path(value)

    @field_validator("cv")
    @classmethod
    def valid_cv(cls, value):
        return asset_path(value, pdf=True)


class Entry(ContentModel):
    title: Localized = Field(default_factory=localized)
    subtitle: Localized = Field(default_factory=localized)
    description: Localized = Field(default_factory=localized)
    status: Localized = Field(default_factory=localized)
    date: str = Field(default="", max_length=160)
    authors: str = Field(default="", max_length=2000)
    url: str = Field(default="", max_length=2048)
    image: str = Field(default="", max_length=200)
    links: list[Link] = Field(default_factory=list, max_length=12)
    confirmed: bool = False
    enabled: bool = True

    @field_validator("title", "subtitle", "status")
    @classmethod
    def bounded_labels(cls, value):
        if any(len(text) > 2000 for text in value.values()):
            raise ValueError("Entry titles and labels must be at most 2,000 characters per language.")
        return value

    @field_validator("url")
    @classmethod
    def valid_url(cls, value):
        return safe_url(value)

    @field_validator("image")
    @classmethod
    def valid_image(cls, value):
        return asset_path(value)


class Site(ContentModel):
    schema_version: Literal[1] = 1
    languages: list[Language] = Field(default_factory=lambda: ["en"], min_length=1, max_length=2)
    default_language: Language = "en"
    template: Literal["academic", "modern", "visual"] = "academic"
    accent: str = Field(default="#426b87", pattern=r"^#[0-9A-Fa-f]{6}$")
    font: Literal["serif", "sans"] = "serif"
    theme: Literal["light", "dark", "auto"] = "auto"
    site_url: str = Field(default="", max_length=2048)
    example: bool = False
    profile: Profile = Field(default_factory=Profile)
    sections: dict[SectionKey, list[Entry]] = Field(default_factory=lambda: {key: [] for key in SECTION_KEYS})
    hidden_sections: list[Literal['about', 'contact', 'news', 'publications', 'projects', 'internships', 'education', 'honors']] = Field(default_factory=list, max_length=8)
    contact: Localized = Field(default_factory=localized)
    hobbies: Localized = Field(default_factory=localized)

    @field_validator("site_url")
    @classmethod
    def valid_origin(cls, value):
        value = safe_url(value)
        if not value:
            return ""
        parsed = urlsplit(value)
        if parsed.path not in ("", "/") or parsed.query or parsed.fragment:
            raise ValueError("Website address must be an HTTPS origin, without a subpath, query, or fragment.")
        return value.rstrip("/") + "/"

    @field_validator("sections")
    @classmethod
    def bounded_sections(cls, value):
        if any(len(entries) > 100 for entries in value.values()):
            raise ValueError("Each section can contain at most 100 entries.")
        return {key: value.get(key, []) for key in SECTION_KEYS}

    @model_validator(mode="after")
    def language_consistency(self):
        if len(set(self.languages)) != len(self.languages):
            raise ValueError("Choose each language only once.")
        if self.default_language not in self.languages:
            raise ValueError("Default language must be one of the selected languages.")
        if len(set(self.hidden_sections)) != len(self.hidden_sections):
            raise ValueError("Hidden sections must be unique.")
        return self


def blank_site() -> Site:
    return Site()
