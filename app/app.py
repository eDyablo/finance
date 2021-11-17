from decimal import Decimal
from flask import Flask, redirect, request, render_template, session
from flask_migrate import Migrate
from flask_session import Session
from helpers import apology, login_required, lookup, validate_password, usd
from models import db, Profile, Transaction, User
from os import environ
from sqlalchemy import desc, func
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

# Make sure API key is set
if not environ.get("IEX_API_KEY"):
    raise RuntimeError("IEX_API_KEY not set")

# Make sure database URL is set
if not environ.get("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL not set")

migrate = Migrate()

app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

app.config["SQLALCHEMY_DATABASE_URI"] = environ.get(
    "DATABASE_URL").replace("postgres://", "postgresql://", 1)

db.init_app(app)

migrate.init_app(app, db)

# Ensure responses aren't cached


@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""

    user = User.query.filter(User.id == session["user_id"]).first()
    if not user:
        return apology("failed to get user", 500)

    amount = func.sum(Transaction.amount).label('amount')
    shares = db.session.query(Transaction.symbol, amount).filter(
        Transaction.user_id == session["user_id"]).group_by(Transaction.symbol).having(amount > 0)

    stocks = []
    for share in shares:
        stock = lookup(share.symbol)
        stocks.append(dict(
            name=stock["name"],
            price=stock["price"],
            shares=share.amount,
            symbol=stock["symbol"],
            total=stock["price"]*share.amount,
        ))

    total = user.cash
    for stock in stocks:
        total += Decimal(stock["total"])

    return render_template("index.html", owned=stocks, cash=user.cash, total=total)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        username = request.form.get("username")
        if not username:
            return apology("must provide username", 403)

        # Ensure password was submitted
        password = request.form.get("password")
        if not password:
            return apology("must provide password", 403)

        # Query database for username
        user = User.query.filter(
            User.name == username).first()

        # Ensure username exists and password is correct
        if not user or not check_password_hash(user.hash, password):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = user.id

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    # User reached the route via POST
    if request.method == "POST":

        # Ensure username was submitted
        username = request.form.get("username")
        if not username:
            return apology("must provide username")

        # Ensure password was submitted
        password = request.form.get("password")
        if not password:
            return apology("must provide password")

        # Ensure password is valid
        elif not "ok" == validate_password(request.form.get("password")):
            return apology(validate_password(request.form.get("password")))

        # Ensure password matches confirmation
        elif request.form.get("password") != request.form.get("confirmation"):
            return apology("the password and the confirmation must match")

        # Check if the username is already registred
        user = User.query.filter(
            User.name == username).first()

        if user:
            return apology("user already registered")

        # Write new user information into the database
        user = User(
            cash=Decimal(10000.00),
            hash=generate_password_hash(password),
            name=username,
        )
        db.session.add(user)
        db.session.commit()

        # Redirect user to login page
        return redirect("/login")

    # User reached the route via GET
    else:
        return render_template("register.html")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote"""

    # User reached the route via POST
    if request.method == "POST":

        symbol = request.form.get("symbol")
        if not symbol:
            return apology("must provide stock symbol")

        stock = lookup(request.form.get("symbol"))
        if not stock:
            return apology("specified stock not found")

        return render_template("quoted.html", stock=stock)

    else:
        return render_template("quote.html")


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    if request.method == "POST":

        symbol = request.form.get("symbol")
        if not symbol:
            return apology("must provide stock symbol")

        stock = lookup(symbol)
        if not stock:
            return apology("stock not found")

        try:
            shares = int(request.form.get("shares"))
        except:
            shares = 0
        if shares <= 0:
            return apology("must provide positive number of shares")

        user = User.query.filter(User.id == session["user_id"]).first()
        if not user:
            return apology("failed to get user", 500)

        total = Decimal(stock["price"] * shares)

        if user.cash < total:
            return apology("not enough cash left")

        transaction = Transaction(
            amount=shares,
            price=stock["price"],
            symbol=stock["symbol"],
            user_id=user.id,
        )

        user.cash -= total

        db.session.add(transaction)
        db.session.commit()

        # Redirect user to home page
        return redirect("/")

    elif request.method == "GET":
        return render_template("buy.html", symbol=request.args.get("symbol"))


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""

    # Fetch owned shares
    shares = func.sum(Transaction.amount).label('shares')
    stocks = db.session.query(Transaction.symbol, shares).filter(
        Transaction.user_id == session["user_id"]).group_by(Transaction.symbol).having(shares > 0)

    if request.method == "POST":

        # Verify entered ticker symbol
        symbol = request.form.get("symbol")
        if not symbol:
            return apology("must provide stock ticker symbol")

        owned = next(
            filter(lambda stock: stock.symbol == symbol, stocks), None)
        if not owned:
            return apology("must provide owned stock symbol")

        try:
            shares = int(request.form.get("shares"))
        except:
            shares = 0
        if shares <= 0:
            return apology("must provide positive number of shares")

        if owned.shares < shares:
            return apology("not enough shares owned")

        user = User.query.filter(User.id == session["user_id"]).first()
        if not user:
            return apology("failed to get user", 500)

        stock = lookup(owned["symbol"])
        if not stock:
            return apology("failed to lookup for stock", 500)

        total = Decimal(stock["price"] * shares)

        transaction = Transaction(
            amount=shares * -1,
            price=stock["price"],
            symbol=stock["symbol"],
            user_id=user.id,
        )

        user.cash += total

        db.session.add(transaction)
        db.session.commit()

        return redirect("/")

    elif request.method == "GET":
        return render_template("sell.html", stocks=stocks, symbol=request.args.get("symbol"))


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""

    transactions = Transaction.query.filter(
        Transaction.user_id == session["user_id"]).order_by(desc(Transaction.time))

    records = []
    for transaction in transactions:
        records.append(dict(
            action='sale' if transaction.amount < 0 else 'purchase',
            price=transaction.price,
            shares=transaction.amount,
            symbol=transaction.symbol,
            time=transaction.time,
        ))

    return render_template("history.html", history=records)


@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    """Manage user profile"""

    # POST
    if request.method == "POST":
        first_name = request.form.get("first_name").strip()
        last_name = request.form.get("last_name").strip()

        # Check if first or last name was submitted
        if first_name or last_name:

            profile = Profile.query.filter(
                Profile.user_id == session["user_id"]).first()

            if not profile:
                profile = Profile(user_id=session["user_id"])
                db.session.add(profile)

            profile.first_name = first_name
            profile.last_name = last_name

        # Check if password was submitted
        password = request.form.get("password").strip()
        if password:

            # Ensure password is valid
            if not "ok" == validate_password(password):
                return apology(validate_password(password))

            # Ensure password confirmation provided
            confirmation = request.form.get("confirmation").strip()
            if not confirmation:
                return apology("password must be confirmed")

            # Ensure password matches confirmation
            if password != confirmation:
                return apology("password and confirmation must match")

            # Update user password in database
            user = User.query.filter(User.id == session["user_id"]).first()
            if not user:
                return apology("failed to get user", 500)

            user.hash = generate_password_hash(password)

        db.session.commit()

        return redirect("/")

    # GET
    elif request.method == "GET":

        profile = Profile.query.filter(
            Profile.user_id == session["user_id"]).first()

        if not profile:
            profile = Profile()

        return render_template("profile.html", profile=profile)


@app.route("/cash", methods=["GET", "POST"])
@login_required
def cash():
    """Change user cash amount"""

    if request.method == "POST":
        user = User.query.filter(User.id == session["user_id"]).first()
        if not user:
            return apology("failed to get user", 500)

        user.cash += Decimal(request.form.get("extra"))

        db.session.commit()

        # Redirect user to home page
        return redirect("/")

    elif request.method == "GET":
        return render_template("cash.html")


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
