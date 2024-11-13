from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import os
from datetime import datetime, timedelta

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'default-key-for-dev')

# Database configuration
database_url = os.environ.get('DATABASE_URL')
if database_url and database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url or 'sqlite:///eticketing.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# User Model
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    tickets = db.relationship('Ticket', backref='user', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

# Movie Model (previously Event)
class Movie(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    duration = db.Column(db.Integer)  # in minutes
    genre = db.Column(db.String(50))
    language = db.Column(db.String(50))
    release_date = db.Column(db.Date)
    image_url = db.Column(db.String(200))
    showings = db.relationship('Showing', backref='movie', lazy=True)

# Showing Model (for movie showtimes)
class Showing(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    movie_id = db.Column(db.Integer, db.ForeignKey('movie.id'), nullable=False)
    datetime = db.Column(db.DateTime, nullable=False)
    screen = db.Column(db.String(50))
    available_seats = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Float, nullable=False)
    tickets = db.relationship('Ticket', backref='showing', lazy=True)

# Ticket Model
class Ticket(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    showing_id = db.Column(db.Integer, db.ForeignKey('showing.id'), nullable=False)
    seat_number = db.Column(db.String(10))
    purchase_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    status = db.Column(db.String(20), nullable=False, default='confirmed')

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
def index():
    movies = Movie.query.all()
    return render_template('index.html', movies=movies)

@app.route('/movie/<int:movie_id>')
def movie_details(movie_id):
    movie = Movie.query.get_or_404(movie_id)
    showings = Showing.query.filter_by(movie_id=movie_id)\
        .filter(Showing.datetime > datetime.now())\
        .order_by(Showing.datetime).all()
    return render_template('movie_details.html', movie=movie, showings=showings)

@app.route('/book/<int:showing_id>', methods=['GET', 'POST'])
@login_required
def book_ticket(showing_id):
    showing = Showing.query.get_or_404(showing_id)
    if request.method == 'POST':
        if showing.available_seats > 0:
            seat_number = f"A{showing.available_seats}"  # Simple seat numbering
            ticket = Ticket(
                user_id=current_user.id,
                showing_id=showing_id,
                seat_number=seat_number,
                status='confirmed'
            )
            showing.available_seats -= 1
            db.session.add(ticket)
            db.session.commit()
            flash('Ticket booked successfully!')
            return redirect(url_for('my_tickets'))
        flash('Sorry, no seats available!')
    return render_template('book_ticket.html', showing=showing)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form.get('username')).first()
        if user and user.check_password(request.form.get('password')):
            login_user(user)
            return redirect(url_for('index'))
        flash('Invalid username or password')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        
        if User.query.filter_by(username=username).first():
            flash('Username already exists')
            return redirect(url_for('register'))
        
        if User.query.filter_by(email=email).first():
            flash('Email already registered')
            return redirect(url_for('register'))
        
        user = User(username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash('Registration successful! Please login.')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/my-tickets')
@login_required
def my_tickets():
    tickets = Ticket.query.filter_by(user_id=current_user.id).all()
    return render_template('my_tickets.html', tickets=tickets)

# Error handlers
@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('500.html'), 500

# Create initial test movies and showings
def create_test_data():
    with app.app_context():
        db.create_all()
        
        # Only create test data if no movies exist
        if not Movie.query.first():
            # Sample movies
            movies = [
                {
                    'title': 'The Dark Knight',
                    'description': 'When the menace known as the Joker wreaks havoc and chaos on the people of Gotham, Batman must accept one of the greatest psychological and physical tests of his ability to fight injustice.',
                    'duration': 152,
                    'genre': 'Action, Crime, Drama',
                    'language': 'English',
                    'release_date': datetime(2008, 7, 18).date(),
                    'image_url': 'https://example.com/dark_knight.jpg'
                },
                {
                    'title': 'Inception',
                    'description': 'A thief who steals corporate secrets through the use of dream-sharing technology is given the inverse task of planting an idea into the mind of a C.E.O.',
                    'duration': 148,
                    'genre': 'Action, Adventure, Sci-Fi',
                    'language': 'English',
                    'release_date': datetime(2010, 7, 16).date(),
                    'image_url': 'https://example.com/inception.jpg'
                },
                {
                    'title': 'The Matrix',
                    'description': 'A computer programmer discovers that reality as he knows it is a simulation created by machines, and joins a rebellion to break free.',
                    'duration': 136,
                    'genre': 'Action, Sci-Fi',
                    'language': 'English',
                    'release_date': datetime(1999, 3, 31).date(),
                    'image_url': 'https://example.com/matrix.jpg'
                }
            ]

            # Add movies to database
            for movie_data in movies:
                movie = Movie(**movie_data)
                db.session.add(movie)
            
            db.session.commit()

            # Add showings for each movie
            movies = Movie.query.all()
            for movie in movies:
                # Create showings for the next 7 days
                for i in range(7):
                    # Two showings per day
                    showing1 = Showing(
                        movie_id=movie.id,
                        datetime=datetime.now() + timedelta(days=i, hours=14),  # 2 PM showing
                        screen=f'Screen {(movie.id + i) % 3 + 1}',
                        available_seats=100,
                        price=12.99
                    )
                    showing2 = Showing(
                        movie_id=movie.id,
                        datetime=datetime.now() + timedelta(days=i, hours=19),  # 7 PM showing
                        screen=f'Screen {(movie.id + i) % 3 + 1}',
                        available_seats=100,
                        price=14.99
                    )
                    db.session.add(showing1)
                    db.session.add(showing2)
            
            db.session.commit()

if __name__ == '__main__':
    create_test_data()
    app.run(debug=True)
