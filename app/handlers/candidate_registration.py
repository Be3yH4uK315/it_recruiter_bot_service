from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command
from app.states.candidate import CandidateRegistration
from app.services.api_client import candidate_api_client, file_api_client
from app.keyboards.inline import get_work_modes_keyboard, WorkModeCallback

router = Router()


@router.message(CandidateRegistration.entering_headline_role)
async def handle_headline_role(message: types.Message, state: FSMContext):
    await state.update_data(headline_role=message.text)
    await message.answer(
        "<b>Шаг 2/6:</b> Отлично! Теперь укажите ваш опыт работы в годах (например, 3.5):"
    )
    await state.set_state(CandidateRegistration.entering_experience_years)


@router.message(CandidateRegistration.entering_experience_years)
async def handle_experience_years(message: types.Message, state: FSMContext):
    try:
        experience = float(message.text.replace(",", "."))
        await state.update_data(experience_years=experience)
        await message.answer(
            "<b>Шаг 3/6:</b> Принято. Теперь перечислите ваши ключевые навыки и инструменты через запятую.\n"
            "<i>Например: Python, FastAPI, Docker, Git, PostgreSQL</i>"
        )
        await state.set_state(CandidateRegistration.entering_skills)
    except ValueError:
        await message.answer("Пожалуйста, введите число (например, 2 или 5.5).")


@router.message(CandidateRegistration.entering_skills)
async def handle_skills(message: types.Message, state: FSMContext):
    skills_list = [skill.strip() for skill in message.text.split(",")]
    await state.update_data(skills=skills_list)
    await message.answer("<b>Шаг 4/6:</b> Укажите вашу текущую локацию (например, Москва или EU):")
    await state.set_state(CandidateRegistration.entering_location)


@router.message(CandidateRegistration.entering_location)
async def handle_location(message: types.Message, state: FSMContext):
    await state.update_data(location=message.text)
    await state.update_data(work_modes=[])
    await message.answer(
        "<b>Шаг 5/6:</b> Выберите желаемые форматы работы:",
        reply_markup=get_work_modes_keyboard()
    )
    await state.set_state(CandidateRegistration.entering_work_modes)


@router.callback_query(WorkModeCallback.filter(F.mode != "done"), CandidateRegistration.entering_work_modes)
async def handle_work_mode_selection(callback: types.CallbackQuery, callback_data: WorkModeCallback, state: FSMContext):
    data = await state.get_data()
    selected_modes = data.get("work_modes", [])

    if callback_data.mode not in selected_modes:
        selected_modes.append(callback_data.mode)
    else:
        selected_modes.remove(callback_data.mode)

    await state.update_data(work_modes=selected_modes)
    await callback.answer(f"Выбранные форматы: {', '.join(selected_modes) if selected_modes else 'пусто'}")


@router.callback_query(WorkModeCallback.filter(F.mode == "done"), CandidateRegistration.entering_work_modes)
async def handle_work_mode_done(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(
        "<b>Шаг 6/6:</b> Отлично! Теперь загрузите ваше резюме в формате PDF или DOCX (до 10 МБ).\n"
        "Если резюме пока нет, можете пропустить этот шаг, отправив команду /skip."
    )
    await state.set_state(CandidateRegistration.uploading_resume)


@router.message(Command("skip"), CandidateRegistration.uploading_resume)
async def handle_skip_resume(message: types.Message, state: FSMContext):
    await message.answer("Хорошо, вы сможете загрузить резюме позже через команду /profile.")
    await process_profile_completion(message, state)


@router.message(F.document, CandidateRegistration.uploading_resume)
async def handle_resume_upload(message: types.Message, state: FSMContext):

    file_info = await message.bot.get_file(message.document.file_id)
    file_data = await message.bot.download_file(file_info.file_path)

    metadata = await file_api_client.upload_resume(
        filename=message.document.file_name,
        file_data=file_data.read(),
        content_type=message.document.mime_type
    )

    if not metadata:
        await message.answer("❌ Произошла ошибка при загрузке файла. Попробуйте снова.")
        return

    metadata["telegram_file_id"] = message.document.file_id

    await state.update_data(resume_meta=metadata)
    await message.answer("✅ Резюме загружено и сохранено!")
    await process_profile_completion(message, state)


async def process_profile_completion(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    await message.answer("Спасибо! Сохраняю ваш обновленный профиль...")

    telegram_id = message.from_user.id

    profile_success = await candidate_api_client.update_candidate_profile(telegram_id, user_data)

    resume_success = True
    if "resume_meta" in user_data:
        resume_success = await candidate_api_client.confirm_resume_upload(telegram_id, user_data['resume_meta'])

    if profile_success and resume_success:
        await message.answer(
            "✅ Ваш профиль успешно создан/обновлен!\n\n"
            "Вы всегда можете его дополнить, используя команду /profile."
        )
    else:
        await message.answer(
            "❌ Произошла ошибка при обновлении профиля. Попробуйте позже."
        )
    await state.clear()


@router.message(CandidateRegistration.entering_skills)
async def handle_skills(message: types.Message, state: FSMContext):
    skills_text = message.text
    skills_list = [skill.strip() for skill in skills_text.split(",")]

    await state.update_data(skills=skills_list)

    user_data = await state.get_data()

    await message.answer("Спасибо! Сохраняю ваш обновленный профиль...")

    telegram_id = message.from_user.id
    success = await candidate_api_client.update_candidate_profile(telegram_id, user_data)

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
