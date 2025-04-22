import streamlit as st
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import urllib.parse
from ytmusicapi import YTMusic

# --- Config ---
st.set_page_config(page_title="Sparks Minimal", layout="centered")

# --- Spotify Setup ---
SPOTIFY_CLIENT_ID = st.secrets["SPOTIFY_CLIENT_ID"]
SPOTIFY_CLIENT_SECRET = st.secrets["SPOTIFY_CLIENT_SECRET"]
SPOTIFY_REDIRECT_URI = "https://emlee66-sparks-demo-app.streamlit.app"

sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
    client_id=SPOTIFY_CLIENT_ID,
    client_secret=SPOTIFY_CLIENT_SECRET,
    redirect_uri=SPOTIFY_REDIRECT_URI,
    scope="user-library-read user-top-read",
    open_browser=False
))

ytmusic = YTMusic()

# --- App Title ---
st.title("🎧 Sparks: Music Discovery")

# --- Get Top Track ---
try:
    tracks = sp.current_user_top_tracks(limit=10)['items']
    if tracks:
        track = tracks[0]
        track_name = track['name']
        artist_name = track['artists'][0]['name']
        st.subheader(f"{track_name} — {artist_name}")

        # --- YouTube Playback ---
        def get_youtube_video_id(track_name, artist_name):
            try:
                query = f"{track_name} {artist_name}"
                results = ytmusic.search(query, filter="songs", limit=1)
                if results and 'videoId' in results[0]:
                    return results[0]['videoId']
            except:
                return None

        video_id = get_youtube_video_id(track_name, artist_name)
        if video_id:
            st.components.v1.iframe(f"https://www.youtube.com/embed/{video_id}", height=315)
        else:
            st.warning("No playable YouTube video found.")
    else:
        st.info("No top tracks found.")
except Exception as e:
    st.error(f"Error loading track: {e}")

# --- Feedback Box ---
st.markdown("### 💬 What do you think?")
st.text_input("Describe this track in a few words:")
st.radio("How does it feel?", ["🌟 Fresh", "🔥 Love it", "🤷‍♀️ Meh", "🔁 Familiar but good"])