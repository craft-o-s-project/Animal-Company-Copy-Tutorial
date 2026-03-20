# Game Backend Server + Admin GUI
# Change AppIDs, paths, IPs, and webhook URL to match your setup

from flask import Flask, request, jsonify, send_file
import requests, json, ipaddress, secrets, base64, time, sqlite3, random, os, string
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading

GENERATE_TOKENS = True
DB_PATH = r'database\data.db'                          # FIX 1: raw string — \d was an invalid escape
DISCORD_WEBHOOK_URL = 'https://discord.com/api/webhooksxxxxx'

# ---------------------------------------------------------------------------
# Default JSON values (used when a user has no saved data yet)
# ---------------------------------------------------------------------------

DEFAULT_AVATAR_INVENTORY = json.dumps({
    'items': [
        'animal_gorilla', 'bp_head_gorilla', 'bp_eye_gorilla',
        'bp_torso_gorilla', 'bp_arm_l_gorilla', 'bp_arm_r_gorilla',
        'bp_butt_gorilla', 'acc_fit_varsityjacket_black',
        'acc_fit_varsityjacket', 'outfit_cube', 'acc_fit_cubes',
        'acc_fit_head_cube', 'animal_skeletongorilla'
    ]
})

DEFAULT_RESEARCH = json.dumps({
    'nodes': [
        'node_arrow', 'node_arrow_heart', 'node_arrow_lightbulb',
        'node_backpack', 'node_backpack_large', 'node_backpack_large_basketball',
        'node_backpack_large_clover', 'node_balloon', 'node_balloon_heart',
        'node_baseball_bat', 'node_boxfan', 'node_clapper', 'node_cluster_grenade',
        'node_company_ration', 'node_crossbow', 'node_crossbow_heart',
        'node_crowbar', 'node_disposable_camera', 'node_dynamite',
        'node_dynamite_cube', 'node_flaregun', 'node_flashbang',
        'node_flashlight_mega', 'node_football', 'node_frying_pan',
        'node_glowsticks', 'node_heart_gun', 'node_hookshot', 'node_hoverpad',
        'node_impact_grenade', 'node_impulse_grenade', 'node_item_nut_shredder',
        'node_jetpack', 'node_lance', 'node_mega_broccoli', 'node_mini_broccoli',
        'node_ogre_hands', 'node_pickaxe', 'node_pickaxe_cny', 'node_pickaxe_cube',
        'node_plunger', 'node_pogostick', 'node_police_baton', 'node_quiver',
        'node_quiver_heart', 'node_revolver', 'node_revolver_ammo', 'node_rpg',
        'node_rpg_ammo', 'node_rpg_cny', 'node_saddle', 'node_shield',
        'node_shield_bones', 'node_shield_police', 'node_shotgun',
        'node_shotgun_ammo', 'node_skill_backpack_cap_1', 'node_skill_backpack_cap_2',
        'node_skill_backpack_cap_3', 'node_skill_explosive_1',
        'node_skill_gundamage_1', 'node_skill_health_1', 'node_skill_health_2',
        'node_skill_left_hip_attachment', 'node_skill_melee_1',
        'node_skill_melee_2', 'node_skill_melee_3',
        'node_skill_right_hip_attachment', 'node_skill_selling_1',
        'node_skill_selling_2', 'node_skill_selling_3', 'node_stick_armbones',
        'node_stick_bone', 'node_sticker_dispenser', 'node_sticky_dynamite',
        'node_tablet', 'node_teleport_grenade', 'node_theramin',
        'node_tripwire_explosive', 'node_umbrella', 'node_umbrella_clover',
        'node_whoopie', 'node_zipline_gun', 'node_zipline_rope'
    ]
})

DEFAULT_GAMEPLAY_PREFS = json.dumps({
    'recents': [
        'item_backpack_small_base', 'item_flaregun', 'item_tele_grenade',
        'item_glowstick', 'item_jetpack', 'item_stick_bone',
        'item_dynamite_cube', 'item_tablet', 'item_plunger', 'item_flashlight_mega'
    ],
    'favorites': ['item_flaregun']
})

DEFAULT_AVATAR_JSON = json.dumps({
    'butt': 'bp_butt_gorilla', 'head': 'bp_head_gorilla', 'tail': '',
    'torso': 'bp_torso_gorilla', 'armLeft': 'bp_arm_l_gorilla',
    'eyeLeft': 'bp_eye_gorilla', 'armRight': 'bp_arm_r_gorilla',
    'eyeRight': 'bp_eye_gorilla',
    'accessories': ['acc_fit_varsityjacket'],
    'primaryColor': '604170'
})

# ---------------------------------------------------------------------------
# Database Setup
# ---------------------------------------------------------------------------

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            ip TEXT PRIMARY KEY,
            username TEXT NOT NULL,
            custom_id TEXT NOT NULL,
            create_time REAL NOT NULL
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS banned_ips (
            ip TEXT PRIMARY KEY,
            reason TEXT DEFAULT 'No reason provided',
            banned_until REAL DEFAULT 0
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS user_data (
            custom_id TEXT PRIMARY KEY,
            hard_currency INTEGER DEFAULT 0,
            soft_currency INTEGER DEFAULT 20000000,
            research_points INTEGER DEFAULT 69420,
            stash_cols INTEGER DEFAULT 16,
            stash_rows INTEGER DEFAULT 8,
            stash_json TEXT DEFAULT '{"items": [], "stashPos": 0, "version": 1}',
            loadout_json TEXT DEFAULT '{"version": 1}',
            avatar_json TEXT DEFAULT '{}',
            avatar_inventory_json TEXT DEFAULT '{}',
            research_json TEXT DEFAULT '{}',
            gameplay_prefs_json TEXT DEFAULT '{}'
        )
    ''')
    # Migrate existing databases that are missing the new columns
    existing_cols = {row[1] for row in cur.execute('PRAGMA table_info(user_data)')}
    migrations = {
        'avatar_inventory_json': "TEXT DEFAULT '{}'",
        'research_json':         "TEXT DEFAULT '{}'",
        'gameplay_prefs_json':   "TEXT DEFAULT '{}'"
    }
    for col, definition in migrations.items():
        if col not in existing_cols:
            cur.execute(f'ALTER TABLE user_data ADD COLUMN {col} {definition}')
            print(f"[DB] Migrated: added column '{col}'")

    conn.commit()
    conn.close()

app = Flask(__name__)
init_db()

# ---------------------------------------------------------------------------
# Middleware: Log all requests to Discord
# ---------------------------------------------------------------------------

@app.after_request
def log_request_to_discord(response):
    method       = request.method
    url          = request.url
    path         = request.path
    headers      = dict(request.headers)
    body         = request.get_data(as_text=True)
    query_params = dict(request.args)
    status_code  = response.status_code

    message = {
        'content': f"📡 **Request to: {path}**",
        'embeds': [{
            'title': 'Request Details',
            'fields': [
                {'name': 'Method',       'value': method,                                                                             'inline': True},
                {'name': 'Path',         'value': path,                                                                               'inline': True},
                {'name': 'Status Code',  'value': str(status_code),                                                                   'inline': True},
                {'name': 'Full URL',     'value': url,                                                                                'inline': False},
                {'name': 'Query Params', 'value': f"```json\n{json.dumps(query_params, indent=2)}```" if query_params else '*(none)*', 'inline': False},
                {'name': 'Headers',      'value': f"```json\n{json.dumps(headers, indent=2)}```",                                     'inline': False},
                {'name': 'Body',         'value': f"```json\n{body}```" if body else '*(empty)*',                                     'inline': False},
            ],
            'color': 65280 if status_code < 400 else 16711680
        }]
    }
    try:
        requests.post(DISCORD_WEBHOOK_URL, json=message)
    except Exception:
        pass
    return response

# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------

def generate_username():
    return 'player-' + ''.join(random.choices(string.ascii_uppercase, k=6))

def generate_custom_id():
    return ''.join(random.choices(string.digits, k=17))

def get_client_ip():
    return request.headers.get('X-Forwarded-For', request.remote_addr)

def is_trusted_ip(ip_address):
    try:
        trusted_public_ips = {'OWNER IP WAS HERE', 'OWNER IP'}
        if ip_address in trusted_public_ips:
            return True
        ip = ipaddress.ip_address(ip_address)
        if ip.version == 4:
            return (ip in ipaddress.IPv4Network('1XXXXX1.0/24') or
                    ip in ipaddress.IPv4Network('1XXXXX8/29'))
        return ip in ipaddress.IPv6Network('2600:4040:303c:5b00::/64')
    except ValueError:
        return False

def get_or_create_user(ip):
    conn = sqlite3.connect(DB_PATH)
    cur  = conn.cursor()

    cur.execute('SELECT reason, banned_until FROM banned_ips WHERE ip = ?', (ip,))
    ban = cur.fetchone()
    if ban:
        reason, banned_until = ban
        if banned_until == 0 or time.time() < banned_until:
            conn.close()
            hours_left = round((banned_until - time.time()) / 3600, 1) if banned_until > 0 else 0
            return None, True, reason, hours_left
        else:
            cur.execute('DELETE FROM banned_ips WHERE ip = ?', (ip,))
            conn.commit()

    cur.execute('SELECT username, custom_id FROM users WHERE ip = ?', (ip,))
    result = cur.fetchone()

    if result:
        username, custom_id = result
    else:
        username  = '<color=red>0x11' if ip == '127.0.0.1' else generate_username()
        custom_id = generate_custom_id()
        cur.execute(
            'INSERT INTO users (ip, username, custom_id, create_time) VALUES (?, ?, ?, ?)',
            (ip, username, custom_id, time.time())
        )
        conn.commit()

    conn.close()
    return {'username': username, 'custom_id': custom_id}, False, None, 0

def get_user_data(custom_id):
    conn = sqlite3.connect(DB_PATH)
    cur  = conn.cursor()
    cur.execute('SELECT * FROM user_data WHERE custom_id = ?', (custom_id,))
    row = cur.fetchone()
    conn.close()

    if row:
        return {
            'custom_id':             row[0],
            'hard_currency':         row[1],
            'soft_currency':         row[2],
            'research_points':       row[3],
            'stash_cols':            row[4],
            'stash_rows':            row[5],
            'stash_json':            row[6],
            'loadout_json':          row[7],
            'avatar_json':           row[8],
            'avatar_inventory_json': row[9],
            'research_json':         row[10],
            'gameplay_prefs_json':   row[11],
        }
    else:
        # New user — insert row with defaults then return it
        conn = sqlite3.connect(DB_PATH)
        cur  = conn.cursor()
        cur.execute(
            '''INSERT OR IGNORE INTO user_data
               (custom_id, avatar_inventory_json, research_json, gameplay_prefs_json, avatar_json)
               VALUES (?, ?, ?, ?, ?)''',
            (custom_id, DEFAULT_AVATAR_INVENTORY, DEFAULT_RESEARCH,
             DEFAULT_GAMEPLAY_PREFS, DEFAULT_AVATAR_JSON)
        )
        conn.commit()
        conn.close()
        return get_user_data(custom_id)

def save_user_data(custom_id, field, value):
    allowed_fields = {
        'hard_currency', 'soft_currency', 'research_points',
        'stash_cols', 'stash_rows', 'stash_json', 'loadout_json',
        'avatar_json', 'avatar_inventory_json', 'research_json', 'gameplay_prefs_json'
    }
    if field not in allowed_fields:
        raise ValueError(f"Invalid field: {field}")
    conn = sqlite3.connect(DB_PATH)
    cur  = conn.cursor()
    cur.execute(f'UPDATE user_data SET {field} = ? WHERE custom_id = ?', (value, custom_id))
    if cur.rowcount == 0:
        cur.execute('INSERT OR IGNORE INTO user_data (custom_id) VALUES (?)', (custom_id,))
        cur.execute(f'UPDATE user_data SET {field} = ? WHERE custom_id = ?', (value, custom_id))
    conn.commit()
    conn.close()

def build_wallet_string(data):
    return json.dumps({
        'stashCols':      data['stash_cols'],
        'stashRows':      data['stash_rows'],
        'hardCurrency':   data['hard_currency'],
        'softCurrency':   data['soft_currency'],
        'researchPoints': data['research_points']
    })

def award_currency(custom_id, soft=0, hard=0, research=0):
    data = get_user_data(custom_id)
    save_user_data(custom_id, 'soft_currency',   data['soft_currency']   + soft)
    save_user_data(custom_id, 'hard_currency',   data['hard_currency']   + hard)
    save_user_data(custom_id, 'research_points', data['research_points'] + research)

def ban_user(ip, reason='No reason provided', hours=0):
    banned_until = time.time() + (hours * 3600) if hours > 0 else 0
    conn = sqlite3.connect(DB_PATH)
    cur  = conn.cursor()
    cur.execute(
        'INSERT OR REPLACE INTO banned_ips (ip, reason, banned_until) VALUES (?, ?, ?)',
        (ip, reason, banned_until)
    )
    conn.commit()
    conn.close()
    print(f"[BAN] {ip} banned for {'permanent' if hours == 0 else f'{hours} hours'} — reason: {reason}")

def generate_jwt(user_id):
    header = {'alg': 'HS256', 'typ': 'JWT'}
    now    = int(time.time())
    payload = {
        'tid': secrets.token_hex(16),
        'uid': user_id,
        'usn': secrets.token_hex(5),
        'vrs': {
            'authID':          secrets.token_hex(20),
            'clientUserAgent': 'MetaQuest 1.16.3.1138_5edcbd98',
            'deviceID':        secrets.token_hex(20),
            'loginType':       'meta_quest'
        },
        'exp': now + 72000,
        'iat': now
    }

    def b64encode(obj):
        return base64.urlsafe_b64encode(json.dumps(obj).encode()).decode().rstrip('=')

    signature = secrets.token_urlsafe(32)
    return f"{b64encode(header)}.{b64encode(payload)}.{signature}"

def generate_token_pair():
    user_id = secrets.token_hex(16)
    return {
        'token':         generate_jwt(user_id),
        'refresh_token': generate_jwt(user_id)
    }

def generate_gameplay_loadout():
    try:
        with open('econ_gameplay_items.json', 'r') as f:
            data     = json.load(f)
        item_ids = [item['id'] for item in data if 'id' in item]
    except Exception as e:
        print(f"Failed to load econ_gameplay_items.json: {e}")
        item_ids = [
            'item_jetpack', 'item_flaregun', 'item_dynamite', 'item_tablet',
            'item_flashlight_mega', 'item_plunger', 'item_crossbow',
            'item_revolver', 'item_shotgun', 'item_pickaxe'
        ]

    children = []
    for _ in range(20):
        if random.random() < 0.7 and 'item_arena_pistol' in item_ids:
            selected_item = 'item_arena_pistol'
        else:
            selected_item = random.choice(item_ids)
        children.append({
            'itemID':          selected_item,
            'scaleModifier':   100,
            'colorHue':        random.randint(10, 111),
            'colorSaturation': random.randint(10, 111)
        })

    return {
        'objects': [{
            'collection':       'user_inventory',
            'key':              'gameplay_loadout',
            'permission_read':  1,
            'permission_write': 1,
            'value': json.dumps({
                'version': 1,
                'back': {
                    'itemID':          'item_backpack_large_base',
                    'scaleModifier':   120,
                    'colorHue':        50,
                    'colorSaturation': 50,
                    'children':        children
                }
            })
        }]
    }

# ---------------------------------------------------------------------------
# Static Response Data
# ---------------------------------------------------------------------------

CLIENT_BOOTSTRAP_RESPONSE = {
    'payload': '{"updateType":"Optional","attestResult":"Valid","attestTokenExpiresAt":1820877961,"photonAppID":"","photonVoiceAppID":"","termsAcceptanceNeeded":[],"dailyMissionDateKey":"","dailyMissions":null,"dailyMissionResetTime":0,"serverTimeUnix":1720877961,"gameDataURL":"https://xeracompany.pythonanywhere.com/game-data-prod.zip}'
}

ECON_ITEMS_RESPONSE = {
    'payload': '[{"id":"item_apple","netID":71,"name":"Apple","description":"An apple a day keeps the doctor away!","category":"Consumables","price":200,"value":7,"isLoot":true,"isPurchasable":false,"isUnique":false,"isDevOnly":false},{"id":"item_arrow","netID":103,"name":"Arrow","description":"Can be attached to the crossbow.","category":"Ammo","price":199,"value":8,"isLoot":false,"isPurchasable":true,"isUnique":false,"isDevOnly":false},{"id":"item_arrow_heart","netID":116,"name":"Heart Arrow","description":"A love-themed arrow that will have your targets seeing hearts!","category":"Ammo","price":199,"value":8,"isLoot":false,"isPurchasable":true,"isUnique":false,"isDevOnly":false}]'
}

STATIC_TOKEN_PAIR = {
    'token':         'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0aWQiOiI3OGU0NDBiOS00NWZjLTRhODYtOTllMy02ZGM5Y2RjN2M1N2UiLCJ1aWQiOiJmM2E1NjE4YS1hMzNmLTQyMDAtYThiYS1lYjM3YzdiZmJmOWMiLCJ1c24iOiJ4ZW5pdHl5dCIsInZycyI6eyJhdXRoSUQiOiJkYTEzZjU4YzJiMjU0ZTgwYTM5YzA3YzRlNzkyNjlmOSIsImNsaWVudFVzZXJBZ2VudCI6Ik1ldGFRdWVzdCAxLjE2LjMuMTEzOF81ZWRjYmQ5OCIsImRldmljZUlEIjoiMTcyZjZjMmU3MWE5NGMwMTBjMWY2Mjk5OWJjM2QzMjEiLCJsb2dpblR5cGUiOiJtZXRhX3F1ZXN0In0sImV4cCI6MTc0NDA2MzQwNiwiaWF0IjoxNzQzOTk0MzE4fQ.nRJLbep6nCGeBTwruOunyNjDUiLxfcvpAJHl7E6n3m8',
    'refresh_token': 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0aWQiOiI3OGU0NDBiOS00NWZjLTRhODYtOTllMy02ZGM5Y2RjN2M1N2UiLCJ1aWQiOiJmM2E1NjE4YS1hMzNmLTQyMDAtYThiYS1lYjM3YzdiZmJmOWMiLCJ1c24iOiJ4ZW5pdHl5dCIsInZycyI6eyJhdXRoSUQiOiJkYTEzZjU4YzJiMjU0ZTgwYTM5YzA3YzRlNzkyNjlmOSIsImNsaWVudFVzZXJBZ2VudCI6Ik1ldGFRdWVzdCAxLjE2LjMuMTEzOF81ZWRjYmQ5OCIsImRldmljZUlEIjoiMTcyZjZjMmU3MWE5NGMwMTBjMWY2Mjk5OWJjM2QzMjEiLCJsb2dpblR5cGUiOiJtZXRhX3F1ZXN0In0sImV4cCI6MTc0NDE0NjIwNiwiaWF0IjoxNzQzOTk0MzE4fQ.f7nTHNnPrJW6oYYo54RDks1iDvntTP2yiBfpHdH-ygQ'
}

ACCOUNT_RESPONSE = {
    'user': {
        'id':          '2e8aace0-282d-4c3d-b9d4-6a3b3ba2c2a6',
        'username':    'ERROR',
        'lang_tag':    'en',
        'metadata':    '{}',
        'edge_count':  4,
        'create_time': '2024-08-24T07:30:12Z',
        'update_time': '2025-04-05T21:00:27Z'
    },
    'wallet':    '{"stashCols":4,"stashRows":2,"hardCurrency":0,"softCurrency":0,"researchPoints":0}',
    'custom_id': '26344644298513663'
}

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route('/v2/account/authenticate/custom', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS'])
def authenticate_custom():
    ip = get_client_ip()
    user, banned, reason, hours_left = get_or_create_user(ip)
    if banned:
        msg = f"You are permanently banned. Reason: {reason}" if hours_left == 0 else f"You are banned for {hours_left} hours. Reason: {reason}"
        return jsonify({'error': msg}), 403
    generate_gameplay_loadout()
    return jsonify(generate_token_pair() if GENERATE_TOKENS else STATIC_TOKEN_PAIR)

@app.route('/v2/account1', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS'])
def account_alt():
    return jsonify(ACCOUNT_RESPONSE)

@app.route('/v2/rpc/purchase.avatarItems', methods=['POST'])
def purchase_avatar_items():
    return jsonify({'payload': ''})

@app.route('/v2/rpc/avatar.update', methods=['POST'])
def avatar_update():
    return jsonify({'payload': ''})

@app.route('/v2/rpc/purchase.gameplayItems', methods=['POST'])
def purchase_gameplay_items():
    return jsonify({'payload': ''})

@app.route('/game-data-prod.zip')
def serve_game_data():
    client_ip = request.remote_addr
    print(f"Request from IP: {client_ip}")
    file_name = 'ram.zip'
    file_path = os.path.join('catalog/', file_name)   # FIX 2: 'catalog\'' was an unterminated string
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return 'File not found', 404
    file_size = os.path.getsize(file_path)
    print(f"Serving {file_name}, size: {file_size} bytes")
    try:
        return send_file(file_path, mimetype='application/zip', as_attachment=False,
                         download_name=file_name, max_age=3600)
    except Exception as e:
        print(f"Error serving file: {e}")
        return f"Error: {str(e)}", 500

@app.route('/v2/account', methods=['GET', 'PUT'])
def account():
    if request.method == 'PUT':
        response = jsonify({})
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate'
        response.headers['Content-Type'] = 'application/json'
        response.headers['Grpc-Metadata-Content-Type'] = 'application/grpc'
        return response
    try:
        ip = get_client_ip()
        user, banned, reason, hours_left = get_or_create_user(ip)
        if banned or user is None:
            raise Exception('User is banned or DB failed')
        data     = get_user_data(user['custom_id'])
        username = 'ALEX [HELPER]' if is_trusted_ip(ip) else 'XERA COMPANY'
        return jsonify({
            'user': {
                'id':          '2e8aace0-282d-4c3d-b9d4-6a3b3ba2c2a6',
                'username':    username,
                'lang_tag':    'en',
                'metadata':    json.dumps({'isDeveloper': str(is_trusted_ip(ip))}),
                'edge_count':  4,
                'create_time': '2024-08-24T07:30:12Z',
                'update_time': '2025-04-05T21:00:27Z'
            },
            'wallet':    build_wallet_string(data),
            'custom_id': user['custom_id']
        })
    except Exception as e:
        print(f"[FALLBACK] DB failed or user banned: {e}")
        import traceback; traceback.print_exc()
        return jsonify(ACCOUNT_RESPONSE)

@app.route('/v2/account/alt2', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS'])
def account_storage():
    return jsonify({'objects': _build_storage_objects_for_ip()})

def _build_storage_objects_for_ip():
    """Return per-user storage objects, falling back to defaults for new users."""
    ip = get_client_ip()
    user, banned, reason, hours_left = get_or_create_user(ip)
    if banned or not user:
        return []
    data = get_user_data(user['custom_id'])
    uid  = '2e8aace0-282d-4c3d-b9d4-6a3b3ba2c2a6'
    now  = '2025-04-05T21:00:27Z'

    # Use saved data if it exists, otherwise fall back to the defaults defined above
    avatar_val   = data['avatar_json']           if data['avatar_json']           != '{}' else DEFAULT_AVATAR_JSON
    av_inv_val   = data['avatar_inventory_json'] if data['avatar_inventory_json'] != '{}' else DEFAULT_AVATAR_INVENTORY
    research_val = data['research_json']         if data['research_json']         != '{}' else DEFAULT_RESEARCH
    prefs_val    = data['gameplay_prefs_json']   if data['gameplay_prefs_json']   != '{}' else DEFAULT_GAMEPLAY_PREFS

    return [
        {
            'collection': 'user_avatar', 'key': '0', 'user_id': uid,
            'value': avatar_val,
            'version': '7a326a2a4d0639a5f08e3116bb99a3bf',
            'permission_read': 2, 'create_time': '2024-10-29T00:22:08Z', 'update_time': now
        },
        {
            'collection': 'user_inventory', 'key': 'avatar', 'user_id': uid,
            'value': av_inv_val,
            'version': 'b6a38347a29ec461a06d5e30ed8b3cd8',
            'permission_read': 1, 'create_time': '2024-10-29T00:22:08Z', 'update_time': now
        },
        {
            'collection': 'user_inventory', 'key': 'research', 'user_id': uid,
            'value': research_val,
            'version': 'bb49186ef5806541f461f4c9f3f4f871',
            'permission_read': 1, 'create_time': '2025-02-20T00:51:38Z', 'update_time': now
        },
        {
            'collection': 'user_inventory', 'key': 'stash', 'user_id': uid,
            'value': data['stash_json'],
            'version': '8e192e752405b279447f0523a9049fdd',
            'permission_read': 1, 'permission_write': 1,
            'create_time': '2025-02-20T00:51:38Z', 'update_time': now
        },
        {
            'collection': 'user_inventory', 'key': 'gameplay_loadout', 'user_id': uid,
            'value': data['loadout_json'],
            'version': '77efb8e3fa276d4674932392a66555e4',
            'permission_read': 1, 'permission_write': 1,
            'create_time': '2025-02-20T00:51:50Z', 'update_time': now
        },
        {
            'collection': 'user_preferences', 'key': 'gameplay_items', 'user_id': uid,
            'value': prefs_val,
            'version': '80aae98f75aab68ca6540247a17cc4a1',
            'permission_read': 1, 'permission_write': 1,
            'create_time': '2025-02-20T00:52:27Z', 'update_time': now
        }
    ]

@app.route('/v2/account/link/device', methods=['POST'])
def link_device():
    return jsonify({
        'id':          secrets.token_hex(16),
        'user_id':     '13b8dce4-2c8e-4945-90b6-19af0c2b0ad7',
        'linked':      True,
        'create_time': '2025-01-15T18:08:45Z'
    })

@app.route('/v2/account/session/refresh', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS'])
def session_refresh():
    return jsonify(generate_token_pair() if GENERATE_TOKENS else STATIC_TOKEN_PAIR)

@app.route('/v2/rpc/attest.start', methods=['POST'])
def attest_start():
    ip = get_client_ip()
    user, banned, reason, hours_left = get_or_create_user(ip)
    if banned:
        msg = f"You are permanently banned. Reason: {reason}" if hours_left == 0 else f"You are banned for {hours_left} hours. Reason: {reason}"
        return jsonify({
            'payload': json.dumps({
                'status':       'banned',
                'attestResult': 'Invalid',
                'message':      msg
            })
        }), 403
    return jsonify({
        'payload': json.dumps({
            'status':       'success',
            'attestResult': 'Valid',
            'message':      'Attestation validated'
        })
    })

@app.route('/v2/storage', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS'])
def storage():
    if request.method == 'POST':
        try:
            data = request.get_json(force=True)

            # ---- READ: client requests objects by ID ----
            if data and 'object_ids' in data:
                user_id = data['object_ids'][0].get('user_id') if data['object_ids'] else None
                if not user_id:
                    return jsonify({'objects': []})
                ip = get_client_ip()
                user, banned, reason, hours_left = get_or_create_user(ip)
                if banned or not user:
                    return jsonify({'objects': []})
                user_data = get_user_data(user['custom_id'])

                avatar_val   = user_data['avatar_json']           if user_data['avatar_json']           != '{}' else DEFAULT_AVATAR_JSON
                av_inv_val   = user_data['avatar_inventory_json'] if user_data['avatar_inventory_json'] != '{}' else DEFAULT_AVATAR_INVENTORY
                research_val = user_data['research_json']         if user_data['research_json']         != '{}' else DEFAULT_RESEARCH
                prefs_val    = user_data['gameplay_prefs_json']   if user_data['gameplay_prefs_json']   != '{}' else DEFAULT_GAMEPLAY_PREFS

                # Build a lookup so we only return what was actually requested
                value_map = {
                    ('user_avatar',        '0'):               avatar_val,
                    ('user_inventory',     'avatar'):          av_inv_val,
                    ('user_inventory',     'research'):        research_val,
                    ('user_inventory',     'stash'):           user_data['stash_json'],
                    ('user_inventory',     'gameplay_loadout'): generate_gameplay_loadout()['objects'][0]['value'],
                    ('user_preferences',   'gameplay_items'):  prefs_val,
                }

                response_objects = []
                for obj_id in data['object_ids']:
                    col = obj_id.get('collection', '')
                    key = obj_id.get('key', '')
                    val = value_map.get((col, key))
                    if val is None:
                        continue
                    response_objects.append({
                        'collection':       col,
                        'key':              key,
                        'user_id':          user_id,
                        'value':            val,
                        'permission_read':  1,
                        'permission_write': 1,
                    })
                return jsonify({'objects': response_objects})

            # ---- WRITE: client saves objects ----
            elif data and 'objects' in data:
                ip = get_client_ip()
                user, banned, reason, hours_left = get_or_create_user(ip)
                if banned or not user:
                    return jsonify({})
                for obj in data['objects']:
                    key        = obj.get('key')
                    collection = obj.get('collection')
                    value      = obj.get('value')
                    if key == 'stash':
                        save_user_data(user['custom_id'], 'stash_json',            value)
                    elif key == 'gameplay_loadout':
                        save_user_data(user['custom_id'], 'loadout_json',          value)
                    elif key == '0' and collection == 'user_avatar':
                        save_user_data(user['custom_id'], 'avatar_json',           value)
                    elif key == 'avatar' and collection == 'user_inventory':
                        save_user_data(user['custom_id'], 'avatar_inventory_json', value)
                    elif key == 'research' and collection == 'user_inventory':
                        save_user_data(user['custom_id'], 'research_json',         value)
                    elif key == 'gameplay_items' and collection == 'user_preferences':
                        save_user_data(user['custom_id'], 'gameplay_prefs_json',   value)
                return jsonify({})

            return jsonify({'objects': []})
        except Exception as e:
            print(f"Storage error: {e}")
            return jsonify({'objects': []})

    # GET — return full per-user object list
    return jsonify({'objects': _build_storage_objects_for_ip()})

@app.route('/v2/storage/econ_gameplay_items', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS'])
def econ_gameplay_items():
    return jsonify(ECON_ITEMS_RESPONSE)

@app.route('/v2/rpc/mining.balance', methods=['GET'])
def mining_balance():
    try:
        ip = get_client_ip()
        user, banned, reason, hours_left = get_or_create_user(ip)
        if not banned and user:
            data = get_user_data(user['custom_id'])
            return jsonify({'payload': json.dumps({
                'hardCurrency':   data['hard_currency'],
                'researchPoints': data['research_points']
            })}), 200
    except Exception as e:
        print(f"mining.balance error: {e}")
    return jsonify({'payload': json.dumps({'hardCurrency': 20000000, 'researchPoints': 999999})}), 200

@app.route('/v2/rpc/purchase.list', methods=['GET'])
def purchase_list():
    return jsonify({'payload': json.dumps({'purchases': [
        {
            'user_id':           '13b8dce4-2c8e-4945-90b6-19af0c2b0ad7',
            'product_id':        'RESEARCH_PACK',
            'transaction_id':    '540282689176766',
            'store':             3,
            'purchase_time':     {'seconds': 1741450711},
            'create_time':       {'seconds': 1741450837, 'nanos': 694669000},
            'update_time':       {'seconds': 1741450837, 'nanos': 694669000},
            'refund_time':       {},
            'provider_response': json.dumps({'success': True}),
            'environment':       2
        },
        {
            'user_id':           '13b8dce4-2c8e-4945-90b6-19af0c2b0ad7',
            'product_id':        'G.O.A.T_BUNDLE',
            'transaction_id':    '540281232510245',
            'store':             3,
            'purchase_time':     {'seconds': 1741450591},
            'create_time':       {'seconds': 1741450722, 'nanos': 851245000},
            'update_time':       {'seconds': 1741450722, 'nanos': 851245000},
            'refund_time':       {},
            'provider_response': json.dumps({'success': True}),
            'environment':       2
        }
    ]})}), 200

@app.route('/v2/rpc/clientBootstrap', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS'])
def client_bootstrap():
    return jsonify(CLIENT_BOOTSTRAP_RESPONSE)

@app.route('/auth', methods=['GET', 'POST'])
def photon_auth():
    auth_token = request.args.get('auth_token')
    print('🔐 Photon Auth Request Received')
    if auth_token:
        print(f"auth_token: {auth_token}")
        message = 'Authentication successful'
    else:
        print('⚠️ No auth_token provided')
        message = 'Authenticated without token'
    return jsonify({
        'ResultCode':    1,
        'Message':       message,
        'UserId':        secrets.token_hex(16),
        'SessionID':     secrets.token_hex(12),
        'Authenticated': True
    }), 200

@app.route('/debug', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS'])
def debug():
    method  = request.method
    url     = request.url
    headers = dict(request.headers)
    body    = request.get_data(as_text=True)
    message = {
        'content': '📡 **/debug request received**',
        'embeds': [{
            'title': 'Request Info',
            'fields': [
                {'name': 'Method',  'value': method,                                         'inline': True},
                {'name': 'URL',     'value': url,                                            'inline': False},
                {'name': 'Headers', 'value': f"```json\n{json.dumps(headers, indent=2)}```", 'inline': False},
                {'name': 'Body',    'value': f"```json\n{body}```" if body else '*(empty)*', 'inline': False},
            ],
            'color': 65484
        }]
    }
    try:
        requests.post(DISCORD_WEBHOOK_URL, json=message)
    except Exception as e:
        return f"Failed to send to Discord: {e}", 500
    return 'Sent debug to discord', 200

# ---------------------------------------------------------------------------
# Admin GUI
# ---------------------------------------------------------------------------

class AdminGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Xera Backend Admin")
        self.root.geometry("1000x700")
        self.root.configure(bg='#1e1e2e')

        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TFrame',           background='#1e1e2e')
        style.configure('TLabel',           background='#1e1e2e', foreground='#cdd6f4', font=('Consolas', 10))
        style.configure('TButton',          background='#313244', foreground='#cdd6f4', font=('Consolas', 10), borderwidth=0, padding=6)
        style.map('TButton',                background=[('active', '#45475a')])
        style.configure('TEntry',           fieldbackground='#313244', foreground='#cdd6f4', insertcolor='#cdd6f4', font=('Consolas', 10))
        style.configure('TNotebook',        background='#1e1e2e', borderwidth=0)
        style.configure('TNotebook.Tab',    background='#313244', foreground='#cdd6f4', font=('Consolas', 10), padding=[10, 4])
        style.map('TNotebook.Tab',          background=[('selected', '#45475a')])
        style.configure('Treeview',         background='#313244', foreground='#cdd6f4', fieldbackground='#313244', font=('Consolas', 10), rowheight=24)
        style.configure('Treeview.Heading', background='#45475a', foreground='#cdd6f4', font=('Consolas', 10, 'bold'))
        style.map('Treeview',               background=[('selected', '#585b70')])

        notebook = ttk.Notebook(root)
        notebook.pack(fill='both', expand=True, padx=10, pady=10)

        self.tab_users    = ttk.Frame(notebook)
        self.tab_currency = ttk.Frame(notebook)
        self.tab_bans     = ttk.Frame(notebook)
        self.tab_logs     = ttk.Frame(notebook)

        notebook.add(self.tab_users,    text='👥  Users')
        notebook.add(self.tab_currency, text='💰  Currency')
        notebook.add(self.tab_bans,     text='🔨  Bans')
        notebook.add(self.tab_logs,     text='📋  Logs')

        self._build_users_tab()
        self._build_currency_tab()
        self._build_bans_tab()
        self._build_logs_tab()

        self.refresh_users()
        self.log("Admin GUI started.")

    # -----------------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------------

    def log(self, message):
        timestamp = time.strftime('%H:%M:%S')
        self.logs_box.configure(state='normal')
        self.logs_box.insert('end', f"[{timestamp}] {message}\n")
        self.logs_box.see('end')
        self.logs_box.configure(state='disabled')

    def _label_entry_row(self, parent, label, row, default=''):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky='w', padx=8, pady=4)
        var   = tk.StringVar(value=default)
        entry = ttk.Entry(parent, textvariable=var, width=30)
        entry.grid(row=row, column=1, sticky='w', padx=8, pady=4)
        return var

    def _colored_button(self, parent, text, color, command, row, col):
        btn = tk.Button(
            parent, text=text, command=command,
            bg=color, fg='#cdd6f4', font=('Consolas', 10),
            relief='flat', padx=8, pady=6, cursor='hand2',
            activebackground='#45475a', activeforeground='#cdd6f4'
        )
        btn.grid(row=row, column=col, sticky='w', padx=4, pady=4)
        return btn

    def _get_user_by_username(self, username):
        conn = sqlite3.connect(DB_PATH)
        cur  = conn.cursor()
        cur.execute('SELECT ip, username, custom_id, create_time FROM users WHERE username = ?', (username,))
        row = cur.fetchone()
        conn.close()
        return row

    # -----------------------------------------------------------------------
    # Users Tab
    # -----------------------------------------------------------------------

    def _build_users_tab(self):
        frame = self.tab_users
        cols  = ('Username', 'IP', 'Custom ID', 'Created')
        self.users_tree = ttk.Treeview(frame, columns=cols, show='headings', selectmode='browse')
        for col in cols:
            self.users_tree.heading(col, text=col)
            self.users_tree.column(col, width=200 if col != 'Created' else 160)
        self.users_tree.pack(fill='both', expand=True, padx=10, pady=(10, 4))

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill='x', padx=10, pady=4)
        self._colored_button(btn_frame, '🔄 Refresh',     '#313244', self.refresh_users, 0, 0)
        self._colored_button(btn_frame, '🗑 Delete User', '#f38ba8', self.delete_user,   0, 1)

    def refresh_users(self):
        for row in self.users_tree.get_children():
            self.users_tree.delete(row)
        conn = sqlite3.connect(DB_PATH)
        cur  = conn.cursor()
        cur.execute('SELECT username, ip, custom_id, create_time FROM users')
        for row in cur.fetchall():
            username, ip, custom_id, create_time = row
            created = time.strftime('%Y-%m-%d %H:%M', time.localtime(create_time))
            self.users_tree.insert('', 'end', values=(username, ip, custom_id, created))
        conn.close()
        self.log("Users list refreshed.")

    def delete_user(self):
        selected = self.users_tree.focus()
        if not selected:
            messagebox.showwarning("No Selection", "Select a user first.")
            return
        values   = self.users_tree.item(selected, 'values')
        username, ip, custom_id = values[0], values[1], values[2]
        if not messagebox.askyesno("Confirm", f"Delete user '{username}' ({ip})?"):
            return
        conn = sqlite3.connect(DB_PATH)
        cur  = conn.cursor()
        cur.execute('DELETE FROM users WHERE ip = ?', (ip,))
        cur.execute('DELETE FROM user_data WHERE custom_id = ?', (custom_id,))
        conn.commit()
        conn.close()
        self.log(f"Deleted user '{username}' ({ip}).")
        self.refresh_users()

    # -----------------------------------------------------------------------
    # Currency Tab
    # -----------------------------------------------------------------------

    def _build_currency_tab(self):
        frame = self.tab_currency

        ttk.Label(frame, text="Target User:", font=('Consolas', 11, 'bold')).grid(
            row=0, column=0, sticky='w', padx=8, pady=(12, 4))

        self.currency_username = self._label_entry_row(frame, 'Username:', 1)
        self.currency_amount   = self._label_entry_row(frame, 'Amount:',   2, default='0')

        ttk.Label(frame, text="Currency Type:").grid(row=3, column=0, sticky='w', padx=8, pady=4)
        self.currency_type = tk.StringVar(value='soft_currency')
        currency_menu      = ttk.Combobox(frame, textvariable=self.currency_type, width=28, state='readonly')
        currency_menu['values'] = ('soft_currency', 'hard_currency', 'research_points')
        currency_menu.grid(row=3, column=1, sticky='w', padx=8, pady=4)

        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=4, column=0, columnspan=2, sticky='w', padx=4, pady=8)
        self._colored_button(btn_frame, '➕ Add',      '#a6e3a1', self.currency_add,      0, 0)
        self._colored_button(btn_frame, '➖ Subtract', '#fab387', self.currency_subtract,  0, 1)
        self._colored_button(btn_frame, '🎁 Set',      '#89b4fa', self.currency_set,       0, 2)
        self._colored_button(btn_frame, '🔍 View',     '#313244', self.currency_view,      0, 3)

        self.currency_info = tk.Text(
            frame, height=6, bg='#313244', fg='#cdd6f4',
            font=('Consolas', 10), relief='flat', state='disabled'
        )
        self.currency_info.grid(row=5, column=0, columnspan=2, sticky='ew', padx=8, pady=8)
        frame.columnconfigure(1, weight=1)

    def _currency_get_user(self):
        username = self.currency_username.get().strip()
        if not username:
            messagebox.showwarning("Missing", "Enter a username.")
            return None, None
        row = self._get_user_by_username(username)
        if not row:
            messagebox.showerror("Not Found", f"No user '{username}' found.")
            return None, None
        return row[0], row[2]  # ip, custom_id

    def currency_add(self):
        ip, custom_id = self._currency_get_user()
        if not custom_id: return
        try:
            amount = int(self.currency_amount.get())
            field  = self.currency_type.get()
            data   = get_user_data(custom_id)
            save_user_data(custom_id, field, data[field] + amount)
            self.log(f"Added {amount} {field} to '{self.currency_username.get()}'.")
            self.currency_view()
        except ValueError:
            messagebox.showerror("Error", "Amount must be an integer.")

    def currency_subtract(self):
        ip, custom_id = self._currency_get_user()
        if not custom_id: return
        try:
            amount  = int(self.currency_amount.get())
            field   = self.currency_type.get()
            data    = get_user_data(custom_id)
            new_val = max(0, data[field] - amount)
            save_user_data(custom_id, field, new_val)
            self.log(f"Subtracted {amount} {field} from '{self.currency_username.get()}'. New: {new_val}.")
            self.currency_view()
        except ValueError:
            messagebox.showerror("Error", "Amount must be an integer.")

    def currency_set(self):
        ip, custom_id = self._currency_get_user()
        if not custom_id: return
        try:
            amount = int(self.currency_amount.get())
            field  = self.currency_type.get()
            save_user_data(custom_id, field, amount)
            self.log(f"Set {field} to {amount} for '{self.currency_username.get()}'.")
            self.currency_view()
        except ValueError:
            messagebox.showerror("Error", "Amount must be an integer.")

    def currency_view(self):
        ip, custom_id = self._currency_get_user()
        if not custom_id: return
        data = get_user_data(custom_id)
        text = (
            f"  Username:        {self.currency_username.get()}\n"
            f"  Custom ID:       {custom_id}\n"
            f"  Soft Currency:   {data['soft_currency']:,}\n"
            f"  Hard Currency:   {data['hard_currency']:,}\n"
            f"  Research Points: {data['research_points']:,}\n"
            f"  Stash:           {data['stash_cols']}x{data['stash_rows']}"
        )
        self.currency_info.configure(state='normal')
        self.currency_info.delete('1.0', 'end')
        self.currency_info.insert('end', text)
        self.currency_info.configure(state='disabled')
        self.log(f"Viewed currency for '{self.currency_username.get()}'.")

    # -----------------------------------------------------------------------
    # Bans Tab
    # -----------------------------------------------------------------------

    def _build_bans_tab(self):
        frame = self.tab_bans

        ttk.Label(frame, text="Active Bans:", font=('Consolas', 11, 'bold')).grid(
            row=0, column=0, columnspan=2, sticky='w', padx=8, pady=(12, 2))

        cols = ('IP', 'Reason', 'Expires')
        self.bans_tree = ttk.Treeview(frame, columns=cols, show='headings', height=6, selectmode='browse')
        self.bans_tree.heading('IP',      text='IP')
        self.bans_tree.heading('Reason',  text='Reason')
        self.bans_tree.heading('Expires', text='Expires')
        self.bans_tree.column('IP',      width=160)
        self.bans_tree.column('Reason',  width=260)
        self.bans_tree.column('Expires', width=180)
        self.bans_tree.grid(row=1, column=0, columnspan=2, sticky='ew', padx=8, pady=4)

        ttk.Separator(frame, orient='horizontal').grid(
            row=2, column=0, columnspan=2, sticky='ew', padx=8, pady=8)

        ttk.Label(frame, text="Ban a User:", font=('Consolas', 11, 'bold')).grid(
            row=3, column=0, sticky='w', padx=8, pady=(4, 2))

        self.ban_username = self._label_entry_row(frame, 'Username:',            4)
        self.ban_reason   = self._label_entry_row(frame, 'Reason:',              5, default='Cheating')
        self.ban_hours    = self._label_entry_row(frame, 'Hours (0=permanent):', 6, default='24')

        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=7, column=0, columnspan=2, sticky='w', padx=4, pady=8)
        self._colored_button(btn_frame, '🔨 Ban User', '#f38ba8', self.do_ban,       0, 0)
        self._colored_button(btn_frame, '✅ Unban',     '#a6e3a1', self.do_unban,     0, 1)
        self._colored_button(btn_frame, '🔄 Refresh',  '#313244', self.refresh_bans, 0, 2)

        frame.columnconfigure(1, weight=1)
        self.refresh_bans()

    def refresh_bans(self):
        for row in self.bans_tree.get_children():
            self.bans_tree.delete(row)
        conn = sqlite3.connect(DB_PATH)
        cur  = conn.cursor()
        cur.execute('SELECT ip, reason, banned_until FROM banned_ips')
        for row in cur.fetchall():
            ip, reason, banned_until = row
            expires = 'Permanent' if banned_until == 0 else time.strftime('%Y-%m-%d %H:%M', time.localtime(banned_until))
            self.bans_tree.insert('', 'end', values=(ip, reason, expires))
        conn.close()
        self.log("Bans list refreshed.")

    def do_ban(self):
        username = self.ban_username.get().strip()
        reason   = self.ban_reason.get().strip() or 'No reason provided'
        if not username:
            messagebox.showwarning("Missing", "Enter a username.")
            return
        try:
            hours = float(self.ban_hours.get())
        except ValueError:
            messagebox.showerror("Error", "Hours must be a number.")
            return
        row = self._get_user_by_username(username)
        if not row:
            messagebox.showerror("Not Found", f"No user '{username}' found.")
            return
        ip    = row[0]
        label = 'permanently' if hours == 0 else f'for {hours} hours'
        ban_user(ip, reason=reason, hours=hours)
        self.log(f"Banned '{username}' ({ip}) {label}. Reason: {reason}")
        self.refresh_bans()

    def do_unban(self):
        selected = self.bans_tree.focus()
        if selected:
            ip = self.bans_tree.item(selected, 'values')[0]
        else:
            username = self.ban_username.get().strip()
            if not username:
                messagebox.showwarning("Missing", "Select a ban or enter a username.")
                return
            row = self._get_user_by_username(username)
            if not row:
                messagebox.showerror("Not Found", f"No user '{username}' found.")
                return
            ip = row[0]
        conn = sqlite3.connect(DB_PATH)
        cur  = conn.cursor()
        cur.execute('DELETE FROM banned_ips WHERE ip = ?', (ip,))
        conn.commit()
        conn.close()
        self.log(f"Unbanned IP: {ip}")
        self.refresh_bans()

    # -----------------------------------------------------------------------
    # Logs Tab
    # -----------------------------------------------------------------------

    def _build_logs_tab(self):
        frame = self.tab_logs
        self.logs_box = scrolledtext.ScrolledText(
            frame, state='disabled', bg='#181825', fg='#a6e3a1',
            font=('Consolas', 10), relief='flat', wrap='word'
        )
        self.logs_box.pack(fill='both', expand=True, padx=10, pady=10)

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill='x', padx=10, pady=(0, 6))
        self._colored_button(btn_frame, '🗑 Clear Logs', '#f38ba8', self.clear_logs, 0, 0)

    def clear_logs(self):
        self.logs_box.configure(state='normal')
        self.logs_box.delete('1.0', 'end')
        self.logs_box.configure(state='disabled')


def start_admin_gui():
    root = tk.Tk()
    AdminGUI(root)
    root.mainloop()

# Start GUI in background thread so Flask still runs normally
gui_thread = threading.Thread(target=start_admin_gui, daemon=True)
gui_thread.start()

if __name__ == '__main__':
    app.run(debug=False)
