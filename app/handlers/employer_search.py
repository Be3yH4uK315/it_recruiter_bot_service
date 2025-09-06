from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from typing import Dict, Any

from app.states.employer import EmployerSearch
from app.services.api_client import employer_api_client, search_api_client, candidate_api_client
from app.keyboards.inline import get_search_results_keyboard, SearchResultAction

router = Router()

def format_candidate_profile(profile: Dict[str, Any]) -> str:
    skills = ", ".join(skill['skill'] for skill in profile.get('skills', []))
    return (
        f"👤 <b>{profile.get('display_name', 'Имя не указано')}</b>\n"
        f"<i>{profile.get('headline_role', 'Должность не указана')}</i>\n\n"
        f"<b>Опыт:</b> {profile.get('experience_years', 0)} лет\n"
        f"<b>Навыки:</b> {skills if skills else 'Не указаны'}\n"
        f"<b>Локация:</b> {profile.get('location', 'Не указана')}"
    )

async def show_candidate_profile(message: types.Message, state: FSMContext):
    data = await state.get_data()
    idx = data['current_index']
    candidate_ids = data['found_candidates']

    candidate_id = candidate_ids[idx]
    profile = await candidate_api_client.get_candidate(candidate_id)

    if not profile:
        await message.answer("Не удалось загрузить профиль кандидата. Попробуйте снова.")
        return

    is_last = (idx + 1) >= len(candidate_ids)
    keyboard = get_search_results_keyboard(candidate_id, is_last)
    await message.answer(format_candidate_profile(profile), reply_markup=keyboard)


@router.message(EmployerSearch.entering_role)
async def handle_search_role(message: types.Message, state: FSMContext):
    await state.update_data(role=message.text)
    await state.set_state(EmployerSearch.entering_must_skills)
    await message.answer("Принято. Какие ключевые навыки и технологии обязательны? (перечислите через запятую)")

@router.message(EmployerSearch.entering_must_skills)
async def handle_search_skills(message: types.Message, state: FSMContext):
    skills = [s.strip().lower() for s in message.text.split(',')]
    await state.update_data(must_skills=skills)
    await state.set_state(EmployerSearch.entering_experience)
    await message.answer("Какой минимальный опыт работы в годах требуется? (введите число, например, 3)")

@router.message(EmployerSearch.entering_experience)
async def handle_search_experience(message: types.Message, state: FSMContext):
    try:
        exp = float(message.text.replace(',', '.'))
        await state.update_data(experience_min=exp)
    except ValueError:
        await message.answer("Пожалуйста, введите число. Попробуйте еще раз.")
        return

    await message.answer("💾 Сохранил. Начинаю поиск кандидатов...", reply_markup=types.ReplyKeyboardRemove())
    filters = await state.get_data()


    employer_profile = await employer_api_client.get_or_create_employer(message.from_user.id, message.from_user.username)
    if not employer_profile:
        await message.answer("❌ Не удалось создать ваш профиль работодателя. Поиск отменен.")
        await state.clear()
        return

    await employer_api_client.create_search_session(employer_profile['id'], filters)

    search_results = await search_api_client.search_candidates(filters)
    if not search_results:
        await message.answer("🤷‍♂️ По вашему запросу кандидатов не найдено. Попробуйте изменить критерии.")
        await state.clear()
        return

    candidate_ids = [res['candidate_id'] for res in search_results]
    await state.update_data(found_candidates=candidate_ids, current_index=0)
    await state.set_state(EmployerSearch.showing_results)

    await message.answer(f"✅ Найдено кандидатов: {len(candidate_ids)}. Показываю первого:")
    await show_candidate_profile(message, state)


@router.callback_query(SearchResultAction.filter(F.action == "next"), EmployerSearch.showing_results)
async def handle_next_candidate(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    new_index = data['current_index'] + 1
    await state.update_data(current_index=new_index)

    await callback.message.edit_reply_markup(reply_markup=None)
    await show_candidate_profile(callback.message, state)
    await callback.answer()

@router.callback_query(SearchResultAction.filter(F.action == "contact"), EmployerSearch.showing_results)
async def handle_show_contact(callback: types.CallbackQuery, callback_data: SearchResultAction, state: FSMContext):
    await callback.answer("Функция показа контактов в разработке.", show_alert=True)