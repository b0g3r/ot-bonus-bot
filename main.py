import logging

from aiogram.utils.executor import start_polling

from common import loop, dp, storage
import user, admin


logging.basicConfig(level=logging.INFO)

if __name__ == '__main__':
    #loop.run_until_complete(storage.reset_all())
    start_polling(dp, loop=loop)

