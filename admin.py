from typing import Dict

from aiogram import types

import config
from common import check_voting_end, dp, bot, send_vote_status


def check_admin(message):
    """
    Проверяет что автор сообщения админ
    """
    return message.chat.id in {config.ADMIN_ID}


async def start_vote_for_one(participant_id: int, bonus: int, all_participants: Dict):
    """
    Запускает голосование для пользователя. Генерирует ему структуру из кандидатов и
    инициализирует процесс голосования
    """
    participant_state = dp.current_state(chat=participant_id, user=participant_id)
    candidates = {
        id: [name, 0] for id, (name, _) in all_participants.items() if id != participant_id
    }
    await participant_state.update_data(
        {
            'candidates': candidates,
            'vote_message_id': None,
            'bonus': bonus,
            'completed': False,
        }
    )
    await bot.send_message(participant_id, 'Приветственное сообщение с инфой о событии')
    await send_vote_status(participant_state)


async def start_vote(participants: Dict):
    """
    Запускает голосование для всех участников
    """
    for participant_id, (_, bonus) in participants.items():
        await start_vote_for_one(participant_id, bonus, participants)


@dp.message_handler(check_admin, commands=['session'], state='*')
async def open_session(message: types.Message):
    """
    Переключает админа на этап заполнения
    """
    state = dp.current_state(chat=message.chat.id, user=message.from_user.id)
    await state.set_state('fill_id')
    await message.reply('state changed to fill_id')


@dp.message_handler(check_admin, commands=['start'], state='*')
async def start_session(message: types.Message):
    """
    Выводит список будущей сессии
    """
    with dp.current_state(chat=message.chat.id, user=message.from_user.id) as state:
        data = await state.get_data()
        participants = data['participants']
        formatted_participants = format_participants(participants)
        if formatted_participants:
            await message.reply('Введи ОК, когда хватит')
            await message.reply(formatted_participants)
        else:
            await message.reply('Пусто')
        await state.set_state('fill_id')


@dp.message_handler(check_admin, commands=['drop'], state='*')
async def drop_session(message: types.Message):
    """
    Обнуляет текущий набор сессии
    """
    with dp.current_state(chat=message.chat.id, user=message.from_user.id) as state:
        await state.update_data({'participants': {}})
        await state.set_state('fill_id')


@dp.message_handler(check_admin, state='fill_id')
async def add_participant(message: types.Message):
    """
    Добавляет участника или участников. При форварде сообщения участника -- приглашает ко вводу
    его имени и премии. При вводе нескольких участников -- парсит их и добавляет всех.
    """
    with dp.current_state(chat=message.chat.id, user=message.from_user.id) as state:
        if message.text.lower() == 'ok':
            await state.set_state('')
            await start_vote((await state.get_data())['participants'])
            return
        forward = message.forward_from
        id = forward.id if forward else int(message.text) if message.text.isdigit() else None
        if id:
            await state.update_data({'participant_id': id})
            await state.set_state('fill_name')
            await message.reply('state changed to fill_name')
        else:
            exist_participants = (await state.get_data()).get('participants')
            participants = parse_participants(message.text)
            participants = {**(exist_participants or {}), **participants}
            await state.update_data({'participants': participants})
            await state.set_state('fill_id')
            await message.reply('Добавлены!')


@dp.message_handler(check_admin, state='fill_name')
async def add_participant(message: types.Message):
    """
    Заполняет имя участника
    """
    with dp.current_state(chat=message.chat.id, user=message.from_user.id) as state:
        await state.update_data({'participant_name': message.text})
        await state.set_state('fill_bonus')
        await message.reply('state changed to fill_bonus')


@dp.message_handler(check_admin, state='fill_bonus')
async def add_participant(message: types.Message):
    """
    Заполняет премию участника
    """
    with dp.current_state(chat=message.chat.id, user=message.from_user.id) as state:
        data = await state.get_data()
        participants = data.get('participants', {})
        participants[data['participant_id']] = (data['participant_name'], int(message.text))
        await state.update_data({'participants': participants})
        await state.set_state('fill_id')
        await message.reply(str(participants))


def format_participants(participants: Dict) -> str:
    """
    Форматирует набор участников в многострочный вывод
    """
    return '\n'.join('{name} ({id}): {bonus}'.format(
        name=p[0],
        id=id,
        bonus=p[1]
    ) for id, p in participants.items())


def parse_participants(participants: str) -> Dict:
    """
    Парсит многострочный набор участников в структуру для сессии
    """
    parsed = {}
    for line in participants.split('\n'):
        name, id, bonus = [el.strip(':)(') for el in line.rsplit(maxsplit=2)]
        parsed[int(id)] = (name, int(bonus))
    return parsed


