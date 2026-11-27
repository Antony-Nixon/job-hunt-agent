import json

from job_hunt_agent.profiles import ProfilePaths, validate_profile_id


def test_profile_paths_are_isolated(tmp_path):
    source = tmp_path / "source.json"
    source.write_text(json.dumps({"identity": {"name": "Avery"}}), encoding="utf-8")
    profile = ProfilePaths(tmp_path / "profiles", "avery-example")
    profile.initialize(source)
    assert profile.master_resume.exists()
    assert profile.database.parent == tmp_path / "profiles" / "avery-example"


def test_profile_id_rejects_path_characters():
    try:
        validate_profile_id("../other")
    except ValueError:
        pass
    else:
        raise AssertionError("path traversal profile id was accepted")

