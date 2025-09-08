from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from typing import Dict, Any

from app.states.employer import EmployerSearch
from app.services.api_client import employer_api_client, search_api_client, candidate_api_client
from app.keyboards.inline import get_liked_candidate_keyboard, get_initial_search_keyboard, SearchResultAction, SearchResultDecision

router = Router()

def format_candidate_profile(profile: Dict[str, Any]) -> str:
    skills_list = profile.get('skills', [])
    skills = ", ".join(skill['skill'] for skill in skills_list) if skills_list else 'Не указаны'
    return (
        f"👤 <b>{profile.get('display_name', 'Имя не указано')}</b>\n"
        f"<i>{profile.get('headline_role', 'Должность не указана')}</i>\n\n"
        f"<b>Опыт:</b> {profile.get('experience_years', 0)} лет\n"
        f"<b>Навыки:</b> {skills}\n"
        f"<b>Локация:</b> {profile.get('location', 'Не указана')}"
    )


async def show_candidate_profile(message: types.Message, state: FSMContext, session_id: str):
    data = await state.get_data()
    idx = data.get('current_index', 0)
    candidate_ids = data.get('found_candidates', [])

    if not candidate_ids or idx >= len(candidate_ids):
        if isinstance(message, types.CallbackQuery):
            await message.answer()
            await message.message.answer("Больше кандидатов по вашему запросу нет. Можете начать новый поиск /search.")
        else:
            await message.answer("Больше кандидатов по вашему запросу нет. Можете начать новый поиск /search.")
        await state.clear()
        return

    candidate_id = candidate_ids[idx]
    profile = await candidate_api_client.get_candidate(candidate_id)

    if not profile:
        await message.answer("Не удалось загрузить профиль кандидата. Показываю следующего.")
        await state.update_data(current_index=idx + 1)
        await show_candidate_profile(message, state, session_id)
        return

    keyboard = get_initial_search_keyboard(candidate_id)

    if isinstance(message, types.CallbackQuery):
        await message.message.answer(format_candidate_profile(profile), reply_markup=keyboard)
    else:
        await message.answer(format_candidate_profile(profile), reply_markup=keyboard)


@router.message(EmployerSearch.entering_role)
async def handle_search_role(message: types.Message, state: FSMContext):
    await state.update_data(role=message.text)
    await state.set_state(EmployerSearch.entering_must_skills)
    await message.answer("<b>Шаг 2/5:</b> Какие ключевые навыки и технологии обязательны? (через запятую)")

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


@router.message(Command("skip"), EmployerSearch.entering_location_and_work_modes)
@router.message(EmployerSearch.entering_location_and_work_modes)
async def handle_location_and_start_search(message: types.Message, state: FSMContext):
    if message.text != "/skip":
        await state.update_data(location_query=message.text)

    await message.answer("💾 Сохранил. Начинаю поиск кандидатов...", reply_markup=types.ReplyKeyboardRemove())
    filters = await state.get_data()

    employer_profile = await employer_api_client.get_or_create_employer(message.from_user.id, message.from_user.username)
    if not employer_profile:
        await message.answer("❌ Не удалось создать ваш профиль работодателя. Поиск отменен.")
        await state.clear()
        return

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


@router.callback_query(SearchResultAction.filter(F.action == "next"), EmployerSearch.showing_results)
async def handle_next_candidate(callback: types.CallbackQuery, state: FSMContext):
    await process_next_candidate(callback, state)


@router.callback_query(SearchResultAction.filter(F.action == "contact"), EmployerSearch.showing_results)
async def handle_show_contact(callback: types.CallbackQuery, callback_data: SearchResultAction, state: FSMContext):
    data = await state.get_data()
    employer_profile = data.get('employer_profile')
    if not employer_profile:
        profile = await employer_api_client.get_or_create_employer(callback.from_user.id, callback.from_user.username)
        if not profile:
            await callback.answer("Не удалось получить ваш профиль работодателя. Попробуйте снова.", show_alert=True)
            return
        await state.update_data(employer_profile=profile)
        employer_profile = profile

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
