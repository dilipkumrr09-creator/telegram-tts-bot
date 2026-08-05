import os
import asyncio
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)
import edge_tts
from pydub import AudioSegment

# Bot Token (Aapka token yahan set kar diya hai)
BOT_TOKEN = "8691941161:AAH6z9bE12_Z5UYAEFno0EvigP9rRXTWmDo"

# In-Memory Storage for User Settings
user_settings = {}

# Popular Voices List
VOICES = {
    "hi_female": ("hi-IN-SwaraNeural", "🇮🇳 Hindi (Female)"),
    "hi_male": ("hi-IN-MadhurNeural", "🇮🇳 Hindi (Male)"),
    "en_female": ("en-US-AriaNeural", "🇺🇸 English (Female)"),
    "en_male": ("en-US-GuyNeural", "🇺🇸 English (Male)"),
    "en_uk_female": ("en-GB-SoniaNeural", "🇬🇧 British (Female)"),
}

DEFAULT_VOICE = "hi-IN-SwaraNeural"
DEFAULT_RATE = "+0%"
DEFAULT_PITCH = "+0Hz"
DEFAULT_VOLUME = "+0dB"

def get_user_config(user_id):
    if user_id not in user_settings:
        user_settings[user_id] = {
            "voice": DEFAULT_VOICE,
            "rate": DEFAULT_RATE,
            "pitch": DEFAULT_PITCH,
            "volume": DEFAULT_VOLUME
        }
    return user_settings[user_id]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "👋 **Welcome to Advanced TTS Bot!**\n\n"
        "Bhejo mujhe koi bhi lamba text, aur main use professional Voice Note (Audio) me convert kar dunga.\n\n"
        "⚙️ **Features:**\n"
        "• Unlimited text chunking support\n"
        "• Multiple voices & accents\n"
        "• Custom Speed, Pitch & Volume settings\n\n"
        "Apni settings change karne ke liye /settings command use karein."
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")

async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    config = get_user_config(user_id)
    
    keyboard = [
        [InlineKeyboardButton("🗣️ Change Voice", callback_data="menu_voice")],
        [
            InlineKeyboardButton("⚡ Speed", callback_data="menu_rate"),
            InlineKeyboardButton("🎵 Pitch", callback_data="menu_pitch"),
        ],
        [InlineKeyboardButton("🔊 Volume", callback_data="menu_volume")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = (
        f"⚙️ **Your Current Settings:**\n"
        f"• Voice: `{config['voice']}`\n"
        f"• Speed: `{config['rate']}`\n"
        f"• Pitch: `{config['pitch']}`\n"
        f"• Volume: `{config['volume']}`"
    )
    await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id
    config = get_user_config(user_id)

    if data == "menu_voice":
        keyboard = []
        for key, (v_id, v_name) in VOICES.items():
            keyboard.append([InlineKeyboardButton(v_name, callback_data=f"set_voice_{v_id}")])
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="menu_main")])
        await query.edit_message_text("🗣️ Select Voice:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("set_voice_"):
        new_voice = data.replace("set_voice_", "")
        config["voice"] = new_voice
        await query.edit_message_text(f"✅ Voice updated successfully to `{new_voice}`!", parse_mode="Markdown")

    elif data == "menu_main":
        keyboard = [
            [InlineKeyboardButton("🗣️ Change Voice", callback_data="menu_voice")],
            [
                InlineKeyboardButton("⚡ Speed", callback_data="menu_rate"),
                InlineKeyboardButton("🎵 Pitch", callback_data="menu_pitch"),
            ],
            [InlineKeyboardButton("🔊 Volume", callback_data="menu_volume")],
        ]
        text = (
            f"⚙️ **Your Current Settings:**\n"
            f"• Voice: `{config['voice']}`\n"
            f"• Speed: `{config['rate']}`\n"
            f"• Pitch: `{config['pitch']}`\n"
            f"• Volume: `{config['volume']}`"
        )
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

def split_text(text, max_length=3500):
    paragraphs = text.split("\n")
    chunks = []
    current_chunk = ""
    for p in paragraphs:
        if len(current_chunk) + len(p) + 1 < max_length:
            current_chunk += p + "\n"
        else:
            if current_chunk:
                chunks.append(current_chunk)
            current_chunk = p + "\n"
    if current_chunk:
        chunks.append(current_chunk)
    return chunks

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if not text:
        return

    user_id = update.effective_user.id
    config = get_user_config(user_id)

    status_msg = await update.message.reply_text("⏳ Processing text and generating audio...")

    try:
        chunks = split_text(text)
        audio_segments = []
        temp_files = []

        for i, chunk in enumerate(chunks):
            if not chunk.strip():
                continue
            temp_filename = f"temp_{user_id}_{i}.mp3"
            temp_files.append(temp_filename)
            
            communicate = edge_tts.Communicate(
                text=chunk,
                voice=config["voice"],
                rate=config["rate"],
                pitch=config["pitch"],
                volume=config["volume"]
            )
            await communicate.save(temp_filename)
            audio_segments.append(AudioSegment.from_mp3(temp_filename))

        if not audio_segments:
            await status_msg.edit_text("❌ No valid text found to convert.")
            return

        combined_audio = audio_segments[0]
        for segment in audio_segments[1:]:
            combined_audio += segment

        final_filename = f"output_{user_id}.mp3"
        combined_audio.export(final_filename, format="mp3")

        with open(final_filename, "rb") as audio_file:
            await update.message.reply_voice(voice=audio_file)

        await status_msg.delete()

        # Cleanup
        for f in temp_files:
            if os.path.exists(f):
                os.remove(f)
        if os.path.exists(final_filename):
            os.remove(final_filename)

    except Exception as e:
        await status_msg.edit_text(f"❌ Error occurred: {str(e)}")

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("settings", settings_command))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text))

    print("🤖 Bot is up and running...")
    app.run_polling()

if __name__ == "__main__":
    main()
    
