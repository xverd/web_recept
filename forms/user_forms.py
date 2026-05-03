from flask_wtf import FlaskForm
from wtforms import PasswordField, StringField, TextAreaField, SubmitField, EmailField, RadioField
from wtforms.validators import DataRequired, Optional

class RegisterForm(FlaskForm):
    username = StringField('Логин', validators=[DataRequired()])
    email = EmailField('Почта', validators=[Optional()])
    phone = StringField('Телефон', validators=[Optional()])
    password = PasswordField('Пароль', validators=[DataRequired()])
    password_again = PasswordField('Повторите пароль', validators=[DataRequired()])
    submit = SubmitField('Зарегистрироваться')

class LoginForm(FlaskForm):
    username = StringField('Логин', validators=[DataRequired()])
    login_type = RadioField('Вход по', choices=[('email', 'Почте'), ('phone', 'Телефону')], 
                           default='email', validators=[DataRequired()])
    email = EmailField('Почта', validators=[Optional()])
    phone = StringField('Телефон', validators=[Optional()])
    password = PasswordField('Пароль', validators=[DataRequired()])
    submit = SubmitField('Войти')