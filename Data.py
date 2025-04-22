import sqlite3
import os

# Define database path
script_dir = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(script_dir, 'nba_project.db')

# Connect to DB
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Enable FK
cursor.execute("PRAGMA foreign_keys = ON")

# Create all necessary tables
cursor.executescript("""
DROP TABLE IF EXISTS HypotheticalStats;
DROP TABLE IF EXISTS HypotheticalPlayers;

CREATE TABLE IF NOT EXISTS Players (
    player_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    team TEXT NOT NULL,
    position TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS Stats (
    stats_id INTEGER PRIMARY KEY,
    player_id INTEGER,
    season TEXT NOT NULL,
    PPG REAL,
    APG REAL,
    RPG REAL,
    STL REAL,
    BLK REAL,
    plus_minus REAL,
    FOREIGN KEY (player_id) REFERENCES Players(player_id)
);

CREATE TABLE IF NOT EXISTS Tier (
    tier_id INTEGER PRIMARY KEY,
    player_id INTEGER UNIQUE,
    tier_name TEXT NOT NULL,
    FOREIGN KEY (player_id) REFERENCES Players(player_id)
);

CREATE TABLE IF NOT EXISTS HypotheticalPlayers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    team TEXT NOT NULL,
    position TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS HypotheticalStats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id INTEGER NOT NULL,
    PPG REAL, APG REAL, RPG REAL, STL REAL, BLK REAL,
    FOREIGN KEY (player_id) REFERENCES HypotheticalPlayers(id) ON DELETE CASCADE
);
""")

conn.commit()
conn.close() 
print("Database initialized with all required tables.")
