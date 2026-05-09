import os
import threading
import webbrowser

from flask import Flask, abort, flash, redirect, render_template, request, url_for
from flask_login import LoginManager, current_user, login_required, login_user, logout_user
from sqlalchemy import or_
from werkzeug.utils import secure_filename

from data import db_session
from data.models import (
    Category,
    Collection,
    Favorite,
    Recipe,
    Review,
    ShoppingItem,
    Tag,
    User,
    ViewHistory,
)
from forms.user_forms import (
    AdminCategoryForm,
    AdminTagForm,
    CollectionForm,
    LoginForm,
    ProfileForm,
    RecipeForm,
    RegisterForm,
    ReviewForm,
    ShoppingItemForm,
)


app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "cookbook_dev_secret")
app.config["UPLOAD_FOLDER"] = os.path.join("static", "uploads")
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
login_manager.login_message = "Войдите, чтобы пользоваться этой функцией."


@app.teardown_appcontext
def shutdown_session(exception=None):
    db_session.remove_session()


@login_manager.user_loader
def load_user(user_id):
    db_sess = db_session.create_session()
    return db_sess.get(User, int(user_id))


def save_uploaded_image(form):
    """Сохраняет картинку рецепта, если пользователь её загрузил."""
    file = form.image_file.data
    if not file or not getattr(file, "filename", ""):
        return None
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    filename = secure_filename(file.filename)
    path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(path)
    return "/" + path.replace("\\", "/")


def parse_ingredient(line):
    if "-" in line:
        name, amount = line.split("-", 1)
        return name.strip(), amount.strip()
    return line.strip(), ""


@app.route("/")
def index():
    db_sess = db_session.create_session()
    q = request.args.get("q", "").strip()
    cuisine = request.args.get("cuisine", "").strip()
    dish_type = request.args.get("dish_type", "").strip()
    difficulty = request.args.get("difficulty", "").strip()
    max_time = request.args.get("max_time", "").strip()
    sort = request.args.get("sort", "new")

    query = db_sess.query(Recipe).filter(Recipe.status == "approved")
    if q:
        pattern = f"%{q}%"
        query = query.filter(
            or_(
                Recipe.title.ilike(pattern),
                Recipe.short_description.ilike(pattern),
                Recipe.ingredients.ilike(pattern),
                Recipe.tags.ilike(pattern),
            )
        )
    if cuisine:
        query = query.filter(Recipe.cuisine == cuisine)
    if dish_type:
        query = query.filter(Recipe.dish_type == dish_type)
    if difficulty:
        query = query.filter(Recipe.difficulty == difficulty)
    if max_time.isdigit():
        query = query.filter(Recipe.cook_time <= int(max_time))

    if sort == "popular":
        query = query.order_by(Recipe.views.desc(), Recipe.created_date.desc())
    elif sort == "az":
        query = query.order_by(Recipe.title.asc())
    else:
        query = query.order_by(Recipe.created_date.desc())

    recipes = query.all()
    cuisines = [row[0] for row in db_sess.query(Recipe.cuisine).filter(Recipe.status == "approved").distinct()]
    dish_types = [row[0] for row in db_sess.query(Recipe.dish_type).filter(Recipe.status == "approved").distinct()]
    return render_template(
        "index.html",
        recipes=recipes,
        cuisines=cuisines,
        dish_types=dish_types,
        filters=request.args,
    )


@app.route("/recipe/<int:recipe_id>", methods=["GET", "POST"])
def recipe_detail(recipe_id):
    db_sess = db_session.create_session()
    recipe = db_sess.get(Recipe, recipe_id)
    if not recipe:
        abort(404)
    allowed = recipe.status == "approved" or (
        current_user.is_authenticated and (current_user.id == recipe.author_id or current_user.is_admin)
    )
    if not allowed:
        abort(404)

    review_form = ReviewForm()
    if review_form.validate_on_submit():
        if not current_user.is_authenticated:
            return redirect(url_for("login"))
        review = (
            db_sess.query(Review)
            .filter(Review.user_id == current_user.id, Review.recipe_id == recipe.id)
            .first()
        )
        if not review:
            review = Review(user_id=current_user.id, recipe_id=recipe.id)
            db_sess.add(review)
        review.rating = int(review_form.rating.data)
        review.text = review_form.text.data
        db_sess.commit()
        flash("Отзыв сохранён.")
        return redirect(url_for("recipe_detail", recipe_id=recipe.id))

    recipe.views += 1
    if current_user.is_authenticated:
        db_sess.add(ViewHistory(user_id=current_user.id, recipe_id=recipe.id))
    db_sess.commit()

    is_favorite = False
    user_collections = []
    if current_user.is_authenticated:
        is_favorite = (
            db_sess.query(Favorite)
            .filter(Favorite.user_id == current_user.id, Favorite.recipe_id == recipe.id)
            .first()
            is not None
        )
        user_collections = db_sess.query(Collection).filter(Collection.user_id == current_user.id).all()

    return render_template(
        "recipe_detail.html",
        recipe=recipe,
        review_form=review_form,
        is_favorite=is_favorite,
        user_collections=user_collections,
    )


@app.route("/recipe/<int:recipe_id>/print")
def print_recipe(recipe_id):
    db_sess = db_session.create_session()
    recipe = db_sess.get(Recipe, recipe_id)
    if not recipe or recipe.status != "approved":
        abort(404)
    return render_template("print_recipe.html", recipe=recipe)


@app.route("/recipe/new", methods=["GET", "POST"])
@login_required
def create_recipe():
    form = RecipeForm()
    if form.validate_on_submit():
        db_sess = db_session.create_session()
        uploaded_url = save_uploaded_image(form)
        recipe = Recipe(
            title=form.title.data,
            short_description=form.short_description.data,
            ingredients=form.ingredients.data,
            steps=form.steps.data,
            tips=form.tips.data,
            image_url=uploaded_url or form.image_url.data,
            video_url=form.video_url.data,
            cuisine=form.cuisine.data,
            dish_type=form.dish_type.data,
            difficulty=form.difficulty.data,
            cook_time=form.cook_time.data,
            tags=form.tags.data,
            status="approved" if current_user.is_admin else "pending",
            author_id=current_user.id,
        )
        db_sess.add(recipe)
        db_sess.commit()
        flash("Рецепт отправлен на модерацию." if recipe.status == "pending" else "Рецепт опубликован.")
        return redirect(url_for("recipe_detail", recipe_id=recipe.id))
    return render_template("recipe_form.html", form=form, title="Добавить рецепт")


@app.route("/recipe/<int:recipe_id>/edit", methods=["GET", "POST"])
@login_required
def edit_recipe(recipe_id):
    db_sess = db_session.create_session()
    recipe = db_sess.get(Recipe, recipe_id)
    if not recipe or (recipe.author_id != current_user.id and not current_user.is_admin):
        abort(403)
    form = RecipeForm(obj=recipe)
    if form.validate_on_submit():
        uploaded_url = save_uploaded_image(form)
        recipe.title = form.title.data
        recipe.short_description = form.short_description.data
        recipe.ingredients = form.ingredients.data
        recipe.steps = form.steps.data
        recipe.tips = form.tips.data
        recipe.image_url = uploaded_url or form.image_url.data
        recipe.video_url = form.video_url.data
        recipe.cuisine = form.cuisine.data
        recipe.dish_type = form.dish_type.data
        recipe.difficulty = form.difficulty.data
        recipe.cook_time = form.cook_time.data
        recipe.tags = form.tags.data
        if not current_user.is_admin:
            recipe.status = "pending"
        db_sess.commit()
        flash("Изменения сохранены.")
        return redirect(url_for("recipe_detail", recipe_id=recipe.id))
    return render_template("recipe_form.html", form=form, title="Редактировать рецепт")


@app.route("/favorite/<int:recipe_id>", methods=["POST"])
@login_required
def toggle_favorite(recipe_id):
    db_sess = db_session.create_session()
    favorite = db_sess.query(Favorite).filter(Favorite.user_id == current_user.id, Favorite.recipe_id == recipe_id).first()
    if favorite:
        db_sess.delete(favorite)
    else:
        db_sess.add(Favorite(user_id=current_user.id, recipe_id=recipe_id))
    db_sess.commit()
    return redirect(request.referrer or url_for("index"))


@app.route("/collections", methods=["GET", "POST"])
@login_required
def collections():
    db_sess = db_session.create_session()
    form = CollectionForm()
    if form.validate_on_submit():
        db_sess.add(Collection(title=form.title.data, description=form.description.data, user_id=current_user.id))
        db_sess.commit()
        return redirect(url_for("collections"))
    items = db_sess.query(Collection).filter(Collection.user_id == current_user.id).order_by(Collection.created_date.desc()).all()
    return render_template("collections.html", form=form, collections=items)


@app.route("/collections/<int:collection_id>/delete", methods=["POST"])
@login_required
def delete_collection(collection_id):
    db_sess = db_session.create_session()
    collection = db_sess.get(Collection, collection_id)
    if not collection or collection.user_id != current_user.id:
        abort(403)
    db_sess.delete(collection)
    db_sess.commit()
    return redirect(url_for("collections"))


@app.route("/collections/<int:collection_id>/add/<int:recipe_id>", methods=["POST"])
@login_required
def add_to_collection(collection_id, recipe_id):
    db_sess = db_session.create_session()
    collection = db_sess.get(Collection, collection_id)
    recipe = db_sess.get(Recipe, recipe_id)
    if not collection or collection.user_id != current_user.id or not recipe:
        abort(403)
    if recipe not in collection.recipes:
        collection.recipes.append(recipe)
        db_sess.commit()
    return redirect(url_for("recipe_detail", recipe_id=recipe_id))


@app.route("/shopping", methods=["GET", "POST"])
@login_required
def shopping():
    db_sess = db_session.create_session()
    form = ShoppingItemForm()
    if form.validate_on_submit():
        db_sess.add(ShoppingItem(user_id=current_user.id, name=form.name.data, amount=form.amount.data))
        db_sess.commit()
        return redirect(url_for("shopping"))
    items = db_sess.query(ShoppingItem).filter(ShoppingItem.user_id == current_user.id).order_by(ShoppingItem.checked, ShoppingItem.name).all()
    return render_template("shopping.html", form=form, items=items)


@app.route("/shopping/from/<int:recipe_id>", methods=["POST"])
@login_required
def shopping_from_recipe(recipe_id):
    db_sess = db_session.create_session()
    recipe = db_sess.get(Recipe, recipe_id)
    if not recipe:
        abort(404)
    for line in recipe.ingredients_list:
        name, amount = parse_ingredient(line)
        if name:
            db_sess.add(ShoppingItem(user_id=current_user.id, name=name, amount=amount, source_recipe_id=recipe.id))
    db_sess.commit()
    flash("Ингредиенты добавлены в список покупок.")
    return redirect(url_for("shopping"))


@app.route("/shopping/<int:item_id>/toggle", methods=["POST"])
@login_required
def toggle_shopping_item(item_id):
    db_sess = db_session.create_session()
    item = db_sess.get(ShoppingItem, item_id)
    if not item or item.user_id != current_user.id:
        abort(403)
    item.checked = not item.checked
    db_sess.commit()
    return redirect(url_for("shopping"))


@app.route("/shopping/<int:item_id>/delete", methods=["POST"])
@login_required
def delete_shopping_item(item_id):
    db_sess = db_session.create_session()
    item = db_sess.get(ShoppingItem, item_id)
    if not item or item.user_id != current_user.id:
        abort(403)
    db_sess.delete(item)
    db_sess.commit()
    return redirect(url_for("shopping"))


@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    db_sess = db_session.create_session()
    user = db_sess.get(User, current_user.id)
    form = ProfileForm(obj=user)
    if form.validate_on_submit():
        user.name = form.name.data
        user.email = form.email.data or None
        user.phone = form.phone.data or None
        user.avatar_url = form.avatar_url.data or None
        if form.password.data:
            user.set_password(form.password.data)
        db_sess.commit()
        flash("Профиль обновлён.")
        return redirect(url_for("profile"))

    favorites = db_sess.query(Favorite).filter(Favorite.user_id == current_user.id).order_by(Favorite.created_date.desc()).all()
    history = (
        db_sess.query(ViewHistory)
        .filter(ViewHistory.user_id == current_user.id)
        .order_by(ViewHistory.viewed_at.desc())
        .limit(10)
        .all()
    )
    my_recipes = db_sess.query(Recipe).filter(Recipe.author_id == current_user.id).order_by(Recipe.created_date.desc()).all()
    return render_template("profile.html", form=form, favorites=favorites, history=history, my_recipes=my_recipes)


@app.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        db_sess = db_session.create_session()
        user = db_sess.query(User).filter(User.username == form.username.data).first()
        if user and not user.is_blocked and user.check_password(form.password.data):
            login_user(user)
            return redirect(url_for("profile"))
        return render_template("login.html", form=form, message="Неверный логин, пароль или аккаунт заблокирован.")
    return render_template("login.html", form=form)


@app.route("/register", methods=["GET", "POST"])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        email = form.email.data.strip() if form.email.data else None
        phone = form.phone.data.strip() if form.phone.data else None
        if not email and not phone:
            return render_template("register.html", form=form, message="Укажите почту или телефон.")
        if form.password.data != form.password_again.data:
            return render_template("register.html", form=form, message="Пароли не совпадают.")

        db_sess = db_session.create_session()
        if db_sess.query(User).filter(User.username == form.username.data).first():
            return render_template("register.html", form=form, message="Такой логин уже занят.")
        if email and db_sess.query(User).filter(User.email == email).first():
            return render_template("register.html", form=form, message="Такая почта уже зарегистрирована.")
        if phone and db_sess.query(User).filter(User.phone == phone).first():
            return render_template("register.html", form=form, message="Такой телефон уже зарегистрирован.")

        user = User(username=form.username.data, name=form.name.data, email=email, phone=phone)
        user.set_password(form.password.data)
        db_sess.add(user)
        db_sess.commit()
        flash("Регистрация прошла успешно. Теперь можно войти.")
        return redirect(url_for("login"))
    return render_template("register.html", form=form)


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("index"))


@app.route("/admin", methods=["GET", "POST"])
@login_required
def admin():
    if not current_user.is_admin:
        abort(403)

    db_sess = db_session.create_session()
    category_form = AdminCategoryForm(prefix="category")
    tag_form = AdminTagForm(prefix="tag")
    if category_form.submit.data and category_form.validate_on_submit():
        if not db_sess.query(Category).filter(Category.name == category_form.name.data).first():
            db_sess.add(Category(name=category_form.name.data, kind=category_form.kind.data))
            db_sess.commit()
        return redirect(url_for("admin"))
    if tag_form.submit.data and tag_form.validate_on_submit():
        if not db_sess.query(Tag).filter(Tag.name == tag_form.name.data).first():
            db_sess.add(Tag(name=tag_form.name.data))
            db_sess.commit()
        return redirect(url_for("admin"))
    pending = db_sess.query(Recipe).filter(Recipe.status == "pending").order_by(Recipe.created_date.desc()).all()
    users = db_sess.query(User).order_by(User.created_date.desc()).all()
    categories = db_sess.query(Category).order_by(Category.kind, Category.name).all()
    tags = db_sess.query(Tag).order_by(Tag.name).all()
    return render_template("admin.html", pending=pending, users=users, categories=categories, tags=tags, category_form=category_form, tag_form=tag_form)


@app.route("/admin/recipe/<int:recipe_id>/<action>", methods=["POST"])
@login_required
def moderate_recipe(recipe_id, action):
    if not current_user.is_admin:
        abort(403)

    db_sess = db_session.create_session()
    recipe = db_sess.get(Recipe, recipe_id)
    if not recipe or action not in {"approve", "reject"}:
        abort(404)
    recipe.status = "approved" if action == "approve" else "rejected"
    db_sess.commit()
    return redirect(url_for("admin"))


@app.route("/admin/user/<int:user_id>/block", methods=["POST"])
@login_required
def block_user(user_id):
    if not current_user.is_admin:
        abort(403)

    db_sess = db_session.create_session()
    user = db_sess.get(User, user_id)
    if not user or user.id == current_user.id:
        abort(403)
    user.is_blocked = not user.is_blocked
    db_sess.commit()
    return redirect(url_for("admin"))


def seed_data():
    db_sess = db_session.create_session()
    if not db_sess.query(User).filter(User.username == "admin").first():
        admin = User(username="admin", name="Администратор", email="admin@cookbook.local", role="admin")
        admin.set_password("admin123")
        db_sess.add(admin)

    if not db_sess.query(Recipe).first():
        recipes = [
            Recipe(
                title="Паста с томатами и базиликом",
                short_description="Быстрый ужин с ярким соусом, сыром и свежей зеленью.",
                ingredients="Паста - 250 г\nТоматы - 3 шт.\nЧеснок - 2 зубчика\nБазилик - 1 пучок\nСыр - 50 г",
                steps="Отварите пасту до состояния al dente.\nОбжарьте чеснок и томаты 5 минут.\nСмешайте пасту с соусом и посыпьте сыром.",
                tips="Не промывайте пасту: крахмал поможет соусу держаться.",
                image_url="https://images.unsplash.com/photo-1551892374-ecf8754cf8b0?auto=format&fit=crop&w=900&q=80",
                cuisine="Итальянская",
                dish_type="Основное",
                difficulty="Легко",
                cook_time=25,
                tags="паста, ужин, вегетарианское",
                status="approved",
            ),
            Recipe(
                title="Сырники с ванилью",
                short_description="Нежные сырники для завтрака со сметаной или ягодами.",
                ingredients="Творог - 400 г\nЯйцо - 1 шт.\nМука - 3 ст. л.\nСахар - 2 ст. л.\nВаниль - по вкусу",
                steps="Разомните творог с яйцом и сахаром.\nДобавьте муку и сформируйте сырники.\nОбжарьте с двух сторон до золотистой корочки.",
                tips="Если творог влажный, добавьте немного больше муки.",
                image_url="https://images.unsplash.com/photo-1565299624946-b28f40a0ae38?auto=format&fit=crop&w=900&q=80",
                cuisine="Русская",
                dish_type="Завтрак",
                difficulty="Средне",
                cook_time=30,
                tags="завтрак, десерт, творог",
                status="approved",
            ),
            Recipe(
                title="Куриный суп с лапшой",
                short_description="Домашний суп с курицей, овощами и тонкой лапшой.",
                ingredients="Курица - 500 г\nЛапша - 100 г\nМорковь - 1 шт.\nЛук - 1 шт.\nЗелень - по вкусу",
                steps="Сварите куриный бульон.\nДобавьте овощи и варите 15 минут.\nДобавьте лапшу и зелень, доведите до готовности.",
                tips="Снимайте пену с бульона, чтобы он был прозрачнее.",
                image_url="https://images.unsplash.com/photo-1547592166-23ac45744acd?auto=format&fit=crop&w=900&q=80",
                cuisine="Домашняя",
                dish_type="Суп",
                difficulty="Легко",
                cook_time=55,
                tags="суп, курица, обед",
                status="approved",
            ),
        ]
        db_sess.add_all(recipes)

    for name, kind in [("Итальянская", "cuisine"), ("Русская", "cuisine"), ("Домашняя", "cuisine"), ("Завтрак", "dish_type"), ("Основное", "dish_type"), ("Суп", "dish_type")]:
        if not db_sess.query(Category).filter(Category.name == name).first():
            db_sess.add(Category(name=name, kind=kind))
    for name in ["десерт", "курица", "быстро", "вегетарианское"]:
        if not db_sess.query(Tag).filter(Tag.name == name).first():
            db_sess.add(Tag(name=name))
    db_sess.commit()


def main():
    db_session.global_init("db/cookbook_full.db")
    seed_data()

    # При запуске из PyCharm сайт сам откроется в браузере.
    url = "http://127.0.0.1:8080"
    threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    app.run(port=8080, host="127.0.0.1", debug=True, use_reloader=False)


if __name__ == "__main__":
    main()
