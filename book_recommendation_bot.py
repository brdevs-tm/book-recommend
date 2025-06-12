import asyncio
import logging
import random
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import asyncpg
from datetime import datetime
import os
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "database": os.getenv("DB_NAME", "book_bot"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", "your_password"),
    "port": os.getenv("DB_PORT", "5432")
}

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

class AddBookForm(StatesGroup):
    title = State()
    author = State()
    genre = State()
    year = State()
    rating = State()

class UpdateBookForm(StatesGroup):
    book_id = State()
    field = State()
    value = State()

async def init_db():
    conn = await asyncpg.connect(**DB_CONFIG)
    try:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS Users (
                user_id BIGINT PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS Genres (
                genre_id SERIAL PRIMARY KEY,
                genre_name TEXT UNIQUE NOT NULL
            );

            CREATE TABLE IF NOT EXISTS Books (
                book_id SERIAL PRIMARY KEY,
                title TEXT NOT NULL,
                author TEXT NOT NULL,
                genre_id INTEGER REFERENCES Genres(genre_id),
                publication_year INTEGER,
                user_id BIGINT REFERENCES Users(user_id),
                rating INTEGER CHECK (rating >= 1 AND rating <= 5),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS Recommendations (
                recommendation_id SERIAL PRIMARY KEY,
                user_id BIGINT REFERENCES Users(user_id),
                book_id INTEGER REFERENCES Books(book_id),
                recommended_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS ReadingList (
                reading_list_id SERIAL PRIMARY KEY,
                user_id BIGINT REFERENCES Users(user_id),
                book_id INTEGER REFERENCES Books(book_id),
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        await conn.execute("""
            DO $$ 
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 
                    FROM information_schema.columns 
                    WHERE table_name = 'books' AND column_name = 'user_id'
                ) THEN
                    ALTER TABLE Books ADD COLUMN user_id BIGINT REFERENCES Users(user_id);
                END IF;
                IF NOT EXISTS (
                    SELECT 1 
                    FROM information_schema.columns 
                    WHERE table_name = 'books' AND column_name = 'rating'
                ) THEN
                    ALTER TABLE Books ADD COLUMN rating INTEGER CHECK (rating >= 1 AND rating <= 5);
                END IF;
            END $$;
        """)

        await conn.execute("""
            INSERT INTO Genres (genre_name)
            VALUES ('Fiction'), ('History'), ('Self-Help')
            ON CONFLICT (genre_name) DO NOTHING;
        """)

        await conn.execute("""
            INSERT INTO Books (title, author, genre_id, publication_year, user_id, rating)
            VALUES
                ('1984', 'George Orwell', (SELECT genre_id FROM Genres WHERE genre_name = 'Fiction'), 1949, NULL, 5),
                ('Pride and Prejudice', 'Jane Austen', (SELECT genre_id FROM Genres WHERE genre_name = 'Fiction'), 1813, NULL, 4),
                ('Dune', 'Frank Herbert', (SELECT genre_id FROM Genres WHERE genre_name = 'Fiction'), 1965, NULL, 5),
                ('Sapiens', 'Yuval Noah Harari', (SELECT genre_id FROM Genres WHERE genre_name = 'History'), 2011, NULL, 4),
                ('The Guns of August', 'Barbara W. Tuchman', (SELECT genre_id FROM Genres WHERE genre_name = 'History'), 1962, NULL, 3),
                ('A People''s History of the United States', 'Howard Zinn', (SELECT genre_id FROM Genres WHERE genre_name = 'History'), 1980, NULL, 4),
                ('Atomic Habits', 'James Clear', (SELECT genre_id FROM Genres WHERE genre_name = 'Self-Help'), 2018, NULL, 5),
                ('The Power of Now', 'Eckhart Tolle', (SELECT genre_id FROM Genres WHERE genre_name = 'Self-Help'), 1997, NULL, 4),
                ('Mindset', 'Carol S. Dweck', (SELECT genre_id FROM Genres WHERE genre_name = 'Self-Help'), 2006, NULL, 3)
            ON CONFLICT DO NOTHING;
        """)
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise
    finally:
        await conn.close()

async def get_main_menu():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📚 Get Recommendations"), KeyboardButton(text="➕ Add Book")],
            [KeyboardButton(text="📖 My Books"), KeyboardButton(text="⭐ Surprise Me!")],
            [KeyboardButton(text="📋 My Reading List"), KeyboardButton(text="📊 My Stats")]
        ],
        resize_keyboard=True
    )
    return keyboard

async def get_genre_keyboard():
    conn = await asyncpg.connect(**DB_CONFIG)
    try:
        genres = await conn.fetch("SELECT genre_name FROM Genres")
        keyboard_buttons = [[KeyboardButton(text=genre['genre_name'])] for genre in genres]
        keyboard = ReplyKeyboardMarkup(keyboard=keyboard_buttons, resize_keyboard=True)
        return keyboard
    finally:
        await conn.close()

async def register_user(user: types.User):
    conn = await asyncpg.connect(**DB_CONFIG)
    try:
        await conn.execute("""
            INSERT INTO Users (user_id, username, first_name, last_name, created_at)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (user_id) DO NOTHING
        """, user.id, user.username, user.first_name, user.last_name, datetime.now())
    finally:
        await conn.close()

async def get_book_recommendations(genre_name: str, limit: int = 3):
    conn = await asyncpg.connect(**DB_CONFIG)
    try:
        books = await conn.fetch("""
            SELECT b.book_id, b.title, b.author, b.publication_year, b.rating
            FROM Books b
            JOIN Genres g ON b.genre_id = g.genre_id
            WHERE g.genre_name = $1
            ORDER BY RANDOM()
            LIMIT $2
        """, genre_name, limit)
        return books
    finally:
        await conn.close()

async def get_random_book():
    conn = await asyncpg.connect(**DB_CONFIG)
    try:
        book = await conn.fetchrow("""
            SELECT b.book_id, b.title, b.author, b.publication_year, b.rating, g.genre_name
            FROM Books b
            JOIN Genres g ON b.genre_id = g.genre_id
            ORDER BY RANDOM()
            LIMIT 1
        """)
        return book
    finally:
        await conn.close()

async def save_recommendation(user_id: int, book_id: int):
    conn = await asyncpg.connect(**DB_CONFIG)
    try:
        await conn.execute("""
            INSERT INTO Recommendations (user_id, book_id, recommended_at)
            VALUES ($1, $2, $3)
        """, user_id, book_id, datetime.now())
    finally:
        await conn.close()

async def add_to_reading_list(user_id: int, book_id: int):
    conn = await asyncpg.connect(**DB_CONFIG)
    try:
        await conn.execute("""
            INSERT INTO ReadingList (user_id, book_id, added_at)
            VALUES ($1, $2, $3)
            ON CONFLICT DO NOTHING
        """, user_id, book_id, datetime.now())
    finally:
        await conn.close()

async def get_user_books(user_id: int):
    conn = await asyncpg.connect(**DB_CONFIG)
    try:
        books = await conn.fetch("""
            SELECT b.book_id, b.title, b.author, b.publication_year, b.rating, g.genre_name
            FROM Books b
            JOIN Genres g ON b.genre_id = g.genre_id
            WHERE b.user_id = $1
        """, user_id)
        return books
    finally:
        await conn.close()

async def get_reading_list(user_id: int):
    conn = await asyncpg.connect(**DB_CONFIG)
    try:
        books = await conn.fetch("""
            SELECT b.book_id, b.title, b.author, b.publication_year, b.rating, g.genre_name
            FROM ReadingList rl
            JOIN Books b ON rl.book_id = b.book_id
            JOIN Genres g ON b.genre_id = g.genre_id
            WHERE rl.user_id = $1
        """, user_id)
        return books
    finally:
        await conn.close()

async def get_user_stats(user_id: int):
    conn = await asyncpg.connect(**DB_CONFIG)
    try:
        stats = await conn.fetchrow("""
            SELECT
                (SELECT COUNT(*) FROM Books WHERE user_id = $1) as books_added,
                (SELECT COUNT(*) FROM Recommendations WHERE user_id = $1) as recommendations_received,
                (SELECT COUNT(*) FROM ReadingList WHERE user_id = $1) as reading_list_count
        """, user_id)
        return stats
    finally:
        await conn.close()

@dp.message(Command("start"))
async def start_command(message: types.Message, state: FSMContext):
    await state.clear()
    await register_user(message.from_user)
    keyboard = await get_main_menu()
    await message.answer(
        "Welcome to the Enhanced Book Bot! 📚\n"
        "What would you like to do?",
        reply_markup=keyboard
    )

@dp.message(lambda message: message.text == "📚 Get Recommendations")
async def get_recommendations(message: types.Message, state: FSMContext):
    await state.clear()
    keyboard = await get_genre_keyboard()
    await message.answer(
        "Choose a genre for book recommendations:",
        reply_markup=keyboard
    )

@dp.message(lambda message: message.text == "➕ Add Book")
async def add_book_start(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Enter the book title:", reply_markup=types.ReplyKeyboardRemove())
    await state.set_state(AddBookForm.title)

@dp.message(lambda message: message.text == "📖 My Books")
async def my_books(message: types.Message, state: FSMContext):
    await state.clear()
    books = await get_user_books(message.from_user.id)
    if not books:
        await message.answer("You haven't added any books yet. Use 'Add Book' to start!", reply_markup=await get_main_menu())
        return

    response = "Your books:\n\n"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    for book in books:
        rating = book['rating'] if book['rating'] is not None else "Unrated"
        response += f"📖 *{book['title']}* by {book['author']} ({book['publication_year']}, {book['genre_name']}, Rating: {rating}/5)\n"
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(text=f"Update {book['title']}", callback_data=f"update_{book['book_id']}"),
            InlineKeyboardButton(text=f"Delete {book['title']}", callback_data=f"delete_{book['book_id']}")
        ])
    
    await message.answer(response, parse_mode="Markdown", reply_markup=keyboard)
    await message.answer("Back to main menu:", reply_markup=await get_main_menu())

@dp.message(lambda message: message.text == "⭐ Surprise Me!")
async def surprise_me(message: types.Message, state: FSMContext):
    await state.clear()
    book = await get_random_book()
    if not book:
        await message.answer("No books available. Add some books first!", reply_markup=await get_main_menu())
        return

    rating = book['rating'] if book['rating'] is not None else "Unrated"
    response = f"Surprise Book! 🎉\n\n📖 *{book['title']}* by {book['author']} ({book['publication_year']}, {book['genre_name']}, Rating: {rating}/5)"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Add to Reading List", callback_data=f"add_reading_{book['book_id']}")]
    ])
    await save_recommendation(message.from_user.id, book['book_id'])
    await message.answer(response, parse_mode="Markdown", reply_markup=keyboard)
    await message.answer("Back to main menu:", reply_markup=await get_main_menu())

@dp.message(lambda message: message.text == "📋 My Reading List")
async def my_reading_list(message: types.Message, state: FSMContext):
    await state.clear()
    books = await get_reading_list(message.from_user.id)
    if not books:
        await message.answer("Your reading list is empty. Add books from recommendations!", reply_markup=await get_main_menu())
        return

    response = "Your reading list:\n\n"
    for book in books:
        rating = book['rating'] if book['rating'] is not None else "Unrated"
        response += f"📖 *{book['title']}* by {book['author']} ({book['publication_year']}, {book['genre_name']}, Rating: {rating}/5)\n"
    
    await message.answer(response, parse_mode="Markdown")
    await message.answer("Back to main menu:", reply_markup=await get_main_menu())

@dp.message(lambda message: message.text == "📊 My Stats")
async def my_stats(message: types.Message, state: FSMContext):
    await state.clear()
    stats = await get_user_stats(message.from_user.id)
    response = "Your stats:\n\n"
    response += f"📚 Books added: {stats['books_added']}\n"
    response += f"✅ Recommendations received: {stats['recommendations_received']}\n"
    response += f"📋 Reading list items: {stats['reading_list_count']}\n"
    await message.answer(response, reply_markup=await get_main_menu())

@dp.message()
async def handle_genre_selection(message: types.Message, state: FSMContext):
    genre = message.text
    conn = await asyncpg.connect(**DB_CONFIG)
    try:
        genre_exists = await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM Genres WHERE genre_name = $1)", genre
        )
        if not genre_exists:
            await message.answer(
                "Please select a valid genre from the keyboard below:",
                reply_markup=await get_genre_keyboard()
            )
            return

        books = await get_book_recommendations(genre)
        if not books:
            await message.answer(
                f"No books found for genre: {genre}. Try another genre:",
                reply_markup=await get_genre_keyboard()
            )
            return

        response = f"Here are 3 {genre} book recommendations:\n\n"
        keyboard = InlineKeyboardMarkup(inline_keyboard=[])
        for book in books:
            rating = book['rating'] if book['rating'] is not None else "Unrated"
            response += f"📖 *{book['title']}* by {book['author']} ({book['publication_year']}, Rating: {rating}/5)\n"
            keyboard.inline_keyboard.append([
                InlineKeyboardButton(text=f"Add {book['title']} to Reading List", callback_data=f"add_reading_{book['book_id']}")
            ])
            await save_recommendation(message.from_user.id, book['book_id'])
        
        await message.answer(response, parse_mode="Markdown", reply_markup=keyboard)
        await message.answer("Back to main menu:", reply_markup=await get_main_menu())
    except Exception as e:
        logger.error(f"Error in handle_genre_selection: {e}")
        await message.answer("An error occurred. Please try again.", reply_markup=await get_main_menu())
    finally:
        await conn.close()

@dp.message(AddBookForm.title)
async def process_title(message: types.Message, state: FSMContext):
    await state.update_data(title=message.text)
    await message.answer("Enter the author:")
    await state.set_state(AddBookForm.author)

@dp.message(AddBookForm.author)
async def process_author(message: types.Message, state: FSMContext):
    await state.update_data(author=message.text)
    await message.answer("Enter the genre (e.g., Fiction, History, Self-Help):")
    await state.set_state(AddBookForm.genre)

@dp.message(AddBookForm.genre)
async def process_genre(message: types.Message, state: FSMContext):
    genre = message.text
    conn = await asyncpg.connect(**DB_CONFIG)
    try:
        genre_id = await conn.fetchval(
            "SELECT genre_id FROM Genres WHERE genre_name = $1", genre
        )
        if not genre_id:
            await message.answer("Genre not found. Please choose an existing genre:")
            return
        await state.update_data(genre_id=genre_id)
        await message.answer("Enter the publication year (e.g., 2020):")
        await state.set_state(AddBookForm.year)
    finally:
        await conn.close()

@dp.message(AddBookForm.year)
async def process_year(message: types.Message, state: FSMContext):
    try:
        year = int(message.text)
        if year < 0 or year > datetime.now().year + 1:
            await message.answer("Please enter a valid year:")
            return
        await state.update_data(year=year)
        await message.answer("Enter your rating (1-5):")
        await state.set_state(AddBookForm.rating)
    except ValueError:
        await message.answer("Please enter a valid number for the year:")

@dp.message(AddBookForm.rating)
async def process_rating(message: types.Message, state: FSMContext):
    try:
        rating = int(message.text)
        if rating < 1 or rating > 5:
            await message.answer("Please enter a rating between 1 and 5:")
            return
        data = await state.get_data()
        conn = await asyncpg.connect(**DB_CONFIG)
        try:
            await conn.execute("""
                INSERT INTO Books (title, author, genre_id, publication_year, user_id, rating)
                VALUES ($1, $2, $3, $4, $5, $6)
            """, data['title'], data['author'], data['genre_id'], data['year'], message.from_user.id, rating)
            await message.answer("Book added successfully!", reply_markup=await get_main_menu())
            await state.clear()
        finally:
            await conn.close()
    except ValueError:
        await message.answer("Please enter a valid number for the rating:")

@dp.callback_query(lambda c: c.data.startswith("add_reading_"))
async def add_reading_list_callback(callback: types.CallbackQuery):
    book_id = int(callback.data.split("_")[2])
    await add_to_reading_list(callback.from_user.id, book_id)
    await callback.message.answer("Book added to your reading list!", reply_markup=await get_main_menu())
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("delete_"))
async def delete_book_callback(callback: types.CallbackQuery):
    book_id = int(callback.data.split("_")[1])
    conn = await asyncpg.connect(**DB_CONFIG)
    try:
        await conn.execute("DELETE FROM Books WHERE book_id = $1 AND user_id = $2", book_id, callback.from_user.id)
        await callback.message.answer("Book deleted successfully!", reply_markup=await get_main_menu())
    finally:
        await conn.close()
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("update_"))
async def update_book_start(callback: types.CallbackQuery, state: FSMContext):
    book_id = int(callback.data.split("_")[1])
    await state.update_data(book_id=book_id)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Title", callback_data="field_title")],
        [InlineKeyboardButton(text="Author", callback_data="field_author")],
        [InlineKeyboardButton(text="Genre", callback_data="field_genre")],
        [InlineKeyboardButton(text="Year", callback_data="field_year")],
        [InlineKeyboardButton(text="Rating", callback_data="field_rating")]
    ])
    await callback.message.answer("Which field would you like to update?", reply_markup=keyboard)
    await state.set_state(UpdateBookForm.field)
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("field_"))
async def process_update_field(callback: types.CallbackQuery, state: FSMContext):
    field = callback.data.split("_")[1]
    await state.update_data(field=field)
    await callback.message.answer(f"Enter the new value for {field}:", reply_markup=types.ReplyKeyboardRemove())
    await state.set_state(UpdateBookForm.value)
    await callback.answer()

@dp.message(UpdateBookForm.value)
async def process_update_value(message: types.Message, state: FSMContext):
    data = await state.get_data()
    field = data['field']
    book_id = data['book_id']
    value = message.text
    conn = await asyncpg.connect(**DB_CONFIG)
    try:
        if field == "year":
            value = int(value)
            if value < 0 or value > datetime.now().year + 1:
                await message.answer("Please enter a valid year:")
                return
        elif field == "rating":
            value = int(value)
            if value < 1 or value > 5:
                await message.answer("Please enter a rating between 1 and 5:")
                return
        elif field == "genre":
            genre_id = await conn.fetchval("SELECT genre_id FROM Genres WHERE genre_name = $1", value)
            if not genre_id:
                await message.answer("Genre not found. Please choose an existing genre:")
                return
            value = genre_id
            field = "genre_id"

        await conn.execute(f"""
            UPDATE Books
            SET {field} = $1
            WHERE book_id = $2 AND user_id = $3
        """, value, book_id, message.from_user.id)
        await message.answer("Book updated successfully!", reply_markup=await get_main_menu())
        await state.clear()
    except ValueError:
        await message.answer(f"Please enter a valid value for {field}:")
    except Exception as e:
        logger.error(f"Error in update: {e}")
        await message.answer("An error occurred. Please try again.")
    finally:
        await conn.close()

async def main():
    await init_db()
    
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())