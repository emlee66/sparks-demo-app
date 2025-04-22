import streamlit as st
from datetime import date, datetime
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import urllib.parse
import requests
import json
import songkick
from ytmusicapi import YTMusic
import random
import pandas as pd

# --- App Configuration ---
st.set_page_config(
    page_title="Sparks: Music Discovery & Live",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'About': "# Sparks Music Explorer\nAI-powered music discovery + live show explorer"
    }
)

# --- Custom CSS ---
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        background: linear-gradient(90deg, #ff9966, #ff5e62);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 1rem;
    }
    .card {
        border-radius: 10px;
        padding: 1.5rem;
        background-color: #f8f9fa;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        margin-bottom: 1rem;
        transition: transform 0.3s ease;
    }
    .card:hover {
        transform: translateY(-5px);
    }
    .artist-image {
        border-radius: 50%;
        width: 100px;
        height: 100px;
        object-fit: cover;
        margin-bottom: 1rem;
    }
    .event-card {
        border-left: 4px solid #ff5e62;
        padding-left: 1rem;
        margin-bottom: 1rem;
    }
    .section-header {
        font-size: 1.5rem;
        margin-bottom: 1rem;
        border-bottom: 2px solid #ff9966;
        padding-bottom: 0.5rem;
    }
    .sidebar .stRadio > div {
        background-color: #f8f9fa;
        border-radius: 5px;
        padding: 10px;
    }
    .stButton>button {
        background-color: #ff9966;
        color: white;
        border-radius: 20px;
        padding: 0.5rem 1rem;
        border: none;
    }
    .stButton>button:hover {
        background-color: #ff5e62;
    }
</style>
""", unsafe_allow_html=True)

# --- API Keys and Setup ---
# Spotify Setup
SPOTIFY_CLIENT_ID = "ba6fec516d7140da92612f005a3e478c"
SPOTIFY_CLIENT_SECRET = "fbb9d547989c4eba99ce32346496fc68"
SPOTIFY_REDIRECT_URI = "http://127.0.0.1:8888/callback"

# Songkick Setup
SONGKICK_API_KEY = "your_songkick_api_key"  # Replace with your actual API key

# Initialize session state
if 'initialized' not in st.session_state:
    st.session_state.initialized = True
    st.session_state.current_index = 0
    st.session_state.location = "Washington, DC"
    st.session_state.saved_tracks = []
    st.session_state.music_source = "Spotify"
    st.session_state.recommendations = []
    st.session_state.user_preferences = {
        "genres": [],
        "mood": "",
        "energy": 0.5,
        "popularity": 50
    }

# --- API Clients ---
# Spotify Client
@st.cache_resource
def get_spotify_client():
    return spotipy.Spotify(auth_manager=SpotifyOAuth(
        client_id=SPOTIFY_CLIENT_ID,
        client_secret=SPOTIFY_CLIENT_SECRET,
        redirect_uri=SPOTIFY_REDIRECT_URI,
        scope="user-library-read user-top-read playlist-modify-public user-follow-read"
    ))

sp = get_spotify_client()

# YouTube Music Client
@st.cache_resource
def get_ytmusic_client():
    return YTMusic()

try:
    ytmusic = get_ytmusic_client()
except Exception as e:
    st.sidebar.warning(f"YouTube Music API initialization error: {e}")
    ytmusic = None

# Songkick Client
@st.cache_resource
def get_songkick_client():
    return songkick.SongkickClient(SONGKICK_API_KEY)

try:
    sk = get_songkick_client()
except Exception as e:
    st.sidebar.warning(f"Songkick API initialization error: {e}")
    sk = None
def get_youtube_video_id(track_name, artist_name):

# --- YouTube Helper ---
    def get_youtube_video_id(track_name, artist_name):
        try:
            query = f"{track_name} {artist_name}"
            results = ytmusic.search(query, filter="songs", limit=1)
            if results and 'videoId' in results[0]:
                return results[0]['videoId']
        except Exception as e:
            st.warning(f"YouTube lookup failed: {e}")
        return None

# --- Helper Functions ---
def get_artist_image(artist_id):
    """Get artist image from Spotify"""
    try:
        artist = sp.artist(artist_id)
        if artist['images']:
            return artist['images'][0]['url']
    except:
        pass
    return "https://via.placeholder.com/300"

def get_recommendations_from_spotify(seed_tracks=None, seed_artists=None, limit=10):
    """Get recommendations from Spotify based on seeds and preferences"""
    if not seed_tracks and not seed_artists:
        return []
    
    try:
        # Get user preferences
        prefs = st.session_state.user_preferences
        
        # Set up recommendation parameters
        params = {
            "limit": limit,
            "target_energy": prefs["energy"],
            "target_popularity": prefs["popularity"]
        }
        
        # Add seed tracks if available
        if seed_tracks:
            params["seed_tracks"] = seed_tracks[:5]  # Spotify allows max 5 seed tracks
        
        # Add seed artists if available and needed
        if seed_artists and (not seed_tracks or len(seed_tracks) < 5):
            params["seed_artists"] = seed_artists[:5 - (len(seed_tracks) if seed_tracks else 0)]
        
        # Get recommendations
        recommendations = sp.recommendations(**params)
        return recommendations['tracks']
    except Exception as e:
        st.error(f"Error getting Spotify recommendations: {e}")
        return []

def get_recommendations_from_ytmusic(query, limit=10):
    """Get recommendations from YouTube Music based on query"""
    if not ytmusic or not query:
        return []
    
    try:
        # Search for tracks
        search_results = ytmusic.search(query, filter="songs", limit=limit)
        
        # Format results to match Spotify format for consistency
        formatted_results = []
        for item in search_results:
            formatted_results.append({
                "name": item.get("title", "Unknown"),
                "artists": [{"name": artist.get("name", "Unknown")} for artist in item.get("artists", [])],
                "album": {"name": item.get("album", {}).get("name", "Unknown")},
                "external_urls": {"youtube": f"https://music.youtube.com/watch?v={item.get('videoId')}"},
                "id": item.get("videoId", ""),
                "source": "youtube"
            })
        
        return formatted_results
    except Exception as e:
        st.error(f"Error getting YouTube Music recommendations: {e}")
        return []

def get_events_from_songkick(location, artist_name=None):
    """Get events from Songkick API"""
    if not sk:
        # Return dummy data if API is not available
        return [
            {"artist": "Fred again..", "venue": "9:30 Club", "date": date(2025, 6, 14), "ticket_url": "#"},
            {"artist": "Paul Kalkbrenner", "venue": "Echostage", "date": date(2025, 7, 2), "ticket_url": "#"},
            {"artist": "Ben Böhmer", "venue": "Flash", "date": date(2025, 6, 30), "ticket_url": "#"},
        ]
    
    try:
        # Get location ID
        locations = sk.search_locations(query=location)
        if not locations:
            return []
        
        location_id = locations[0].id
        
        # Get events for location
        events = sk.get_events(location_id=location_id)
        
        # Filter by artist if provided
        if artist_name:
            events = [e for e in events if artist_name.lower() in e.display_name.lower()]
        
        # Format events
        formatted_events = []
        for event in events:
            formatted_events.append({
                "artist": event.display_name,
                "venue": event.venue.display_name,
                "date": event.start.date,
                "ticket_url": event.uri
            })
        
        return formatted_events
    except Exception as e:
        st.error(f"Error getting events from Songkick: {e}")
        # Return dummy data as fallback
        return [
            {"artist": "Fred again..", "venue": "9:30 Club", "date": date(2025, 6, 14), "ticket_url": "#"},
            {"artist": "Paul Kalkbrenner", "venue": "Echostage", "date": date(2025, 7, 2), "ticket_url": "#"},
            {"artist": "Ben Böhmer", "venue": "Flash", "date": date(2025, 6, 30), "ticket_url": "#"},
        ]

def create_spotify_playlist(track_ids, playlist_name="My Sparks Playlist"):
    """Create a Spotify playlist with the given tracks"""
    try:
        # Get user ID
        user_id = sp.me()['id']
        
        # Create playlist
        playlist = sp.user_playlist_create(user_id, playlist_name, public=True, 
                                          description="Created with Sparks Music Explorer")
        
        # Add tracks to playlist
        if track_ids:
            sp.playlist_add_items(playlist['id'], track_ids)
        
        return playlist['external_urls']['spotify']
    except Exception as e:
        st.error(f"Error creating playlist: {e}")
        return None

# --- Sidebar ---
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/000000/musical-notes.png", width=80)
    st.markdown("<h2 class='main-header'>Sparks</h2>", unsafe_allow_html=True)
    
    menu = st.radio("Navigate", [
        "🏠 Home & Discover", 
        "🎭 Live Shows", 
        "🎧 Your Music", 
        "⚙️ Preferences"
    ])
    
    st.markdown("---")
    
    # Music source selector
    st.session_state.music_source = st.selectbox(
        "Music Source", 
        ["Spotify", "YouTube Music"],
        index=0 if st.session_state.music_source == "Spotify" else 1
    )
    
    # Location selector for concerts
    if "🎭 Live Shows" in menu:
        st.session_state.location = st.text_input("Location", st.session_state.location)
    
    st.markdown("---")
    st.markdown("### About")
    st.markdown("Sparks helps you discover new music and live shows based on your preferences.")
    st.markdown("Made with ❤️ using Streamlit")

# --- Main Content ---
# Home & Discover
if "🏠 Home & Discover" in menu:
    st.markdown("<h1 class='main-header'>Music Discovery</h1>", unsafe_allow_html=True)
    
    tabs = st.tabs(["Your Top Tracks", "Recommendations", "Explore"])
    
    # Your Top Tracks Tab
    with tabs[0]:
        st.markdown("<div class='section-header'>Your Spotify Top Tracks</div>", unsafe_allow_html=True)
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            # Get top tracks if not already in session state
            if 'track_list' not in st.session_state:
                try:
                    st.session_state.track_list = sp.current_user_top_tracks(limit=10)['items']
                except Exception as e:
                    st.error(f"Error fetching top tracks: {e}")
                    st.session_state.track_list = []
            
            track_list = st.session_state.track_list
            
            if track_list:
                index = st.session_state.current_index
                current_track = track_list[index]
                track_name = current_track['name']
                artist_name = current_track['artists'][0]['name']
                artist_id = current_track['artists'][0]['id']
                album_name = current_track['album']['name']
                
                # Display track info
                st.markdown(f"### Now Playing: {track_name}")
                st.markdown(f"**Artist:** {artist_name}")
                st.markdown(f"**Album:** {album_name}")
                
                # YouTube embed search query


video_id = get_youtube_video_id(track_name, artist_name)
if video_id:
    st.components.v1.iframe(f"https://www.youtube.com/embed/{video_id}", height=315)
else:
    st.info("No playable YouTube video found.")

    # Track controls
    col_prev, col_save, col_next = st.columns(3)
                
    with col_prev:
        if st.button("⏮️ Previous"):
            if index > 0:
                st.session_state.current_index -= 1
            else:
                st.session_state.current_index = len(track_list) - 1
            st.rerun()
    
    with col_save:
        if st.button("❤️ Save Track"):
            if current_track['id'] not in [t['id'] for t in st.session_state.saved_tracks]:
                st.session_state.saved_tracks.append(current_track)
                st.success(f"Saved: {track_name}")
            else:
                st.info("Track already saved")
    
    with col_next:
        if st.button("⏭️ Next Track"):
            if index < len(track_list) - 1:
                st.session_state.current_index += 1
            else:
                st.session_state.current_index = 0
                st.rerun()
            else:
                st.write("No top tracks found. Make sure your Spotify account has listening history.")
        
        with col2:
            if track_list:
                # Display artist image
                artist_image = get_artist_image(artist_id)
                st.image(artist_image, width=200)
                
                # Track feedback
                st.markdown("### Your Feedback")
                st.text_input("Describe this track:", key="feedback_text")
                st.select_slider(
                    "Energy level:",
                    options=["Chill", "Moderate", "Energetic"],
                    value="Moderate",
                    key="energy_feedback"
                )
                st.radio(
                    "Your reaction:", 
                    ["🌟 Feels fresh", "🧠 Love it", "😕 Too polished", "🔎 Intriguing but unsure"], 
                    key="reaction"
                )
                
                if st.button("Submit Feedback"):
                    st.success("Thanks for your feedback! We'll use it to improve your recommendations.")
    
    # Recommendations Tab
    with tabs[1]:
        st.markdown("<div class='section-header'>Personalized Recommendations</div>", unsafe_allow_html=True)
        
        # Get recommendations based on selected music source
        if st.session_state.music_source == "Spotify":
            if 'track_list' in st.session_state and st.session_state.track_list:
                # Get seed tracks and artists
                seed_tracks = [track['id'] for track in st.session_state.track_list[:3]]
                seed_artists = [track['artists'][0]['id'] for track in st.session_state.track_list[:2]]
                
                # Get recommendations
                if st.button("Get Fresh Recommendations"):
                    with st.spinner("Finding new tracks you might like..."):
                        recommendations = get_recommendations_from_spotify(
                            seed_tracks=seed_tracks,
                            seed_artists=seed_artists,
                            limit=10
                        )
                        st.session_state.recommendations = recommendations
            else:
                st.warning("Listen to some tracks first to get personalized recommendations.")
        else:  # YouTube Music
            if 'track_list' in st.session_state and st.session_state.track_list:
                # Create search query from top tracks
                query = " ".join([
                    f"{track['name']} {track['artists'][0]['name']}"
                    for track in st.session_state.track_list[:2]
                ])
                
                # Get recommendations
                if st.button("Get YouTube Music Recommendations"):
                    with st.spinner("Finding tracks on YouTube Music..."):
                        recommendations = get_recommendations_from_ytmusic(query, limit=10)
                        st.session_state.recommendations = recommendations
            else:
                st.warning("Listen to some tracks first to get personalized recommendations.")
        
        # Display recommendations
        if 'recommendations' in st.session_state and st.session_state.recommendations:
            st.markdown("### Based on your taste, you might like:")
            
            # Create a grid of recommendations
            cols = st.columns(2)
            for i, track in enumerate(st.session_state.recommendations):
                with cols[i % 2]:
                    st.markdown(f"""
                    <div class='card'>
                        <h4>{track['name']}</h4>
                        <p>by {track['artists'][0]['name']}</p>
                        <p><em>From: {track.get('album', {}).get('name', 'Unknown')}</em></p>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Add button to play the track
                    if st.button(f"Play", key=f"play_{i}"):
                        if st.session_state.music_source == "Spotify":
                            # Create YouTube search query
                            query = urllib.parse.quote(f"{track['name']} {track['artists'][0]['name']}")
                            youtube_embed_url = f"https://www.youtube.com/embed?listType=search&list={query}"
                            st.session_state.current_embed = youtube_embed_url
                        else:  # YouTube Music
                            video_id = track.get('id', '')
                            if video_id:
                                youtube_embed_url = f"https://www.youtube.com/embed/{video_id}"
                                st.session_state.current_embed = youtube_embed_url
                    
                    # Add button to save the track
                    if st.button(f"Save", key=f"save_{i}"):
                        if track not in st.session_state.saved_tracks:
                            st.session_state.saved_tracks.append(track)
                            st.success(f"Saved: {track['name']}")
                        else:
                            st.info("Track already saved")
            
            # Display current embed if available
            if 'current_embed' in st.session_state:
                st.components.v1.iframe(st.session_state.current_embed, height=315)
            
            # Create playlist button
            if st.session_state.music_source == "Spotify" and st.button("Create Spotify Playlist from Recommendations"):
                track_ids = [track['id'] for track in st.session_state.recommendations if 'id' in track]
                playlist_url = create_spotify_playlist(track_ids, "Sparks Recommendations")
                if playlist_url:
                    st.success(f"Playlist created! [Open in Spotify]({playlist_url})")
    
    # Explore Tab
    with tabs[2]:
        st.markdown("<div class='section-header'>Explore New Music</div>", unsafe_allow_html=True)
        
        # Genre explorer
        genres = [
            "Pop", "Rock", "Hip Hop", "Electronic", "Jazz", "Classical", 
            "R&B", "Country", "Folk", "Metal", "Indie", "Ambient"
        ]
        
        selected_genres = st.multiselect("Select genres to explore:", genres)
        
        col1, col2 = st.columns(2)
        
        with col1:
            popularity = st.slider("Popularity", 0, 100, 50)
        
        with col2:
            energy = st.slider("Energy", 0.0, 1.0, 0.5)
        
        if st.button("Explore") and selected_genres:
            # Update user preferences
            st.session_state.user_preferences["genres"] = selected_genres
            st.session_state.user_preferences["popularity"] = popularity
            st.session_state.user_preferences["energy"] = energy
            
            # Get recommendations based on genres
            try:
                # Get genre seeds
                genre_seeds = sp.recommendation_genre_seeds()['genres']
                valid_genres = [g for g in selected_genres if g.lower() in genre_seeds]
                
                if valid_genres:
                    recommendations = sp.recommendations(
                        seed_genres=valid_genres[:5],  # Spotify allows max 5 seed genres
                        limit=10,
                        target_popularity=popularity,
                        target_energy=energy
                    )['tracks']
                    
                    st.session_state.recommendations = recommendations
                    st.success(f"Found {len(recommendations)} tracks based on your preferences!")
                    st.rerun()
                else:
                    st.warning("No valid genre seeds found. Try different genres.")
            except Exception as e:
                st.error(f"Error exploring genres: {e}")

# Live Shows
elif "🎭 Live Shows" in menu:
    st.markdown("<h1 class='main-header'>Live Shows</h1>", unsafe_allow_html=True)
    
    # Location search
    location = st.session_state.location
    st.markdown(f"<div class='section-header'>Upcoming Concerts in {location}</div>", unsafe_allow_html=True)
    
    # Artist filter
    artist_filter = st.text_input("Filter by artist (optional)")
    
    # Get events
    with st.spinner(f"Finding events in {location}..."):
        events = get_events_from_songkick(location, artist_filter)
    
    if events:
        # Display events in a table
        event_data = []
        for event in events:
            event_data.append({
                "Artist": event["artist"],
                "Venue": event["venue"],
                "Date": event["date"].strftime("%b %d, %Y") if isinstance(event["date"], date) else event["date"],
                "Tickets": event["ticket_url"]
            })
        
        df = pd.DataFrame(event_data)
        st.dataframe(df, use_container_width=True, hide_index=True)
        
        # Display events as cards
        st.markdown("### Event Details")
        for event in events:
            with st.expander(f"{event['artist']} at {event['venue']}"):
                st.markdown(f"""
                <div class='event-card'>
                    <h3>{event['artist']}</h3>
                    <p><strong>Venue:</strong> {event['venue']}</p>
                    <p><strong>Date:</strong> {event['date'].strftime('%B %d, %Y') if isinstance(event['date'], date) else event['date']}</p>
                    <p><a href="{event['ticket_url']}" target="_blank">Get Tickets</a></p>
                </div>
                """, unsafe_allow_html=True)
                
                # Add button to check out the artist
                if st.button(f"Check out {event['artist'].split(' ')[0]}'s music", key=f"artist_{event['artist']}"):
                    # Search for artist on selected platform
                    if st.session_state.music_source == "Spotify":
                        try:
                            results = sp.search(q=event['artist'], type='artist', limit=1)
                            if results['artists']['items']:
                                artist_id = results['artists']['items'][0]['id']
                                top_tracks = sp.artist_top_tracks(artist_id)['tracks']
                                
                                if top_tracks:
                                    st.session_state.recommendations = top_tracks
                                    st.success(f"Found top tracks for {event['artist']}!")
                                    st.rerun()
                        except Exception as e:
                            st.error(f"Error finding artist on Spotify: {e}")
                    else:  # YouTube Music
                        try:
                            if ytmusic:
                                recommendations = get_recommendations_from_ytmusic(event['artist'], limit=5)
                                if recommendations:
                                    st.session_state.recommendations = recommendations
                                    st.success(f"Found tracks for {event['artist']} on YouTube Music!")
                                    st.rerun()
                        except Exception as e:
                            st.error(f"Error finding artist on YouTube Music: {e}")
    else:
        st.info(f"No events found in {location}. Try a different location or check back later.")
        
        # Suggest popular music cities
        st.markdown("### Popular Music Cities")
        cols = st.columns(3)
        cities = ["New York", "Los Angeles", "London", "Berlin", "Tokyo", "Austin"]
        
        for i, city in enumerate(cities):
            with cols[i % 3]:
                if st.button(city):
                    st.session_state.location = city
                    st.rerun()

# Your Music
elif "🎧 Your Music" in menu:
    st.markdown("<h1 class='main-header'>Your Music</h1>", unsafe_allow_html=True)
    
    tabs = st.tabs(["Saved Tracks", "Create Playlist", "Following"])
    
    # Saved Tracks Tab
    with tabs[0]:
        st.markdown("<div class='section-header'>Your Saved Tracks</div>", unsafe_allow_html=True)
        
        if st.session_state.saved_tracks:
            # Display saved tracks
            for i, track in enumerate(st.session_state.saved_tracks):
                col1, col2, col3 = st.columns([3, 1, 1])
                
                with col1:
                    st.markdown(f"""
                    <div class='card'>
                        <h4>{track['name']}</h4>
                        <p>by {track['artists'][0]['name']}</p>
                    </div>
                    """, unsafe_allow_html=True)
                
                with col2:
                    if st.button("Play", key=f"play_saved_{i}"):
                        # Create YouTube search query
                        query = urllib.parse.quote(f"{track['name']} {track['artists'][0]['name']}")
                        youtube_embed_url = f"https://www.youtube.com/embed?listType=search&list={query}"
                        st.session_state.current_embed = youtube_embed_url
                        st.rerun()
                
                with col3:
                    if st.button("Remove", key=f"remove_{i}"):
                        st.session_state.saved_tracks.pop(i)
                        st.rerun()
            
            # Display current embed if available
            if 'current_embed' in st.session_state:
                st.components.v1.iframe(st.session_state.current_embed, height=315)
        else:
            st.info("You haven't saved any tracks yet. Explore music and save tracks you like!")
    
    # Create Playlist Tab
    with tabs[1]:
        st.markdown("<div class='section-header'>Create Spotify Playlist</div>", unsafe_allow_html=True)
        
        if st.session_state.music_source == "Spotify":
            if st.session_state.saved_tracks:
                playlist_name = st.text_input("Playlist Name", "My Sparks Playlist")
                
                # Show tracks to include
                st.markdown("### Tracks to include:")
                selected_tracks = []
                
                for i, track in enumerate(st.session_state.saved_tracks):
                    if 'source' not in track or track['source'] != 'youtube':  # Only include Spotify tracks
                        selected = st.checkbox(f"{track['name']} - {track['artists'][0]['name']}", value=True, key=f"include_{i}")
                        if selected:
                            selected_tracks.append(track)
                
                if st.button("Create Playlist") and selected_tracks:
                    track_ids = [track['id'] for track in selected_tracks if 'id' in track]
                    playlist_url = create_spotify_playlist(track_ids, playlist_name)
                    if playlist_url:
                        st.success(f"Playlist created! [Open in Spotify]({playlist_url})")
            else:
                st.info("Save some tracks first to create a playlist.")
        else:
            st.info("Switch to Spotify in the sidebar to create playlists.")
    
    # Following Tab
    with tabs[2]:
        st.markdown("<div class='section-header'>Artists You Follow</div>", unsafe_allow_html=True)
        
        if st.session_state.music_source == "Spotify":
            try:
                # Get followed artists
                followed_artists = sp.current_user_followed_artists(limit=10)
                
                if followed_artists and followed_artists['artists']['items']:
                    # Display artists in a grid
                    cols = st.columns(3)
                    for i, artist in enumerate(followed_artists['artists']['items']):
                        with cols[i % 3]:
                            # Get artist image
                            image_url = artist['images'][0]['url'] if artist['images'] else "https://via.placeholder.com/150"
                            
                            st.image(image_url, width=150)
                            st.markdown(f"**{artist['name']}**")
                            st.markdown(f"Followers: {artist['followers']['total']:,}")
                            
                            # Button to see top tracks
                            if st.button(f"Top Tracks", key=f"top_{artist['id']}"):
                                top_tracks = sp.artist_top_tracks(artist['id'])['tracks']
                                st.session_state.recommendations = top_tracks
                                st.rerun()
                else:
                    st.info("You're not following any artists on Spotify yet.")
            except Exception as e:
                st.error(f"Error fetching followed artists: {e}")
        else:
            st.info("Switch to Spotify to see artists you follow.")

# Preferences
elif "⚙️ Preferences" in menu:
    st.markdown("<h1 class='main-header'>Your Preferences</h1>", unsafe_allow_html=True)
    
    tabs = st.tabs(["Music Preferences", "App Settings", "About"])
    
    # Music Preferences Tab
    with tabs[0]:
        st.markdown("<div class='section-header'>Music Preferences</div>", unsafe_allow_html=True)
        
        # Genre preferences
        st.markdown("### Favorite Genres")
        genres = [
            "Pop", "Rock", "Hip Hop", "Electronic", "Jazz", "Classical", 
            "R&B", "Country", "Folk", "Metal", "Indie", "Ambient"
        ]
        
        selected_genres = st.multiselect(
            "Select your favorite genres:", 
            genres, 
            default=st.session_state.user_preferences.get("genres", [])
        )
        
        # Energy and popularity preferences
        st.markdown("### Music Characteristics")
        col1, col2 = st.columns(2)
        
        with col1:
            energy = st.slider(
                "Energy Level", 
                0.0, 1.0, 
                st.session_state.user_preferences.get("energy", 0.5),
                help="How energetic do you want your music recommendations to be?"
            )
        
        with col2:
            popularity = st.slider(
                "Popularity", 
                0, 100, 
                st.session_state.user_preferences.get("popularity", 50),
                help="Do you prefer mainstream hits or more obscure tracks?"
            )
        
        # Mood preferences
        st.markdown("### Mood")
        mood = st.text_area(
            "Describe your preferred mood or vibe:", 
            st.session_state.user_preferences.get("mood", ""),
            help="Example: 'uplifting and energetic' or 'chill and relaxing'"
        )
        
        # Save preferences
        if st.button("Save Preferences"):
            st.session_state.user_preferences = {
                "genres": selected_genres,
                "energy": energy,
                "popularity": popularity,
                "mood": mood
            }
            st.success("Preferences saved! Your recommendations will be updated accordingly.")
    
    # App Settings Tab
    with tabs[1]:
        st.markdown("<div class='section-header'>App Settings</div>", unsafe_allow_html=True)
        
        # Default location
        st.markdown("### Default Location for Concerts")
        default_location = st.text_input(
            "Enter your city:", 
            st.session_state.location
        )
        
        # Default music source
        st.markdown("### Default Music Source")
        default_source = st.radio(
            "Select your preferred music source:",
            ["Spotify", "YouTube Music"],
            index=0 if st.session_state.music_source == "Spotify" else 1
        )
        
        # Save settings
        if st.button("Save Settings"):
            st.session_state.location = default_location
            st.session_state.music_source = default_source
            st.success("Settings saved!")
    
    # About Tab
    with tabs[2]:
        st.markdown("<div class='section-header'>About Sparks Music Explorer</div>", unsafe_allow_html=True)
        
        st.markdown("""
        ### Sparks Music Explorer
        
        Sparks is an AI-powered music discovery and live show explorer app that helps you:
        
        - Discover new music based on your preferences
        - Find live shows in your area
        - Create and manage playlists
        - Explore music across different platforms
        
        #### Features
        
        - **Spotify Integration**: Access your top tracks, create playlists, and get personalized recommendations
        - **YouTube Music Integration**: Find and play tracks from YouTube Music
        - **Live Show Discovery**: Find concerts and events in your area using Songkick
        - **Personalized Recommendations**: Get music recommendations based on your preferences
        
        #### How to Use
        
        1. Navigate using the sidebar menu
        2. Explore your top tracks and save the ones you like
        3. Get personalized recommendations based on your music taste
        4. Find live shows in your area
        5. Create playlists from your saved tracks
        
        #### Credits
        
        Built with Streamlit, Spotify API, YouTube Music API, and Songkick API.
        """)
