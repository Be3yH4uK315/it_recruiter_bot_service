from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command
from app.states.candidate import CandidateRegistration
from app.services.api_client import api_client

router = Router()


@router.message(CandidateRegistration.entering_headline_role)
async def handle_headline_role(message: types.Message, state: FSMContext):
    await state.update_data(headline_role=message.text)
    await message.answer(
        "Отлично! Теперь укажите ваш опыт работы в годах (например, 3.5):"
    )
    await state.set_state(CandidateRegistration.entering_experience_years)


@router.message(CandidateRegistration.entering_experience_years)
async def handle_experience_years(message: types.Message, state: FSMContext):
    try:
        experience = float(message.text.replace(",", "."))
        await state.update_data(experience_years=experience)
        await message.answer(
            "Принято. Теперь перечислите ваши ключевые навыки и инструменты через запятую.\n"
            "<i>Например: Python, FastAPI, Docker, Git, PostgreSQL</i>"
        )
        await state.set_state(CandidateRegistration.entering_skills)
    except ValueError:
        await message.answer("Пожалуйста, введите число (например, 2 или 5.5).")


@router.message(CandidateRegistration.entering_skills)
async def handle_skills(message: types.Message, state: FSMContext):
    skills_text = message.text
    skills_list = [skill.strip() for skill in skills_text.split(",")]

    await state.update_data(skills=skills_list)

    user_data = await state.get_data()

    await message.answer("Спасибо! Сохраняю ваш обновленный профиль...")

    telegram_id = message.from_user.id
    success = await api_client.update_candidate_profile(telegram_id, user_data)

    if success:
        await message.answer(
            "✅ Ваш профиль успешно обновлен!\n\n"
            "Вы всегда можете его дополнить, используя команду /profile (в разработке)."
        )
    else:
        await message.answer(
            "❌ Произошла ошибка при обновлении профиля. Попробуйте позже."
        )

    await state.clear()


@router.message(Command("cancel"))
async def cancel_handler(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is None:
        return

    await state.clear()
    await message.answer("Действие отменено.")
