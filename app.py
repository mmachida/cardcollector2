from flask import Flask, render_template_string, request, redirect, url_for
from pymongo import MongoClient
from datetime import timedelta
from bson import ObjectId
import os

app = Flask(__name__)

# --- Conexão MongoDB ---
MONGO_URI = os.getenv("uri")  # pega a variável de ambiente chamada 'uri'
client = MongoClient(MONGO_URI)
db = client["gacha"]
users_col = db["users"]
inventory_col = db["inventory"]
cards_col = db["cards"]
log_col = db["log_history"]

# --- Template HTML ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>mGacha Dashboard</title>
    <style>
        body { font-family: Arial; background: #111; color: white; margin: 20px; }
        h2, h3 { margin: 5px 0; }
        .cards { display: flex; flex-wrap: wrap; gap: 10px; }
        .card { width: 285px; text-align: center; margin-bottom: 20px; }
        .card img { width: 100%; display: block; }
        select, button { padding: 5px; margin-right: 5px; }
        .filters { display: flex; align-items: flex-end; margin-bottom: 20px; gap: 10px; }
        textarea { width: 100%; background: #222; color: #fff; }
    </style>
</head>
<body>
    <h1>🎴 mGacha Dashboard</h1>

    <h2>🏆 Top 3 usuários com mais cartas únicas</h2>
    {% for user in top_users %}
        <div>{{ user['twitch_name'] }} - {{ user['total_unique_cards'] }}/{{ total_unique_cards }}</div>
    {% endfor %}

    <hr>

    <form method="get" action="{{ url_for('index') }}">
        <label>Usuário:</label>
        <select name="user_id" onchange="this.form.submit()">
            {% for user in all_users %}
                <option value="{{ user['_id'] }}" {% if selected_user_id and selected_user_id == user['_id'] %}selected{% endif %}>{{ user['twitch_name'] }}</option>
            {% endfor %}
        </select>

        <div class="filters">
            <div>
                <label>Tipo de ordenação:</label>
                <select name="sort_type" onchange="this.form.submit()">
                    {% for option in ['Número','Alfabético','Raridade','Quantidade'] %}
                        <option value="{{ option }}" {% if sort_type == option %}selected{% endif %}>{{ option }}</option>
                    {% endfor %}
                </select>
            </div>
            <div>
                <button name="reverse" value="{{ '1' if not reverse else '0' }}">⇅</button>
            </div>
        </div>
    </form>

    <h2>📦 Cartas de {{ selected_user_name }}</h2>
    <div class="cards">
        {% for card in cards_list %}
            <div class="card">
                <img src="{{ card['image_url'] }}">
                <div>{{ card['name'] }} - {{ card['rarity'] }} x{{ card['quantity'] }}</div>
            </div>
        {% endfor %}
        {% if not cards_list %}
            <div>Nenhuma carta encontrada</div>
        {% endif %}
    </div>

    <hr>
    <h2>📜 Histórico de ações de {{ selected_user_name }}</h2>
    {% if logs_list %}
        <textarea rows="10" readonly>
{% for log in logs_list %}{{ log }}
{% endfor %}
        </textarea>
    {% else %}
        <div>Nenhum registro encontrado</div>
    {% endif %}
</body>
</html>
"""

# --- Rota principal ---
@app.route("/", methods=["GET"])
def index():
    all_users = list(users_col.find())
    total_unique_cards = cards_col.count_documents({})
    top_users = list(users_col.find().sort("total_unique_cards", -1).limit(3))

    # --- Obter parâmetros ---
    user_id = request.args.get("user_id")
    sort_type = request.args.get("sort_type", "Número")
    reverse = request.args.get("reverse", "0") == "1"

    selected_user_id = ObjectId(user_id) if user_id else None
    selected_user_doc = users_col.find_one({"_id": selected_user_id}) if selected_user_id else None
    selected_user_name = selected_user_doc["twitch_name"] if selected_user_doc else ""

    # --- Carregar cartas ---
    cards_list = []
    if selected_user_id:
        user_inventory = inventory_col.find({"user_id": selected_user_id})
        for item in user_inventory:
            card_doc = cards_col.find_one({"_id": item["card_id"]})
            if card_doc:
                cards_list.append({
                    "number": card_doc.get("card_number", 0),
                    "name": card_doc["name"],
                    "rarity": card_doc["rarity"],
                    "image_url": card_doc["image_url"],
                    "quantity": item.get("quantity", 1)
                })

    # --- Ordenação ---
    if sort_type == "Número":
        cards_list.sort(key=lambda x: x["number"], reverse=reverse)
    elif sort_type == "Alfabético":
        cards_list.sort(key=lambda x: x["name"].lower(), reverse=reverse)
    elif sort_type == "Raridade":
        rarity_order = ["legendary", "epic", "rare", "common"]
        cards_list.sort(key=lambda x: rarity_order.index(x["rarity"].lower()), reverse=reverse)
    elif sort_type == "Quantidade":
        cards_list.sort(key=lambda x: x["quantity"], reverse=True)  # default maior -> menor

    # --- Histórico ---
    logs_list = []
    if selected_user_doc:
        logs_cursor = log_col.find({"twitch_id": selected_user_doc["twitch_id"]}).sort("timestamp", -1)
        for log in logs_cursor:
            ts = log["timestamp"]
            ts_brasil = ts - timedelta(hours=3)
            details = log.get("details", {})
            name = details.get("name", "")
            rarity = details.get("rarity", "")
            logs_list.append(f"{ts_brasil.strftime('%Y-%m-%d %H:%M:%S')} - {log['action']} - {name} - {rarity}")

    return render_template_string(
        HTML_TEMPLATE,
        all_users=all_users,
        top_users=top_users,
        total_unique_cards=total_unique_cards,
        selected_user_id=selected_user_id,
        selected_user_name=selected_user_name,
        sort_type=sort_type,
        reverse=reverse,
        cards_list=cards_list,
        logs_list=logs_list
    )

if __name__ == "__main__":
    app.run(debug=True)
