import logging  # Import the logging module for logging messages
import sqlite3  # Import the SQLite library for working with SQLite databases
import os  # Import the OS module for interacting with the operating system
import yt_dlp  # Import the yt-dlp library for downloading videos and audio from YouTube
from aiogram import Bot, Dispatcher, executor, types  # Import necessary classes from the aiogram library
from aiogram.contrib.fsm_storage.memory import MemoryStorage  # Import the class for storing FSM states in memory
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import StatesGroup, State  # Import classes for creating states
from requests import get  # Import the function for sending HTTP requests

logging.basicConfig(level=logging.INFO)  # Configure logging

bot = Bot(token="API_TOKEN")  # Create an instance of the bot

storage = MemoryStorage()  # Create in-memory storage for FSM states
dp = Dispatcher(bot, storage=storage)  # Create a dispatcher for handling messages

# Create a connection to the SQLite database (or create a new one if it doesn't exist)
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


# Create a class to collect file names
class FilenameCollectorPP(yt_dlp.postprocessor.common.PostProcessor):
    def __init__(self):
        super(FilenameCollectorPP, self).__init__(None)
        self.filenames = []

    def run(self, information):
        self.filenames.append(information["filepath"])
        return [], information


# Handler for the '/start' and '/help' commands
@dp.message_handler(commands=['start', 'help'])
async def send_welcome(message: types.Message):
    await message.reply("Hello, I can download any track for you👌\nCheck out how to do this in the command menu😊")


# Create a class for states
class Form(StatesGroup):
    song = State()  # Create a state 'song'


# Handler for the '/download' command
@dp.message_handler(commands='download')
async def start_cmd_handler(message: types.Message):
    await message.reply("Please send me the name and artist of the track😄")
    await Form.song.set()  # Set the user to the 'song' state


# Handler for messages in the 'song' state
@dp.message_handler(state=Form.song)
async def process_name(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['song'] = message.text  # Save the message text in the state
    await message.reply('Please wait...😴')
    YDL_OPTIONS = {'format': 'bestaudio/best',
                   'noplaylist': 'True',
                   'postprocessors': [{
                       'key': 'FFmpegExtractAudio',
                       'preferredcodec': 'mp3',
                       'preferredquality': '192'
                   }],
                   'outtmpl': 'music/%(title)s.%(ext)s',  # Save files in the 'music' folder
                   }
    with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
        try:
            get(data['song'])
        except:
            filename_collector = FilenameCollectorPP()
            ydl.add_post_processor(filename_collector)
            info_dict = ydl.extract_info(f"ytsearch:{data['song']}", download=False)
            if not info_dict['entries']:
                await message.reply("Your music is so cool that it's not even in our database🤪")
                return
            video = ydl.extract_info(f"ytsearch:{data['song']}", download=True)['entries'][0]
            await message.reply_document(open(filename_collector.filenames[0], 'rb'))
            await message.reply(f'Here is your music, enjoy😋')
            await state.finish()

            # Save search information in the database
            c.execute("INSERT INTO music_history (user_id, search_query, file_path) VALUES (?, ?, ?)",
                      (message.from_user.id, data['song'], filename_collector.filenames[0]))
            conn.commit()

        else:
            video = ydl.extract_info(data['song'], download=True)

        return filename_collector.filenames[0]


# Handler for the '/history' command
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


# Handler for the '/download_from_history' command
@dp.message_handler(commands=['download_from_history'])
async def download_from_history(message: types.Message):
    user_id = message.from_user.id
    await message.reply("Please wait, searching for your songs in the database🧐")
    c.execute("SELECT file_path FROM music_history WHERE user_id=?", (user_id,))
    file_paths = c.fetchall()
    for file_path in file_paths:
        with open(file_path[0], 'rb') as f:
            await message.reply_document(f)
    await message.reply("That's all🥳")


# Handler for the '/delete_history' command
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
        executor.start_polling(dp)  # Start the bot
    finally:
        # Close the database connection
        conn.close()
