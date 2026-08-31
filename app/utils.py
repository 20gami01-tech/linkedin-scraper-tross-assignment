import re
from datetime import datetime, timezone
from urllib.parse import urlparse


def extract_public_identifier(linkedin_url: str) -> str:
    """Pull the '/in/<identifier>' slug out of a LinkedIn profile URL."""
    parsed = urlparse(linkedin_url.strip())
    if "linkedin.com" not in parsed.netloc:
        raise ValueError("URL does not look like a linkedin.com profile URL")
    match = re.search(r"/in/([^/?#]+)", parsed.path)
    if not match:
        raise ValueError("Could not find a profile identifier (/in/<id>) in the URL")
    return match.group(1)


def build_image_url(image_ref: dict | None) -> str | None:
    """Reconstruct a usable image URL from a Voyager vector-image reference."""
    if not image_ref:
        return None
    vector = image_ref.get("vectorImage") or image_ref.get(
        "com.linkedin.common.VectorImage"
    )
    if not vector:
        return None
    root = vector.get("rootUrl", "")
    artifacts = vector.get("artifacts", [])
    if not artifacts:
        return None
    largest = max(artifacts, key=lambda a: a.get("width", 0))
    segment = largest.get("fileIdentifyingUrlPathSegment", "")
    return f"{root}{segment}" if root and segment else None


def format_date(date_obj: dict | None) -> str | None:
    if not date_obj:
        return None
    year = date_obj.get("year")
    month = date_obj.get("month")
    if year and month:
        return f"{year}-{int(month):02d}"
    if year:
        return str(year)
    return None


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
