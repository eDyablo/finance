from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()


class User(db.Model):
    __tablename__ = 'users'

    # Schema
    id = db.Column(db.Integer, primary_key=True)
    cash = db.Column(db.Numeric, default=0)
    hash = db.Column(db.String(120), nullable=False)
    name = db.Column(db.String(80), unique=True, nullable=False)

    # Relations
    profiles = db.relationship('Profile', backref='user', lazy=True)


class Profile(db.Model):
    __tablename__ = 'profiles'

    # Schema
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.Text)
    last_name = db.Column(db.Text)

    # Relations
    user_id = db.Column(db.Integer, db.ForeignKey(
        f'{User.__tablename__}.id'), nullable=False)


class Transaction(db.Model):
    __tablename__ = 'transactions'

    # Schema
    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Numeric, nullable=False)
    symbol = db.Column(db.String(5), nullable=False)
    time = db.Column(db.DateTime, default=datetime.now)

    # Relations
    user_id = db.Column(db.Integer, db.ForeignKey(
        f'{User.__tablename__}.id'), nullable=False)
