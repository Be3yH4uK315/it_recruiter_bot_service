from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command
from app.states.candidate import CandidateRegistration
from app.services.api_client import candidate_api_client, file_api_client
from app.keyboards.inline import (
    get_work_modes_keyboard, WorkModeCallback,
    get_skill_kind_keyboard, SkillKindCallback,
    get_skill_level_keyboard, SkillLevelCallback,
    get_confirmation_keyboard, ConfirmationCallback
)

router = Router()

# --- DISPALY NAME ---
@router.message(CandidateRegistration.entering_display_name)
async def handle_display_name(message: types.Message, state: FSMContext):
    await state.update_data(display_name=message.text)
    await message.answer(
        "<b>Шаг 2/9:</b> Приятно познакомиться! Теперь введите вашу основную должность (например, Python Backend Developer):"
    )

    await state.set_state(CandidateRegistration.entering_headline_role)

# --- HEADLINE ROLE ---
@router.message(CandidateRegistration.entering_headline_role)
async def handle_headline_role(message: types.Message, state: FSMContext):
    await state.update_data(headline_role=message.text)
    await message.answer(
        "<b>Шаг 3/9:</b> Отлично! Теперь укажите ваш опыт работы в годах (например, 3.5):"
    )
    await state.set_state(CandidateRegistration.entering_experience_years)

# --- EXPERIENCE YEARS ---
@router.message(CandidateRegistration.entering_experience_years)
async def handle_experience_years(message: types.Message, state: FSMContext):
    try:
        experience = float(message.text.replace(",", "."))
        await state.update_data(experience_years=experience)
        await state.update_data(skills=[], projects=[])
        await message.answer(
            "<b>Шаг 4/9: Блок навыков.</b>\n\n"
            "Давайте добавим ваш первый навык. Введите его название (например, Python):"
        )
        await state.set_state(CandidateRegistration.adding_skill_name)
    except ValueError:
        await message.answer("Пожалуйста, введите число (например, 2 или 5.5).")

# --- SKILLS ---
@router.message(CandidateRegistration.adding_skill_name)
async def handle_skill_name(message: types.Message, state: FSMContext):
    await state.update_data(current_skill_name=message.text)
    await message.answer("Отлично. Укажите тип этого навыка:", reply_markup=get_skill_kind_keyboard())
    await state.set_state(CandidateRegistration.adding_skill_kind)

@router.callback_query(SkillKindCallback.filter(), CandidateRegistration.adding_skill_kind)
async def handle_skill_kind(callback: types.CallbackQuery, callback_data: SkillKindCallback, state: FSMContext):
    await state.update_data(current_skill_kind=callback_data.kind)
    await callback.message.edit_text("Понял. Теперь оцените свой уровень владения по шкале от 1 до 5:", reply_markup=get_skill_level_keyboard())
    await state.set_state(CandidateRegistration.adding_skill_level)
    await callback.answer()

@router.callback_query(SkillLevelCallback.filter(), CandidateRegistration.adding_skill_level)
async def handle_skill_level(callback: types.CallbackQuery, callback_data: SkillLevelCallback, state: FSMContext):
    data = await state.get_data()

    new_skill = {
        "skill": data.get("current_skill_name"),
        "kind": data.get("current_skill_kind"),
        "level": callback_data.level
    }

    skills_list = data.get("skills", [])
    skills_list.append(new_skill)
    await state.update_data(skills=skills_list)

    await state.update_data(current_skill_name=None, current_skill_kind=None)

    await callback.message.edit_text(
        f"✅ Навык '{new_skill['skill']}' добавлен. Хотите добавить еще один?",
        reply_markup=get_confirmation_keyboard(step="add_skill")
    )
    await state.set_state(CandidateRegistration.confirm_add_another_skill)
    await callback.answer()

@router.callback_query(ConfirmationCallback.filter(F.step == "add_skill"), CandidateRegistration.confirm_add_another_skill)
async def handle_confirm_add_skill(callback: types.CallbackQuery, callback_data: ConfirmationCallback, state: FSMContext):
    if callback_data.action == "yes":
        await callback.message.edit_text("Введите название следующего навыка:")
        await state.set_state(CandidateRegistration.adding_skill_name)
    else:
        await callback.message.edit_text(
            "<b>Шаг 5/9: Блок проектов.</b>\n\n"
            "Хотите добавить проекты/портфолио в свой профиль?",
            reply_markup=get_confirmation_keyboard(step="start_project")
        )
        await state.set_state(CandidateRegistration.confirm_start_adding_projects)
    await callback.answer()

# --- PROJECT ---
@router.callback_query(ConfirmationCallback.filter(F.step == "start_project"),
                       CandidateRegistration.confirm_start_adding_projects)
async def handle_start_projects(callback: types.CallbackQuery, callback_data: ConfirmationCallback, state: FSMContext):
    if callback_data.action == "yes":
        await callback.message.edit_text("Отлично! Введите название вашего проекта:")
        await state.set_state(CandidateRegistration.adding_project_title)
    else:
        await callback.message.delete()
        await callback.message.answer("Хорошо, пропускаем этот шаг.")
        await ask_for_location(callback.message, state)
    await callback.answer()

@router.message(CandidateRegistration.adding_project_title)
async def handle_project_title(message: types.Message, state: FSMContext):
    await state.update_data(current_project_title=message.text)
    await message.answer("Теперь добавьте краткое описание проекта. Можно отправить /skip, чтобы пропустить.")
    await state.set_state(CandidateRegistration.adding_project_description)

@router.message(CandidateRegistration.adding_project_description)
@router.message(Command("skip"), CandidateRegistration.adding_project_description)
async def handle_project_description(message: types.Message, state: FSMContext):
    if message.text and not message.text.startswith('/skip'):
        await state.update_data(current_project_description=message.text)
    else:
        await state.update_data(current_project_description=None)

    await message.answer("И последнее: вставьте ссылки на проект (GitHub, сайт), если есть. Можно отправить /skip.")
    await state.set_state(CandidateRegistration.adding_project_links)

@router.message(CandidateRegistration.adding_project_links)
@router.message(Command("skip"), CandidateRegistration.adding_project_links)
async def handle_project_links(message: types.Message, state: FSMContext):
    data = await state.get_data()
    links = {}
    if message.text and not message.text.startswith('/skip'):
        links = {"main_link": message.text}

    new_project = {
        "title": data.get("current_project_title"),
        "description": data.get("current_project_description"),
        "links": links
    }

    projects_list = data.get("projects", [])
    projects_list.append(new_project)
    await state.update_data(projects=projects_list)
    await state.update_data(current_project_title=None, current_project_description=None)

    await message.answer(
        f"✅ Проект '{new_project['title']}' добавлен. Хотите добавить еще один?",
        reply_markup=get_confirmation_keyboard(step="add_project")
    )
    await state.set_state(CandidateRegistration.confirm_add_another_project)

@router.callback_query(ConfirmationCallback.filter(F.step == "add_project"),
                       CandidateRegistration.confirm_add_another_project)
async def handle_confirm_add_project(callback: types.CallbackQuery, callback_data: ConfirmationCallback,
                                     state: FSMContext):
    if callback_data.action == "yes":
        await callback.message.edit_text("Введите название следующего проекта:")
        await state.set_state(CandidateRegistration.adding_project_title)
    else:
        await callback.message.delete()
        await ask_for_location(callback.message, state)
    await callback.answer()

# --- LOCATION ---
async def ask_for_location(message: types.Message, state: FSMContext):
    await message.answer("<b>Шаг 6/9:</b> Укажите вашу текущую локацию (например, Москва или EU):")
    await state.set_state(CandidateRegistration.entering_location)

@router.message(CandidateRegistration.entering_location)
async def handle_location(message: types.Message, state: FSMContext):
    await state.update_data(location=message.text)
    await state.update_data(work_modes=[])
    await message.answer(
        "<b>Шаг 7/9:</b> Выберите желаемые форматы работы:",
        reply_markup=get_work_modes_keyboard()
    )
    await state.set_state(CandidateRegistration.entering_work_modes)

# --- WORK MODE ---
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
    telegram_id = callback.from_user.id
    print(f"handle_work_mode_done called with telegram_id={telegram_id}")
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(
        "<b>Шаг 8/9:</b> Отлично! Теперь загрузите ваше резюме в формате PDF или DOCX (до 10 МБ).\n"
        "Если резюме пока нет, можете пропустить этот шаг, отправив команду /skip."
    )
    await state.set_state(CandidateRegistration.uploading_resume)
    await callback.answer()

# --- RESUME ---
@router.message(F.document, CandidateRegistration.uploading_resume)
async def handle_resume_upload(message: types.Message, state: FSMContext):
    user_telegram_id = message.from_user.id
    print(f"handle_resume_upload called with telegram_id={user_telegram_id}")

    await message.answer("Загружаю ваше резюме...")
    file_info = await message.bot.get_file(message.document.file_id)
    file_data = await message.bot.download_file(file_info.file_path)

    new_file_response = await file_api_client.upload_file(
        filename=message.document.file_name,
        file_data=file_data.read(),
        content_type=message.document.mime_type,
        owner_id=user_telegram_id,
        file_type='resume'
    )
    if not new_file_response:
        await message.answer("❌ Ошибка при загрузке файла. Попробуйте снова.")
        return

    new_file_id = new_file_response['id']

    old_file_id_to_delete = None
    candidate_profile = await candidate_api_client.get_candidate_by_telegram_id(user_telegram_id)
    if candidate_profile and candidate_profile.get("resumes"):
        old_file_id_to_delete = candidate_profile["resumes"][0]["file_id"]

    await message.answer("Привязываю резюме к вашему профилю...")
    success_replace = await candidate_api_client.replace_resume(user_telegram_id, new_file_id)
    if not success_replace:
        await message.answer("❌ Ошибка при привязке резюме к профилю.")
        return

    if old_file_id_to_delete:
        await file_api_client.delete_file(old_file_id_to_delete, owner_telegram_id=user_telegram_id)
        print(f"Old resume file {old_file_id_to_delete} has been marked for deletion.")

    user_data = await state.get_data()
    await message.answer("Сохраняю остальные данные профиля...")

    profile_success = await candidate_api_client.update_candidate_profile(user_telegram_id, user_data)

    if profile_success:
        await message.answer(
            "<b>Шаг 9/9:</b> Загрузите аватарку (фото, до 5 МБ).\n"
            "Если хотите пропустить, отправьте /skip."
        )
        await state.set_state(CandidateRegistration.uploading_avatar)
    else:
        await message.answer("❌ Произошла ошибка при обновлении данных профиля.")
        await state.clear()

@router.message(Command("skip"), CandidateRegistration.uploading_resume)
async def handle_skip_resume(message: types.Message, state: FSMContext):
    user_telegram_id = message.from_user.id
    print(f"handle_skip_resume called with telegram_id={user_telegram_id}")
    await message.answer("Хорошо, вы сможете загрузить резюме позже через команду /profile.")

    user_data = await state.get_data()
    telegram_id = message.from_user.id

    await message.answer("Спасибо! Сохраняю ваш профиль...")

    profile_success = await candidate_api_client.update_candidate_profile(telegram_id, user_data)

    if profile_success:
        await message.answer(
            "<b>Шаг 9/9:</b> Загрузите аватарку (фото, до 5 МБ).\n"
            "Если хотите пропустить, отправьте /skip."
        )
        await state.set_state(CandidateRegistration.uploading_avatar)
    else:
        await message.answer(
            "❌ Произошла ошибка при обновлении профиля. Попробуйте позже."
        )
        await state.clear()

# --- AVATAR ---
@router.message(F.photo, CandidateRegistration.uploading_avatar)
async def handle_avatar_upload(message: types.Message, state: FSMContext):
    user_telegram_id = message.from_user.id
    print(f"handle_avatar_upload (registration) called with telegram_id={user_telegram_id}")

    await message.answer("Обрабатываю фото...")

    photo = message.photo[-1]
    file_info = await message.bot.get_file(photo.file_id)
    file_data = await message.bot.download_file(file_info.file_path)

    extension = file_info.file_path.split('.')[-1].lower()
    content_type = 'image/jpeg' if extension in ['jpg', 'jpeg'] else 'image/png' if extension == 'png' else 'image/jpeg'
    filename = f"{photo.file_unique_id}.{extension}"

    file_response = await file_api_client.upload_file(
        filename=filename,
        file_data=file_data.read(),
        content_type=content_type,
        owner_id=user_telegram_id,
        file_type='avatar'
    )
    if not file_response:
        await message.answer("❌ Ошибка при загрузке фото. Попробуйте снова.")
        return

    new_file_id = file_response['id']
    success = await candidate_api_client.replace_avatar(
        telegram_id=user_telegram_id,
        file_id=new_file_id
    )

    if success:
        await message.answer(
            "✅ Ваш профиль успешно создан/обновлен с аватаркой!\n\n"
            "Вы всегда можете его дополнить, используя команду /profile."
        )
    else:
        await message.answer(
            "❌ Произошла ошибка при обновлении аватара. Профиль сохранён без аватарки."
        )

    await state.clear()

@router.message(Command("skip"), CandidateRegistration.uploading_avatar)
async def handle_skip_avatar(message: types.Message, state: FSMContext):
    user_telegram_id = message.from_user.id
    print(f"handle_skip_avatar called with telegram_id={user_telegram_id}")
    await message.answer(
        "✅ Ваш профиль успешно создан/обновлен без аватарки!\n\n"
        "Вы всегда можете добавить аватарку через команду /profile."
    )
    await state.clear()

# --- CANCEL ---
@router.message(Command("cancel"))
async def cancel_handler(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is None:
        return

    await state.clear()
    await message.answer("Действие отменено.")
