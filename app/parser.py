"""
The Voyager `profileView` response is a flat, normalized graph: a top-level
object plus an `included` list of entities (positions, education, skills,
etc.), each tagged with a `$type`. This module buckets those entities by
type and reshapes them into the flat schema this API exposes.

Because LinkedIn's internal field names have drifted over the years (and
across account/locale variants), lookups below use `.get()` defensively —
missing fields come back as `null` rather than raising.
"""

from .utils import build_image_url, format_date


def _index_by_type(included: list[dict]) -> dict[str, list[dict]]:
    buckets: dict[str, list[dict]] = {}
    for item in included:
        type_name = item.get("$type", "")
        short_name = type_name.rsplit(".", 1)[-1]
        buckets.setdefault(short_name, []).append(item)
    return buckets


def _find_primary_profile(included: list[dict]) -> dict:
    """
    The flat `included` array can contain more than one profile-shaped
    entity (mini-profiles of connections, etc). The reliable signal for
    "this is the profile being requested" is an entityUrn containing
    'fsd_profile:' combined with a firstName field — matching on $type
    alone is not sufficient in the current dash-style response.
    """
    for item in included:
        if item.get("firstName") and "fsd_profile:" in item.get("entityUrn", ""):
            return item
    # Fallback for older/alternate response shapes.
    for item in included:
        if item.get("$type", "").endswith("Profile") and item.get("firstName"):
            return item
    return {}


def parse_profile(raw: dict, public_identifier: str, input_url: str) -> dict:
    included = raw.get("included", [])
    buckets = _index_by_type(included)

    profile = _find_primary_profile(included)

    first = profile.get("firstName")
    last = profile.get("lastName")
    full = " ".join(p for p in [first, last] if p) or None

    experience = [
        {
            "title": p.get("title"),
            "company": p.get("companyName"),
            "location": p.get("locationName"),
            "start_date": format_date((p.get("dateRange") or {}).get("start")),
            "end_date": format_date((p.get("dateRange") or {}).get("end")),
            "description": p.get("description"),
        }
        for p in buckets.get("Position", [])
    ]

    education = [
        {
            "school": e.get("schoolName"),
            "degree": e.get("degreeName"),
            "field_of_study": e.get("fieldOfStudy"),
            "start_date": format_date((e.get("dateRange") or {}).get("start")),
            "end_date": format_date((e.get("dateRange") or {}).get("end")),
        }
        for e in buckets.get("Education", [])
    ]

    skills = [s.get("name") for s in buckets.get("Skill", []) if s.get("name")]

    certifications = [
        {
            "name": c.get("name"),
            "issuing_organization": c.get("authority"),
            "issue_date": format_date((c.get("timePeriod") or {}).get("start")),
        }
        for c in buckets.get("Certification", [])
    ]

    languages = [
        {"name": lang.get("name"), "proficiency": lang.get("proficiency")}
        for lang in buckets.get("Language", [])
    ]

    return {
        "input_url": input_url,
        "public_identifier": public_identifier,
        "name": {"first": first, "last": last, "full": full},
        "headline": profile.get("headline"),
        "location": profile.get("locationName") or profile.get("geoLocationName"),
        "industry": profile.get("industryName"),
        "about": profile.get("summary"),
        "profile_picture_url": build_image_url(
            (profile.get("profilePicture") or {}).get("displayImageReference")
        ),
        "background_image_url": build_image_url(
            (profile.get("backgroundPicture") or {}).get("displayImageReference")
        ),
        "experience": experience,
        "education": education,
        "skills": skills,
        "certifications": certifications,
        "languages": languages,
    }
