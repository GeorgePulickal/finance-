import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

PRICE = {}

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

    #Show portfolio of stocks
    #find all current positions that user has
    portfolio = db.execute("SELECT * FROM portfolio WHERE id = ? AND shares > 0",session["user_id"] )

    #find the user
    users = db.execute("SELECT * FROM users WHERE id = ?",session["user_id"])

    #initialize variable
    total = 0

    #for each open position, find the current price and store the current price and the current value of shares in porfolio
    for row in range(0, len(portfolio)):

        position = portfolio[row]
        symbol = position['symbol']

        #find the current price and insert into portfolio
        price_current = lookup(symbol)['price']
        position['current'] = round(price_current, 2)

        #find the total value of position and insert into portfolio
        position['currenttotal'] = round(price_current * position['shares'], 2)
        total += float(position['currenttotal'])

    #return the index webpage
    total += float(users[0]['cash'])
    total_rounded = round(total, 2)
    return render_template("index.html", portfolio = portfolio, users = users, total_rounded = total_rounded)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    #Buy shares of stock

    #if user input something
    if request.method == "POST":

        #store user inputs
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")
        user_id =  session["user_id"]

        #no symbol or shares input
        if not symbol:
            return apology("must provide symbol", 403)
        elif not shares:
            return apology("must provide valid number of shares", 403)

        #incorrect symbol
        elif lookup(symbol) == None:
            return apology("Invalid Symbol", 403)

        #out of range shares
        elif shares < '1':
            return apology("invalid shares", 403)

        #find user current position for specific company
        position = db.execute("SELECT * FROM portfolio WHERE symbol = ? AND id = ? ", symbol, user_id)

        #find the current price of the stock, and the total price of stocks
        price_share = lookup(symbol)['price']
        price_total = float(shares) * price_share

        #find users current cash allowance
        cash_dict = db.execute("SELECT cash FROM users WHERE id = ?", user_id)
        cash = cash_dict[0]['cash']

        #if too expensive return error, else update new cash allowance
        if float(cash) - price_total < 0:
            return apology("Not enough cash", 403)
        else:
            remaining_cash = cash - price_total
            db.execute("UPDATE users SET cash = ? WHERE id = ?", round(remaining_cash, 2), user_id)

        #if first position of company, create new row in portfolio, else update the new position to the portfolio
        if len(position) == 0:
            db.execute("INSERT INTO portfolio (id, symbol, name, shares, price) VALUES( ?, ?, ?, ?, ?)", user_id, symbol, lookup(symbol)['name'], shares, round(price_share, 2))
        else:
            new_position = position[0]['shares'] + int(shares)
            db.execute("UPDATE portfolio SET shares = ? WHERE symbol = ?", new_position, symbol)

        #update transactions table with new transaction
        db.execute("INSERT INTO transactions(id, type, symbol, name, shares, price, total, timestamp) VALUES( ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)", user_id,"Buy", symbol, lookup(symbol)['name'], shares, round(price_share, 2), round(price_total, 2))

        #return to homepage with portfolio
        return redirect("/")

    #if method is 'GET' then show buy page
    else:
        return render_template("buy.html")



@app.route("/history")
@login_required
def history():
    #Show history of transactions
    #find all transactions made by user
    transactions = db.execute("SELECT * FROM transactions WHERE id = ? ORDER BY timestamp ", session["user_id"])
    return render_template("history.html", transactions = transactions)


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
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

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
    #Get stock quote
    #if user input
    if request.method == "POST":

        #store user input
        symbol = request.form.get("symbol")

        #find price of company
        price = lookup(symbol)

        #if invalid send error, else go to quoted.html
        if price == None:
            return apology("Invalid Symbol")
        else:
            return render_template("quoted.html", price = price)

    #if method="GET"
    else:
        return render_template("quote.html")



@app.route("/add-withdraw", methods=["GET", "POST"])
@login_required
def add():
    if request.method == "POST":

        #store user input
        value = round(float(request.form.get("value")), 2)
        user_id = session["user_id"]
        users = db.execute("SELECT * FROM users WHERE id = ?",user_id)

        #find cash allowance of user
        cash = float(users[0]['cash'])

        #find new cash allowance
        new_cash = value + cash

        #take out more money than you have
        if new_cash < 0:
            return apology("not enough money", 403)

        #Add too much money
        elif new_cash > 100000:
            return apology("too much money", 403)

        #Update the cash allowance
        db.execute("UPDATE users SET cash = ? WHERE id = ?", new_cash, session["user_id"])

        #Add option
        if value > 0 :
            db.execute("INSERT INTO transactions(id, type, symbol, name, shares, price, total, timestamp) VALUES( ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)", user_id,"", "", "FUNDS ADDED", "",value, "")

        #Withdraw option
        elif value < 0:
            value = value * (-1)
            db.execute("INSERT INTO transactions(id, type, symbol, name, shares, price, total, timestamp) VALUES( ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)", user_id,"","", "FUNDS WITHDRAWN", "", value, "")

        #show portfolio
        return redirect("/")
    else:
        return render_template("add_withdraw.html")






@app.route("/register", methods=["GET", "POST"])
def register():

    #clear any previous users
    session.clear()
    #Register user
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        # Ensure username was submitted
        if not username:
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not password:
            return apology("must provide password", 403)

        #Ensure confirmation submitted
        elif not confirmation:
            return apology("must confirm password", 403)

        #Ensure password confirmed
        if password != confirmation:
            return apology("Password not confirmed", 403)


        # Query database for username, if existing username
        row = db.execute("SELECT * FROM users WHERE username = ?", username)

        #if already that username
        if len(row) != 0:
            return apology("existing username", 403)

        #create password hash and insert username and hash into database
        else:
            password_hash = generate_password_hash(password)
            db.execute("INSERT INTO users(username, hash) VALUES( ?, ?)", username, password_hash)

            # Remember which user has logged in
            row = db.execute("SELECT * FROM users WHERE username = ?", username)
            session["user_id"] = row[0]["id"]

            # Redirect user to home page
            return redirect("/")

    else:
        return render_template("register.html")



@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    #Sell shares of stock
    if request.method == "POST":

        #store user input
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")
        user_id = session["user_id"]

        #no symbol
        if not symbol:
            return apology("must provide symbol", 403)


        #no shares
        elif not shares:
            return apology("must provide valid number of shares", 403)


        #incorrect symbol
        elif lookup(symbol) == None:
            return apology("Invalid Symbol", 403)


        #shares out of range
        elif shares < '1':
            return apology("invalid shares", 403)


        #find users current position on stock
        position = db.execute("SELECT * FROM portfolio WHERE symbol = ? AND id = ? ", symbol, user_id)


        #no shares purchased
        if len(position) == 0:
            return apology("NO SHARES TO SELL", 403)


        #more than 1 position on given stock
        elif len(position) != 1:
            return apology("Portfolio error", 403)

        #
        else:
            #new amount of shares
            new_position = position[0]['shares'] - int(shares)


            #less than 0, then not enough shares
            if new_position < 0:
                return apology("not enough shares to sell", 403)

            else:
                #update the new position on portfolio
                db.execute("UPDATE portfolio SET shares = ? WHERE symbol = ?", new_position, symbol)


                #find the total value of selling shares
                price_share = lookup(symbol)['price']
                price_total = float(shares) * price_share


                #find users current cash allowance
                cash_dict = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
                cash = cash_dict[0]['cash']


                #add to transactions
                db.execute("INSERT INTO transactions(id, type, symbol, name, shares, price, total, timestamp) VALUES( ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)", user_id,"Sell", symbol, lookup(symbol)['name'],
                shares, round(price_share, 2), round(price_total, 2))


                #find users new cash allowance
                remaining_cash = float(cash) + price_total
                db.execute("UPDATE users SET cash = ? WHERE id = ?", remaining_cash, session["user_id"])


                return redirect("/")

    else:
        return render_template("sell.html")



def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
