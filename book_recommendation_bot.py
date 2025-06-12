import asyncio
import logging
import random
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
import asyncpg
from datetime import datetime
import os
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Bot configuration
BOT_TOKEN = os.getenv("BOT_TOKEN")
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "database": os.getenv("DB_NAME", "book_bot"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", "your_password"),
    "port": os.getenv("DB_PORT", "5432")
}

# Initialize bot and dispatcher
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Database initialization
async def init_db():
    conn = await asyncpg.connect(**DB_CONFIG)
    try:
        # Create tables if they don't exist
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
                publication_year INTEGER
            );

            CREATE TABLE IF NOT EXISTS Recommendations (
                recommendation_id SERIAL PRIMARY KEY,
                user_id BIGINT REFERENCES Users(user_id),
                book_id INTEGER REFERENCES Books(book_id),
                recommended_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # Insert sample genres if not present
        await conn.execute("""
            INSERT INTO Genres (genre_name)
            VALUES ('Fiction'), ('History'), ('Self-Help')
            ON CONFLICT (genre_name) DO NOTHING;
        """)

        # Insert sample books if not present
        await conn.execute("""
            INSERT INTO Books (title, author, genre_id, publication_year)
            VALUES
                ('1984', 'George Orwell', (SELECT genre_id FROM Genres WHERE genre_name = 'Fiction'), 1949),
                ('Pride and Prejudice', 'Jane Austen', (SELECT genre_id FROM Genres WHERE genre_name = 'Fiction'), 1813),
                ('Dune', 'Frank Herbert', (SELECT genre_id FROM Genres WHERE genre_name = 'Fiction'), 1965),
                ('Sapiens', 'Yuval Noah Harari', (SELECT genre_id FROM Genres WHERE genre_name = 'History'), 2011),
                ('The Guns of August', 'Barbara W. Tuchman', (SELECT genre_id FROM Genres WHERE genre_name = 'History'), 1962),
                ('A People''s History of the United States', 'Howard Zinn', (SELECT genre_id FROM Genres WHERE genre_name = 'History'), 1980),
                ('Atomic Habits', 'James Clear', (SELECT genre_id FROM Genres WHERE genre_name = 'Self-Help'), 2018),
                ('The Power of Now', 'Eckhart Tolle', (SELECT genre_id FROM Genres WHERE genre_name = 'Self-Help'), 1997),
                ('Mindset', 'Carol S. Dweck', (SELECT genre_id FROM Genres WHERE genre_name = 'Self-Help'), 2006)
            ON CONFLICT DO NOTHING;
        """)
        logger.info("Database initialized successfully")
    finally:
        await conn.close()

# Create keyboard with genres
async def get_genre_keyboard():
    conn = await asyncpg.connect(**DB_CONFIG)
    try:
        genres = await conn.fetch("SELECT genre_name FROM Genres")
        # Create a list of lists for keyboard buttons
        keyboard_buttons = [[KeyboardButton(text=genre['genre_name'])] for genre in genres]
        keyboard = ReplyKeyboardMarkup(keyboard=keyboard_buttons, resize_keyboard=True)
        return keyboard
    finally:
        await conn.close()

# Register user in database
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

# Get book recommendations
async def get_book_recommendations(genre_name: str, limit: int = 3):
    conn = await asyncpg.connect(**DB_CONFIG)
    try:
        books = await conn.fetch("""
            SELECT b.title, b.author, b.publication_year
            FROM Books b
            JOIN Genres g ON b.genre_id = g.genre_id
            WHERE g.genre_name = $1
            ORDER BY RANDOM()
            LIMIT $2
        """, genre_name, limit)
        return books
    finally:
        await conn.close()

# Save recommendation to database
async def save_recommendation(user_id: int, book_title: str):
    conn = await asyncpg.connect(**DB_CONFIG)
    try:
        await conn.execute("""
            INSERT INTO Recommendations (user_id, book_id, recommended_at)
            VALUES (
                $1,
                (SELECT book_id FROM Books WHERE title = $2 LIMIT 1),
                $3
            )
        """, user_id, book_title, datetime.now())
    finally:
        await conn.close()

# Command handlers
@dp.message(Command("start"))
async def start_command(message: types.Message):
    await register_user(message.from_user)
    keyboard = await get_genre_keyboard()
    await message.answer(
        "Welcome to the Book Recommendation Bot! 📚\n"
        "Please choose a genre to get book recommendations:",
        reply_markup=keyboard
    )

# Genre selection handler
@dp.message()
async def handle_genre_selection(message: types.Message):
    genre = message.text
    conn = await asyncpg.connect(**DB_CONFIG)
    try:
        genre_exists = await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM Genres WHERE genre_name = $1)", genre
        )
        if not genre_exists:
            keyboard = await get_genre_keyboard()
            await message.answer(
                "Please select a valid genre from the keyboard below:",
                reply_markup=keyboard
            )
            return

        books = await get_book_recommendations(genre)
        if not books:
            keyboard = await get_genre_keyboard()
            await message.answer(
                f"No books found for genre: {genre}. Try another genre:",
                reply_markup=keyboard
            )
            return

        response = f"Here are 3 {genre} book recommendations:\n\n"
        for book in books:
            response += f"📖 *{book['title']}* by {book['author']} ({book['publication_year']})\n"
            await save_recommendation(message.from_user.id, book['title'])
        
        keyboard = await get_genre_keyboard()
        await message.answer(response, parse_mode="Markdown", reply_markup=keyboard)
    except Exception as e:
        logger.error(f"Error in handle_genre_selection: {e}")
        await message.answer("An error occurred. Please try again.")
    finally:
        await conn.close()

async def main():
    # Initialize database
    await init_db()
    
    # Start polling
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())