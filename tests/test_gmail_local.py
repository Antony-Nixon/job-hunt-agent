from job_hunt_agent.gmail_local import credential_name


def test_gmail_credential_name_is_profile_scoped():
    assert credential_name("example-profile") == "example-profile:gmail-oauth"

