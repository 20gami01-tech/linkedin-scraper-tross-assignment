from app.parser import parse_profile


def test_parse_profile_basic():
    raw = {
        "included": [
            # A decoy mini-profile (e.g. a connection or endorser) that also
            # has firstName but is NOT the requested profile — the parser
            # must not pick this one.
            {
                "$type": "com.linkedin.voyager.identity.shared.MiniProfile",
                "entityUrn": "urn:li:fs_miniProfile:someoneElse",
                "firstName": "Not",
                "lastName": "TheOne",
            },
            {
                "$type": "com.linkedin.voyager.dash.identity.profile.Profile",
                "entityUrn": "urn:li:fsd_profile:janedoe123",
                "firstName": "Jane",
                "lastName": "Doe",
                "headline": "Software Engineer",
                "locationName": "Bengaluru, India",
                "summary": "I build things.",
            },
            {
                "$type": "com.linkedin.voyager.identity.profile.Position",
                "title": "Engineer",
                "companyName": "Acme Corp",
                "dateRange": {"start": {"year": 2022, "month": 1}},
            },
            {
                "$type": "com.linkedin.voyager.identity.profile.Education",
                "schoolName": "State University",
                "degreeName": "B.Tech",
                "fieldOfStudy": "Computer Science",
            },
            {
                "$type": "com.linkedin.voyager.identity.profile.Skill",
                "name": "Python",
            },
        ]
    }

    result = parse_profile(raw, "janedoe", "https://www.linkedin.com/in/janedoe/")

    assert result["name"]["full"] == "Jane Doe"
    assert result["headline"] == "Software Engineer"
    assert result["experience"][0]["company"] == "Acme Corp"
    assert result["education"][0]["school"] == "State University"
    assert "Python" in result["skills"]
