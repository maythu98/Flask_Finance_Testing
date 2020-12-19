import os
import datetime

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    user_id = session['user_id']

    shares = db.execute("SELECT * FROM user_shares WHERE user_id=:id", id=user_id)

    total_price = db.execute("SELECT sum(total_price) as total_price FROM user_shares WHERE user_id=:id", id=user_id)
    total_share_value = total_price[0].get('total_price')
    if not total_share_value:
        total_share_value = 0

    user_cash = db.execute("SELECT cash FROM users WHERE id=:id limit 1", id=user_id)
    user_cash = user_cash[0].get('cash')
    
    total_value = total_share_value + user_cash

    user_cash = "{0:.2f}".format(user_cash)
    total_value = "{0:.2f}".format(total_value)

    return render_template('index.html', user_cash=user_cash, shares=shares, total_value=total_value)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    user_id = session['user_id']
    """Buy shares of stock"""
    if request.method == "GET":
        return render_template('buy.html')
    else:
        symbol = request.form.get('symbol')
        if not symbol:
            return apology("must provide symbol", 403)

        share = request.form.get('share')
        if not share:
            return apology("must provide share", 403)

        # check valide symbol
        company_data = lookup(symbol)
        if not company_data:
            return apology("please type valide symbol", 400)

        # check user cash to buy shares
        share_price = company_data['price']
        company_name = company_data['name']
        total_price = share_price * float(share)
        users = db.execute("SELECT cash FROM users WHERE id=:user_id", user_id=user_id)
        user_cash = users[0].get('cash')
        if user_cash < total_price:
            return apology("Can Not Afford")

        # Buy Share
        now = datetime.datetime.now()
        #Add share to user_share
        current_user_share = db.execute("SELECT * FROM user_shares WHERE user_id=:user_id AND symbol=:symbol", user_id=user_id, symbol=symbol)
        if not current_user_share:
            db.execute("INSERT INTO user_shares (user_id, symbol, name, share, price, total_price) VALUES (:user_id, :symbol, :name, :share, :price, :total_price)", user_id=user_id, symbol=symbol, name=company_name, share=share, price=share_price, total_price=total_price)

            current_user_share = db.execute("SELECT * FROM user_shares WHERE user_id=:user_id AND symbol=:symbol", user_id=user_id, symbol=symbol)
            share_id = current_user_share[0].get('id')
        else:
            share_id = current_user_share[0].get('id')
            current_share = current_user_share[0].get('share')
            total_share = current_share + int(share)
            db.execute("UPDATE user_shares SET share=:total_share, price=:price, total_price=:total_price WHERE user_id=:user_id AND symbol=:symbol", user_id=user_id, symbol=symbol, price=share_price, total_price=total_price, total_share=total_share)
        
        #Record Share Record
        db.execute("INSERT INTO share_histories (user_share_id, type, share, price, total_price, created_at) VALUES (:user_share_id, :type, :share, :price, :total_price, :created_at)", user_share_id=share_id, type=1, share=share, price=share_price, total_price=total_price, created_at=now)

         # update user cash
        cash = user_cash - total_price
        db.execute("UPDATE users SET cash=:cash WHERE id=:user_id", cash=cash, user_id=user_id)

        return redirect('/')


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    shares = db.execute("SELECT us.symbol as symbol, sh.type, sh.share, sh.total_price as total_price, sh.created_at as created_at FROM share_histories as sh JOIN user_shares as us WHERE us.id = sh.user_share_id AND us.user_id=:id Order By sh.created_at desc", id=session['user_id'])

    return render_template("history.html", shares = shares)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""
    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

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


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "GET":
        return render_template('quote.html')
    else:
        quote = request.form.get('name')
        if not quote:
            return apology("must provide quote", 403)  
        
        info = lookup(quote)
        if not info:
            return apology("Invalid Quote", 403)

        return render_template('quoted.html', info=info)


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "GET":
        return render_template("register.html")
    else:
        name    = request.form.get('username')
        pwd     = request.form.get('password')
        if not name:
            return apology("must provide username", 403)
        
        if not pwd:
            return apology("must provide password", 403)
        
        if not request.form.get('confirmpassword'):
            return apology("must provide confirm-password", 403)

        pwd = generate_password_hash(pwd)
        
        db.execute("INSERT INTO users (username,hash) VALUES (:name, :pwd)", name = name, pwd = pwd)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=name)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    user_id = session['user_id']
    """Sell shares of stock"""
    if request.method == "GET":
        symbols = db.execute("SELECT symbol FROM user_shares WHERE user_id=:user_id", user_id=user_id)
        return render_template('sell.html', symbols=symbols)
    else:
        symbol = request.form.get('symbol')
        if not symbol:
            return apology("must have symbol", 403)

        share = request.form.get('share')
        if not share:
            return apology("must have share", 403)
        # too much share
        current_user_share = db.execute("SELECT id, share, total_price FROM user_shares WHERE user_id=:user_id AND symbol=:symbol", user_id=user_id, symbol=symbol)
        if not current_user_share:
            return apology("Does not Have this share!", 400)

        current_share = current_user_share[0].get('share')
        current_total_price = current_user_share[0].get('total_price')
        current_total_price = float(current_total_price)
        user_share_id = current_user_share[0].get('id')
        current_share = int(current_share)
        share = int(share)
        if share > current_share:
            return apology("Too Many Shares", 400)

        #current share market
        share_market = lookup(symbol)
        if not share_market:
            return apology("Invalid Symbol", 403)

        share_price = share_market['price']
        company_name = share_market['name']
        total_price = float(share_price) * float(share)

        # Buy Share
        #REduce From current user_shares
        final_share = current_share - share
        final_total_price = current_total_price - total_price
        print("total final share", final_share)
        print( "final Total price", final_total_price)
        db.execute("UPDATE user_shares SET share=:final_share, price=:price, total_price=:total_price WHERE id=:user_share_id", user_share_id=user_share_id, final_share=final_share, price=share_price, total_price=final_total_price)
        
        #share history
        now = datetime.datetime.now()
        db.execute("INSERT INTO share_histories (user_share_id, type, share, price, total_price, created_at) VALUES (:user_share_id, :type, :share, :price, :total_price, :created_at)", user_share_id=user_share_id, type=2, share=share, price=share_price, total_price=total_price, created_at=now)

         # update user cash
        users = db.execute("SELECT cash FROM users WHERE id=:user_id", user_id=user_id)
        user_cash = users[0].get('cash')
        cash = user_cash + total_price
        db.execute("UPDATE users SET cash=:cash WHERE id=:user_id", cash=cash, user_id=user_id)
        
        return redirect('/')



def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)

# export FLASK_APP=application.py
# export API_KEY=pk_18958ff3937e4d6e89f0986c09f0d9d6
# CREATE TABLE user_shares (id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, user_id INTEGER NOT NULL, symbol VARCHAR(255) NOT NULL, name VARCHAR(255), share INTEGER NOT NULL, price DOUBLE(10, 2), total_price DOUBLE(10,2));
# CREATE INDEX 'symbol' ON 'user_shares' ('symbol');

# CREATE TABLE share_histories (id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, user_share_id INTEGER NOT NULL, type INTEGER NOT NULL, share INTEGER NOT NULL, price DOUBLE(10, 2), total_price DOUBLE(10,2), created_at DATETIME);
# CREATE INDEX 'user_share_id' ON 'share_histories' ('user_share_id');