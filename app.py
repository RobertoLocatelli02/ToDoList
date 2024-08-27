from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_mail import Mail, Message
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user, fresh_login_required
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'roberto.locatelli.testes@gmail.com'
app.config['MAIL_PASSWORD'] = 'Locatelli123'

app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)

mail = Mail(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.session_protection = "strong"

DATABASE = 'todo.db'

def connect_db():
    return sqlite3.connect(DATABASE)

@login_manager.user_loader
def load_user(user_id):
    conn = connect_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    user = cur.fetchone()
    conn.close()
    if user:
        return User(user[0], user[1], user[2])
    return None

class User(UserMixin):
    def __init__(self, id, username, email):
        self.id = id
        self.username = username
        self.email = email

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        hashed_password = generate_password_hash(password)

        conn = connect_db()
        cur = conn.cursor()
        cur.execute("INSERT INTO users (username, email, password) VALUES (?, ?, ?)", 
                    (username, email, hashed_password))
        conn.commit()
        conn.close()

        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        conn = connect_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE email = ?", (email,))
        user = cur.fetchone()
        conn.close()

        if user and check_password_hash(user[3], password):
            user_obj = User(user[0], user[1], user[2])
            login_user(user_obj)
            session.permanent = True 
            return redirect(url_for('index'))
        else:
            flash('Falha no login.', 'danger')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    conn = connect_db()
    cur = conn.cursor()
    cur.execute("SELECT id, task, status, due_date FROM tasks WHERE user_id = ?", (current_user.id,))
    tasks = cur.fetchall()
    conn.close()
    return render_template('index.html', tasks=tasks)

@app.route('/add', methods=['GET', 'POST'])
@login_required
def add_task():
    if request.method == 'POST':
        task = request.form['task']
        due_date_str = request.form['due_date']
        due_date = datetime.strptime(due_date_str, '%Y-%m-%d')

        conn = connect_db()
        cur = conn.cursor()
        cur.execute("INSERT INTO tasks (task, status, user_id, due_date) VALUES (?, ?, ?, ?)", 
                    (task, 'incomplete', current_user.id, due_date))
        conn.commit()
        conn.close()
        return redirect(url_for('index'))
    return render_template('add_task.html')

@app.route('/edit/<int:task_id>', methods=['GET', 'POST'])
@login_required
def edit_task(task_id):
    conn = connect_db()
    cur = conn.cursor()
    if request.method == 'POST':
        task = request.form['task']
        due_date_str = request.form['due_date']
        due_date = datetime.strptime(due_date_str, '%Y-%m-%d')
        cur.execute("UPDATE tasks SET task = ?, due_date = ? WHERE id = ? AND user_id = ?", 
                    (task, due_date, task_id, current_user.id))
        conn.commit()
        conn.close()
        return redirect(url_for('index'))
    else:
        cur.execute("SELECT * FROM tasks WHERE id = ? AND user_id = ?", (task_id, current_user.id))
        task = cur.fetchone()
        conn.close()
        if task:
            return render_template('edit_task.html', task=task)
        else:
            return redirect(url_for('index'))

@app.route('/delete/<int:task_id>')
@login_required
def delete_task(task_id):
    conn = connect_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM tasks WHERE id = ? AND user_id = ?", (task_id, current_user.id))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route('/complete/<int:task_id>')
@login_required
def complete_task(task_id):
    conn = connect_db()
    cur = conn.cursor()
    cur.execute("UPDATE tasks SET status = 'complete' WHERE id = ? AND user_id = ?", 
                (task_id, current_user.id))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

def send_reminder_email(task):
    msg = Message('Lembrete de tarefa', 
                  sender='roberto.locatelli.testes@gmail.com', 
                  recipients=[current_user.email])
    msg.body = f"Olá, {current_user.username}! Você tem um lembrete de tarefa: {task[1]} para {task[2]}."
    mail.send(msg)

@app.route('/send_reminders')
@login_required
def send_reminders():
    conn = connect_db()
    cur = conn.cursor()
    cur.execute("SELECT id, task, due_date FROM tasks WHERE user_id = ? AND status = 'incomplete'", 
                (current_user.id,))
    tasks = cur.fetchall()
    
    for task in tasks:
        if len(task) < 3 or not task[2]:
            continue
        
        due_date = datetime.strptime(task[2], '%Y-%m-%d %H:%M:%S')
        if due_date - datetime.now() <= timedelta(days=1):
            send_reminder_email(task)
    
    conn.close()
    return redirect(url_for('index'))

@app.route('/send_email')
def send_email():
    try:
        msg = Message('Test Email', sender='roberto.locatelli.testes@gmail.com', recipients=['roberto.locatelli.testes@gmail.com'])
        msg.body = 'This is a test email from Flask!'
        mail.send(msg)
        return 'Email sent successfully!'
    except Exception as e:
        return f'Failed to send email: {str(e)}'

if __name__ == '__main__':
    conn = connect_db()
    cur = conn.cursor()
    cur.execute('''CREATE TABLE IF NOT EXISTS users
                   (id INTEGER PRIMARY KEY, username TEXT NOT NULL, email TEXT NOT NULL, password TEXT NOT NULL)''')
    cur.execute('''CREATE TABLE IF NOT EXISTS tasks
                   (id INTEGER PRIMARY KEY, user_id INTEGER, task TEXT NOT NULL, status TEXT NOT NULL,
                   due_date DATETIME, FOREIGN KEY(user_id) REFERENCES users(id))''')
    conn.commit()
    conn.close()
    app.run(debug=True)
