from flask import Flask, render_template, redirect
from flask_login import LoginManager, login_user, logout_user, login_required
from data import db_session
from forms.user_forms import RegisterForm, LoginForm
from data.users import User

app = Flask(__name__)
app.config['SECRET_KEY'] = 'yandexlyceum_secret_key'

login_manager = LoginManager()
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    db_sess = db_session.create_session()
    return db_sess.get(User, user_id)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        db_sess = db_session.create_session()
        
        # Определяем, по чему ищем пользователя
        if form.login_type.data == 'email':
            user = db_sess.query(User).filter(User.email == form.email.data).first()
        else:
            user = db_sess.query(User).filter(User.phone == form.phone.data).first()
        
        # Проверяем логин и пароль
        if user and user.username == form.username.data and user.check_password(form.password.data):
            login_user(user)
            return redirect('/profile')
        
        return render_template('login.html', title='Вход', form=form, 
                               message="Неправильный логин или пароль")
    
    return render_template('login.html', title='Вход', form=form)

@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        # Проверяем, что хотя бы одно контактное поле заполнено
        email = form.email.data.strip() if form.email.data else ''
        phone = form.phone.data.strip() if form.phone.data else ''
        
        if not email and not phone:
            return render_template('register.html', title='Регистрация',
                                   form=form,
                                   message="Укажите хотя бы почту или телефон")
        
        if form.password.data != form.password_again.data:
            return render_template('register.html', title='Регистрация',
                                   form=form,
                                   message="Пароли не совпадают")
        
        db_sess = db_session.create_session()
        
        # Проверяем, не занят ли логин
        if db_sess.query(User).filter(User.username == form.username.data).first():
            return render_template('register.html', title='Регистрация',
                                   form=form,
                                   message="Такой логин уже занят")
        
        # Проверяем email если указан
        if email and db_sess.query(User).filter(User.email == email).first():
            return render_template('register.html', title='Регистрация',
                                   form=form,
                                   message="Такая почта уже зарегистрирована")
        
        # Проверяем телефон если указан
        if phone and db_sess.query(User).filter(User.phone == phone).first():
            return render_template('register.html', title='Регистрация',
                                   form=form,
                                   message="Такой телефон уже зарегистрирован")
        
        user = User(
            username=form.username.data,
            email=email if email else None,
            phone=phone if phone else None
        )
        user.set_password(form.password.data)
        db_sess.add(user)
        db_sess.commit()
        return redirect('/login')
        
    return render_template('register.html', title='Регистрация', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect('/')

@app.route('/profile')
@login_required
def profile():
    from flask_login import current_user
    return f"Профиль пользователя: {current_user.name} <br> <a href='/logout'>Выйти</a>"

def main():
    db_session.global_init("db/cook.db")
    app.run(port=8080, host='127.0.0.1')

if __name__ == '__main__':
    main()