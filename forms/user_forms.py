from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField
from wtforms import (
    EmailField,
    IntegerField,
    PasswordField,
    SelectField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import DataRequired, Length, NumberRange, Optional


class RegisterForm(FlaskForm):
    username = StringField("Логин", validators=[DataRequired(), Length(min=3, max=80)])
    name = StringField("Имя", validators=[DataRequired(), Length(max=120)])
    email = EmailField("Почта", validators=[Optional(), Length(max=120)])
    phone = StringField("Телефон", validators=[Optional(), Length(max=40)])
    password = PasswordField("Пароль", validators=[DataRequired(), Length(min=6)])
    password_again = PasswordField("Повторите пароль", validators=[DataRequired()])
    submit = SubmitField("Зарегистрироваться")


class LoginForm(FlaskForm):
    username = StringField("Логин", validators=[DataRequired()])
    password = PasswordField("Пароль", validators=[DataRequired()])
    submit = SubmitField("Войти")


class ProfileForm(FlaskForm):
    name = StringField("Имя", validators=[DataRequired(), Length(max=120)])
    email = EmailField("Почта", validators=[Optional(), Length(max=120)])
    phone = StringField("Телефон", validators=[Optional(), Length(max=40)])
    avatar_url = StringField("Ссылка на аватар", validators=[Optional(), Length(max=300)])
    password = PasswordField("Новый пароль", validators=[Optional(), Length(min=6)])
    submit = SubmitField("Сохранить")


class RecipeForm(FlaskForm):
    title = StringField("Название", validators=[DataRequired(), Length(max=160)])
    short_description = TextAreaField("Краткое описание", validators=[DataRequired(), Length(max=500)])
    ingredients = TextAreaField("Ингредиенты", validators=[DataRequired()])
    steps = TextAreaField("Шаги приготовления", validators=[DataRequired()])
    tips = TextAreaField("Советы автора", validators=[Optional()])
    image_url = StringField("Ссылка на фото", validators=[Optional(), Length(max=500)])
    image_file = FileField("Или загрузите фото", validators=[Optional(), FileAllowed(["jpg", "jpeg", "png", "webp"])])
    video_url = StringField("Ссылка на видео", validators=[Optional(), Length(max=500)])
    cuisine = StringField("Кухня мира", validators=[DataRequired(), Length(max=80)])
    dish_type = StringField("Тип блюда", validators=[DataRequired(), Length(max=80)])
    difficulty = SelectField("Сложность", choices=[("Легко", "Легко"), ("Средне", "Средне"), ("Сложно", "Сложно")])
    cook_time = IntegerField("Время, минут", validators=[DataRequired(), NumberRange(min=1, max=1440)])
    tags = StringField("Теги через запятую", validators=[Optional(), Length(max=250)])
    submit = SubmitField("Сохранить рецепт")


class CollectionForm(FlaskForm):
    title = StringField("Название коллекции", validators=[DataRequired(), Length(max=120)])
    description = TextAreaField("Описание", validators=[Optional(), Length(max=400)])
    submit = SubmitField("Сохранить")


class ReviewForm(FlaskForm):
    rating = SelectField("Оценка", choices=[(str(i), str(i)) for i in range(1, 6)], validators=[DataRequired()])
    text = TextAreaField("Комментарий", validators=[Optional(), Length(max=1000)])
    submit = SubmitField("Отправить отзыв")


class ShoppingItemForm(FlaskForm):
    name = StringField("Продукт", validators=[DataRequired(), Length(max=200)])
    amount = StringField("Количество", validators=[Optional(), Length(max=120)])
    submit = SubmitField("Добавить")


class AdminCategoryForm(FlaskForm):
    name = StringField("Название", validators=[DataRequired(), Length(max=80)])
    kind = SelectField(
        "Тип",
        choices=[("cuisine", "Кухня мира"), ("dish_type", "Тип блюда"), ("difficulty", "Сложность")],
    )
    submit = SubmitField("Добавить категорию")


class AdminTagForm(FlaskForm):
    name = StringField("Тег", validators=[DataRequired(), Length(max=80)])
    submit = SubmitField("Добавить тег")
