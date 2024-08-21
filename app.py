from flask import Flask, render_template, request, url_for, redirect, session, flash, send_file
import pickle
import numpy as np
import pandas as pd
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, EmailField, SubmitField
from wtforms.validators import DataRequired, Email, ValidationError
import bcrypt
from flask_mysqldb import MySQL
import matplotlib
matplotlib.use('agg')
import matplotlib.pyplot as plt
import mysql.connector
import io
from io import BytesIO
import base64
from wordcloud import WordCloud
from collections import Counter

popular_df=pickle.load(open('popular.pkl','rb'))
pt=pickle.load(open('pt.pkl','rb'))
books=pickle.load(open('books.pkl','rb'))
similarity_scores=pickle.load(open('similarity_scores.pkl','rb'))

app = Flask(__name__, static_folder='assets')

#MySQL Database initialization
app.config['MYSQL_HOST']='localhost'
app.config['MYSQL_USER']='root'
app.config['MYSQL_PASSWORD']='140818'
app.config['MYSQL_DB']='smartlibrary'
app.secret_key='d342e90b04ba20f98b309f4e432d13be'

mysql=MySQL(app)


class RegisterForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired()])
    email = EmailField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired()])
    submit=SubmitField("Register")

    def validate_email(self,field):
        cursor=mysql.connection.cursor()
        cursor.execute("SELECT * FROM users WHERE email=%s", (field.data,))
        user=cursor.fetchone()
        cursor.close()
        if user:
            raise ValidationError("Email already registered")


class LoginForm(FlaskForm):
    email = EmailField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired()])
    submit=SubmitField("Login")

@app.route('/dashboard2')
def dashboard2():
    return render_template('dashboard2.html')

@app.route('/games')
def contact():
    return render_template('games.html')

@app.route('/recommend')
def recommend():
    return render_template('recommend.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    #flash("You have been logged out successfully")
    return redirect(url_for('hello'))

@app.route('/dashboard')
def dashboard():
    if 'user_id' in session:
        user_id=session['user_id']
        cursor=mysql.connection.cursor()
        cursor.execute("SELECT * FROM users WHERE id=%s", (user_id,))
        user=cursor.fetchone()
        cursor.execute("SELECT COUNT(*) FROM books")
        book_count = cursor.fetchone()[0]  # Fetch the count from the result

        cursor.close()

        if user:
            return render_template('dashboard.html', user=user,book_count=book_count)

    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    form=LoginForm()
    if form.validate_on_submit():
        email=form.email.data
        password=form.password.data
        salt= bcrypt.gensalt()
        hashed_password=bcrypt.hashpw(password.encode('utf-8'),salt)
        #database
        cursor =mysql.connection.cursor()
        cursor.execute('SELECT * FROM users WHERE email=%s', (email,))
        user=cursor.fetchone()
        mysql.connection.commit()
        cursor.close()
        if user and bcrypt.checkpw(password.encode('utf-8'),hashed_password):
            session['user_id']=user[0]
            if email == 'admin@gmail.com':
                return redirect(url_for('dashboard'))
            else:
                return redirect(url_for('dashboard2'))
        else:
            flash('Login Failed')
            return redirect(url_for('login'))

    return render_template('login.html',form=form)

@app.route('/register', methods=['GET','POST'])
def register():
    form=RegisterForm()
    if form.validate_on_submit():
        name=form.name.data
        email=form.email.data
        password=form.password.data
        
        hashed_password=bcrypt.hashpw(password.encode('utf-8'),bcrypt.gensalt())
        #database
        cursor =mysql.connection.cursor()
        cursor.execute('INSERT INTO users(name,email,password) VALUES(%s,%s,%s)', (name,email,password))
        mysql.connection.commit()
        cursor.close()

        return redirect(url_for('login'))

    return render_template('register.html',form=form)

@app.route('/recommend_books' ,methods=['post'])
def recommend_books():
    user_input= request.form.get('user_input')
    if user_input not in pt.index:
        return render_template('request.html')
        
    index = np.where(pt.index==user_input)[0][0]
    similar_items = sorted(list(enumerate(similarity_scores[index])),key=lambda x:x[1],reverse=True)[1:11]

    data=[]
    for i in similar_items:     
        item=[]
        temp_df=books[books['Book-Title']==pt.index[i[0]]]
        item.extend(list(temp_df.drop_duplicates('Book-Title')['Book-Title'].values))
        item.extend(list(temp_df.drop_duplicates('Book-Title')['Book-Author'].values))
        item.extend(list(temp_df.drop_duplicates('Book-Title')['Image-URL-M'].values))
        data.append(item)
    print(data)
    return render_template('recommend.html',data=data )

@app.route('/display')
def display():
    cursor=mysql.connection.cursor()
    # Execute the query to fetch books
    cursor.execute("SELECT ISBN, `Book-Title`, `Book-Author`, `Year-Of-Publication`, Publisher FROM books")
    books = cursor.fetchall()
    cursor.close()
    return render_template('dashboard.html', books=books)

# Get Book Count
@app.route('/count')
def count():
     cur = mysql.connection.cursor()
     cur.execute("SELECT COUNT(*) FROM books")
     book_count = cur.fetchone()[0]  # Fetch the count from the result
     cur.close()
     # Pass the count to the HTML template
     return render_template('add_book.html', book_count=book_count)


# Add Book
@app.route('/add_book', methods=['GET','POST'])
def add_book():
    if request.method == 'POST':
    # Extract book details from the form
        isbn = request.form.get('isbn')
        title = request.form['title']
        author = request.form['author']
        year = request.form['year']
        publisher = request.form['publisher']
        image_url = request.form.get('image_url')
        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO books (ISBN, `Book-Title`, `Book-Author`, `Year-Of-Publication`, Publisher, `Image-URL-M`) VALUES (%s, %s, %s, %s, %s, %s)", (isbn, title, author, year, publisher, image_url))
        mysql.connection.commit()
        cur.close()
        flash('Book added successfully', 'success')
        return redirect(url_for('add_book'))
    return render_template('add_book.html')


@app.route('/search', methods=['GET', 'POST'])
def search_book():
    if request.method == 'POST':
        search_query = request.form['search_query']
        if search_query not in pt.index:
            return render_template('request.html')
        cursor = mysql.connection.cursor()
        cursor.execute("SELECT ISBN,`Book-Title`,`Book-Author`, `Year-Of-Publication`, `Publisher` FROM books WHERE `Book-Title` LIKE %s OR `Book-Author` LIKE %s", ('%' + search_query + '%', '%' + search_query + '%'))
        books = cursor.fetchall()
        cursor.close()
        return render_template('search_results.html', books=books)
    return render_template('search.html')

# Delete Book by Name
@app.route('/delete_book', methods=['GET','POST'])
def delete_book():
    if request.method == 'POST':
        title = request.form['title']
        cur = mysql.connection.cursor()
        cur.execute("DELETE FROM books WHERE `Book-Title` = %s", (title,))
        mysql.connection.commit()
        cur.close()
        flash('Book deleted successfully', 'success')
    return render_template('delete.html')


@app.route('/')
def hello():
    return render_template('index.html', book_name=list(popular_df['Book-Title'].values),
                           author=list(popular_df['Book-Author'].values),
                           image=list(popular_df['Image-URL-M'].values),
                           votes=list(popular_df['num_ratings'].values),
                           rating=list(popular_df['avg_rating'].values))


# Request
@app.route('/requestbook', methods=['POST'])
def requestbook():
    if request.method == 'POST':
         # Extract book details from the form
        title_book = request.form['title_book']
        author_book = request.form['author_book']
        edition_book = request.form['edition_book']
        publisher_book = request.form['publisher_book']
        quantity = request.form.get('quantity')
        email = request.form['email']
        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO requests (Title, Author, Edition, Publisher, Quantity, Email) VALUES (%s, %s, %s, %s, %s, %s)", ( title_book, author_book, edition_book, publisher_book, quantity, email))
        mysql.connection.commit()
        cur.close()
        flash('Book request placed successfully, futher updates on email', 'success')
        return render_template('request.html')





def generate_year_distribution_chart(years, counts):
    plt.figure(figsize=(10, 6))
    plt.bar(years, counts)
    plt.xlabel('Publication Year')
    plt.ylabel('Number of Books')
    plt.title('Distribution of Book Publication Years')
    plt.xticks(years[::15],rotation=45)
    image = BytesIO()
    plt.savefig(image, format='png')
    plt.close()
    encoded_image = base64.b64encode(image.getvalue()).decode('utf-8')
    return encoded_image

def generate_genre_distribution_pie(genres, counts):
    plt.figure(figsize=(8, 8))
    plt.pie(counts, labels=genres, autopct='%1.1f%%', startangle=140)
    plt.title('Distribution of Book Genres')
    image = BytesIO()
    plt.savefig(image, format='png')
    plt.close()
    encoded_image = base64.b64encode(image.getvalue()).decode('utf-8')
    return encoded_image

def fetch_year_distribution_data():
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT `Year-Of-Publication`, COUNT(*) FROM books GROUP BY `Year-Of-Publication` ORDER BY `Year-Of-Publication`LIMIT 70000")
    data = cursor.fetchall()
    years = [row[0] for row in data]
    counts = [row[1] for row in data]
    cursor.close()
    return years, counts

def fetch_genre_distribution_data():
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT Publisher, COUNT(*) FROM books GROUP BY `Publisher`LIMIT 8")
    data = cursor.fetchall()
    genres = [row[0] for row in data]
    counts = [row[1] for row in data]
    cursor.close()
    return genres, counts

@app.route('/visual')
def visual():
    years, year_counts = fetch_year_distribution_data()
    year_chart = generate_year_distribution_chart(years, year_counts)
    
    genres, genre_counts = fetch_genre_distribution_data()
    genre_chart = generate_genre_distribution_pie(genres, genre_counts)
    booktitle=generate_word_cloud(books['Book-Title'])
    
    return render_template('visual.html', year_chart=year_chart, genre_chart=genre_chart, booktitle=booktitle,books=books)

# Function to generate word cloud of book titles
def generate_word_cloud(book_titles):
    wordcloud = WordCloud(width=800, height=400, background_color='white').generate(' '.join(book_titles))
    plt.figure(figsize=(10, 6))
    plt.imshow(wordcloud, interpolation='bilinear')
    plt.axis('off')
    plt.title('Word Cloud of Book Titles')
    image = BytesIO()
    plt.savefig(image, format='png')
    plt.show()
    encoded_image = base64.b64encode(image.getvalue()).decode('utf-8')
    return encoded_image




if __name__ == '__main__':
    app.run(debug=True)
