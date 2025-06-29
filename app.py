from flask import Flask, render_template, request, redirect, session, jsonify, send_from_directory
import pymysql
from scraper import main_system
import uuid
import os
from datetime import datetime
from werkzeug.utils import secure_filename

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

# Config for image uploads
UPLOAD_FOLDER = os.path.join(os.getcwd(), 'img')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.before_request
def assign_user():
    if 'user_id' not in session:
        session['user_id'] = str(uuid.uuid4())
        try:
            with db.cursor() as cursor:
                insert_user_sql = "INSERT INTO users (uuid) VALUES (%s)"
                cursor.execute(insert_user_sql, (session['user_id'],))
                db.commit()
                # Get the user's id for future use
                cursor.execute("SELECT id FROM users WHERE uuid = %s", (session['user_id'],))
                user = cursor.fetchone()
                session['user_db_id'] = user['id']
        except Exception as e:
            print("❌ User creation error:", e)
    elif 'user_db_id' not in session:
        # If user_id exists but user_db_id doesn't, get the id
        try:
            with db.cursor() as cursor:
                cursor.execute("SELECT id FROM users WHERE uuid = %s", (session['user_id'],))
                user = cursor.fetchone()
                if user:
                    session['user_db_id'] = user['id']
        except Exception as e:
            print("❌ Error getting user id:", e)

@app.route('/', methods=['GET', 'POST'])
def index():
    posts = []
    results = []
    
    # Get existing posts
    try:
        with db.cursor() as cursor:
            # Join with users table to get UUID
            sql = """
                SELECT p.id, p.content, p.created_at, u.uuid as user_id 
                FROM posts p 
                JOIN users u ON p.user_id = u.id 
                ORDER BY p.created_at DESC
            """
            cursor.execute(sql)
            posts = cursor.fetchall()
    except Exception as e:
        print("❌ Error fetching posts:", e)

    if request.method == 'POST':
        # This now only handles the search functionality
        if 'query' in request.form:
            # Handle search query
            query = request.form['query']
            serpapi_key = request.form['serpapi_key'] or None
            results = main_system(query, serpapi_key)

            try:
                with db.cursor() as cursor:
                    for item in results:
                        url = item["url"]
                        insert_result_sql = "INSERT INTO results (query, url) VALUES (%s, %s)"
                        cursor.execute(insert_result_sql, (query, url))
                        result_id = cursor.lastrowid

                        for text, label in item["entities"]:
                            insert_entity_sql = "INSERT INTO entities (result_id, entity_text, entity_label) VALUES (%s, %s, %s)"
                            cursor.execute(insert_entity_sql, (result_id, text, label))
                db.commit()
            except Exception as e:
                print("❌ DB Insert Error:", e)

    return render_template('index.html', posts=posts, results=results)

@app.route('/add_post', methods=['POST'])
def add_post():
    if 'user_db_id' not in session:
        return jsonify({'status': 'error', 'message': 'User not logged in'}), 401

    post_content = request.form.get('post_content')
    image_file = request.files.get('image')
    image_path = None

    # Handle image upload
    if image_file and allowed_file(image_file.filename):
        filename = secure_filename(str(uuid.uuid4()) + '_' + image_file.filename)
        image_file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        image_path = filename

    if not post_content and not image_path:
        return jsonify({'status': 'error', 'message': 'Post content or image required'}), 400

    try:
        with db.cursor() as cursor:
            created_time = datetime.now()
            insert_post_sql = "INSERT INTO posts (user_id, content, created_at, image_path) VALUES (%s, %s, %s, %s)"
            cursor.execute(insert_post_sql, (session['user_db_id'], post_content, created_time, image_path))
            new_post_id = cursor.lastrowid
            db.commit()

            # Fetch the user's UUID to display
            cursor.execute("SELECT uuid FROM users WHERE id = %s", (session['user_db_id'],))
            user = cursor.fetchone()
            user_uuid = user['uuid'] if user else 'Anonymous'

        return jsonify({
            'status': 'success',
            'post': {
                'id': new_post_id,
                'content': post_content,
                'user_id': user_uuid,
                'created_at': created_time.strftime('%Y-%m-%d %H:%M'),
                'image_path': image_path
            }
        })
    except Exception as e:
        print("❌ Error creating post:", e)
        return jsonify({'status': 'error', 'message': 'Failed to create post'}), 500

@app.route('/img/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    app.run(debug=True)
