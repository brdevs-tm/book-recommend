# 📚 Book Recommendation Bot

A smart PostgreSQL-powered Telegram bot that recommends books to users based on their preferred genre. Built using `aiogram` for Telegram integration and fully asynchronous Python backend.

---

## 🚀 Features

- 🔍 Users can select a genre (e.g., Fiction, History, Self-Help)
- 🎲 Recommends 3 random books from the selected genre
- 🧠 Tracks user interactions for future personalization
- 🗃️ PostgreSQL database with normalized schema
- 💬 Easy-to-use Telegram interface using custom reply keyboards

---

## 🛠️ Technologies Used

- 🐍 Python 3.11+
- 🤖 [Aiogram 3.x](https://docs.aiogram.dev)
- 🐘 PostgreSQL
- 🔐 Asyncpg (for async PostgreSQL queries)
- 📦 Dotenv (for environment variables)

---

## 🧱 Database Schema

**Users**  
| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL | Primary key |
| telegram_id | BIGINT | Unique user ID from Telegram |
| username | TEXT | Optional Telegram username |
| joined_at | TIMESTAMP | Registration date |

**Genres**  
| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL | Primary key |
| name | TEXT | Genre name |

**Books**  
| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL | Primary key |
| title | TEXT | Book title |
| author | TEXT | Author name |
| genre_id | INTEGER | Foreign key to Genres table |

**Recommendations**  
| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL | Primary key |
| user_id | INTEGER | Foreign key to Users |
| book_id | INTEGER | Foreign key to Books |
| recommended_at | TIMESTAMP | When the book was recommended |

---

## ⚙️ Setup Instructions

### 1. Clone the Repository

```bash
git clone https://github.com/brdevs-tm/book-recommend.git
cd book-recommend
```
