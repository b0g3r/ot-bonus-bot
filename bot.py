import asyncio
import logging
import random
from typing import Dict

from aiogram import Bot, types
from aiogram.contrib.fsm_storage.redis import RedisStorage
from aiogram.dispatcher import Dispatcher, FSMContext

import config

logging.basicConfig(level=logging.INFO)

loop = asyncio.get_event_loop()
bot = Bot(token=config.API_TOKEN, loop=loop)

storage = RedisStorage()
dp = Dispatcher(bot, storage=storage)

ADMIN_ID = 211270198

def check_admin(message):
    return message.chat.id in {ADMIN_ID}


def format_participants(participants: Dict) -> str:
    return '\n'.join('{name} ({id}): {bonus}'.format(
        name=p[0],
        id=id,
        bonus=p[1]
    ) for id, p in participants.items())


def parse_participants(participants: str) -> Dict:
    parsed = {}
    for line in participants.split('\n'):
        name, id, bonus = [el.strip(':)(') for el in line.rsplit(maxsplit=2)]
        parsed[int(id)] = (name, int(bonus))
    return parsed


@dp.message_handler(check_admin, commands=['session'], state='*')
async def open_session(message: types.Message):
    state = dp.current_state(chat=message.chat.id, user=message.from_user.id)
    await state.set_state('fill_id')
    await message.reply('state changed to fill_id')


@dp.message_handler(check_admin, commands=['start'], state='*')
async def start_session(message: types.Message):
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
    with dp.current_state(chat=message.chat.id, user=message.from_user.id) as state:
        
        await state.update_data({'participants': {}})
        await state.set_state('fill_id')


async def check_end_vote(admin_state: FSMContext):
    participants = (await admin_state.get_data())['participants']
    for participant_id in participants:
        participant_state = dp.current_state(chat=participant_id, user=participant_id)
        completed = (await participant_state.get_data()).get('completed', False)
        if not completed:
            print('fuck', completed, participant_id)
            return
    result = {p_id: 0 for p_id in participants}
    for participant_id in participants:
        participant_state = dp.current_state(chat=participant_id, user=participant_id)
        votes = (await participant_state.get_data())['votes']
        for candidate, bonus in votes.items():
            result[candidate] += bonus
    for participant_id, bonus in result.items():
        await bot.send_message(participant_id, 'Твоя премия: {0}'.format(bonus))
    await bot.send_message(
        ADMIN_ID,
        '\n'.join(
            '{0}: {1}'.format(participants[p_id][0], bonus) for p_id, bonus in result.items()
        )
    )


async def start_vote_for_one(participant_id: int, name: str, bonus: int, all_participants: Dict):
    participant_state = dp.current_state(chat=participant_id, user=participant_id)
    await participant_state.set_state('wait_vote')
    candidates = [
        [id, name] for id, (name, _) in all_participants.items() if id != participant_id
    ]
    await participant_state.update_data(
        {
            'candidates': candidates,
            'votes': {},
            'bonus': bonus,
            'completed': False,
        }
    )
    await set_candidate(participant_state, bonus)


async def start_vote(participants: Dict):
    for participant_id, (name, bonus) in participants.items():
        await start_vote_for_one(participant_id, name, bonus, participants)


async def set_candidate(state: FSMContext, rest: int):
    data = await state.get_data()
    print('set_candidate', data)
    candidate = random.choice([c for c in data['candidates'] if c[0] not in data['votes']])
    await state.update_data(
        {
            'candidate': candidate,
        }
    )
    await state.set_state('voting')
    await bot.send_message(state.user, 'Осталось: {0}'.format(rest))
    await bot.send_message(state.user, '{0}. Сколько денег ему отдашь?'.format(candidate[1]))


@dp.message_handler(state='voting')
async def voting(message: types.Message):
    with dp.current_state(chat=message.chat.id, user=message.from_user.id) as state:
        data = await state.get_data()
        try:
            bonus = int(message.text)
        except ValueError:
            await message.reply('Это не число даже')
            return
        candidate = data['candidate']
        votes = {**data['votes'], candidate[0]: bonus}
        rest = check_rest(data['bonus'], votes)
        if rest < 0:
            await message.reply('Да у тебя столько нет')
            return
        await state.update_data({'votes': votes})
        if len(data['candidates']) == len(votes):
            if rest != 0:
                await message.reply('Не сошлось, давай сначала')
                await state.update_data({'votes': {}})
                await set_candidate(state, data['bonus'])
                return
            else:
                await state.set_state('vote_over')
                await state.update_data({'completed': True})
                await check_end_vote(dp.current_state(chat=ADMIN_ID, user=ADMIN_ID))
                await message.reply('Ну вот и всё, ожидай')
        else:
            await set_candidate(state, rest)


@dp.message_handler(check_admin, state='*', commands=['check'])
async def check(message: types.Message):
    await check_end_vote(dp.current_state(chat=ADMIN_ID, user=ADMIN_ID))


def check_rest(full_bonus: int, votes: Dict[int, int]) -> int:
    return full_bonus - sum(votes.values())


@dp.message_handler(check_admin, state='fill_id')
async def add_participant(message: types.Message):
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
    with dp.current_state(chat=message.chat.id, user=message.from_user.id) as state:
        await state.update_data({'participant_name': message.text})
        await state.set_state('fill_bonus')
        await message.reply('state changed to fill_bonus')


@dp.message_handler(check_admin, state='fill_bonus')
async def add_participant(message: types.Message):
    with dp.current_state(chat=message.chat.id, user=message.from_user.id) as state:
        data = await state.get_data()
        participants = data.get('participants', {})
        participants[data['participant_id']] = (data['participant_name'], int(message.text))
        await state.update_data({'participants': participants})
        await state.set_state('fill_id')
        await message.reply(str(participants))



