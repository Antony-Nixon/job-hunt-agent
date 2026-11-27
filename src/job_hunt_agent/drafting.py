"""Truthful draft builder that only copies verified profile facts."""

from .schemas import JobRecord, ProfileFact


def cover_letter_draft(job: JobRecord, facts: list[ProfileFact], name: str = "Candidate") -> str:
    job.validate()
    verified = [fact for fact in facts if fact.confidence >= 0.8]
    if not verified:
        raise ValueError("A draft requires at least one verified profile fact")
    evidence = "\n".join(f"- {fact.value} (source: {fact.source})" for fact in verified)
    return (f"Dear {job.company_name} hiring team,\n\nI am interested in the {job.title} role. "
            f"The following verified facts may be relevant:\n{evidence}\n\nSincerely,\n{name}\n\n"
            "REVIEW REQUIRED: edit this draft and verify every claim before use.")
