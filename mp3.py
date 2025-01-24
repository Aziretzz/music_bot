import logging
import sqlite3
import os
import yt_dlp
from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import StatesGroup, State

logging.basicConfig(level=logging.INFO)
bot = Bot(token="Api-Token")
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)
print(sqlite3.sqlite_version)
conn = sqlite3.connect('mp3_db.db')
c = conn.cursor()

# Create the table if it doesn't exist
c.execute('''   
    CREATE TABLE IF NOT EXISTS music_history (
        id INTEGER PRIMARY KEY,
        user_id TEXT,
        search_query TEXT,
        file_path TEXT
    )
''')


# Updated FilenameCollectorPP to handle no requested_downloads key
class FilenameCollectorPP(yt_dlp.postprocessor.PostProcessor):
    def __init__(self, downloader=None):
        super().__init__(downloader)
        self.filenames = []

    def run(self, information):
        # Check and fetch 'filepath' directly
        if 'filepath' in information:
            self.filenames.append(information["filepath"])
        else:
            raise Exception("Failed to retrieve file path")
        return [], information


@dp.message_handler(commands=['start', 'help'])
async def send_welcome(message: types.Message):
    await message.reply("Hello, I can download any track for you👌\nCheck out how to do this in the command menu😊")


class Form(StatesGroup):
    song = State()


@dp.message_handler(commands='download')
async def start_cmd_handler(message: types.Message):
    await message.reply("Please send me the name and artist of the track😄")
    await Form.song.set()


@dp.message_handler(state=Form.song)
async def process_name(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['song'] = message.text
    await message.reply('Please wait...😴')

    YDL_OPTIONS = {
        'format': 'bestaudio/best',
        'noplaylist': True,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192'
        }],
        'paths': {'home': 'music/'},
        'quiet': True,
    }

    with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
        try:
            # Use FilenameCollectorPP to get file name
            filename_collector = FilenameCollectorPP()
            ydl.add_post_processor(filename_collector)

            # Search and download the track
            info_dict = ydl.extract_info(f"ytsearch:{data['song']}", download=False)
            if not info_dict['entries']:
                await message.reply("Your music is so cool that it's not even in our database🤪")
                return

            info_dict_download = ydl.extract_info(f"ytsearch:{data['song']}", download=True)

            # Send the downloaded file to the user
            await message.reply_document(open(filename_collector.filenames[0], 'rb'))
            await message.reply('Here is your music, enjoy😋')
            await state.finish()

            # Save record to the database
            c.execute("INSERT INTO music_history (user_id, search_query, file_path) VALUES (?, ?, ?)",
                      (message.from_user.id, data['song'], filename_collector.filenames[0]))
            conn.commit()

        except Exception as e:
            logging.error(f"Error while processing download: {e}")
            await message.reply("Unknown error occurred during download. Please try again later.")


@dp.message_handler(commands=['history'])
async def show_history(message: types.Message):
    user_id = message.from_user.id

    c.execute("SELECT * FROM music_history WHERE user_id=?", (user_id,))
    rows = c.fetchall()
    if rows:
        history = "\n".join([f"{row[0]}. {row[2]}" for row in rows])
        await message.reply(f"Here is your search history:\n{history}")
    else:
        await message.reply("Your search history is empty.")


@dp.message_handler(commands=['download_from_history'])
async def download_from_history(message: types.Message):
    user_id = message.from_user.id
    await message.reply("Please wait, searching for your songs in the database🧐")
    c.execute("SELECT file_path FROM music_history WHERE user_id=?", (user_id,))
    file_paths = c.fetchall()
    for file_path in file_paths:
        if os.path.exists(file_path[0]):
            with open(file_path[0], 'rb') as f:
                await message.reply_document(f)
        else:
            await message.reply(f"File {file_path[0]} no longer exists.")
    await message.reply("That's all🥳")


@dp.message_handler(commands=['delete_history'])
async def delete_history(message: types.Message):
    user_id = message.from_user.id
    c.execute("SELECT file_path FROM music_history WHERE user_id=?", (user_id,))
    file_paths = c.fetchall()
    if not file_paths:
        await message.reply("Your download history is empty😕")
    else:
        for file_path in file_paths:
            if os.path.exists(file_path[0]):
                os.remove(file_path[0])

        c.execute("DELETE FROM music_history WHERE user_id=?", (user_id,))
        conn.commit()
        await message.reply("History deleted😎")


if __name__ == '__main__':
    try:
        executor.start_polling(dp)
    finally:
        conn.close()  # Close DB connection
