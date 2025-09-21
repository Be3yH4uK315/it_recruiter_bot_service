from typing import Dict, Any

def format_candidate_profile(profile: Dict[str, Any]) -> str:
    """Форматирование профиля для отображения."""
    text = (
        f"<b>👤 {profile.get('display_name', 'Имя не указано')}</b>\n"
        f"<i>{profile.get('headline_role', 'Должность не указана')}</i>\n\n"
        f"<b>📍 Локация:</b> {profile.get('location', 'Не указана')}\n"
        f"<b>💻 Форматы работы:</b> {', '.join(profile.get('work_modes') or ['Не указаны'])}\n"
    )

    experiences = profile.get('experiences', [])
    if experiences:
        total_exp = profile.get('experience_years', 0)
        text += f"<b>📈 Общий опыт:</b> ~{total_exp} лет\n\n"
        text += "<b>💼 Опыт работы:</b>\n"
        for exp in experiences[:3]:
            end_date = (exp.get('end_date') or 'н.в.').replace('-', '.')
            start_date = (exp.get('start_date') or '').replace('-', '.')
            if exp.get('responsibilities'):
                text += f" <i>{exp.get('responsibilities')[:200]}</i>\n"
            text += (
                f"  • <b>{exp.get('position')}</b> в {exp.get('company')}\n"
                f"    <i>({start_date} - {end_date})</i>\n"
            )
    else:
        text += f"<b>📈 Опыт:</b> {profile.get('experience_years', 'Не указан')} лет\n"

    skills = profile.get('skills', [])
    if skills:
        hard_skills = [s['skill'] for s in skills if s['kind'] == 'hard']
        tools = [s['skill'] for s in skills if s['kind'] == 'tool']
        languages = [s['skill'] for s in skills if s['kind'] == 'language']
        skills_text = "\n<b>🛠 Ключевые навыки и инструменты:</b>\n"
        if hard_skills:
            skills_text += f" • <b>Hard Skills:</b> {', '.join(hard_skills)}\n"
        if tools:
            skills_text += f" • <b>Инструменты:</b> {', '.join(tools)}\n"
        if languages:
            skills_text += f" • <b>Языки:</b> {', '.join(languages)}\n"
        text += skills_text

    projects = profile.get('projects', [])
    if projects:
        text += "\n<b>🚀 Проекты:</b>\n"
        for p in projects[:3]:
            text += f"  • <b>{p.get('title', 'Без названия')}</b>\n"
            if p.get('description'):
                text += f" <i>{p.get('description')[:200]}...</i>\n"
            if p.get('links') and p['links'].get('main_link'):
                text += f" (<a href='{p['links']['main_link']}'>Ссылка</a>)\n"
            else:
                text += "\n"

    return text