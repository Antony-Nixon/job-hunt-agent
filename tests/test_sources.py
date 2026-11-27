from job_hunt_agent.sources import ashby_jobs, greenhouse_jobs, lever_jobs


def test_greenhouse_normalizes_public_job():
    jobs = greenhouse_jobs("acme", {"jobs": [{"id": 1, "title": "Automation Engineer", "company_name": "Acme", "absolute_url": "https://boards.greenhouse.io/acme/jobs/1", "updated_at": "2026-11-14T00:00:00Z", "content": "<p>Python automation</p>", "location": {"name": "Remote"}}]})
    assert jobs[0].job_id == "greenhouse:acme:1"
    assert jobs[0].description == "Python automation"


def test_lever_normalizes_public_job():
    jobs = lever_jobs("acme", [{"id": "1", "text": "Automation Engineer", "hostedUrl": "https://jobs.lever.co/acme/1", "createdAt": 1763078400000, "descriptionPlain": "Python API", "categories": {"location": "Remote", "commitment": "Full-time"}, "workplaceType": "remote"}])
    assert jobs[0].source_name == "lever"
    assert jobs[0].work_mode == "remote"


def test_ashby_excludes_unlisted_jobs():
    jobs = ashby_jobs("acme", {"jobs": [{"id": "1", "title": "Automation Engineer", "jobUrl": "https://jobs.ashbyhq.com/acme/1", "descriptionPlain": "Python", "isListed": False}]})
    assert jobs == []

