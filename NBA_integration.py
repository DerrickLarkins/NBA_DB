from flask import Flask, jsonify, request, make_response
import sqlite3
from flask_cors import CORS
import os
import logging
from math import sqrt
from werkzeug.middleware.proxy_fix import ProxyFix


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('nba_api.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
CORS(app, resources={
    r"/*": {
        "origins": ["http://localhost:8000", "http://127.0.0.1:8000"],
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type"]
    }
})

# Database configuration
script_dir = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(script_dir, 'nba_project.db')


def get_db_connection():
    """Create and return a database connection with row factory."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def validate_player_id(player_id):
    """Validate player ID is a positive integer."""
    try:
        return int(player_id) > 0
    except (ValueError, TypeError):
        return False

def calculate_position_tier(stats, position):
    # Slightly increased impact from STL/BLK for all-time defenders
    overall_weights = {
        'PPG': 0.4,
        'APG': 0.25,
        'RPG': 0.15,
        'STL': 0.1,
        'BLK': 0.1
    }

    # Role-accurate weights
    position_weights = {
        'PG': {'PPG': 0.3, 'APG': 0.45, 'RPG': 0.05, 'STL': 0.15, 'BLK': 0.05},
        'SG': {'PPG': 0.45, 'APG': 0.2,  'RPG': 0.1,  'STL': 0.15, 'BLK': 0.1},
        'SF': {'PPG': 0.4,  'APG': 0.2,  'RPG': 0.2,  'STL': 0.1,  'BLK': 0.1},
        'PF': {'PPG': 0.3,  'APG': 0.1,  'RPG': 0.35, 'STL': 0.1,  'BLK': 0.15},
        'C':  {'PPG': 0.25, 'APG': 0.05, 'RPG': 0.4,  'STL': 0.05, 'BLK': 0.25}
    }

    def score(s, weights):
        return sum(s.get(k, 0) * w for k, w in weights.items())

    def assign(score):
        if score >= 12:
            return "Tier 1 - Superstar"      # truly elite (MVP, All-NBA 1st)
        elif score >= 10:
            return "Tier 2 - All-Star"       # high-level consistent excellence
        elif score >= 5:
            return "Tier 3 - Starter"        # key contributors
        elif score >= 2:
            return "Tier 4 - Role Player"    # reliable role guys
        else:
            return "Tier 5 - Bench"

    o_score = score(stats, overall_weights)
    p_score = score(stats, position_weights.get(position.upper(), overall_weights))

    return assign(o_score), assign(p_score)



@app.route('/players', methods=['GET'])
def get_players():
    """Get all players with pagination support."""
    try:
        page = request.args.get('page', default=1, type=int)
        per_page = request.args.get('per_page', default=50, type=int)
        offset = (page - 1) * per_page

        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Get paginated players
            cursor.execute("""
                SELECT player_id, name, team, position 
                FROM Players 
                LIMIT ? OFFSET ?
            """, (per_page, offset))
            players = cursor.fetchall()
            
            # Get total count for pagination metadata
            cursor.execute("SELECT COUNT(*) FROM Players")
            total_players = cursor.fetchone()[0]

        response = {
            'data': [dict(player) for player in players],
            'meta': {
                'page': page,
                'per_page': per_page,
                'total_pages': (total_players + per_page - 1) // per_page,
                'total_players': total_players
            }
        }
        return jsonify(response)
    
    except Exception as e:
        logger.error(f"Error fetching players: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/players/<int:player_id>', methods=['GET'])
def get_player(player_id):
    if not validate_player_id(player_id):
        return jsonify({'error': 'Invalid player ID'}), 400

    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT p.player_id, p.name, p.team, p.position,
                       AVG(s.PPG) as avg_ppg,
                       AVG(s.APG) as avg_apg,
                       AVG(s.RPG) as avg_rpg,
                       AVG(s.STL) as avg_stl,
                       AVG(s.BLK) as avg_blk
                FROM Players p
                LEFT JOIN Stats s ON p.player_id = s.player_id
                WHERE p.player_id = ?
                GROUP BY p.player_id
            """, (player_id,))
            player = cursor.fetchone()

            if not player:
                return jsonify({'error': 'Player not found'}), 404

            stats = {
                'PPG': player['avg_ppg'] or 0,
                'APG': player['avg_apg'] or 0,
                'RPG': player['avg_rpg'] or 0,
                'STL': player['avg_stl'] or 0,
                'BLK': player['avg_blk'] or 0
            }

            overall_tier, position_tier = calculate_position_tier(stats, player['position'])

            response = dict(player)
            response['overall_tier'] = overall_tier
            response['position_tier'] = position_tier

            return jsonify(response)

    except Exception as e:
        logger.error(f"Error fetching player {player_id}: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500


@app.route('/stats/<int:player_id>', methods=['GET'])
def get_player_stats(player_id):
    """Get all stats for a specific player with season sorting."""
    if not validate_player_id(player_id):
        return jsonify({'error': 'Invalid player ID'}), 400
    
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT stats_id, player_id, season, PPG, APG, RPG, STL, BLK, plus_minus
                FROM Stats
                WHERE player_id = ?
                ORDER BY season DESC
            """, (player_id,))
            stats = cursor.fetchall()
            
            if not stats:
                return jsonify({'error': 'No stats found for this player'}), 404
            
        return jsonify([dict(stat) for stat in stats])
    
    except Exception as e:
        logger.error(f"Error fetching stats for player {player_id}: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/search', methods=['GET'])
def search_players():
    """Search players by name with fuzzy matching."""
    name = request.args.get('name', '').strip()
    if not name or len(name) < 2:
        return jsonify({'error': 'Search term must be at least 2 characters'}), 400
    
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT player_id, name, team, position
                FROM Players
                WHERE name LIKE ? OR name LIKE ? OR name LIKE ?
                LIMIT 20
            """, (f'%{name}%', f'{name}%', f'%{name}'))
            players = cursor.fetchall()
            
        return jsonify([dict(player) for player in players])
    
    except Exception as e:
        logger.error(f"Error searching players: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/compare_players', methods=['GET'])

@app.route('/hypotheticals', methods=['POST'])
def add_hypothetical():
    try:
        data = request.get_json()

        # Validate required fields
        required_fields = ['name', 'team', 'position', 'PPG', 'APG', 'RPG', 'STL', 'BLK']
        if not all(field in data for field in required_fields):
            return jsonify({'error': 'Missing required fields'}), 400

        # Extract and validate
        name = data['name']
        team = data['team']
        position = data['position'].upper()
        stats = {key: float(data[key]) for key in ['PPG', 'APG', 'RPG', 'STL', 'BLK']}

        # Insert player
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO HypotheticalPlayers (name, team, position)
            VALUES (?, ?, ?)
        """, (name, team, position))
        player_id = cursor.lastrowid

        # Insert stats
        cursor.execute("""
            INSERT INTO HypotheticalStats (player_id, PPG, APG, RPG, STL, BLK)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (player_id, stats['PPG'], stats['APG'], stats['RPG'], stats['STL'], stats['BLK']))

        # Calculate tiers
        overall_tier, position_tier = calculate_position_tier(stats, position)

        conn.commit()
        return jsonify({
            'player_id': player_id,
            'name': name,
            'position': position,
            'team': team,
            'stats': stats,
            'overall_tier': overall_tier,
            'position_tier': position_tier
        })

    except Exception as e:
        logger.error(f"Failed to add hypothetical: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/hypotheticals', methods=['GET'])
def list_hypotheticals():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Fetch players and their stats
        cursor.execute("""
            SELECT hp.id, hp.name, hp.team, hp.position,
                   hs.PPG, hs.APG, hs.RPG, hs.STL, hs.BLK
            FROM HypotheticalPlayers hp
            JOIN HypotheticalStats hs ON hp.id = hs.player_id
        """)
        rows = cursor.fetchall()

        # Compute tiers
        result = []
        for row in rows:
            player = dict(row)
            stats = {k: player[k] for k in ['PPG', 'APG', 'RPG', 'STL', 'BLK']}
            overall_tier, position_tier = calculate_position_tier(stats, player['position'])

            player['overall_tier'] = overall_tier
            player['position_tier'] = position_tier
            result.append(player)

        return jsonify(result)

    except Exception as e:
        logger.error(f"Failed to list hypotheticals: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/hypotheticals/<int:player_id>', methods=['PUT'])
@app.route('/hypotheticals/<int:player_id>', methods=['PUT'])
def update_hypothetical(player_id):
    try:
        data = request.get_json()
        with get_db_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                UPDATE HypotheticalPlayers
                SET name = ?, team = ?, position = ?
                WHERE id = ?
            """, (data['name'], data['team'], data['position'], player_id))

            cursor.execute("""
                UPDATE HypotheticalStats
                SET PPG = ?, APG = ?, RPG = ?, STL = ?, BLK = ?
                WHERE player_id = ?
            """, (data['PPG'], data['APG'], data['RPG'], data['STL'], data['BLK'], player_id))

            conn.commit()
        return jsonify({'message': 'Updated successfully'})
    except Exception as e:
        logger.error(f"Update failed: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@app.route('/hypotheticals/<int:player_id>', methods=['DELETE'])
def delete_hypothetical(player_id):
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM HypotheticalPlayers WHERE id = ?", (player_id,))
            if not cursor.fetchone():
                return jsonify({'error': 'Player not found'}), 404

            
            cursor.execute("DELETE FROM HypotheticalPlayers WHERE id = ?", (player_id,))
            conn.commit()

        return jsonify({'message': f'Hypothetical player {player_id} deleted.'})
    except Exception as e:
        logger.error(f"Delete failed: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@app.route('/health', methods=['GET'])
def health_check():
    """Simple health check endpoint."""
    try:
        with get_db_connection() as conn:
            conn.execute("SELECT 1 FROM Players LIMIT 1")
        return jsonify({'status': 'healthy'})
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return jsonify({'status': 'unhealthy', 'error': str(e)}), 500

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Resource not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Server error: {str(error)}")
    return jsonify({'error': 'Internal server error'}), 500

@app.route('/compare_by_season_v2', methods=['GET'])
def compare_by_season_v2():
    player1_id = request.args.get('player1_id')
    player2_id = request.args.get('player2_id')
    season1 = request.args.get('season1')
    season2 = request.args.get('season2')
    category = request.args.get('category', 'overall')

    if not all([player1_id, player2_id, season1, season2]):
        return jsonify({'error': 'Missing required parameters'}), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        def get_player(player_id, season):
            cursor.execute("""
                SELECT p.name, p.position, s.PPG, s.APG, s.RPG, s.STL, s.BLK
                FROM Stats s
                JOIN Players p ON s.player_id = p.player_id
                WHERE s.player_id = ? AND s.season = ?
            """, (player_id, season))
            return cursor.fetchone()

        p1 = get_player(player1_id, season1)
        p2 = get_player(player2_id, season2)

        if not p1 or not p2:
            return jsonify({'error': 'One or both players not found for that season'}), 404

        def format_player(row, pid, season):
            stats = {k: row[k] or 0 for k in ['PPG', 'APG', 'RPG', 'STL', 'BLK']}
            overall, position = calculate_position_tier(stats, row['position'])
            return {
                'id': pid,
                'name': row['name'],
                'season': season,
                **stats,
                'overall_tier': overall,
                'position_tier': position
            }

        return jsonify({
            'category': category,
            'player1': format_player(p1, player1_id, season1),
            'player2': format_player(p2, player2_id, season2)
        })

    except Exception as e:
        logger.error(f"Comparison error: {e}")
        return jsonify({'error': 'Internal server error'}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)