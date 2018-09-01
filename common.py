import asyncio
import logging
from typing import Dict, Tuple

from aiogram import Bot, types
from aiogram.contrib.fsm_storage.redis import RedisStorage
from aiogram.dispatcher import Dispatcher, FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

import config

logger = logging.getLogger(__name__)

loop = asyncio.get_event_loop()
bot = Bot(token=config.API_TOKEN, loop=loop)

storage = RedisStorage()
dp = Dispatcher(bot, storage=storage)


async def check_voting_end():
    """
    Проверяет что голосование закончено, и если оно закончено -- рассылает уведомление.
    Админу -- общий результат
    """
    admin_state = dp.current_state(chat=config.ADMIN_ID, user=config.ADMIN_ID)
    participants = (await admin_state.get_data())['participants']
    for participant_id in participants:
        participant_state = dp.current_state(chat=participant_id, user=participant_id)
        participant_data = await participant_state.get_data()
        if not participant_data['completed']:
            return
    result = {p_id: 0 for p_id in participants}
    for participant_id in participants:
        participant_state = dp.current_state(chat=participant_id, user=participant_id)
        candidates = (await participant_state.get_data())['candidates']
        for id, (_, bonus) in candidates.items():
            result[id] += bonus
    for participant_id, calc_bonus in result.items():
        participant_state = dp.current_state(chat=participant_id, user=participant_id)
        full_bonus = (await participant_state.get_data())['bonus']
        await bot.send_message(participant_id, 'Твоя премия: {0}. У тебя было {1}'.format(
            calc_bonus,
            full_bonus
        ))
    await bot.send_message(
        config.ADMIN_ID,
        '\n'.join(
            '{0}: {1}'.format(participants[p_id][0], bonus) for p_id, bonus in result.items()
        )
    )


async def send_vote_status(state: FSMContext):
    """
    Отправляет участнику голосования текущий статус его голосования
    """
    data = await state.get_data()
    message_parts = [
        'Короче, голосование',
        f"Остаток: {calculate_rest(data['bonus'], data['candidates'])}"
    ]
    inline_keyboard = InlineKeyboardMarkup(row_width=1)
    for id, (name, bonus) in data['candidates'].items():
        mark = '☑️' if bonus <= 0 else '✅'
        inline_keyboard.add(InlineKeyboardButton(f"{mark} {name}: {bonus}", callback_data=id))
    inline_keyboard.add(InlineKeyboardButton('Завершить голосование', callback_data='check'))
    message_id = (await bot.send_message(
        state.user,
        "\n".join(message_parts),
      reply_markup=inline_keyboard
    ))['message_id']
    await state.update_data({'vote_message_id': message_id})
    await state.set_state('voting')


def calculate_rest(full_bonus: int, candidates: Dict[int, Tuple[str, int]]) -> int:
    """
    Высчитывает остаток от премии, вычитая из полной сумму голосов
    """
    return full_bonus - sum(el[1] for el in candidates.values())
