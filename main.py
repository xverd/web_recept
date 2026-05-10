import os
import threading
import webbrowser

from flask import Flask, abort, flash, redirect, render_template, request, url_for
from flask_login import LoginManager, current_user, login_required, login_user, logout_user
from sqlalchemy import or_
from werkzeug.utils import secure_filename

from data import db_session
from data.models import Category, Collection, Favorite, Recipe, Review, ShoppingItem, Tag, User, ViewHistory
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
app.config["SECRET_KEY"] = "cookbook_secret_key"
app.config["UPLOAD_FOLDER"] = os.path.join("static", "images")
app.config["YANDEX_MAPS_API_KEY"] = "f3a0fe3a-b07e-4840-a1da-06f18b2ddf13"

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
login_manager.login_message = "Сначала войдите в аккаунт."


@app.teardown_appcontext
def close_db(error=None):
    db_session.remove_session()


@login_manager.user_loader
def load_user(user_id):
    db_sess = db_session.create_session()
    return db_sess.get(User, int(user_id))


def save_image(form):
    file = form.image_file.data
    if not file or not file.filename:
        return None
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    filename = secure_filename(file.filename)
    path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(path)
    return "/" + path.replace("\\", "/")


def split_ingredient(line):
    if "-" in line:
        name, amount = line.split("-", 1)
        return name.strip(), amount.strip()
    return line.strip(), ""


def add_shopping_item(db_sess, user_id, name, amount="", recipe_id=None):
    name = name.strip()[:80]
    amount = amount.strip()[:40] if amount else ""
    if not name:
        return

    old_item = db_sess.query(ShoppingItem).filter(
        ShoppingItem.user_id == user_id,
        ShoppingItem.name == name,
        ShoppingItem.amount == amount,
        ShoppingItem.source_recipe_id == recipe_id,
    ).first()
    if not old_item:
        db_sess.add(ShoppingItem(user_id=user_id, name=name, amount=amount, source_recipe_id=recipe_id))


def delete_shopping_duplicates(db_sess, user_id):
    items = db_sess.query(ShoppingItem).filter(ShoppingItem.user_id == user_id).order_by(ShoppingItem.id).all()
    seen = set()
    for item in items:
        key = (item.name.lower(), item.amount or "", item.source_recipe_id)
        if key in seen:
            db_sess.delete(item)
        else:
            seen.add(key)
    db_sess.commit()


def user_can_open_recipe(recipe):
    if recipe.status == "approved":
        return True
    if not current_user.is_authenticated:
        return False
    return current_user.is_admin or recipe.author_id == current_user.id


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
        text = f"%{q}%"
        query = query.filter(or_(Recipe.title.ilike(text), Recipe.ingredients.ilike(text), Recipe.tags.ilike(text)))
    if cuisine:
        query = query.filter(Recipe.cuisine == cuisine)
    if dish_type:
        query = query.filter(Recipe.dish_type == dish_type)
    if difficulty:
        query = query.filter(Recipe.difficulty == difficulty)
    if max_time.isdigit() and int(max_time) > 0:
        query = query.filter(Recipe.cook_time <= int(max_time))

    if sort == "popular":
        query = query.order_by(Recipe.views.desc())
    elif sort == "az":
        query = query.order_by(Recipe.title)
    else:
        query = query.order_by(Recipe.created_date.desc())

    recipes = query.all()
    cuisines = [row[0] for row in db_sess.query(Recipe.cuisine).filter(Recipe.status == "approved").distinct()]
    dish_types = [row[0] for row in db_sess.query(Recipe.dish_type).filter(Recipe.status == "approved").distinct()]
    return render_template("index.html", recipes=recipes, cuisines=cuisines, dish_types=dish_types, filters=request.args)


@app.route("/recipe/<int:recipe_id>", methods=["GET", "POST"])
def recipe_detail(recipe_id):
    db_sess = db_session.create_session()
    recipe = db_sess.get(Recipe, recipe_id)
    if not recipe or not user_can_open_recipe(recipe):
        abort(404)

    form = ReviewForm()
    if form.validate_on_submit():
        if not current_user.is_authenticated:
            return redirect(url_for("login"))
        review = db_sess.query(Review).filter(Review.user_id == current_user.id, Review.recipe_id == recipe.id).first()
        if not review:
            review = Review(user_id=current_user.id, recipe_id=recipe.id)
            db_sess.add(review)
        review.rating = int(form.rating.data)
        review.text = form.text.data
        db_sess.commit()
        flash("Отзыв сохранён.")
        return redirect(url_for("recipe_detail", recipe_id=recipe.id))

    recipe.views += 1
    if current_user.is_authenticated:
        db_sess.add(ViewHistory(user_id=current_user.id, recipe_id=recipe.id))
    db_sess.commit()

    is_favorite = False
    collections = []
    if current_user.is_authenticated:
        is_favorite = db_sess.query(Favorite).filter(Favorite.user_id == current_user.id, Favorite.recipe_id == recipe.id).first() is not None
        collections = db_sess.query(Collection).filter(Collection.user_id == current_user.id).all()

    return render_template(
        "recipe_detail.html",
        recipe=recipe,
        review_form=form,
        is_favorite=is_favorite,
        user_collections=collections,
        yandex_maps_api_key=app.config["YANDEX_MAPS_API_KEY"],
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
        recipe = Recipe(
            title=form.title.data,
            short_description=form.short_description.data,
            ingredients=form.ingredients.data,
            steps=form.steps.data,
            tips=form.tips.data,
            image_url=save_image(form) or form.image_url.data,
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
        flash("Рецепт сохранён. Если вы не админ, он попадёт на модерацию.")
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
        recipe.title = form.title.data
        recipe.short_description = form.short_description.data
        recipe.ingredients = form.ingredients.data
        recipe.steps = form.steps.data
        recipe.tips = form.tips.data
        recipe.image_url = save_image(form) or form.image_url.data
        recipe.video_url = form.video_url.data
        recipe.cuisine = form.cuisine.data
        recipe.dish_type = form.dish_type.data
        recipe.difficulty = form.difficulty.data
        recipe.cook_time = form.cook_time.data
        recipe.tags = form.tags.data
        if not current_user.is_admin:
            recipe.status = "pending"
        db_sess.commit()
        flash("Рецепт обновлён.")
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
    user_collections = db_sess.query(Collection).filter(Collection.user_id == current_user.id).all()
    return render_template("collections.html", form=form, collections=user_collections)


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
    if not collection or not recipe or collection.user_id != current_user.id:
        abort(403)
    if recipe not in collection.recipes:
        collection.recipes.append(recipe)
        db_sess.commit()
    return redirect(url_for("recipe_detail", recipe_id=recipe_id))


@app.route("/shopping", methods=["GET", "POST"])
@login_required
def shopping():
    db_sess = db_session.create_session()
    delete_shopping_duplicates(db_sess, current_user.id)
    form = ShoppingItemForm()
    if form.validate_on_submit():
        add_shopping_item(db_sess, current_user.id, form.name.data, form.amount.data)
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
    for line in recipe.get_ingredients():
        name, amount = split_ingredient(line)
        add_shopping_item(db_sess, current_user.id, name, amount, recipe.id)
    db_sess.commit()
    flash("Ингредиенты добавлены в список покупок без повторов.")
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
        flash("Профиль сохранён.")
        return redirect(url_for("profile"))
    favorites = db_sess.query(Favorite).filter(Favorite.user_id == current_user.id).all()
    history = db_sess.query(ViewHistory).filter(ViewHistory.user_id == current_user.id).order_by(ViewHistory.viewed_at.desc()).limit(10).all()
    my_recipes = db_sess.query(Recipe).filter(Recipe.author_id == current_user.id).all()
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
            return render_template("register.html", form=form, message="Такая почта уже занята.")
        if phone and db_sess.query(User).filter(User.phone == phone).first():
            return render_template("register.html", form=form, message="Такой телефон уже занят.")

        user = User(username=form.username.data, name=form.name.data, email=email, phone=phone)
        user.set_password(form.password.data)
        db_sess.add(user)
        db_sess.commit()
        flash("Регистрация прошла успешно.")
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
    pending = db_sess.query(Recipe).filter(Recipe.status == "pending").all()
    users = db_sess.query(User).order_by(User.created_date.desc()).all()
    categories = db_sess.query(Category).all()
    tags = db_sess.query(Tag).all()
    return render_template("admin.html", pending=pending, users=users, categories=categories, tags=tags, category_form=category_form, tag_form=tag_form)


@app.route("/admin/recipe/<int:recipe_id>/<action>", methods=["POST"])
@login_required
def moderate_recipe(recipe_id, action):
    if not current_user.is_admin:
        abort(403)
    db_sess = db_session.create_session()
    recipe = db_sess.get(Recipe, recipe_id)
    if not recipe:
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


def add_recipe_if_not_exists(db_sess, title, short_description, ingredients, steps, image_url, cuisine, dish_type, difficulty, cook_time, tags, tips=""):
    recipe = db_sess.query(Recipe).filter(Recipe.title == title).first()
    if recipe:
        recipe.short_description = short_description
        recipe.ingredients = ingredients
        recipe.steps = steps
        recipe.image_url = image_url
        recipe.cuisine = cuisine
        recipe.dish_type = dish_type
        recipe.difficulty = difficulty
        recipe.cook_time = cook_time
        recipe.tags = tags
        recipe.status = "approved"
        return
    db_sess.add(Recipe(
        title=title,
        short_description=short_description,
        ingredients=ingredients,
        steps=steps,
        tips=tips,
        image_url=image_url,
        cuisine=cuisine,
        dish_type=dish_type,
        difficulty=difficulty,
        cook_time=cook_time,
        tags=tags,
        status="approved",
    ))


def seed_data():
    db_sess = db_session.create_session()
    if not db_sess.query(User).filter(User.username == "admin").first():
        admin = User(username="admin", name="Администратор", email="admin@cookbook.local", phone="79990000000", role="admin")
        admin.set_password("admin123")
        db_sess.add(admin)

    dishes = [
        ("Паста с томатами и базиликом", "Быстрый ужин с ярким соусом и зеленью.", "Паста - 250 г\nТоматы - 3 шт.\nЧеснок - 2 зубчика\nБазилик - 1 пучок\nСыр - 50 г", "Отварите пасту.\nОбжарьте чеснок и томаты.\nСмешайте пасту с соусом и сыром.", "/static/images/pasta.svg", "Итальянская", "Основное", "Легко", 25, "паста, ужин, вегетарианское"),
        ("Сырники с ванилью", "Нежные сырники для завтрака со сметаной или ягодами.", "Творог - 400 г\nЯйцо - 1 шт.\nМука - 3 ст. л.\nСахар - 2 ст. л.\nВаниль - по вкусу", "Смешайте творог, яйцо и сахар.\nДобавьте муку.\nСформируйте сырники и обжарьте.", "/static/images/syrniki.svg", "Русская", "Завтрак", "Средне", 30, "завтрак, десерт, творог"),
        ("Куриный суп с лапшой", "Домашний суп с курицей, овощами и лапшой.", "Курица - 500 г\nЛапша - 100 г\nМорковь - 1 шт.\nЛук - 1 шт.\nЗелень - по вкусу", "Сварите бульон.\nДобавьте овощи.\nДобавьте лапшу и зелень.", "/static/images/soup.svg", "Домашняя", "Суп", "Легко", 55, "суп, курица, обед"),
        ("Греческий салат", "Свежий салат с овощами, фетой и маслинами.", "Огурцы - 2 шт.\nПомидоры - 3 шт.\nФета - 150 г\nМаслины - 80 г\nОливковое масло - 2 ст. л.", "Нарежьте овощи.\nДобавьте фету и маслины.\nЗаправьте маслом.", "/static/images/salad.svg", "Греческая", "Салат", "Легко", 15, "салат, овощи, быстро"),
        ("Шоколадные панкейки", "Мягкие панкейки с какао для сладкого завтрака.", "Мука - 180 г\nКакао - 2 ст. л.\nЯйцо - 1 шт.\nМолоко - 220 мл\nСахар - 2 ст. л.", "Смешайте сухие продукты.\nДобавьте яйцо и молоко.\nЖарьте на сухой сковороде.", "/static/images/pancakes.svg", "Американская", "Десерт", "Легко", 25, "десерт, завтрак, шоколад"),
        ("Рис с овощами", "Простое горячее блюдо из риса и овощей.", "Рис - 200 г\nМорковь - 1 шт.\nПерец - 1 шт.\nГорошек - 100 г\nСоевый соус - 2 ст. л.", "Отварите рис.\nОбжарьте овощи.\nСмешайте рис с овощами и соусом.", "/static/images/rice.svg", "Азиатская", "Основное", "Легко", 35, "рис, овощи, вегетарианское"),
        ("Омлет с сыром", "Быстрый завтрак из яиц, молока и сыра.", "Яйца - 3 шт.\nМолоко - 50 мл\nСыр - 60 г\nСоль - по вкусу", "Взбейте яйца с молоком.\nВылейте на сковороду.\nДобавьте сыр и доведите до готовности.", "/static/images/omelet.svg", "Французская", "Завтрак", "Легко", 12, "омлет, сыр, быстро"),
        ("Ягодный смузи", "Освежающий напиток из ягод и йогурта.", "Ягоды - 200 г\nЙогурт - 250 мл\nМёд - 1 ст. л.\nБанан - 1 шт.", "Положите всё в блендер.\nВзбейте до однородности.\nПодавайте охлаждённым.", "/static/images/smoothie.svg", "Домашняя", "Напиток", "Легко", 7, "напиток, ягоды, быстро"),
    ]
    for dish in dishes:
        add_recipe_if_not_exists(db_sess, *dish)

    for name, kind in [
        ("Итальянская", "cuisine"), ("Русская", "cuisine"), ("Домашняя", "cuisine"), ("Греческая", "cuisine"),
        ("Американская", "cuisine"), ("Азиатская", "cuisine"), ("Основное", "dish_type"), ("Завтрак", "dish_type"),
        ("Суп", "dish_type"), ("Салат", "dish_type"), ("Десерт", "dish_type"), ("Напиток", "dish_type"),
    ]:
        if not db_sess.query(Category).filter(Category.name == name).first():
            db_sess.add(Category(name=name, kind=kind))
    for name in ["быстро", "десерт", "курица", "овощи", "вегетарианское", "завтрак"]:
        if not db_sess.query(Tag).filter(Tag.name == name).first():
            db_sess.add(Tag(name=name))
    db_sess.commit()


def main():
    os.makedirs("../../Documents/New project/web_recept_source/db", exist_ok=True)
    db_session.global_init("db/cookbook_full.db")
    seed_data()
    url = "http://127.0.0.1:8080"
    threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    app.run(host="127.0.0.1", port=8080, debug=True, use_reloader=False)


if __name__ == "__main__":
    main()
