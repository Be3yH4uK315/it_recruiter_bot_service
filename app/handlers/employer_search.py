from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from typing import Dict, Any
from app.states.employer import EmployerSearch
from app.services.api_client import employer_api_client, search_api_client, candidate_api_client, file_api_client
from app.keyboards.inline import get_liked_candidate_keyboard, get_initial_search_keyboard, SearchResultAction, SearchResultDecision

router = Router()

# --- FORMAT PROFILE ---
def format_candidate_profile(profile: Dict[str, Any]) -> str:
    text = (
        f"<b>👤 Имя:</b> {profile.get('display_name', 'Не указано')}\n"
        f"<b>📌 Должность:</b> {profile.get('headline_role', 'Не указано')}\n"
        f"<b>📈 Опыт:</b> {profile.get('experience_years', 'Не указан')} лет\n"
        f"<b>📍 Локация:</b> {profile.get('location', 'Не указана')}\n"
        f"<b>💻 Форматы работы:</b> {', '.join(profile.get('work_modes') or ['Не указаны'])}\n"
    )

    skills = profile.get('skills', [])
    if skills:
        hard_skills = [s['skill'] for s in skills if s['kind'] == 'hard']
        tools = [s['skill'] for s in skills if s['kind'] == 'tool']

        skills_text = "\n<b>🛠 Ключевые навыки и инструменты:</b>\n"
        if hard_skills:
            skills_text += f" • <b>Hard Skills:</b> {', '.join(hard_skills)}\n"
        if tools:
            skills_text += f" • <b>Инструменты:</b> {', '.join(tools)}\n"
        text += skills_text

    projects = profile.get('projects', [])
    if projects:
        projects_text = "\n<b>🚀 Проекты:</b>\n"
        for p in projects:
            projects_text += f"  - <b>{p.get('title', 'Без названия')}</b>\n"
            if p.get('description'):
                projects_text += f"    <i>{p.get('description')}</i>\n"
            if p.get('links') and p['links'].get('main_link'):
                 projects_text += f"    <a href='{p['links']['main_link']}'>Ссылка</a>\n"
        text += projects_text

    return text


async def show_candidate_profile(message: types.Message | types.CallbackQuery, state: FSMContext, session_id: str):
    data = await state.get_data()
    idx = data.get('current_index', 0)
    candidate_ids = data.get('found_candidates', [])

    target_message = message.message if isinstance(message, types.CallbackQuery) else message

    if not candidate_ids or idx >= len(candidate_ids):
        await target_message.answer("Больше кандидатов по вашему запросу нет. Можете начать новый поиск /search.")
        if isinstance(message, types.CallbackQuery):
            await message.answer()
        await state.clear()
        return

    candidate_id = candidate_ids[idx]
    profile = await candidate_api_client.get_candidate(candidate_id)

    if not profile:
        await target_message.answer("Не удалось загрузить профиль кандидата. Показываю следующего.")
        await state.update_data(current_index=idx + 1)
        await show_candidate_profile(message, state, session_id)
        return

    avatar_url = None
    if profile.get("avatars"):
        avatar_file_id = profile["avatars"][0]["file_id"]
        avatar_url = await file_api_client.get_download_url_by_file_id(avatar_file_id)

    caption = format_candidate_profile(profile)
    has_resume = bool(profile.get("resumes"))
    keyboard = get_initial_search_keyboard(candidate_id, has_resume)

    if avatar_url:
        await target_message.answer_photo(
            photo=avatar_url,
            caption=caption,
            reply_markup=keyboard
        )
    else:
        await target_message.answer(
            text=caption,
            reply_markup=keyboard
        )

    if isinstance(message, types.CallbackQuery):
        await message.answer()

# --- EMPLOYER SEARCH ---
# --- ROLE ---
@router.message(EmployerSearch.entering_role)
async def handle_search_role(message: types.Message, state: FSMContext):
    await state.update_data(role=message.text)
    await state.set_state(EmployerSearch.entering_must_skills)
    await message.answer("<b>Шаг 2/5:</b> Какие ключевые навыки и технологии обязательны? (через запятую)")

# --- SKILLS ---
@router.message(EmployerSearch.entering_must_skills)
async def handle_search_skills(message: types.Message, state: FSMContext):
    skills = [s.strip().lower() for s in message.text.split(',')]
    await state.update_data(must_skills=skills)
    await state.set_state(EmployerSearch.entering_nice_skills)
    await message.answer("<b>Шаг 3/5:</b> Какие навыки желательны, но не обязательны? (через запятую, или /skip)")

@router.message(Command("skip"), EmployerSearch.entering_nice_skills)
@router.message(EmployerSearch.entering_nice_skills)
async def handle_nice_skills(message: types.Message, state: FSMContext):
    if message.text != "/skip":
        skills = [s.strip().lower() for s in message.text.split(',')]
        await state.update_data(nice_skills=skills)

    await state.set_state(EmployerSearch.entering_experience)
    await message.answer("<b>Шаг 4/5:</b> Какой минимальный и максимальный опыт требуется? (например, 2-5)")

# --- EXPERIENCE YEARS ---
@router.message(EmployerSearch.entering_experience)
async def handle_search_experience(message: types.Message, state: FSMContext):
    try:
        parts = message.text.replace(',', '.').split('-')
        exp_min = float(parts[0].strip())
        exp_max = float(parts[1].strip()) if len(parts) > 1 else None
        await state.update_data(experience_min=exp_min, experience_max=exp_max)
    except (ValueError, IndexError):
        await message.answer("Неверный формат. Введите число или диапазон, например: 3 или 2-5. Попробуйте еще раз.")
        return

    await state.set_state(EmployerSearch.entering_location_and_work_modes)
    await message.answer("<b>Шаг 5/5:</b> Укажите желаемую локацию и форматы работы. (например, EU remote, или /skip)")

# --- LOCATION AND START ---
@router.message(Command("skip"), EmployerSearch.entering_location_and_work_modes)
@router.message(EmployerSearch.entering_location_and_work_modes)
async def handle_location_and_start_search(message: types.Message, state: FSMContext):
    if message.text != "/skip":
        await state.update_data(location_query=message.text)

    await message.answer("💾 Сохранил. Начинаю поиск кандидатов...", reply_markup=types.ReplyKeyboardRemove())

    employer_profile = await employer_api_client.get_or_create_employer(message.from_user.id, message.from_user.username)
    if not employer_profile:
        await message.answer("❌ Не удалось создать ваш профиль работодателя. Поиск отменен.")
        await state.clear()
        return
    await state.update_data(employer_profile=employer_profile)

    filters = await state.get_data()

    search_session = await employer_api_client.create_search_session(employer_profile['id'], filters)
    if not search_session:
        await message.answer("❌ Не удалось создать сессию поиска. Попробуйте позже.")
        await state.clear()
        return

    session_id = search_session['id']
    await state.update_data(session_id=session_id)

    search_results = await search_api_client.search_candidates(filters)
    if not search_results:
        await message.answer("🤷‍♂️ По вашему запросу кандидатов не найдено. Попробуйте изменить критерии.")
        await state.clear()
        return

    candidate_ids = [res['candidate_id'] for res in search_results]
    await state.update_data(found_candidates=candidate_ids, current_index=0)
    await state.set_state(EmployerSearch.showing_results)

    await message.answer(f"✅ Найдено кандидатов: {len(candidate_ids)}. Показываю первого:")
    await show_candidate_profile(message, state, session_id)

async def process_next_candidate(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    session_id = data.get("session_id")
    if not session_id:
        await callback.answer("Сессия истекла.", show_alert=True)
        return

    new_index = data.get('current_index', 0) + 1
    await state.update_data(current_index=new_index)

    await callback.message.delete()
    await show_candidate_profile(callback, state, session_id)
    await callback.answer()

# --- DECISION ---
@router.callback_query(SearchResultDecision.filter(), EmployerSearch.showing_results)
async def handle_decision(callback: types.CallbackQuery, callback_data: SearchResultDecision, state: FSMContext):
    data = await state.get_data()
    session_id = data.get("session_id")

    if not session_id:
        await callback.answer("Ошибка: сессия поиска истекла. Начните заново.", show_alert=True)
        return

    success = await employer_api_client.save_decision(
        session_id=session_id,
        candidate_id=callback_data.candidate_id,
        decision=callback_data.action
    )

    if not success:
        await callback.answer("Не удалось сохранить выбор.", show_alert=True)
        return

    if callback_data.action == "like":
        await callback.answer("✅ Кандидат отмечен как подходящий.")
        new_keyboard = get_liked_candidate_keyboard(callback_data.candidate_id)
        await callback.message.edit_reply_markup(reply_markup=new_keyboard)
    else:
        await callback.answer("Выбор сохранен.")
        await process_next_candidate(callback, state)

# --- NEXT ---
@router.callback_query(SearchResultAction.filter(F.action == "next"), EmployerSearch.showing_results)
async def handle_next_candidate(callback: types.CallbackQuery, state: FSMContext):
    await process_next_candidate(callback, state)

# --- CONTACTS ---
@router.callback_query(SearchResultAction.filter(F.action == "contact"), EmployerSearch.showing_results)
async def handle_show_contact(callback: types.CallbackQuery, callback_data: SearchResultAction, state: FSMContext):
    data = await state.get_data()
    employer_profile = data.get('employer_profile')
    if not employer_profile:
        await callback.answer("Ошибка сессии: профиль работодателя не найден. Начните поиск заново.", show_alert=True)
        return

    await callback.answer("Запрашиваю контакты...", show_alert=False)

    response = await employer_api_client.request_contacts(
        employer_id=employer_profile['id'],
        candidate_id=callback_data.candidate_id
    )

    if not response:
        await callback.message.answer("❌ Произошла ошибка при запросе контактов.")
        return

    if response.get("granted") and response.get("contacts"):
        contacts = response["contacts"]
        contact_text = "\n".join([f"<b>{key.capitalize()}:</b> {value}" for key, value in contacts.items()])
        await callback.message.answer(f"✅ Доступ получен. Контакты кандидата:\n\n{contact_text}")
    else:
        await callback.message.answer("🤷‍♂️ Кандидат ограничил доступ к своим контактам.")

# --- RESUME ---
@router.callback_query(SearchResultAction.filter(F.action == "get_resume"), EmployerSearch.showing_results)
async def handle_get_resume(callback: types.CallbackQuery, callback_data: SearchResultAction, state: FSMContext):
    await callback.answer("Запрашиваю профиль...")

    profile = await candidate_api_client.get_candidate(callback_data.candidate_id)

    if not profile or not profile.get("resumes"):
        await callback.message.answer("У этого кандидата нет загруженного резюме.")
        return

    file_id = profile["resumes"][0]["file_id"]

    await callback.answer("Запрашиваю ссылку на файл...")

    link = await file_api_client.get_download_url_by_file_id(file_id)

    if link:
        keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="📥 Скачать файл", url=link)]
        ])
        await callback.message.answer(
            "🔗 Ваша ссылка на скачивание (действительна 5 минут):",
            reply_markup=keyboard
        )
    else:
        await callback.message.answer("Не удалось получить ссылку на резюме. Сервис файлов может быть недоступен.")
