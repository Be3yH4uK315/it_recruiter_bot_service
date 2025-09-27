from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters.callback_data import CallbackData
from typing import Literal, Set

class ContactsVisibilityCallback(CallbackData, prefix="vis"):
    """Callback для выбора видимости контактов."""
    visibility: str

class SkillKindCallback(CallbackData, prefix="skill_kind"):
    """Callback для выбора типа навыка."""
    kind: str

class SkillLevelCallback(CallbackData, prefix="skill_level"):
    """Callback для выбора уровня навыка."""
    level: int

class ConfirmationCallback(CallbackData, prefix="confirm"):
    """Callback для подтверждения действий."""
    action: Literal["yes", "no"]
    step: str

class RoleCallback(CallbackData, prefix="role"):
    """Callback для выбора роли."""
    role_name: str

class EditFieldCallback(CallbackData, prefix="edit_field"):
    """Callback для выбора поля редактирования."""
    field_name: str

class WorkModeCallback(CallbackData, prefix="work_mode"):
    """Callback для выбора формата работы."""
    mode: str

class ProfileAction(CallbackData, prefix="profile_action"):
    """Callback для действий с профилем."""
    action: str

class SearchResultDecision(CallbackData, prefix="search_dec"):
    """Callback для решений по результатам поиска."""
    action: str
    candidate_id: str

class SearchResultAction(CallbackData, prefix="search_res"):
    """Callback для действий с результатами поиска."""
    action: str
    candidate_id: str

def get_role_selection_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора роли."""
    keyboard = [
        [
            InlineKeyboardButton(
                text="👤 Я кандидат",
                callback_data=RoleCallback(role_name="candidate").pack(),
            )
        ],
        [
            InlineKeyboardButton(
                text="🏢 Я работодатель",
                callback_data=RoleCallback(role_name="employer").pack(),
            )
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_contacts_visibility_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура видимости контактов."""
    keyboard = [
        [
            InlineKeyboardButton(
                text="По запросу (on_request)",
                callback_data=ContactsVisibilityCallback(visibility="on_request").pack()
            )
        ],
        [
            InlineKeyboardButton(
                text="Публичные (public)",
                callback_data=ContactsVisibilityCallback(visibility="public").pack()
            )
        ],
        [
            InlineKeyboardButton(
                text="Скрытые (hidden)",
                callback_data=ContactsVisibilityCallback(visibility="hidden").pack()
            )
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_work_modes_keyboard(selected: Set[str] = set()) -> InlineKeyboardMarkup:
    """Клавиатура форматов работы (с отмеченными)."""
    modes = ["office", "remote", "hybrid", "done"]
    keyboard = [
        [
            InlineKeyboardButton(
                text=f"{'✅ ' if m in selected else ''}{m.capitalize()}" if m != "done" else "Готово",
                callback_data=WorkModeCallback(mode=m).pack(),
            ) for m in modes
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_profile_actions_keyboard(has_avatar: bool = False, has_resume: bool = False) -> InlineKeyboardMarkup:
    """Клавиатура выбора работы с профилем."""
    keyboard = [
        [InlineKeyboardButton(text="🖼️ Сменить аватар", callback_data=ProfileAction(action="upload_avatar").pack())],
        [InlineKeyboardButton(text="✏️ Редактировать профиль", callback_data=ProfileAction(action="edit").pack())],
        [InlineKeyboardButton(text="📄 Загрузить/обновить резюме", callback_data=ProfileAction(action="upload_resume").pack())]
    ]
    if has_avatar:
        keyboard.append([InlineKeyboardButton(text="🗑️ Удалить аватарку", callback_data=ProfileAction(action="delete_avatar").pack())])
    if has_resume:
        keyboard.append([InlineKeyboardButton(text="🗑️ Удалить резюме", callback_data=ProfileAction(action="delete_resume").pack())])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_initial_search_keyboard(candidate_id: str, has_resume: bool) -> InlineKeyboardMarkup:
    """Клавиатура выбора действия по результату поиска."""
    keyboard = [
        [
            InlineKeyboardButton(
                text="👍 Подходит",
                callback_data=SearchResultDecision(action="like", candidate_id=candidate_id).pack()
            ),
            InlineKeyboardButton(
                text="👎 Не подходит",
                callback_data=SearchResultDecision(action="dislike", candidate_id=candidate_id).pack()
            )
        ]
    ]

    if has_resume:
        keyboard.append([
            InlineKeyboardButton(
                text="📄 Скачать резюме",
                callback_data=SearchResultAction(action="get_resume", candidate_id=candidate_id).pack()
            )
        ])

    keyboard.append([
        InlineKeyboardButton(
            text="➡️ Следующий",
            callback_data=SearchResultAction(action="next", candidate_id="0").pack()
        )
    ])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_liked_candidate_keyboard(candidate_id: str) -> InlineKeyboardMarkup:
    """Клавиатура для лайкнутого кандидата."""
    keyboard = [
        [
            InlineKeyboardButton(
                text="📞 Показать контакты",
                callback_data=SearchResultAction(action="contact", candidate_id=candidate_id).pack()
            )
        ],
        [
            InlineKeyboardButton(
                text="➡️ Следующий",
                callback_data=SearchResultAction(action="next", candidate_id="0").pack()
            )
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_profile_edit_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура редактирования профиля."""
    keyboard = [
        [
            InlineKeyboardButton(text="Аватарка", callback_data=EditFieldCallback(field_name="avatar").pack()),
            InlineKeyboardButton(text="ФИО", callback_data=EditFieldCallback(field_name="display_name").pack()),
        ],
        [
            InlineKeyboardButton(text="Должность", callback_data=EditFieldCallback(field_name="headline_role").pack()),
            InlineKeyboardButton(text="Навыки", callback_data=EditFieldCallback(field_name="skills").pack()),
        ],
        [
            InlineKeyboardButton(text="Опыт работы", callback_data=EditFieldCallback(field_name="experiences").pack()),
            InlineKeyboardButton(text="Локация", callback_data=EditFieldCallback(field_name="location").pack()),
        ],
        [
            InlineKeyboardButton(text="Формат работы", callback_data=EditFieldCallback(field_name="work_modes").pack()),
            InlineKeyboardButton(text="Проекты", callback_data=EditFieldCallback(field_name="projects").pack()),
        ],
        [
            InlineKeyboardButton(text="📞 Контакты", callback_data=EditFieldCallback(field_name="contacts").pack()),
        ],
        [
            InlineKeyboardButton(text="⬅️ Назад", callback_data=EditFieldCallback(field_name="back").pack())
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_skill_kind_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора типа навыка."""
    buttons = [
        [InlineKeyboardButton(text="Hard Skill", callback_data=SkillKindCallback(kind="hard").pack())],
        [InlineKeyboardButton(text="Инструмент (Tool)", callback_data=SkillKindCallback(kind="tool").pack())],
        [InlineKeyboardButton(text="Язык (Language)", callback_data=SkillKindCallback(kind="language").pack())],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_skill_level_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора уровня навыка."""
    buttons = [
        [
            InlineKeyboardButton(text=str(i), callback_data=SkillLevelCallback(level=i).pack())
            for i in range(1, 6)
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_confirmation_keyboard(step: str) -> InlineKeyboardMarkup:
    """Клавиатура подтверждения действия."""
    buttons = [
        [
            InlineKeyboardButton(text="✅ Да", callback_data=ConfirmationCallback(action="yes", step=step).pack()),
            InlineKeyboardButton(text="❌ Нет, продолжить", callback_data=ConfirmationCallback(action="no", step=step).pack())
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)