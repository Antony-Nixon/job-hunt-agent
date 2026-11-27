"""Local profile isolation for multiple job seekers on one device."""

import re
import shutil
from dataclasses import dataclass
from pathlib import Path


def validate_profile_id(profile_id: str) -> str:
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,62}", profile_id):
        raise ValueError("profile id must use lowercase letters, numbers, and hyphens")
    return profile_id


@dataclass(frozen=True)
class ProfilePaths:
    root: Path
    profile_id: str

    @property
    def directory(self) -> Path:
        return self.root / validate_profile_id(self.profile_id)

    @property
    def database(self) -> Path:
        return self.directory / "job_hunt_agent.db"

    @property
    def master_resume(self) -> Path:
        return self.directory / "master_resume.json"

    @property
    def output(self) -> Path:
        return self.directory / "output"

    def initialize(self, source_resume: Path) -> None:
        if self.master_resume.exists():
            raise FileExistsError(f"Profile already exists: {self.profile_id}")
        self.directory.mkdir(parents=True, exist_ok=True)
        self.output.mkdir(exist_ok=True)
        shutil.copy2(source_resume, self.master_resume)
