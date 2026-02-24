from __future__ import annotations

from .schema import ResumeContent


def build_resume_preview(resume: ResumeContent) -> str:
    bullet = "\u2022"
    lines: list[str] = []

    header = resume.header
    header_line = " | ".join(
        [
            header.name,
            header.phone,
            header.email,
            header.linkedin,
            header.github,
        ]
    )

    lines.append(header_line)
    lines.append("")

    lines.append("PROFESSIONAL SUMMARY")
    lines.append(resume.professional_summary.strip())
    lines.append("")

    lines.append("TECHNICAL SKILLS")
    lines.extend(skill.strip() for skill in resume.technical_skills)
    lines.append("")

    lines.append("WORK EXPERIENCE")
    lines.append("Thorogood")
    for item in resume.work_experience.thorogood_bullets:
        lines.append(f"{bullet} {item.strip()}")
    lines.append("GWU GTA")
    for item in resume.work_experience.gwu_gta_bullets:
        lines.append(f"{bullet} {item.strip()}")
    lines.append("")

    lines.append("PROJECTS")
    lines.append("wtchtwr")
    for item in resume.projects.wtchtwr_bullets:
        lines.append(f"{bullet} {item.strip()}")

    lines.append(resume.projects.project2.name.strip())
    for item in resume.projects.project2.bullets:
        lines.append(f"{bullet} {item.strip()}")

    lines.append(resume.projects.project3.name.strip())
    for item in resume.projects.project3.bullets:
        lines.append(f"{bullet} {item.strip()}")
    lines.append("")

    lines.append("EDUCATION")
    lines.extend(line.strip() for line in resume.education_lines)
    lines.append("")

    lines.append("JD MATCH MAP")
    for item in resume.jd_match_map:
        lines.append(f"{bullet} {item.strip()}")

    return "\n".join(lines).strip() + "\n"
