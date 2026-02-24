from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Header(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    phone: str
    email: str
    linkedin: str
    github: str


class WorkExperience(BaseModel):
    model_config = ConfigDict(extra="forbid")

    thorogood_bullets: list[str] = Field(default_factory=list)
    gwu_gta_bullets: list[str] = Field(default_factory=list)


class ProjectEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    bullets: list[str] = Field(default_factory=list)


class Projects(BaseModel):
    model_config = ConfigDict(extra="forbid")

    wtchtwr_bullets: list[str] = Field(default_factory=list)
    project2: ProjectEntry
    project3: ProjectEntry


class ResumeContent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    header: Header
    professional_summary: str
    technical_skills: list[str] = Field(default_factory=list)
    work_experience: WorkExperience
    projects: Projects
    education_lines: list[str] = Field(default_factory=list)
    jd_match_map: list[str] = Field(default_factory=list)


class ResumeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["final", "questions"]
    clarifying_questions: list[str] | None = None
    resume: ResumeContent | None = None

    @model_validator(mode="after")
    def validate_status_payload(self) -> "ResumeResponse":
        if self.status == "questions":
            if not self.clarifying_questions:
                raise ValueError(
                    "clarifying_questions must be provided when status='questions'."
                )
            if self.resume is not None:
                raise ValueError("resume must be omitted when status='questions'.")
        if self.status == "final" and self.resume is None:
            raise ValueError("resume must be provided when status='final'.")
        return self
