# NBA_DB
# NBA Era Comparison Tool

**What it is**:  
– A Flask API + SQLite backend for NBA player stats & hypothetical players  
– A static HTML/JS front‑end to search, compare, add, edit, and delete records

## Setup

```bash
# 1. Clone
git clone https://github.com/your‑username/nba-era-comparison.git
cd nba-era-comparison

# 2. Create & activate virtualenv (optional but recommended)
python3 -m venv venv
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Initialize database
python init_db.py

# 5a. Run the backend API
python app.py

# 5b. Serve front‑end:
#    (in another terminal)
cd static
python -m http.server 8000
