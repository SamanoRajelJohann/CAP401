from flask import Flask, render_template, request, redirect, session
import pymysql
from scraper import main_system
import uuid
import os

app = Flask(__name__)

app.secret_key = os.getenv("FLASK_SECRET_KEY", "fallback-insecure-dev-key")

# MySQL Config
db = pymysql.connect(
    host="localhost",
    user="root",
    password="",
    db="websearch_demo",
    charset="utf8mb4",
    cursorclass=pymysql.cursors.DictCursor
)

@app.before_request
def assign_user():
    if 'user_id' not in session:
        session['user_id'] = str(uuid.uuid4())
        try:
            with db.cursor() as cursor:
                insert_user_sql = "INSERT INTO users (uuid) VALUES (%s)"
                cursor.execute(insert_user_sql, (session['user_id'],))
                db.commit()
        except Exception as e:
            print("❌ User creation error:", e)

@app.route('/', methods=['GET', 'POST'])
def index():
    results = []
    if request.method == 'POST':
        query = request.form['query']
        serpapi_key = request.form['serpapi_key'] or None
        results = main_system(query, serpapi_key)

        try:
            with db.cursor() as cursor:
                for item in results:
                    url = item["url"]

                    # Insert into results table
                    insert_result_sql = "INSERT INTO results (query, url) VALUES (%s, %s)"
                    cursor.execute(insert_result_sql, (query, url))
                    result_id = cursor.lastrowid  # get the last inserted ID

                    # Insert associated entities
                    for text, label in item["entities"]:
                        insert_entity_sql = "INSERT INTO entities (result_id, entity_text, entity_label) VALUES (%s, %s, %s)"
                        cursor.execute(insert_entity_sql, (result_id, text, label))

            db.commit()
        except Exception as e:
            print("❌ DB Insert Error:", e)

    return render_template('index.html', results=results)


if __name__ == '__main__':
    app.run(debug=True)
