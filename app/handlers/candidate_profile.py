from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from app.keyboards.inline import get_profile_actions_keyboard, ProfileAction, get_profile_edit_keyboard, \
    EditFieldCallback, get_work_modes_keyboard, WorkModeCallback, get_skill_kind_keyboard, SkillKindCallback, \
    get_skill_level_keyboard, SkillLevelCallback, get_confirmation_keyboard, ConfirmationCallback
from app.services.api_client import candidate_api_client
from aiogram.fsm.context import FSMContext
from app.states.candidate import CandidateRegistration, CandidateProfileEdit
from app.handlers.employer_search import format_candidate_profile

router = Router()

# --- PROFILE ---
@router.message(Command("profile"))
async def cmd_profile(message: Message | CallbackQuery, state: FSMContext):
    await state.clear()

    if isinstance(message, Message):
        user_id = message.from_user.id
    else:
        user_id = message.from_user.id
        message = message.message

    profile = await candidate_api_client.get_candidate_by_telegram_id(user_id)

    if not profile:
        await message.answer(
            "Ваш профиль не найден. Возможно, стоит начать с команды /start и зарегистрироваться как кандидат."
        )
        return

    await message.answer("Ваш текущий профиль:")
    await message.answer(
        format_candidate_profile(profile),
        reply_markup=get_profile_actions_keyboard()
    )

# --- ACTION ---
@router.callback_query(ProfileAction.filter())
async def handle_profile_action(callback: CallbackQuery, callback_data: ProfileAction, state: FSMContext):
    if callback_data.action == "edit":
        await state.set_state(CandidateProfileEdit.choosing_field)
        await callback.message.edit_text(
            "Какое поле вы хотите отредактировать?",
            reply_markup=get_profile_edit_keyboard()
        )
    elif callback_data.action == "upload_resume":
        await state.set_state(CandidateRegistration.uploading_resume)
        await callback.message.delete()
        await callback.message.answer(
            "Пожалуйста, загрузите ваше новое резюме (PDF/DOCX, до 10 МБ).\n"
            "Чтобы отменить, введите /cancel."
        )
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

    await callback.answer()

# --- TXT VALUE ---
@router.message(CandidateProfileEdit.editing_field)
async def handle_new_value(message: Message, state: FSMContext):
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

# --- BACK ---
@router.callback_query(EditFieldCallback.filter(F.field_name == "back"), CandidateProfileEdit.choosing_field)
async def handle_back_to_profile(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.delete()
    await cmd_profile(callback.message, state)
    await callback.answer()