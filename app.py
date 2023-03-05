from flask import Flask,render_template

app = Flask(__name__)

@app.route("/")
def home():
    return render_template("home.html")

@app.route("/user_dashboard")
def user_dashboard():
    return render_template("user_dashboard.html")

if __name__ == '__main__':
    app.run(debug=True)