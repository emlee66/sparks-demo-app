import streamlit as st
from datetime import date
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import urllib.parse

# --- Spotify Setup ---
SPOTIFY_CLIENT_ID = "ba6fec516d7140da92612f005a3e478c"
SPOTIFY_CLIENT_SECRET = "fbb9d547989c4eba99ce32346496fc68"
SPOTIFY_REDIRECT_URI = "http://127.0.0.1:8888/callback"

sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
    client_id=SPOTIFY_CLIENT_ID,
    client_secret=SPOTIFY_CLIENT_SECRET,
    redirect_uri=SPOTIFY_REDIRECT_URI,
    scope="user-library-read user-top-read"
))

# --- App Layout ---
st.set_page_config(page_title="Sparks: Music Discovery & Live", layout="centered")
st.title("🎵 Sparks: Music Discovery")

menu = st.sidebar.radio("Navigate", ["Home Playlist", "Live Shows in DC", "Feedback"])

# --- Home Playlist ---
if menu == "Home Playlist":
    st.subheader("🎶 Your Spotify Top Tracks")

    if 'track_list' not in st.session_state:
        st.session_state.track_list = sp.current_user_top_tracks(limit=10)['items']
        st.session_state.current_index = 0

    track_list = st.session_state.track_list
    index = st.session_state.current_index

    if track_list:
        current_track = track_list[index]
        track_name = current_track['name']
        artist_name = current_track['artists'][0]['name']

        st.markdown(f"### Now Playing: {track_name} — {artist_name}")

        # YouTube embed search query
        query = urllib.parse.quote(f"{track_name} {artist_name}")
        youtube_embed_url = f"https://www.youtube.com/embed?listType=search&list={query}"

        st.components.v1.iframe(youtube_embed_url, height=315)

        st.text_input("Describe this track in a few words:", key="feedback_text")
        st.radio("Your reaction:", ["🌟 Feels fresh", "🧠 Love it", "😕 Too polished", "🔎 Intriguing but unsure"], key="reaction")

        if st.button("Next Track"):
            if index < len(track_list) - 1:
                st.session_state.current_index += 1
            else:
                st.session_state.current_index = 0  # Loop to beginning
    else:
        st.write("No top tracks found. Make sure your Spotify account has listening history.")

# --- Live Shows ---
elif menu == "Live Shows in DC":
    st.subheader("🎭 Upcoming Concerts in DC")
    events = [
        {"artist": "Fred again..", "venue": "9:30 Club", "date": date(2025, 6, 14)},
        {"artist": "Paul Kalkbrenner", "venue": "Echostage", "date": date(2025, 7, 2)},
        {"artist": "Ben Böhmer", "venue": "Flash", "date": date(2025, 6, 30)},
    ]
    for event in events:
        st.markdown(f"**{event['artist']}** at *{event['venue']}* on {event['date'].strftime('%b %d, %Y')}")
        st.button(f"Listen to {event['artist']} playlist")

# --- Feedback Tab ---
elif menu == "Feedback":
    st.subheader("🔍 Refine Your Sound")
    st.write("Describe what you're looking for more of:")
    mood = st.text_area("What kind of sound grabs you lately? (e.g., gritty, raw, uplifting, hypnotic)")
    if st.button("Submit Preferences"):
        st.success("Thanks! We'll use this to improve your next playlist.")