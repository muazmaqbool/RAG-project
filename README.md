# E-Commerce AI RAG Pipeline & Scraper

This repository contains a fully autonomous Extract, Transform, Load (ETL) pipeline and a Retrieval-Augmented Generation (RAG) backend. It scrapes e-commerce hardware data, uses an AI Mixture of Experts (MoE) to deduce missing specifications via web search, and stores everything in a local PostgreSQL vector database.

## 🚀 Quick Setup (For New Devices)

If you have just cloned this repository onto a new machine, you can set everything up automatically using the provided setup script. 

### Prerequisites
1. **Docker Desktop** must be installed and running on your machine.
2. **Python 3.10+** must be installed.

### Automatic Setup (Mac/Linux)
Open your terminal in the project directory and run:

```bash
chmod +x setup.sh
./setup.sh
```

This script will automatically:
- Spin up the PostgreSQL database in Docker Desktop.
- Create the `products`, `product_history`, and `media_gallery` tables.
- Create a Python virtual environment (`venv`).
- Install all necessary pip dependencies (including architecture-specific database drivers).

### Manual Setup (Windows or Step-by-Step)
If you prefer not to use the automated script, follow these steps:

1. **Start the Database**
   ```bash
   docker compose up -d
   ```
2. **Create Python Environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows use: venv\Scripts\activate
   ```
3. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```
4. **Initialize Tables (One-time only)**
   Open `pgAdmin4`, connect to `localhost:5432` (Username: `postgres`, Password: `mysecretpassword`), open the Query Tool for the `postgres` database, and run the contents of `init.sql`.

---

## 🛠️ Environment Configuration

You must create a `.env` file in the root of the project with the following keys:
```env
FIREWORKS_API_KEY=your_api_key_here
DB_HOST=localhost
DB_PORT=5432
DB_NAME=postgres
DB_USER=postgres
DB_PASSWORD=mysecretpassword
```

## 🎮 Usage

Once your environment is set up, everything is run through the central orchestrator:

```bash
source venv/bin/activate
python daily_update.py
```
This will open the Interactive CLI Dashboard where you can update the URL lists, run the scraping/AI enrichment pipeline, or repair broken data.
