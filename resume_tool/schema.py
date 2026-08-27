from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .utils import word_count


OutputFormat = Literal["docx", "pdf", "both"]


class ResumeMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    company: str = ""
    role: str = ""
    location: str = ""
    compensation: str = ""
    job_url: str = ""
    source: str = ""
    project_count: Literal[1, 2] = 1
    include_awards: bool = True
    output_format: OutputFormat = "both"

    @field_validator("output_format", mode="before")
    @classmethod
    def normalize_output_format(cls, value):
        return str(value).strip().casefold() if value is not None else value


class WorkExperience(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ilink_bullets: list[str] = Field(min_length=6, max_length=6)
    gwu_gta_bullets: list[str] = Field(min_length=3, max_length=3)
    thorogood_bullets: list[str] = Field(min_length=7, max_length=7)

    @field_validator("ilink_bullets", "gwu_gta_bullets", "thorogood_bullets")
    @classmethod
    def validate_bullets(cls, bullets: list[str]) -> list[str]:
        return _validated_bullets(bullets)


class ProjectEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1)
    bullets: list[str] = Field(min_length=3, max_length=4)

    @field_validator("bullets")
    @classmethod
    def validate_bullets(cls, bullets: list[str]) -> list[str]:
        return _validated_bullets(bullets)


class Projects(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project1: ProjectEntry
    project2: ProjectEntry | None = None


class ResumeContent(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    professional_summary: str
    technical_skills: list[str] = Field(min_length=6, max_length=6)
    work_experience: WorkExperience
    projects: Projects

    @field_validator("professional_summary")
    @classmethod
    def validate_summary(cls, value: str) -> str:
        count = word_count(value)
        if not 50 <= count <= 60:
            raise ValueError(f"professional_summary must contain 50-60 words; found {count}.")
        return value.strip()

    @field_validator("technical_skills")
    @classmethod
    def validate_skills(cls, lines: list[str]) -> list[str]:
        validated: list[str] = []
        for index, line in enumerate(lines):
            value = line.strip()
            category, separator, items_text = value.partition(":")
            items = [item.strip() for item in items_text.split(",") if item.strip()]
            if not separator or not category.strip() or len(items) < 3:
                raise ValueError(
                    f"technical_skills[{index}] must use 'Category: item, item, item'."
                )
            validated.append(value)
        return validated


class ResumeDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metadata: ResumeMetadata
    resume: ResumeContent

    @model_validator(mode="after")
    def validate_project_contract(self) -> "ResumeDocument":
        count = self.metadata.project_count
        project1 = self.resume.projects.project1
        project2 = self.resume.projects.project2
        if count == 1:
            if len(project1.bullets) != 4:
                raise ValueError("project1 must have exactly 4 bullets when project_count=1.")
            if project2 is not None:
                raise ValueError("project2 must be null when project_count=1.")
        else:
            if len(project1.bullets) != 3:
                raise ValueError("project1 must have exactly 3 bullets when project_count=2.")
            if project2 is None:
                raise ValueError("project2 is required when project_count=2.")
            if len(project2.bullets) != 3:
                raise ValueError("project2 must have exactly 3 bullets when project_count=2.")
            if project1.name.casefold() == project2.name.casefold():
                raise ValueError("project1 and project2 names must be different.")
        return self


def _validated_bullets(bullets: list[str]) -> list[str]:
    validated: list[str] = []
    for index, bullet in enumerate(bullets):
        value = bullet.strip()
        if not value:
            raise ValueError(f"bullet {index + 1} must not be empty.")
        count = word_count(value)
        if count > 17:
            raise ValueError(f"bullet {index + 1} exceeds 17 words; found {count}.")
        validated.append(value)
    return validated
