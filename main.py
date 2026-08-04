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

# Bot Token (Yahan apna BotFather ka Token daalo)
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN_HERE")

# In-Memory Storage for User Settings
user_settings = {}

# Popular Voices List
VOICES = {
    "hi_female": ("hi-IN-SwaraNeural", "🇮🇳 Hindi Female (Swara)"),
    "hi_male": ("hi-IN-MadhurNeural", "🇮🇳 Hindi Male (Madhur)"),
    "en_us_female": ("en-US-AnaNeural", "🇺🇸 English Female (Ana)"),
    "en_us_male": ("en-US-GuyNeural", "🇺🇸 English Male (Guy)"),
    "en_uk_female": ("en-GB-SoniaNeural", "🇬🇧 English Female (Sonia)"),
    "ur_male": ("ur-PK-AsadNeural", "🇵🇰 Urdu Male (Asad)"),
}

def get_user_config(chat_id):
    if chat_id not in user_settings:
        user_settings[chat_id] = {
            "voice": "hi-IN-SwaraNeural",
            "rate": "+0%",
            "pitch": "+0Hz",
        }
    return user_settings[chat_id]

def split_text(text, max_length=1000):
    sentences = re.split(r'(?<=[.!?\n]) +', text)
    chunks = []
    current_chunk = ""
    for sentence in sentences:
        if len(current_chunk) + len(sentence) <= max_length:
            current_chunk += sentence + " "
        else:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = sentence + " "
    if current_chunk:
        chunks.append(current_chunk.strip())
    return chunks

async def generate_chunk_audio(text_chunk, output_file, voice, rate, pitch):
    communicate = edge_tts.Communicate(
        text=text_chunk,
        voice=voice,
        rate=rate,
        pitch=pitch,
    )
    await communicate.save(output_file)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 **Welcome to Text to Speech Bot!**\n\n"
        "1. Mujhe koi bhi kitna bhi bada text bhejo, main audio bana dunga.\n"
        "2. Voice/Speed/Pitch change karne ke liye `/settings` command use karo.",
        parse_mode="Markdown"
    )

async def settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    config = get_user_config(chat_id)
    
    text = (
        f"⚙️ **Current Settings:**\n\n"
        f"🎙 **Voice:** `{config['voice']}`\n"
        f"⚡ **Speed:** `{config['rate']}`\n"
        f"🎵 **Pitch:** `{config['pitch']}`"
    )
    
    keyboard = [
        [InlineKeyboardButton("🎙 Change Voice", callback_data="menu_voice")],
        [InlineKeyboardButton("⚡ Change Speed", callback_data="menu_speed")],
        [InlineKeyboardButton("🎵 Change Pitch", callback_data="menu_pitch")],
    ]
    
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    config = get_user_config(chat_id)
    data = query.data

    if data == "menu_voice":
        keyboard = [[InlineKeyboardButton(name, callback_data=f"set_v_{code}")] for code, (v_id, name) in VOICES.items()]
        await query.edit_message_text("🎙 **Select Voice:**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data == "menu_speed":
        keyboard = [
            [
                InlineKeyboardButton("0.75x", callback_data="set_s_-25%"),
                InlineKeyboardButton("1.0x (Normal)", callback_data="set_s_+0%"),
                InlineKeyboardButton("1.25x", callback_data="set_s_+25%"),
                InlineKeyboardButton("1.5x", callback_data="set_s_+50%"),
            ]
        ]
        await query.edit_message_text("⚡ **Select Speed:**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data == "menu_pitch":
        keyboard = [
            [
                InlineKeyboardButton("Low (-10Hz)", callback_data="set_p_-10Hz"),
                InlineKeyboardButton("Normal (0Hz)", callback_data="set_p_+0Hz"),
                InlineKeyboardButton("High (+10Hz)", callback_data="set_p_+10Hz"),
            ]
        ]
        await query.edit_message_text("🎵 **Select Pitch:**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data.startswith("set_v_"):
        key = data.replace("set_v_", "")
        config["voice"] = VOICES[key][0]
        await query.edit_message_text(f"✅ Voice updated to: `{VOICES[key][1]}`", parse_mode="Markdown")

    elif data.startswith("set_s_"):
        config["rate"] = data.replace("set_s_", "")
        await query.edit_message_text(f"✅ Speed updated to: `{config['rate']}`", parse_mode="Markdown")

    elif data.startswith("set_p_"):
        config["pitch"] = data.replace("set_p_", "")
        await query.edit_message_text(f"✅ Pitch updated to: `{config['pitch']}`", parse_mode="Markdown")

async def handle_tts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    user_text = update.message.text
    config = get_user_config(chat_id)

    status_msg = await update.message.reply_text("⏳ Processing audio...")
    chunks = split_text(user_text)
    temp_files = []

    try:
        for i, chunk in enumerate(chunks):
            temp_file = f"temp_{chat_id}_{i}.mp3"
            await generate_chunk_audio(chunk, temp_file, config["voice"], config["rate"], config["pitch"])
            temp_files.append(temp_file)

        combined = AudioSegment.empty()
        for file in temp_files:
            combined += AudioSegment.from_file(file)

        final_output = f"final_{chat_id}.mp3"
        combined.export(final_output, format="mp3")

        await status_msg.edit_text("📤 Uploading audio...")
        with open(final_output, "rb") as audio:
            await update.message.reply_audio(audio=audio, title="Generated Speech")

        for file in temp_files:
            if os.path.exists(file):
                os.remove(file)
        if os.path.exists(final_output):
            os.remove(final_output)

        await status_msg.delete()

    except Exception as e:
        await status_msg.edit_text(f"❌ Error: {str(e)}")

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("settings", settings))
    app.add_handler(CallbackQueryHandler(button_click))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_tts))

    print("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
  
