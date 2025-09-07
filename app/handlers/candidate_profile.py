from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from app.keyboards.inline import get_profile_actions_keyboard, ProfileAction, get_profile_edit_keyboard, EditFieldCallback
from app.services.api_client import candidate_api_client
from aiogram.fsm.context import FSMContext
from app.states.candidate import CandidateRegistration, CandidateProfileEdit
from app.handlers.employer_search import format_candidate_profile

router = Router()


@router.message(Command("profile"))
async def cmd_profile(message: Message, state: FSMContext):
    await state.clear()
    profile = await candidate_api_client.get_candidate_by_telegram_id(message.from_user.id)

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


@router.callback_query(EditFieldCallback.filter(F.field_name != "back"), CandidateProfileEdit.choosing_field)
async def handle_field_chosen(callback: CallbackQuery, callback_data: EditFieldCallback, state: FSMContext):
    field = callback_data.field_name
    await state.update_data(field_to_edit=field)
    await state.set_state(CandidateProfileEdit.editing_field)

    prompts = {
        "headline_role": "Введите новую должность:",
        "experience_years": "Введите новый опыт в годах:",
        "skills": "Перечислите новые навыки через запятую:",
        "location": "Введите новую локацию:",
    }
    await callback.message.edit_text(prompts.get(field, "Введите новое значение:"))
    await callback.answer()


@router.message(CandidateProfileEdit.editing_field)
async def handle_new_value(message: Message, state: FSMContext):
    data = await state.get_data()
    field = data.get("field_to_edit")
    new_value = message.text

    update_payload = {}
    if field == "skills":
        update_payload[field] = [s.strip() for s in new_value.split(',')]
    else:
        update_payload[field] = new_value

    success = await candidate_api_client.update_candidate_profile(message.from_user.id, update_payload)

    if success:
        await message.answer("✅ Поле успешно обновлено!")
    else:
        await message.answer("❌ Произошла ошибка при обновлении.")

    await state.clear()
    await cmd_profile(message, state)


@router.callback_query(EditFieldCallback.filter(F.field_name == "back"), CandidateProfileEdit.choosing_field)
async def handle_back_to_profile(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.delete()
    await cmd_profile(callback.message, state)
    await callback.answer()