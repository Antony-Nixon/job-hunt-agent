"""Master-resume loading and truthful, deterministic output generation."""

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .schemas import JobRecord, ProfileFact


def _terms(value: str) -> set[str]:
    return {
        word.lower()
        for word in re.findall(r"[A-Za-z][A-Za-z0-9+#.-]{1,}", value)
        if len(word) > 2
    }


@dataclass(frozen=True)
class MasterResume:
    """Owner-approved source material; output may select facts but never invent them."""

    data: dict
    source: str

    @property
    def name(self) -> str:
        return self.data["identity"]["name"]

    @classmethod
    def load(cls, path: str | Path) -> "MasterResume":
        source = Path(path)
        data = json.loads(source.read_text(encoding="utf-8"))
        for key in ("identity", "summary", "experience", "projects", "skills", "education"):
            if key not in data:
                raise ValueError(f"Master resume is missing {key}")
        if not data["identity"].get("name"):
            raise ValueError("Master resume requires identity.name")
        return cls(data, str(source))

    def facts(self) -> list[ProfileFact]:
        """Create traceable facts for scoring and drafting."""
        verified_at = datetime.now(timezone.utc)
        source = self.data.get("source", self.source)
        values: dict[str, str] = {
            "identity.name": self.name,
            "summary": self.data["summary"],
            "skills": ", ".join(self.data["skills"]),
            "education": self.data["education"],
        }
        for key, value in self.data.get("contact", {}).items():
            values[f"contact.{key}"] = value
        for preference, value in self.data.get("preferences", {}).items():
            values[f"preference.{preference}"] = json.dumps(value) if not isinstance(value, str) else value
        for item in self.data["experience"] + self.data["projects"]:
            prefix = item["id"]
            values[f"{prefix}.role"] = item.get("role", item.get("name", ""))
            values[f"{prefix}.evidence"] = " ".join(item["highlights"])
        return [ProfileFact(key, value, source, verified_at) for key, value in values.items() if value]


def _relevant_highlights(item: dict, job_terms: set[str]) -> list[str]:
    highlights = item["highlights"]
    relevant = [bullet for bullet in highlights if _terms(bullet) & job_terms]
    return relevant or highlights[:2]


def tailored_resume_markdown(master: MasterResume, job: JobRecord) -> str:
    """Create a role-focused Markdown resume by selecting original verified statements."""
    job_terms = _terms(f"{job.title} {job.description}")
    contact = master.data.get("contact", {})
    contact_line = " | ".join(value for value in contact.values() if value)
    lines = [f"# {master.name}", contact_line, "", "## Professional Summary", master.data["summary"], "", "## Relevant Experience"]
    items = master.data["experience"] + master.data["projects"]
    ranked = sorted(items, key=lambda item: len(_terms(" ".join(item["highlights"])) & job_terms), reverse=True)
    for item in ranked[:4]:
        heading = item.get("role", item.get("name"))
        organization = item.get("organization", "Independent Project")
        period = item.get("period", "")
        lines.extend([f"### {heading} — {organization}", period])
        lines.extend(f"- {bullet}" for bullet in _relevant_highlights(item, job_terms))
        lines.append("")
    lines.extend(["## Technical Skills", ", ".join(master.data["skills"]), "", "## Education", master.data["education"], "", "---", f"Tailored for: {job.title} at {job.company_name}", "Every claim above is selected from the owner-approved master resume; review before use."])
    return "\n".join(lines)


def interview_prep_markdown(master: MasterResume, job: JobRecord) -> str:
    """Create a reviewable interview-prep brief grounded only in the job and master resume."""
    job_terms = _terms(f"{job.title} {job.description}")
    skills = _terms(" ".join(master.data["skills"]))
    matched = sorted(skills & job_terms)
    known_requirements = {"python", "sql", "selenium", "automation", "api", "crm", "salesforce", "hubspot", "javascript", "cloudflare", "rpa"}
    gaps = sorted((job_terms & known_requirements) - skills)
    items = master.data["experience"] + master.data["projects"]
    ranked = sorted(items, key=lambda item: len(_terms(" ".join(item["highlights"])) & job_terms), reverse=True)
    stories = []
    for item in ranked[:4]:
        stories.append((item.get("role", item.get("name")), _relevant_highlights(item, job_terms)))
    lines = [f"# Interview Prep: {job.title} — {job.company_name}", "", "## Role Snapshot", job.description, "", "## Your Evidence of Fit", f"Matched terms: {', '.join(matched) or 'No direct keyword match; use the stories below.'}", f"Discuss or clarify: {', '.join(gaps) or 'No predefined skill gaps detected.'}", "", "## STAR Stories to Prepare"]
    for title, bullets in stories[:4]:
        lines.append(f"### {title}")
        lines.extend(f"- {bullet}" for bullet in bullets)
        lines.append("Prepare: situation, your specific actions, measurable result, and what you learned.")
    lines.extend(["", "## Likely Questions", "- Walk us through an automation system you designed, including failure handling and data integrity.", "- How do you make an automated workflow idempotent and safe to retry?", "- Describe a project where you translated an operational problem into a CRM, ERP, or dashboard workflow.", "- How would you evaluate and improve the reliability of an API or browser-based automation?", f"- Why does the {job.title} role at {job.company_name} fit your next step?", "", "## Questions to Ask", "- Which workflow failures create the greatest operational risk for this team?", "- How are automation reliability, data quality, and business impact measured?", "- What would a successful first 90 days look like?", "", "## Final Review", "Do not claim experience, salary expectations, work authorization, or availability beyond what you can personally confirm."])
    return "\n".join(lines)
