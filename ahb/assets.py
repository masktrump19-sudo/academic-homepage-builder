"""Bounded, explicitly selected public attachments; never used for raw imports."""
from io import BytesIO
from pathlib import PurePosixPath
import re
from PIL import Image, ImageOps, UnidentifiedImageError

MAX_UPLOAD = 20 * 1024 * 1024
Image.MAX_IMAGE_PIXELS = 24_000_000
ASSET_RE = re.compile(r"assets/uploads/[A-Za-z0-9][A-Za-z0-9_.-]{0,120}\.(?:png|jpg|jpeg|webp|pdf)\Z", re.I)


def valid_asset_path(path: str) -> bool:
    return bool(ASSET_RE.fullmatch(path)) and '..' not in PurePosixPath(path).parts and '\\' not in path


def sanitize_attachment(filename: str, data: bytes) -> tuple[bytes, str, str]:
    if not data or len(data) > MAX_UPLOAD:
        raise ValueError('Choose a non-empty attachment smaller than 20 MB.')
    suffix = PurePosixPath(filename.replace('\\', '/')).suffix.lower()
    if suffix == '.pdf':
        from pypdf import PdfReader, PdfWriter
        try:
            reader = PdfReader(BytesIO(data))
            if reader.is_encrypted or not 0 < len(reader.pages) <= 100:
                raise ValueError('Use an unencrypted PDF with at most 100 pages.')
            writer = PdfWriter()
            # Prune the source graph before copying it. Removing references after
            # add_page() can leave private streams in the writer's object table.
            omitted = {
                '/Annots', '/AA', '/A', '/OpenAction', '/JS', '/JavaScript',
                '/EmbeddedFiles', '/Metadata', '/AF', '/EF', '/FS', '/AcroForm',
                '/XFA', '/PieceInfo', '/Thumb', '/B', '/StructTreeRoot',
            }
            def clean(obj, seen):
                if hasattr(obj, 'get_object'):
                    obj = obj.get_object()
                if id(obj) in seen:
                    return
                seen.add(id(obj))
                if isinstance(obj, dict):
                    for key in list(obj):
                        if str(key) in omitted:
                            del obj[key]
                        elif str(key) != '/Parent':
                            clean(obj[key], seen)
                elif isinstance(obj, list):
                    for item in obj:
                        clean(item, seen)
            seen = set()
            for page in reader.pages:
                clean(page, seen)
                writer.add_page(page, excluded_keys=omitted)
            # Catalog-level forms, attachments and outlines are never imported.
            writer.metadata = None
            output = BytesIO()
            writer.write(output)
            return output.getvalue(), '.pdf', 'application/pdf'
        except ValueError:
            raise
        except Exception as exc:
            raise ValueError('This PDF attachment could not be read. Try a fresh PDF export.') from exc
    if suffix not in {'.png', '.jpg', '.jpeg', '.webp'}:
        raise ValueError('Public attachments must be PNG, JPEG, WebP or PDF. SVG is not accepted.')
    try:
        with Image.open(BytesIO(data)) as image:
            if image.width * image.height > Image.MAX_IMAGE_PIXELS:
                raise ValueError('Image exceeds 24 megapixels.')
            image = ImageOps.exif_transpose(image)
            image.thumbnail((2400, 2400))
            image = image.convert('RGBA' if 'A' in image.getbands() else 'RGB')
            # A fresh pixel image intentionally strips EXIF, location and other metadata.
            fresh = Image.new(image.mode, image.size)
            fresh.paste(image)
            output = BytesIO()
            fresh.save(output, format='PNG', optimize=True)
            return output.getvalue(), '.png', 'image/png'
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ValueError('Invalid or oversized image.') from exc
