from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from app.keyboards.inline import get_role_selection_keyboard, RoleCallback
from app.services.api_client import candidate_api_client
from aiogram.fsm.context import FSMContext
from app.states.candidate import CandidateRegistration
from app.states.employer import EmployerSearch

router = Router()


@router.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "👋 Добро пожаловать в IT Recruiter Bot!\n\n"
        "Я помогу вам найти работу или подобрать специалиста в IT.\n\n"
        "Пожалуйста, выберите вашу роль:",
        reply_markup=get_role_selection_keyboard(),
    )


@router.callback_query(RoleCallback.filter(F.role_name == "candidate"))
async def cq_select_candidate(callback: CallbackQuery, state: FSMContext):
    await callback.answer()

    user = callback.from_user
    await candidate_api_client.create_candidate(
        telegram_id=user.id, display_name=user.username or user.full_name
    )

    await state.set_state(CandidateRegistration.entering_headline_role)
    await callback.message.edit_text(
        "Отлично! Давайте заполним ваш профиль.\n\n"
        "<b>Шаг 1/3:</b> Введите вашу основную должность (например, Python Backend Developer):"
    )


@router.callback_query(RoleCallback.filter(F.role_name == "employer"))
async def cq_select_employer(callback: CallbackQuery, state: FSMContext):
    await state.set_state(EmployerSearch.entering_role)
    await callback.message.edit_text(
        "Отлично! Начинаем поиск кандидатов.\n\n"
        "<b>Шаг 1/3:</b> Какую должность вы ищете? (например, Frontend Developer)"
    )
    await callback.answer()
