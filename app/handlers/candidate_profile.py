from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from app.keyboards.inline import get_profile_actions_keyboard, ProfileAction, get_profile_edit_keyboard, \
    EditFieldCallback, get_work_modes_keyboard, WorkModeCallback, get_skill_kind_keyboard, SkillKindCallback, \
    get_skill_level_keyboard, SkillLevelCallback, get_confirmation_keyboard, ConfirmationCallback
from app.services.api_client import candidate_api_client, file_api_client
from aiogram.fsm.context import FSMContext
from app.states.candidate import CandidateProfileEdit
from app.handlers.employer_search import format_candidate_profile

router = Router()

# --- PROFILE ---
@router.message(Command("profile"))
async def cmd_profile(message: Message, state: FSMContext, telegram_id: int = None):
    await state.clear()

    if isinstance(message, CallbackQuery):
        target_message = message.message
        user_id = message.from_user.id
    else:
        target_message = message
        user_id = message.from_user.id

    profile = await candidate_api_client.get_candidate_by_telegram_id(user_id)

    if not profile:
        await target_message.answer(
            "Ваш профиль не найден. Возможно, стоит начать с команды /start."
        )
        return

    await target_message.answer("Ваш текущий профиль:")

    avatar_url = None
    if profile.get("avatars"):
        avatar_file_id = profile["avatars"][0]["file_id"]
        avatar_url = await file_api_client.get_download_url_by_file_id(avatar_file_id)

    caption = format_candidate_profile(profile)
    has_avatar = bool(profile.get("avatars"))
    has_resume = bool(profile.get("resumes"))
    keyboard = get_profile_actions_keyboard(has_avatar=has_avatar, has_resume=has_resume)

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

    if isinstance(message, CallbackQuery):
        await message.answer()

# --- ACTION ---
@router.callback_query(ProfileAction.filter())
async def handle_profile_action(callback: CallbackQuery, callback_data: ProfileAction, state: FSMContext):
    telegram_id = callback.from_user.id
    print(f"handle_profile_action called with telegram_id={telegram_id}, action={callback_data.action}")
    if callback_data.action == "edit":
        await state.set_state(CandidateProfileEdit.choosing_field)
        await callback.message.edit_text(
            "Какое поле вы хотите отредактировать?",
            reply_markup=get_profile_edit_keyboard()
        )
    elif callback_data.action == "upload_resume":
        await state.set_state(CandidateProfileEdit.uploading_resume)
        await callback.message.delete()
        await callback.message.answer(
            "Пожалуйста, загрузите ваше новое резюме (PDF/DOCX, до 10 МБ).\n"
            "Чтобы отменить, введите /cancel."
        )
    elif callback_data.action == "upload_avatar":
        await state.set_state(CandidateProfileEdit.uploading_avatar)
        await callback.message.delete()
        await callback.message.answer(
            "Пожалуйста, отправьте фото, которое хотите установить как аватар.\n"
            "Чтобы отменить, введите /cancel."
        )
    elif callback_data.action == "delete_avatar":
        success = await candidate_api_client.delete_avatar(callback.from_user.id)
        if success:
            await callback.message.answer("✅ Аватарка удалена!")
        else:
            await callback.message.answer("❌ Ошибка при удалении аватарки.")
        await callback.message.delete()
        await cmd_profile(callback.message, state, telegram_id=telegram_id)
    elif callback_data.action == "delete_resume":
        success = await candidate_api_client.delete_resume(callback.from_user.id)
        if success:
            await callback.message.answer("✅ Резюме удалено!")
        else:
            await callback.message.answer("❌ Ошибка при удалении резюме.")
        await callback.message.delete()
        await cmd_profile(callback.message, state, telegram_id=telegram_id)
    await callback.answer()

# --- CHOSEN ---
@router.callback_query(EditFieldCallback.filter(F.field_name != "back"), CandidateProfileEdit.choosing_field)
async def handle_field_chosen(callback: CallbackQuery, callback_data: EditFieldCallback, state: FSMContext):
    field = callback_data.field_name
    await state.update_data(field_to_edit=field)

    prompts = {
        "display_name": "Введите новые Фамилию Имя Отчество (ФИО):",
        "headline_role": "Введите новую должность:",
        "experience_years": "Введите новый опыт в годах:",
        "location": "Введите новую локацию:",
    }

    if field in prompts:
        await state.set_state(CandidateProfileEdit.editing_field)
        await callback.message.edit_text(prompts[field])

    elif field == "skills":
        await state.update_data(new_skills=[])
        await state.set_state(CandidateProfileEdit.editing_skill_name)
        await callback.message.edit_text(
            "Редактирование навыков. Ваши текущие навыки будут полностью заменены.\n\n"
            "Введите название первого навыка:"
        )

    elif field == "projects":
        await state.update_data(new_projects=[])
        await state.set_state(CandidateProfileEdit.editing_project_title)
        await callback.message.edit_text(
            "Редактирование проектов. Ваши текущие проекты будут полностью заменены.\n\n"
            "Введите название первого проекта:"
        )

    elif field == "work_modes":
        await state.update_data(work_modes=[])
        await state.set_state(CandidateProfileEdit.editing_work_modes)
        await callback.message.edit_text(
            "Выберите желаемые форматы работы:",
            reply_markup=get_work_modes_keyboard()
        )

    elif field == "avatar":
        await state.set_state(CandidateProfileEdit.uploading_avatar)
        await callback.message.edit_text("Пожалуйста, отправьте фото для новой аватарки.")

    await callback.answer()

# --- TXT VALUE ---
@router.message(CandidateProfileEdit.editing_field)
async def handle_new_value(message: Message, state: FSMContext):
    telegram_id = message.from_user.id
    print(f"handle_new_value called with telegram_id={telegram_id}")
    data = await state.get_data()
    field = data.get("field_to_edit")
    update_payload = {field: message.text}

    success = await candidate_api_client.update_candidate_profile(message.from_user.id, update_payload)

    if success:
        await message.answer("✅ Поле успешно обновлено!")
    else:
        await message.answer("❌ Произошла ошибка при обновлении.")

    await state.clear()
    await cmd_profile(message, state)

# --- SKILLS ---
@router.message(CandidateProfileEdit.editing_skill_name)
async def handle_edit_skill_name(message: Message, state: FSMContext):
    await state.update_data(current_skill_name=message.text)
    await message.answer("Укажите тип этого навыка:", reply_markup=get_skill_kind_keyboard())
    await state.set_state(CandidateProfileEdit.editing_skill_kind)

@router.callback_query(SkillKindCallback.filter(), CandidateProfileEdit.editing_skill_kind)
async def handle_edit_skill_kind(callback: CallbackQuery, callback_data: SkillKindCallback, state: FSMContext):
    await state.update_data(current_skill_kind=callback_data.kind)
    await callback.message.edit_text("Оцените свой уровень владения (1-5):", reply_markup=get_skill_level_keyboard())
    await state.set_state(CandidateProfileEdit.editing_skill_level)
    await callback.answer()

@router.callback_query(SkillLevelCallback.filter(), CandidateProfileEdit.editing_skill_level)
async def handle_edit_skill_level(callback: CallbackQuery, callback_data: SkillLevelCallback, state: FSMContext):
    data = await state.get_data()
    new_skill = {
        "skill": data.get("current_skill_name"),
        "kind": data.get("current_skill_kind"),
        "level": callback_data.level
    }
    skills_list = data.get("new_skills", [])
    skills_list.append(new_skill)
    await state.update_data(new_skills=skills_list)
    await callback.message.edit_text(
        f"✅ Навык '{new_skill['skill']}' добавлен. Хотите добавить еще один?",
        reply_markup=get_confirmation_keyboard(step="edit_skill")
    )
    await state.set_state(CandidateProfileEdit.confirm_edit_another_skill)
    await callback.answer()

@router.callback_query(ConfirmationCallback.filter(F.step == "edit_skill"),
                       CandidateProfileEdit.confirm_edit_another_skill)
async def handle_confirm_edit_skill(callback: CallbackQuery, callback_data: ConfirmationCallback,
                                    state: FSMContext):
    if callback_data.action == "yes":
        await callback.message.edit_text("Введите название следующего навыка:")
        await state.set_state(CandidateProfileEdit.editing_skill_name)
    else:
        data = await state.get_data()
        update_payload = {"skills": data.get("new_skills", [])}
        success = await candidate_api_client.update_candidate_profile(callback.from_user.id, update_payload)
        if success:
            await callback.message.answer("✅ Навыки успешно обновлены!")
        else:
            await callback.message.answer("❌ Произошла ошибка при обновлении.")

        await state.clear()
        await callback.message.delete()
        await cmd_profile(callback, state)
    await callback.answer()

# --- PROJECT ---
@router.message(CandidateProfileEdit.editing_project_title)
async def handle_edit_project_title(message: Message, state: FSMContext):
    await state.update_data(current_project_title=message.text)
    await message.answer("Теперь добавьте краткое описание проекта. Можно отправить /skip.")
    await state.set_state(CandidateProfileEdit.editing_project_description)

@router.message(CandidateProfileEdit.editing_project_description)
@router.message(Command("skip"), CandidateProfileEdit.editing_project_description)
async def handle_edit_project_description(message: Message, state: FSMContext):
    description = message.text if message.text and not message.text.startswith('/skip') else None
    await state.update_data(current_project_description=description)
    await message.answer("Вставьте ссылки на проект (GitHub, сайт), если есть. Можно /skip.")
    await state.set_state(CandidateProfileEdit.editing_project_links)

@router.message(CandidateProfileEdit.editing_project_links)
@router.message(Command("skip"), CandidateProfileEdit.editing_project_links)
async def handle_edit_project_links(message: Message, state: FSMContext):
    data = await state.get_data()
    links = {"main_link": message.text} if message.text and not message.text.startswith('/skip') else {}
    new_project = {
        "title": data.get("current_project_title"),
        "description": data.get("current_project_description"),
        "links": links
    }
    projects_list = data.get("new_projects", [])
    projects_list.append(new_project)
    await state.update_data(new_projects=projects_list)
    await message.answer(
        f"✅ Проект '{new_project['title']}' добавлен. Хотите добавить еще один?",
        reply_markup=get_confirmation_keyboard(step="edit_project")
    )
    await state.set_state(CandidateProfileEdit.confirm_edit_another_project)

@router.callback_query(ConfirmationCallback.filter(F.step == "edit_project"),
                       CandidateProfileEdit.confirm_edit_another_project)
async def handle_confirm_edit_project(callback: CallbackQuery, callback_data: ConfirmationCallback,
                                      state: FSMContext):
    if callback_data.action == "yes":
        await callback.message.edit_text("Введите название следующего проекта:")
        await state.set_state(CandidateProfileEdit.editing_project_title)
    else:
        data = await state.get_data()
        update_payload = {"projects": data.get("new_projects", [])}
        success = await candidate_api_client.update_candidate_profile(callback.from_user.id, update_payload)
        if success:
            await callback.message.answer("✅ Проекты успешно обновлены!")
        else:
            await callback.message.answer("❌ Произошла ошибка при обновлении.")

        await state.clear()
        await callback.message.delete()
        await cmd_profile(callback, state)
    await callback.answer()

# --- WORK MODE ---
@router.callback_query(WorkModeCallback.filter(F.mode != "done"), CandidateProfileEdit.editing_work_modes)
async def handle_edit_work_mode_selection(callback: CallbackQuery, callback_data: WorkModeCallback,
                                          state: FSMContext):
    data = await state.get_data()
    selected_modes = data.get("work_modes", [])
    if callback_data.mode not in selected_modes:
        selected_modes.append(callback_data.mode)
    else:
        selected_modes.remove(callback_data.mode)
    await state.update_data(work_modes=selected_modes)
    await callback.answer(f"Выбрано: {', '.join(selected_modes) if selected_modes else 'пусто'}")

@router.callback_query(WorkModeCallback.filter(F.mode == "done"), CandidateProfileEdit.editing_work_modes)
async def handle_edit_work_mode_done(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    update_payload = {"work_modes": data.get("work_modes", [])}
    success = await candidate_api_client.update_candidate_profile(callback.from_user.id, update_payload)
    if success:
        await callback.message.answer("✅ Форматы работы успешно обновлены!")
    else:
        await callback.message.answer("❌ Произошла ошибка при обновлении.")

    await state.clear()
    await callback.message.delete()
    await cmd_profile(callback, state)
    await callback.answer()

# --- RESUME ---
@router.message(F.document, CandidateProfileEdit.uploading_resume)
async def handle_resume_upload(message: Message, state: FSMContext):
    user_telegram_id = message.from_user.id
    print(f"handle_resume_upload called with telegram_id={user_telegram_id}")

    await message.answer("Обрабатываю резюме...")

    document = message.document
    if document.mime_type not in ['application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document']:
        await message.answer("❌ Пожалуйста, загрузите файл в формате PDF или DOCX.")
        return
    if document.file_size > 10 * 1024 * 1024:  # 10MB limit
        await message.answer("❌ Файл слишком большой (максимум 10 МБ).")
        return

    file_info = await message.bot.get_file(document.file_id)
    file_data = await message.bot.download_file(file_info.file_path)

    old_file_id_to_delete = None
    candidate_profile = await candidate_api_client.get_candidate_by_telegram_id(user_telegram_id)
    if candidate_profile and candidate_profile.get("resumes"):
        old_file_id_to_delete = candidate_profile["resumes"][0]["file_id"]

    extension = document.file_name.split('.')[-1].lower()
    content_type = 'application/pdf' if extension == 'pdf' else 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' if extension == 'docx' else 'application/pdf'
    filename = document.file_name

    file_response = await file_api_client.upload_file(
        filename=filename,
        file_data=file_data.read(),
        content_type=content_type,
        owner_id=user_telegram_id,
        file_type='resume'
    )

    if not file_response:
        await message.answer("❌ Ошибка при загрузке резюме. Попробуйте снова.")
        return

    new_file_id = file_response['id']
    success = await candidate_api_client.replace_resume(
        telegram_id=user_telegram_id,
        file_id=new_file_id
    )

    if success:
        await message.answer("✅ Резюме успешно обновлено!")
        if old_file_id_to_delete:
            await file_api_client.delete_file(old_file_id_to_delete, owner_telegram_id=user_telegram_id)
            print(f"Old resume file {old_file_id_to_delete} deleted.")
    else:
        await message.answer("❌ Произошла ошибка при обновлении резюме.")

    await state.clear()
    await cmd_profile(message, state)

# --- AVATAR ---
@router.message(F.photo, CandidateProfileEdit.uploading_avatar)
async def handle_avatar_upload(message: Message, state: FSMContext):
    user_telegram_id = message.from_user.id
    print(f"handle_avatar_upload called with telegram_id={user_telegram_id}")

    await message.answer("Обрабатываю фото...")

    photo = message.photo[-1]
    file_info = await message.bot.get_file(photo.file_id)
    file_data = await message.bot.download_file(file_info.file_path)

    old_file_id_to_delete = None
    candidate_profile = await candidate_api_client.get_candidate_by_telegram_id(user_telegram_id)
    if candidate_profile and candidate_profile.get("avatars"):
        old_file_id_to_delete = candidate_profile["avatars"][0]["file_id"]

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
        await message.answer("✅ Аватар успешно обновлен!")
        if old_file_id_to_delete:
            await file_api_client.delete_file(old_file_id_to_delete, owner_telegram_id=user_telegram_id)
            print(f"Old avatar file {old_file_id_to_delete} deleted.")
    else:
        await message.answer("❌ Произошла ошибка при обновлении аватара.")

    await state.clear()
    await cmd_profile(message, state)

# --- BACK ---
@router.callback_query(EditFieldCallback.filter(F.field_name == "back"), CandidateProfileEdit.choosing_field)
async def handle_back_to_profile(callback: CallbackQuery, state: FSMContext):
    telegram_id = callback.from_user.id
    print(f"handle_back_to_profile called with telegram_id={telegram_id}")
    await state.clear()
    await callback.message.delete()
    await cmd_profile(callback.message, state)
    await callback.answer()