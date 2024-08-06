import logging  # Импортируем модуль для логирования
import sqlite3  # Импортируем библиотеку для работы с базой данных SQLite
import os
import yt_dlp  # Импортируем библиотеку для скачивания видео и аудио с YouTube
from aiogram import Bot, Dispatcher, executor, types  # Импортируем необходимые классы из библиотеки aiogram
from aiogram.contrib.fsm_storage.memory import MemoryStorage  # Импортируем класс для хранения состояний в памяти
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import StatesGroup, State  # Импортируем классы для создания состояний
from requests import get  # Импортируем функцию для отправки HTTP-запросов

logging.basicConfig(level=logging.INFO)  # Настраиваем логирование

bot = Bot(token="7228254452:AAG55Ju4hI3EeKmOwaE4GWeEoXPPHqROy4M")  # Создаем экземпляр бота

storage = MemoryStorage()  # Создаем хранилище состояний в памяти
dp = Dispatcher(bot, storage=storage)  # Создаем диспетчер для обработки сообщений

# Создаем подключение к базе данных (или создаем новую, если она не существует)
conn = sqlite3.connect('mp3_db.db')
c = conn.cursor()

# Создаем таблицу, если она еще не существует
c.execute('''
    CREATE TABLE IF NOT EXISTS music_history (
        id INTEGER PRIMARY KEY,
        user_id TEXT,
        search_query TEXT,
        file_path TEXT
    )
''')


# Создаем класс для сбора имен файлов
class FilenameCollectorPP(yt_dlp.postprocessor.common.PostProcessor):
    def __init__(self):
        super(FilenameCollectorPP, self).__init__(None)
        self.filenames = []

    def run(self, information):
        self.filenames.append(information["filepath"])
        return [], information


# Обработчик команд '/start' и '/help'
@dp.message_handler(commands=['start', 'help'])
async def send_welcome(message: types.Message):
    await message.reply("Привет, я могу скачать для тебя любой трек👌\nПосмотри как это сделать в меню команд😊")


# Создаем класс состояний
class Form(StatesGroup):
    song = State()  # Создаем состояние 'song'


# Обработчик команды '/download'
@dp.message_handler(commands='download')
async def start_cmd_handler(message: types.Message):
    await message.reply("Пожалуйста, отправьте мне название и автора трека😄")
    await Form.song.set()  # Переводим пользователя в состояние 'song'


# Обработчик сообщений в состоянии 'song'
@dp.message_handler(state=Form.song)
async def process_name(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['song'] = message.text  # Сохраняем текст сообщения в состоянии
    # Здесь вы можете добавить код для скачивания и отправки песни
    await message.reply('Ожидайте...😴')
    YDL_OPTIONS = {'format': 'bestaudio/best',
                   'noplaylist': 'True',
                   'postprocessors': [{
                       'key': 'FFmpegExtractAudio',
                       'preferredcodec': 'mp3',
                       'preferredquality': '192'
                   }],
                   'outtmpl': 'music/%(title)s.%(ext)s',  # Сохраняем файлы в папке 'music'
                   }
    with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
        try:
            get(data['song'])
        except:
            filename_collector = FilenameCollectorPP()
            ydl.add_post_processor(filename_collector)
            info_dict = ydl.extract_info(f"ytsearch:{data['song']}", download=False)
            if not info_dict['entries']:
                await message.reply("Ваша музыка настолько крута, что её даже в нашей базе нет🤪")
                return
            video = ydl.extract_info(f"ytsearch:{data['song']}", download=True)['entries'][0]
            await message.reply_document(open(filename_collector.filenames[0], 'rb'))
            await message.reply(f'Вот ваша музыка наслаждайтесь😋')
            await state.finish()

            # Сохраняем информацию о поиске в базе данных
            c.execute("INSERT INTO music_history (user_id, search_query, file_path) VALUES (?, ?, ?)",
                      (message.from_user.id, data['song'], filename_collector.filenames[0]))
            conn.commit()

        else:
            video = ydl.extract_info(data['song'], download=True)

        return filename_collector.filenames[0]


# Обработчик команды '/history'
@dp.message_handler(commands=['history'])
async def show_history(message: types.Message):
    user_id = message.from_user.id

    c.execute("SELECT * FROM music_history WHERE user_id=?", (user_id,))
    rows = c.fetchall()
    if rows:
        history = "\n".join([f"{row[0]}. {row[2]}" for row in rows])
        await message.reply(f"Вот ваша история поиска:\n{history}")
    else:
        await message.reply("Ваша история поиска пуста.")


# Обработчик команды '/download_from_history'
@dp.message_handler(commands=['download_from_history'])
async def download_from_history(message: types.Message):
    user_id = message.from_user.id
    await message.reply("Подождите, ищем ваши песни в базе🧐")
    c.execute("SELECT file_path FROM music_history WHERE user_id=?", (user_id,))
    file_paths = c.fetchall()
    print(file_paths)
    for file_path in file_paths:
        with open(file_path[0], 'rb') as f:
            await message.reply_document(f)
    await message.reply("Это все🥳")


@dp.message_handler(commands=['delete_history'])
async def delete_history(message: types.Message):
    user_id = message.from_user.id
    c.execute("SELECT file_path FROM music_history WHERE user_id=?", (user_id,))
    file_paths =c.fetchall()
    if not file_paths:
        await message.reply("Ваша история загрузок пуста😕")
    else:
        for file_path in file_paths:
            if os.path.exists(file_path[0]):
                os.remove(file_path[0])

        c.execute("DELETE FROM music_history WHERE user_id=?", (user_id,))
        conn.commit()
        await message.reply("История удалена😎")


if __name__ == '__main__':
    try:
        executor.start_polling(dp)  # Запускаем бота
    finally:
        # Закрываем соединение с базой данных
        conn.close()
