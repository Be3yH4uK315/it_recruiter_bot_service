from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from app.keyboards.inline import get_role_selection_keyboard, RoleCallback
from app.services.api_client import candidate_api_client
from aiogram.fsm.context import FSMContext
from app.states.candidate import CandidateRegistration
from app.states.employer import EmployerSearch
from app.core.messages import Messages

router = Router()

@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(Messages.Common.START,
        reply_markup=get_role_selection_keyboard(),
    )

@router.callback_query(RoleCallback.filter(F.role_name == "candidate"))
async def cq_select_candidate(callback: CallbackQuery, state: FSMContext):
    await callback.answer()

    user = callback.from_user
    await candidate_api_client.create_candidate(
        telegram_id=user.id, telegram_name=user.username or user.full_name
    )

    await state.set_state(CandidateRegistration.entering_display_name)
    await callback.message.edit_text(Messages.CandidateRegistration.STEP_1)

@router.callback_query(RoleCallback.filter(F.role_name == "employer"))
async def cq_select_employer(callback: CallbackQuery, state: FSMContext):
    await state.set_state(EmployerSearch.entering_role)
    await callback.message.edit_text(Messages.EmployerSearch.STEP_1)
    await callback.answer()

@router.message(Command("search"))
async def cmd_search(message: Message, state: FSMContext):
    await state.set_state(EmployerSearch.entering_role)
    await message.answer(Messages.EmployerSearch.STEP_1)