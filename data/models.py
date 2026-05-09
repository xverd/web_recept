import datetime as dt

import sqlalchemy as sa
from flask_login import UserMixin
from sqlalchemy.orm import relationship
from werkzeug.security import check_password_hash, generate_password_hash

from .db_session import SqlAlchemyBase


collection_recipes = sa.Table(
    "collection_recipes",
    SqlAlchemyBase.metadata,
    sa.Column("collection_id", sa.Integer, sa.ForeignKey("collections.id"), primary_key=True),
    sa.Column("recipe_id", sa.Integer, sa.ForeignKey("recipes.id"), primary_key=True),
)


class User(SqlAlchemyBase, UserMixin):
    __tablename__ = "users"

    id = sa.Column(sa.Integer, primary_key=True, autoincrement=True)
    username = sa.Column(sa.String(80), unique=True, nullable=False, index=True)
    name = sa.Column(sa.String(120), nullable=False, default="Пользователь")
    email = sa.Column(sa.String(120), unique=True, index=True, nullable=True)
    phone = sa.Column(sa.String(40), unique=True, nullable=True)
    avatar_url = sa.Column(sa.String(300), nullable=True)
    role = sa.Column(sa.String(20), nullable=False, default="user")
    is_blocked = sa.Column(sa.Boolean, nullable=False, default=False)
    hashed_password = sa.Column(sa.String(250), nullable=False)
    created_date = sa.Column(sa.DateTime, default=dt.datetime.now)

    recipes = relationship("Recipe", back_populates="author", cascade="all, delete-orphan")
    favorites = relationship("Favorite", back_populates="user", cascade="all, delete-orphan")
    collections = relationship("Collection", back_populates="user", cascade="all, delete-orphan")
    reviews = relationship("Review", back_populates="user", cascade="all, delete-orphan")
    shopping_items = relationship("ShoppingItem", back_populates="user", cascade="all, delete-orphan")

    @property
    def is_admin(self):
        return self.role in {"admin", "moderator"}

    def set_password(self, password):
        self.hashed_password = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.hashed_password, password)

    def get_id(self):
        return str(self.id)


class Recipe(SqlAlchemyBase):
    __tablename__ = "recipes"

    id = sa.Column(sa.Integer, primary_key=True, autoincrement=True)
    title = sa.Column(sa.String(160), nullable=False, index=True)
    short_description = sa.Column(sa.String(500), nullable=False)
    ingredients = sa.Column(sa.Text, nullable=False)
    steps = sa.Column(sa.Text, nullable=False)
    tips = sa.Column(sa.Text, nullable=True)
    image_url = sa.Column(sa.String(500), nullable=True)
    video_url = sa.Column(sa.String(500), nullable=True)
    cuisine = sa.Column(sa.String(80), nullable=False, default="Домашняя")
    dish_type = sa.Column(sa.String(80), nullable=False, default="Основное")
    difficulty = sa.Column(sa.String(30), nullable=False, default="Средне")
    cook_time = sa.Column(sa.Integer, nullable=False, default=30)
    tags = sa.Column(sa.String(250), nullable=True)
    status = sa.Column(sa.String(20), nullable=False, default="pending")
    views = sa.Column(sa.Integer, nullable=False, default=0)
    created_date = sa.Column(sa.DateTime, default=dt.datetime.now)
    author_id = sa.Column(sa.Integer, sa.ForeignKey("users.id"), nullable=True)

    author = relationship("User", back_populates="recipes")
    favorites = relationship("Favorite", back_populates="recipe", cascade="all, delete-orphan")
    reviews = relationship("Review", back_populates="recipe", cascade="all, delete-orphan")
    history = relationship("ViewHistory", back_populates="recipe", cascade="all, delete-orphan")
    collections = relationship("Collection", secondary=collection_recipes, back_populates="recipes")

    @property
    def ingredients_list(self):
        return [row.strip() for row in self.ingredients.splitlines() if row.strip()]

    @property
    def steps_list(self):
        return [row.strip() for row in self.steps.splitlines() if row.strip()]

    @property
    def tags_list(self):
        if not self.tags:
            return []
        return [tag.strip() for tag in self.tags.split(",") if tag.strip()]

    @property
    def avg_rating(self):
        if not self.reviews:
            return 0
        return round(sum(review.rating for review in self.reviews) / len(self.reviews), 1)


class Favorite(SqlAlchemyBase):
    __tablename__ = "favorites"
    __table_args__ = (sa.UniqueConstraint("user_id", "recipe_id", name="uq_favorite_user_recipe"),)

    id = sa.Column(sa.Integer, primary_key=True, autoincrement=True)
    user_id = sa.Column(sa.Integer, sa.ForeignKey("users.id"), nullable=False)
    recipe_id = sa.Column(sa.Integer, sa.ForeignKey("recipes.id"), nullable=False)
    created_date = sa.Column(sa.DateTime, default=dt.datetime.now)

    user = relationship("User", back_populates="favorites")
    recipe = relationship("Recipe", back_populates="favorites")


class Collection(SqlAlchemyBase):
    __tablename__ = "collections"

    id = sa.Column(sa.Integer, primary_key=True, autoincrement=True)
    title = sa.Column(sa.String(120), nullable=False)
    description = sa.Column(sa.String(400), nullable=True)
    user_id = sa.Column(sa.Integer, sa.ForeignKey("users.id"), nullable=False)
    created_date = sa.Column(sa.DateTime, default=dt.datetime.now)

    user = relationship("User", back_populates="collections")
    recipes = relationship("Recipe", secondary=collection_recipes, back_populates="collections")


class ViewHistory(SqlAlchemyBase):
    __tablename__ = "view_history"

    id = sa.Column(sa.Integer, primary_key=True, autoincrement=True)
    user_id = sa.Column(sa.Integer, sa.ForeignKey("users.id"), nullable=False)
    recipe_id = sa.Column(sa.Integer, sa.ForeignKey("recipes.id"), nullable=False)
    viewed_at = sa.Column(sa.DateTime, default=dt.datetime.now)

    user = relationship("User")
    recipe = relationship("Recipe", back_populates="history")


class Review(SqlAlchemyBase):
    __tablename__ = "reviews"
    __table_args__ = (sa.UniqueConstraint("user_id", "recipe_id", name="uq_review_user_recipe"),)

    id = sa.Column(sa.Integer, primary_key=True, autoincrement=True)
    user_id = sa.Column(sa.Integer, sa.ForeignKey("users.id"), nullable=False)
    recipe_id = sa.Column(sa.Integer, sa.ForeignKey("recipes.id"), nullable=False)
    rating = sa.Column(sa.Integer, nullable=False)
    text = sa.Column(sa.Text, nullable=True)
    created_date = sa.Column(sa.DateTime, default=dt.datetime.now)

    user = relationship("User", back_populates="reviews")
    recipe = relationship("Recipe", back_populates="reviews")


class ShoppingItem(SqlAlchemyBase):
    __tablename__ = "shopping_items"

    id = sa.Column(sa.Integer, primary_key=True, autoincrement=True)
    user_id = sa.Column(sa.Integer, sa.ForeignKey("users.id"), nullable=False)
    name = sa.Column(sa.String(200), nullable=False)
    amount = sa.Column(sa.String(120), nullable=True)
    checked = sa.Column(sa.Boolean, nullable=False, default=False)
    source_recipe_id = sa.Column(sa.Integer, sa.ForeignKey("recipes.id"), nullable=True)
    created_date = sa.Column(sa.DateTime, default=dt.datetime.now)

    user = relationship("User", back_populates="shopping_items")
    recipe = relationship("Recipe")


class Category(SqlAlchemyBase):
    __tablename__ = "categories"

    id = sa.Column(sa.Integer, primary_key=True, autoincrement=True)
    name = sa.Column(sa.String(80), unique=True, nullable=False)
    kind = sa.Column(sa.String(40), nullable=False, default="dish_type")


class Tag(SqlAlchemyBase):
    __tablename__ = "tags"

    id = sa.Column(sa.Integer, primary_key=True, autoincrement=True)
    name = sa.Column(sa.String(80), unique=True, nullable=False)
