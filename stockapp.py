from flask import Flask, render_template, request, redirect, jsonify
import yfinance as yf
import json
from datetime import datetime
import os
import matplotlib.pyplot as plt
from flask import send_file
import matplotlib
matplotlib.use('Agg')  # Use a non-GUI backend
import matplotlib.pyplot as plt
from urllib.parse import quote as url_quote



app = Flask(__name__)

# File to store user profiles and portfolios
USER_DATA_FILE = "user_data.json"

users = {}
current_user = None

# Load user data from file
def load_user_data():
    global users
    try:
        with open(USER_DATA_FILE, "r") as file:
            users = json.load(file)
    except FileNotFoundError:
        print("User data file not found. Starting with default values.")
    except Exception as e:
        print(f"Error loading user data: {e}")

# Save user data to file
def save_user_data():
    global users
    try:
        with open(USER_DATA_FILE, "w") as file:
            json.dump(users, file)
    except Exception as e:
        print(f"Error saving user data: {e}")

# Initialize user account if not exists
def initialize_user(username):
    global users
    if username not in users:
        users[username] = {
            "cash_balance": 1000000.00,
            "portfolio": {},
            "transaction_history": []
        }

# Function to fetch real-time stock data
def get_stock_info(ticker):
    try:
        ticker += ".NS"  # Append ".NS" for Indian stocks
        stock = yf.Ticker(ticker)
        stock_data = stock.history(period="1d")
        current_price = stock_data['Close'].iloc[-1]
        daily_high = stock_data['High'].iloc[-1]
        daily_low = stock_data['Low'].iloc[-1]
        yearly_high = stock.info['fiftyTwoWeekHigh']
        yearly_low = stock.info['fiftyTwoWeekLow']
        return current_price, daily_high, daily_low, yearly_high, yearly_low
    except Exception as e:
        print(f"Error fetching data for {ticker}: {e}")
        return None, None, None, None, None

@app.route('/')
def index():
    load_user_data()
    top_gainers = [
        {"ticker": "RELIANCE", "change": 5.67},
        {"ticker": "TCS", "change": 4.89},
        {"ticker": "INFY", "change": 3.45},
    ]
    top_losers = [
        {"ticker": "HDFC", "change": -5.12},
        {"ticker": "ONGC", "change": -4.89},
        {"ticker": "BPCL", "change": -4.45},
    ]
    return render_template('index.html', users=list(users.keys()), current_user=current_user, top_gainers=top_gainers,
        top_losers=top_losers)

@app.route('/welcome', methods=['GET', 'POST'])
def welcome():
    global current_user
    if request.method == 'POST':
        username = request.form.get('username')
        if not username:
            return redirect('/')
        initialize_user(username)
        current_user = username
    if current_user is None:
        return redirect('/')
    user_data = users[current_user]
    portfolio = user_data.get("portfolio", {})
    return render_template('welcome.html', current_user=current_user, portfolio=portfolio, balance=user_data["cash_balance"])

@app.route('/stock_trend', methods=['GET', 'POST'])
def stock_trend():
    global current_user
    if current_user is None:
        return redirect('/')

    if request.method == 'POST':
        try:
            # Retrieve form data
            ticker = request.form.get('ticker', '').upper()
            
            # Validate input
            if not ticker:
                return render_template('stock_trend.html', error="Please enter a valid stock ticker.")

            # Fetch stock data for the last 6 months
            stock = yf.Ticker(ticker + ".NS")
            stock_data = stock.history(period="6mo")

            if stock_data.empty:
                return render_template('stock_trend.html', error="No data found for the provided ticker.")

            # Plot the stock trend
            plt.figure(figsize=(10, 6))
            plt.plot(stock_data.index, stock_data['Close'], label=f"{ticker} Closing Price", linewidth=2)
            plt.title(f"{ticker} Stock Trend - Last 6 Months", fontsize=16)
            plt.xlabel("Date", fontsize=12)
            plt.ylabel("Closing Price (₹)", fontsize=12)
            plt.legend()
            plt.grid(True)

            # Save the plot to a file
            image_path = os.path.join("static", f"{ticker}_trend.png")
            plt.savefig(image_path)
            plt.close()

            # Success - Display the trend graph
            return render_template('stock_trend.html', image_path=image_path, balance=users[current_user]["cash_balance"])

        except Exception as e:
            print(f"Error generating stock trend graph: {e}")
            return render_template('stock_trend.html', error="An error occurred while fetching or plotting the stock data.", balance=users[current_user]["cash_balance"])

    # GET request to display the stock trend form
    return render_template('stock_trend.html', balance=users[current_user]["cash_balance"])



@app.route('/switch_user', methods=['POST'])
def switch_user():
    global current_user
    username = request.form['username']
    initialize_user(username)
    current_user = username
    save_user_data()
    return redirect('/')

@app.route('/add_funds', methods=['GET', 'POST'])
def add_funds():
    global current_user
    if request.method == 'POST':
        amount = float(request.form['amount'])
        users[current_user]["cash_balance"] += amount
        save_user_data()
        return redirect('/welcome')
    return render_template('add_funds.html', balance=users[current_user]["cash_balance"])


@app.route('/buy_stock', methods=['GET', 'POST'])
def buy_stock():
    global current_user
    if current_user is None:
        return redirect('/')

    if request.method == 'POST':
        try:
            # Retrieve form data
            ticker = request.form.get('ticker', '').upper()
            quantity = int(request.form.get('quantity', 0))
            
            # Validate form inputs
            if not ticker or quantity <= 0:
                return render_template('buy_stock.html', error="Invalid ticker or quantity.", balance=users[current_user]["cash_balance"])

            # Fetch stock price
            current_price, _, _, _, _ = get_stock_info(ticker)
            if current_price is None:
                return render_template('buy_stock.html', error="Failed to fetch stock price.", balance=users[current_user]["cash_balance"])

            # Calculate total cost
            total_cost = quantity * current_price
            if total_cost > users[current_user]["cash_balance"]:
                return render_template('buy_stock.html', error="Insufficient funds.", balance=users[current_user]["cash_balance"])

            # Update portfolio and cash balance
            users[current_user]["cash_balance"] -= total_cost
            portfolio = users[current_user]["portfolio"]
            if ticker in portfolio:
                portfolio[ticker]["quantity"] += quantity
                portfolio[ticker]["total_investment"] += total_cost
            else:
                portfolio[ticker] = {"quantity": quantity, "total_investment": total_cost}

            # Record transaction
            users[current_user]["transaction_history"].append({
                "type": "buy",
                "ticker": ticker,
                "quantity": quantity,
                "price": current_price,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })

            # Save data and redirect
            save_user_data()
            success_message = f"Successfully purchased {quantity} shares of {ticker} at ₹{current_price:.2f} each."
            return render_template('welcome.html', current_user=current_user, portfolio=portfolio, balance=users[current_user]["cash_balance"], success_message=success_message)

        except Exception as e:
            print(f"Error buying stock: {e}")
            return render_template('buy_stock.html', error="An error occurred while processing your request.", balance=users[current_user]["cash_balance"])

    # GET request to render the buy stock page
    return render_template('buy_stock.html', balance=users[current_user]["cash_balance"])


@app.route('/sell_stock', methods=['GET', 'POST'])
def sell_stock():
    global current_user
    if current_user is None:
        return redirect('/')
    try:
        if request.method == 'POST':
            # Retrieve form data
            ticker = request.form.get('ticker', '').upper()
            quantity = int(request.form.get('quantity', 0))

            # Validate input
            if not ticker or quantity <= 0:
                print("Invalid ticker or quantity.")
                return redirect('/welcome')

            # Fetch user's portfolio
            portfolio = users[current_user].get("portfolio", {})
            if ticker not in portfolio or portfolio[ticker]["quantity"] < quantity:
                print(f"Insufficient stock quantity or ticker {ticker} not in portfolio.")
                return redirect('/welcome')

            # Get the current price of the stock
            current_price, _, _, _, _ = get_stock_info(ticker)
            if current_price is None:
                print(f"Failed to fetch current price for {ticker}.")
                return redirect('/welcome')

            # Calculate earnings and update portfolio
            total_earnings = current_price * quantity
            investment_per_share = portfolio[ticker]["total_investment"] / portfolio[ticker]["quantity"]
            portfolio[ticker]["quantity"] -= quantity
            portfolio[ticker]["total_investment"] -= investment_per_share * quantity

            # Remove the stock from portfolio if quantity is zero
            if portfolio[ticker]["quantity"] == 0:
                del portfolio[ticker]

            # Update user's cash balance and transaction history
            users[current_user]["cash_balance"] += total_earnings
            users[current_user]["transaction_history"].append({
                "type": "sell",
                "ticker": ticker,
                "quantity": quantity,
                "price": current_price,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })

            # Save updated data
            save_user_data()
            print(f"Sold {quantity} shares of {ticker} at ₹{current_price} each.")
            return redirect('/welcome')

        # For GET requests, render the sell_stock page
        portfolio = users[current_user].get("portfolio", {})
        return render_template('sell_stock.html', portfolio=portfolio, balance=users[current_user]["cash_balance"])

    except Exception as e:
        print(f"Error selling stock: {e}")
        return redirect('/welcome')


@app.route('/portfolio')
def portfolio():
    global current_user
    if current_user is None:
        return redirect('/')
    
    user_data = users.get(current_user, {})
    portfolio = user_data.get("portfolio", {})
    cash_balance = user_data.get("cash_balance", 0)

    total_portfolio_value = 0
    enhanced_portfolio = {}

    for ticker, data in portfolio.items():
        current_price, _, _, _, _ = get_stock_info(ticker)  # Fetch current price
        if current_price:
            current_value = current_price * data["quantity"]
            profit_loss = current_value - data["total_investment"]
            profit_loss_percent = (profit_loss / data["total_investment"] * 100) if data["total_investment"] > 0 else 0
            total_portfolio_value += current_value
            enhanced_portfolio[ticker] = {
                "quantity": data["quantity"],
                "total_investment": data["total_investment"],
                "current_value": current_value,
                "profit_loss": profit_loss,
                "profit_loss_percent": profit_loss_percent
            }

    total_balance = cash_balance + total_portfolio_value

    return render_template(
        'portfolio.html',
        portfolio=enhanced_portfolio,
        balance=cash_balance,
        total_balance=total_balance
    )



@app.route('/transaction_history')
def transaction_history():
    global current_user
    transaction_history = users.get(current_user, {}).get("transaction_history", [])
    return render_template('transaction_history.html', transaction_history=transaction_history)

@app.route('/suggest_stocks_to_purchase', methods=['GET'])
def suggest_stocks_to_purchase():
    stock_list = ["RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS", "ITC.NS", "ICICIBANK.NS", "SBIN.NS", "BHARTIARTL.NS", "HINDUNILVR.NS", "WIPRO.NS"]
    stock_data = {}
    for ticker in stock_list:
        stock = yf.Ticker(ticker)
        history = stock.history(period="5d")
        if len(history) >= 2:
            prev_close = history['Close'].iloc[-2]
            last_close = history['Close'].iloc[-1]
            change_percent = ((last_close - prev_close) / prev_close) * 100
            stock_data[ticker] = change_percent
    sorted_stocks = sorted(stock_data.items(), key=lambda x: x[1])
    suggestions = [{"ticker": ticker, "change": change} for ticker, change in sorted_stocks[:5]]

    # Render the HTML page instead of returning JSON
    return render_template('suggest_stocks_to_purchase.html', suggestions=suggestions)


@app.route('/suggest_stocks_to_sell', methods=['GET'])
def suggest_stocks_to_sell():
    global current_user
    user_data = users.get(current_user, {})
    portfolio = user_data.get("portfolio", {})
    sell_candidates = []
    for ticker, data in portfolio.items():
        current_price, _, _, _, _ = get_stock_info(ticker)
        if current_price:
            investment_per_share = data["total_investment"] / data["quantity"]
            profit_percent = ((current_price - investment_per_share) / investment_per_share) * 100
            sell_candidates.append({"ticker": ticker, "profit": profit_percent})
    sell_candidates = sorted(sell_candidates, key=lambda x: x["profit"], reverse=True)

    # Render the HTML page instead of returning JSON
    return render_template('suggest_stocks_to_sell.html', suggestions=sell_candidates)

if __name__ == '__main__':
    load_user_data()
    app.run(debug=True, port=7000)

