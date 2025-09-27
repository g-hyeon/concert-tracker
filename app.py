from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import sqlite3
import os
from werkzeug.utils import secure_filename
from datetime import datetime
import requests
import json

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'  # Change this to a secure secret key

# Configuration
UPLOAD_FOLDER = 'static/photos'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# API Keys - Add your actual API keys here
SPOTIFY_CLIENT_ID = 'your_spotify_client_id'
SPOTIFY_CLIENT_SECRET = 'your_spotify_client_secret'
GOOGLE_MAPS_API_KEY = 'your_google_maps_api_key'
TICKETMASTER_API_KEY = 'your_ticketmaster_api_key'

# Ensure upload directory exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def init_db():
    conn = sqlite3.connect('concerts.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS concerts
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  artist TEXT NOT NULL,
                  venue TEXT NOT NULL,
                  date TEXT NOT NULL,
                  musician_rating REAL,
                  crowd_rating REAL,
                  venue_rating REAL,
                  overall_rating REAL,
                  notes TEXT,
                  photo_filename TEXT,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()

def calculate_overall_rating(musician, crowd, venue):
    """Calculate overall rating: 0.8*musician + 0.1*crowd + 0.1*venue"""
    if musician is None or crowd is None or venue is None:
        return None
    return round(0.8 * musician + 0.1 * crowd + 0.1 * venue, 2)

def get_spotify_token():
    """Get Spotify access token"""
    try:
        auth_url = 'https://accounts.spotify.com/api/token'
        auth_data = {
            'grant_type': 'client_credentials',
            'client_id': SPOTIFY_CLIENT_ID,
            'client_secret': SPOTIFY_CLIENT_SECRET,
        }
        response = requests.post(auth_url, data=auth_data)
        if response.status_code == 200:
            return response.json()['access_token']
    except Exception as e:
        print(f"Error getting Spotify token: {e}")
    return None

@app.route('/')
def index():
    conn = sqlite3.connect('concerts.db')
    c = conn.cursor()
    
    # Get filter parameters
    sort_by = request.args.get('sort', 'date_desc')
    date_filter = request.args.get('date_filter', '')
    
    # Base query
    query = "SELECT * FROM concerts WHERE 1=1"
    params = []
    
    # Add date filter
    if date_filter:
        query += " AND date LIKE ?"
        params.append(f"%{date_filter}%")
    
    # Add sorting
    if sort_by == 'rating_desc':
        query += " ORDER BY overall_rating DESC NULLS LAST"
    elif sort_by == 'rating_asc':
        query += " ORDER BY overall_rating ASC NULLS LAST"
    elif sort_by == 'date_asc':
        query += " ORDER BY date ASC"
    else:  # date_desc (default)
        query += " ORDER BY date DESC"
    
    c.execute(query, params)
    concerts = c.fetchall()
    conn.close()
    
    return render_template('index.html', concerts=concerts, sort_by=sort_by, date_filter=date_filter)

@app.route('/add_concert', methods=['GET', 'POST'])
def add_concert():
    if request.method == 'POST':
        artist = request.form['artist']
        venue = request.form['venue']
        date = request.form['date']
        
        # Check if ratings were provided (not empty strings)
        musician_rating = float(request.form['musician_rating']) if request.form['musician_rating'].strip() else None
        crowd_rating = float(request.form['crowd_rating']) if request.form['crowd_rating'].strip() else None
        venue_rating = float(request.form['venue_rating']) if request.form['venue_rating'].strip() else None
        notes = request.form['notes']
        
        # Calculate overall rating only if all ratings are provided
        overall_rating = calculate_overall_rating(musician_rating, crowd_rating, venue_rating)
        
        # Handle photo upload
        photo_filename = None
        if 'photo' in request.files:
            file = request.files['photo']
            if file and file.filename != '' and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                # Add timestamp to avoid conflicts
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_')
                photo_filename = timestamp + filename
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], photo_filename))
        
        # Save to database
        conn = sqlite3.connect('concerts.db')
        c = conn.cursor()
        c.execute('''INSERT INTO concerts 
                     (artist, venue, date, musician_rating, crowd_rating, venue_rating, 
                      overall_rating, notes, photo_filename)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                  (artist, venue, date, musician_rating, crowd_rating, venue_rating,
                   overall_rating, notes, photo_filename))
        conn.commit()
        conn.close()
        
        flash('Concert added successfully!', 'success')
        return redirect(url_for('index'))
    
    return render_template('add_concert.html')

@app.route('/edit_concert/<int:concert_id>', methods=['GET', 'POST'])
def edit_concert(concert_id):
    conn = sqlite3.connect('concerts.db')
    c = conn.cursor()
    
    if request.method == 'POST':
        artist = request.form['artist']
        venue = request.form['venue']
        date = request.form['date']
        
        # Check if ratings were provided (not empty strings)
        musician_rating = float(request.form['musician_rating']) if request.form['musician_rating'].strip() else None
        crowd_rating = float(request.form['crowd_rating']) if request.form['crowd_rating'].strip() else None
        venue_rating = float(request.form['venue_rating']) if request.form['venue_rating'].strip() else None
        notes = request.form['notes']
        
        # Calculate overall rating only if all ratings are provided
        overall_rating = calculate_overall_rating(musician_rating, crowd_rating, venue_rating)
        
        # Get current photo filename
        c.execute("SELECT photo_filename FROM concerts WHERE id = ?", (concert_id,))
        current_photo = c.fetchone()[0]
        photo_filename = current_photo
        
        # Handle photo upload
        if 'photo' in request.files:
            file = request.files['photo']
            if file and file.filename != '' and allowed_file(file.filename):
                # Delete old photo if exists
                if current_photo:
                    old_path = os.path.join(app.config['UPLOAD_FOLDER'], current_photo)
                    if os.path.exists(old_path):
                        os.remove(old_path)
                
                filename = secure_filename(file.filename)
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_')
                photo_filename = timestamp + filename
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], photo_filename))
        
        # Update database
        c.execute('''UPDATE concerts 
                     SET artist=?, venue=?, date=?, musician_rating=?, crowd_rating=?, 
                         venue_rating=?, overall_rating=?, notes=?, photo_filename=?
                     WHERE id=?''',
                  (artist, venue, date, musician_rating, crowd_rating, venue_rating,
                   overall_rating, notes, photo_filename, concert_id))
        conn.commit()
        conn.close()
        
        flash('Concert updated successfully!', 'success')
        return redirect(url_for('index'))
    
    # GET request - show edit form
    c.execute("SELECT * FROM concerts WHERE id = ?", (concert_id,))
    concert = c.fetchone()
    conn.close()
    
    if not concert:
        flash('Concert not found!', 'error')
        return redirect(url_for('index'))
    
    return render_template('edit_concert.html', concert=concert)

@app.route('/delete_concert/<int:concert_id>')
def delete_concert(concert_id):
    conn = sqlite3.connect('concerts.db')
    c = conn.cursor()
    
    # Get photo filename before deleting
    c.execute("SELECT photo_filename FROM concerts WHERE id = ?", (concert_id,))
    result = c.fetchone()
    if result and result[0]:
        photo_path = os.path.join(app.config['UPLOAD_FOLDER'], result[0])
        if os.path.exists(photo_path):
            os.remove(photo_path)
    
    c.execute("DELETE FROM concerts WHERE id = ?", (concert_id,))
    conn.commit()
    conn.close()
    
    flash('Concert deleted successfully!', 'success')
    return redirect(url_for('index'))

@app.route('/api/spotify_artists')
def spotify_artists():
    """Get artist suggestions from Spotify"""
    query = request.args.get('q', '')
    if not query or len(query) < 2:
        return jsonify([])
    
    token = get_spotify_token()
    if not token:
        return jsonify([])
    
    try:
        headers = {'Authorization': f'Bearer {token}'}
        params = {'q': query, 'type': 'artist', 'limit': 10}
        response = requests.get('https://api.spotify.com/v1/search', 
                               headers=headers, params=params)
        
        if response.status_code == 200:
            data = response.json()
            artists = []
            for artist in data['artists']['items']:
                artists.append({
                    'name': artist['name'],
                    'genres': artist.get('genres', [])
                })
            return jsonify(artists)
    except Exception as e:
        print(f"Error searching Spotify: {e}")
    
    return jsonify([])

@app.route('/api/google_venues')
def google_venues():
    """Get venue suggestions from Google Places"""
    query = request.args.get('q', '')
    if not query or len(query) < 2:
        return jsonify([])
    
    try:
        params = {
            'input': query,
            'types': 'establishment',
            'key': GOOGLE_MAPS_API_KEY
        }
        response = requests.get('https://maps.googleapis.com/maps/api/place/autocomplete/json',
                               params=params)
        
        if response.status_code == 200:
            data = response.json()
            venues = []
            for prediction in data.get('predictions', []):
                venues.append({
                    'name': prediction['description'],
                    'place_id': prediction['place_id']
                })
            return jsonify(venues)
    except Exception as e:
        print(f"Error searching Google Places: {e}")
    
    return jsonify([])

@app.route('/import_ticketmaster')
def import_ticketmaster():
    """Import concerts from Ticketmaster (placeholder - requires user authentication)"""
    # This would require OAuth flow with Ticketmaster
    # For now, just show a message
    flash('Ticketmaster import feature requires API setup and user authentication.', 'info')
    return redirect(url_for('index'))

if __name__ == '__main__':
    init_db()
    app.run(debug=True)