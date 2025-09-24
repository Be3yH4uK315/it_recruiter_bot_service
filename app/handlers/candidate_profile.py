from aiogram import Router, F
from aiogram.filters import Command, StateFilter
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from app.keyboards.inline import (
    ProfileAction, get_profile_edit_keyboard, 
    EditFieldCallback, get_work_modes_keyboard, 
    WorkModeCallback, SkillKindCallback, 
    SkillLevelCallback, ConfirmationCallback,
    ContactsVisibilityCallback
)
from app.services.api_client import candidate_api_client
from app.states.candidate import CandidateFSM
from app.handlers.candidate_registration import (
    handle_block_entry, handle_confirm, handle_work_mode_selection, 
    handle_work_mode_done, handle_skill_kind, handle_skill_level,
    handle_contacts, handle_contacts_visibility, handle_resume_upload, 
    handle_avatar_upload, _show_profile
)
from app.core.messages import Messages
import logging

router = Router()
logger = logging.getLogger(__name__)

@router.message(Command("profile"))
async def cmd_profile(message: Message, state: FSMContext):
    logger.info(f"User {message.from_user.id} started /profile command")
    await state.update_data(mode='edit')
    await _show_profile(message, state)

@router.callback_query(ProfileAction.filter())
async def handle_profile_action(callback: CallbackQuery, callback_data: ProfileAction, state: FSMContext):
    logger.info(f"User {callback.from_user.id} selected profile action: {callback_data.action}")
    await state.update_data(mode='edit')
    if callback_data.action == "edit":
        await state.set_state(CandidateFSM.choosing_field)
        await callback.message.edit_text(Messages.Profile.CHOOSE_FIELD, reply_markup=get_profile_edit_keyboard())
    elif callback_data.action == "upload_resume":
        await state.update_data(file_type='resume')
        await state.set_state(CandidateFSM.uploading_file)
        await callback.message.delete()
        await callback.message.answer(Messages.Profile.UPLOAD_RESUME)
    elif callback_data.action == "upload_avatar":
        await state.update_data(file_type='avatar')
        await state.set_state(CandidateFSM.uploading_file)
        await callback.message.delete()
        await callback.message.answer(Messages.Profile.UPLOAD_AVATAR)
    elif callback_data.action == "delete_avatar":
        success = await candidate_api_client.delete_avatar(callback.from_user.id)
        if success:
            await callback.message.answer(Messages.Profile.DELETE_AVATAR_OK)
        else:
            await callback.message.answer(Messages.Profile.DELETE_AVATAR_ERROR)
        await callback.message.delete()
        await _show_profile(callback, state)
    elif callback_data.action == "delete_resume":
        success = await candidate_api_client.delete_resume(callback.from_user.id)
        if success:
            await callback.message.answer(Messages.Profile.DELETE_RESUME_OK)
        else:
            await callback.message.answer(Messages.Profile.DELETE_RESUME_ERROR)
        await callback.message.delete()
        await _show_profile(callback, state)
    await callback.answer()

@router.callback_query(EditFieldCallback.filter(F.field_name != "back"), CandidateFSM.choosing_field)
async def handle_field_chosen(callback: CallbackQuery, callback_data: EditFieldCallback, state: FSMContext):
    field = callback_data.field_name
    logger.info(f"User {callback.from_user.id} chose to edit field: {field}")
    await state.update_data(field_to_edit=field)
    prompts = {
        "display_name": Messages.Profile.ENTER_NAME,
        "headline_role": Messages.Profile.ENTER_ROLE,
        "location": Messages.Profile.ENTER_LOCATION,
    }
    if field in prompts:
        await state.update_data(current_field=field)
        await state.set_state(CandidateFSM.entering_basic_info)
        await callback.message.edit_text(prompts[field])
    elif field == "contacts":
        await state.set_state(CandidateFSM.editing_contacts)
        await callback.message.answer(Messages.Profile.ENTER_CONTACTS)
    elif field == "experiences":
        await state.update_data(block_type='experience', current_step='company', new_experiences=[])
        await state.set_state(CandidateFSM.block_entry)
        await callback.message.answer(Messages.Profile.ENTER_EXPERIENCE_COMPANY)
    elif field == "skills":
        await state.update_data(block_type='skill', current_step='name', new_skills=[])
        await state.set_state(CandidateFSM.block_entry)
        await callback.message.answer(Messages.Profile.ENTER_SKILL_NAME)
    elif field == "projects":
        await state.update_data(block_type='project', current_step='title', new_projects=[])
        await state.set_state(CandidateFSM.block_entry)
        await callback.message.answer(Messages.Profile.ENTER_PROJECT_TITLE)
    elif field == "work_modes":
        await state.update_data(option_type='work_modes', work_modes=[])
        await state.set_state(CandidateFSM.selecting_options)
        await callback.message.answer(
            Messages.Profile.WORK_MODE_SELECT,
            reply_markup=get_work_modes_keyboard(selected=set())
        )
    await callback.answer()

@router.callback_query(EditFieldCallback.filter(F.field_name == "back"), CandidateFSM.choosing_field)
async def handle_back_to_profile(callback: CallbackQuery, state: FSMContext):
    logger.info(f"User {callback.from_user.id} returned to profile")
    await state.clear()
    await _show_profile(callback, state)
    await callback.answer()

@router.message(CandidateFSM.block_entry)
async def handle_block_edit(message: Message, state: FSMContext):
    data = await state.get_data()
    block_type = data.get('block_type')
    current_step = data.get('current_step')
    logger.info(f"User {message.from_user.id} in block_entry, block_type={block_type}, current_step={current_step}")
    await handle_block_entry(message, state)

@router.callback_query(ConfirmationCallback.filter(), CandidateFSM.confirm_action)
async def handle_confirm_edit(callback: CallbackQuery, callback_data: ConfirmationCallback, state: FSMContext):
    data = await state.get_data()
    action_type = data.get('action_type')
    logger.info(f"User {callback.from_user.id} in confirm_action, action_type={action_type}")
    await handle_confirm(callback, callback_data, state)

@router.callback_query(WorkModeCallback.filter(F.mode != "done"), CandidateFSM.selecting_options)
async def handle_work_mode_selection_edit(callback: CallbackQuery, callback_data: WorkModeCallback, state: FSMContext):
    logger.info(f"User {callback.from_user.id} selecting work mode: {callback_data.mode}")
    await handle_work_mode_selection(callback, callback_data, state)

@router.callback_query(WorkModeCallback.filter(F.mode == "done"), CandidateFSM.selecting_options)
async def handle_work_mode_done_edit(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    logger.info(f"User {callback.from_user.id} finished work mode selection")
    await handle_work_mode_done(callback, state)

@router.callback_query(SkillKindCallback.filter(), CandidateFSM.selecting_options)
async def handle_skill_kind_edit(callback: CallbackQuery, callback_data: SkillKindCallback, state: FSMContext):
    logger.info(f"User {callback.from_user.id} selected skill kind: {callback_data.kind}")
    await handle_skill_kind(callback, callback_data, state)

@router.callback_query(SkillLevelCallback.filter(), CandidateFSM.selecting_options)
async def handle_skill_level_edit(callback: CallbackQuery, callback_data: SkillLevelCallback, state: FSMContext):
    logger.info(f"User {callback.from_user.id} selected skill level: {callback_data.level}")
    await handle_skill_level(callback, callback_data, state)

@router.message(CandidateFSM.editing_contacts)
@router.message(Command("skip"), CandidateFSM.editing_contacts)
async def handle_contacts_edit(message: Message, state: FSMContext):
    logger.info(f"User {message.from_user.id} entered contacts")
    await handle_contacts(message, state)

@router.callback_query(ContactsVisibilityCallback.filter(), CandidateFSM.selecting_options)
async def handle_contacts_visibility_edit(callback: CallbackQuery, callback_data: ContactsVisibilityCallback, state: FSMContext):
    logger.info(f"User {callback.from_user.id} selected contacts visibility: {callback_data.visibility}")
    await handle_contacts_visibility(callback, callback_data, state)

@router.message(F.document, CandidateFSM.uploading_file)
async def handle_resume_upload_edit(message: Message, state: FSMContext):
    logger.info(f"User {message.from_user.id} uploading resume")
    await handle_resume_upload(message, state)

@router.message(F.photo, CandidateFSM.uploading_file)
async def handle_avatar_upload_edit(message: Message, state: FSMContext):
    logger.info(f"User {message.from_user.id} uploading avatar")
    await handle_avatar_upload(message, state)

@router.message(Command("cancel"), StateFilter(CandidateFSM))
async def cancel_handler(message: Message, state: FSMContext):
    logger.info(f"User {message.from_user.id} cancelled FSM")
    await state.clear()
    await message.answer(Messages.Common.CANCELLED)

@router.message(StateFilter(CandidateFSM))
async def invalid_input(message: Message, state: FSMContext):
    current_state = await state.get_state()
    logger.warning(f"Invalid input from user {message.from_user.id} in state {current_state}: {message.text}")
    await message.answer(Messages.Common.INVALID_INPUT)