import os
import asyncio
import logging
from pyrogram import Client, filters
from pyrogram.types import Message
import yt_dlp
from keep_alive import keep_alive

# Start keep-alive server
keep_alive()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
API_ID = int(os.getenv("API_ID", "32819831"))
API_HASH = os.getenv("API_HASH", "78c8247d43646a5cfb7199f54cd25ffc")
BOT_TOKEN = os.getenv("BOT_TOKEN", "7798631552:AAF0hhd1jJccWOa0hIUh-yZfweVu0EaxsQg")

# Initialize Pyrogram client
app = Client(
    "music_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# Store for music queues
music_queues = {}

class MusicPlayer:
    def __init__(self, chat_id):
        self.chat_id = chat_id
        self.queue = []
        self.is_playing = False
        self.current_song = None

    def add_to_queue(self, song_info):
        self.queue.append(song_info)
        return len(self.queue)

    def get_next_song(self):
        if self.queue:
            self.current_song = self.queue.pop(0)
            return self.current_song
        self.current_song = None
        return None

    def clear_queue(self):
        self.queue.clear()
        self.current_song = None
        self.is_playing = False

def get_music_player(chat_id):
    if chat_id not in music_queues:
        music_queues[chat_id] = MusicPlayer(chat_id)
    return music_queues[chat_id]

def search_youtube(query):
    try:
        ydl_opts = {
            'format': 'bestaudio/best',
            'quiet': True,
            'no_warnings': True,
            'default_search': 'ytsearch',
            'noplaylist': True
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch:{query}", download=False)
            if 'entries' in info and info['entries']:
                return info['entries'][0]
        return None
    except Exception as e:
        logger.error(f"Error searching YouTube: {e}")
        return None

def get_audio_url(video_info):
    try:
        formats = video_info.get('formats', [])
        audio_formats = [f for f in formats if f.get('acodec') != 'none' and f.get('vcodec') == 'none']
        
        if audio_formats:
            opus_format = next((f for f in audio_formats if f.get('ext') == 'webm'), None)
            if opus_format:
                return opus_format['url']
            return audio_formats[0]['url']
        
        for fmt in formats:
            if fmt.get('acodec') != 'none':
                return fmt['url']
                
        return None
    except Exception as e:
        logger.error(f"Error getting audio URL: {e}")
        return None

@app.on_message(filters.command("start"))
async def start_command(client, message: Message):
    await message.reply_text(
        "🎵 **Music Bot Started!**\n\n"
        "Available commands:\n"
        "• `/play <song name>` - Play music\n"
        "• `/skip` - Skip current song\n"
        "• `/stop` - Stop music\n"
        "• `/queue` - Show current queue\n"
        "• `/help` - Show help message"
    )

@app.on_message(filters.command("help"))
async def help_command(client, message: Message):
    await message.reply_text(
        "🎵 **Music Bot Help**\n\n"
        "**Commands:**\n"
        "• `/play <song name>` - Search and play music\n"
        "• `/skip` - Skip to next song\n"
        "• `/stop` - Stop music and clear queue\n"
        "• `/queue` - Show music queue\n"
        "• `/clear` - Clear queue\n\n"
        "**Usage:**\n"
        "Use `/play` followed by song name!"
    )

@app.on_message(filters.command("play"))
async def play_music(client, message: Message):
    try:
        if len(message.command) < 2:
            await message.reply_text("❌ Please provide a song name. Usage: `/play <song name>`")
            return

        query = " ".join(message.command[1:])
        chat_id = message.chat.id
        
        await message.reply_text(f"🔍 Searching for: `{query}`...")

        video_info = search_youtube(query)
        if not video_info:
            await message.reply_text("❌ No results found. Try a different search term.")
            return

        player = get_music_player(chat_id)
        
        song_info = {
            'title': video_info.get('title', 'Unknown Title'),
            'duration': video_info.get('duration', 0),
            'url': get_audio_url(video_info),
            'thumbnail': video_info.get('thumbnail'),
            'requested_by': message.from_user.first_name if message.from_user else "Unknown"
        }

        if not song_info['url']:
            await message.reply_text("❌ Could not get audio stream. Try another song.")
            return

        position = player.add_to_queue(song_info)
        
        duration = f"{song_info['duration']//60}:{song_info['duration']%60:02d}" if song_info['duration'] else "Unknown"
        
        response_text = (
            f"🎵 **Added to Queue**\n\n"
            f"**Title:** {song_info['title']}\n"
            f"**Duration:** {duration}\n"
            f"**Requested by:** {song_info['requested_by']}\n"
            f"**Position in queue:** #{position}"
        )
        
        if song_info['thumbnail']:
            try:
                await message.reply_photo(
                    photo=song_info['thumbnail'],
                    caption=response_text
                )
                return
            except Exception:
                pass
        
        await message.reply_text(response_text)
        
        if not player.is_playing:
            await play_next_song(client, chat_id)

    except Exception as e:
        logger.error(f"Error in play_music: {e}")
        await message.reply_text("❌ An error occurred while processing your request.")

async def play_next_song(client, chat_id):
    player = get_music_player(chat_id)
    
    if player.is_playing:
        return
        
    next_song = player.get_next_song()
    if not next_song:
        player.is_playing = False
        return
    
    player.is_playing = True
    
    try:
        duration = f"{next_song['duration']//60}:{next_song['duration']%60:02d}" if next_song['duration'] else "Unknown"
        
        now_playing_text = (
            f"🎶 **Now Playing**\n\n"
            f"**Title:** {next_song['title']}\n"
            f"**Duration:** {duration}\n"
            f"**Requested by:** {next_song['requested_by']}"
        )
        
        try:
            if next_song['thumbnail']:
                await client.send_photo(
                    chat_id=chat_id,
                    photo=next_song['thumbnail'],
                    caption=now_playing_text
                )
            else:
                await client.send_message(chat_id, now_playing_text)
        except Exception:
            await client.send_message(chat_id, now_playing_text)
        
        # Simulate playing
        if next_song['duration']:
            await asyncio.sleep(min(next_song['duration'], 30))
        
        player.is_playing = False
        await play_next_song(client, chat_id)
        
    except Exception as e:
        logger.error(f"Error playing next song: {e}")
        player.is_playing = False
        await client.send_message(chat_id, "❌ Error playing song. Moving to next...")
        await play_next_song(client, chat_id)

@app.on_message(filters.command("skip"))
async def skip_song(client, message: Message):
    chat_id = message.chat.id
    player = get_music_player(chat_id)
    
    if not player.is_playing and not player.queue:
        await message.reply_text("❌ No music is currently playing.")
        return
    
    player.is_playing = False
    await message.reply_text("⏭️ Skipped current song.")
    await play_next_song(client, chat_id)

@app.on_message(filters.command("stop"))
async def stop_music(client, message: Message):
    chat_id = message.chat.id
    player = get_music_player(chat_id)
    
    player.clear_queue()
    await message.reply_text("⏹️ Music stopped and queue cleared.")

@app.on_message(filters.command("queue"))
async def show_queue(client, message: Message):
    chat_id = message.chat.id
    player = get_music_player(chat_id)
    
    if not player.queue and not player.current_song:
        await message.reply_text("📭 Queue is empty.")
        return
    
    queue_text = "🎵 **Music Queue**\n\n"
    
    if player.current_song:
        queue_text += f"**Now Playing:** {player.current_song['title']}\n\n"
    
    if player.queue:
        queue_text += "**Up Next:**\n"
        for i, song in enumerate(player.queue[:10], 1):
            duration = f"{song['duration']//60}:{song['duration']%60:02d}" if song['duration'] else "Unknown"
            queue_text += f"{i}. {song['title']} ({duration})\n"
        
        if len(player.queue) > 10:
            queue_text += f"\n...and {len(player.queue) - 10} more songs"
    else:
        queue_text += "No songs in queue"
    
    await message.reply_text(queue_text)

@app.on_message(filters.command("clear"))
async def clear_queue(client, message: Message):
    chat_id = message.chat.id
    player = get_music_player(chat_id)
    
    queue_count = len(player.queue)
    player.queue.clear()
    
    await message.reply_text(f"🧹 Cleared {queue_count} songs from queue.")

async def main():
    await app.start()
    logger.info("Music Bot Started Successfully!")
    print("🎵 Music Bot is running on Render!")
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())