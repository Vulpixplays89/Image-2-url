import telebot
import requests
import os
import time
import pymongo
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from threading import Thread
from flask import Flask

# 🔑 Load credentials from environment variables (Set these before running)
TELEGRAM_BOT_TOKEN = os.getenv("BOT_TOKEN")
IMGBB_API_KEY = os.getenv("API_KEY")
MONGO_URI = os.getenv("DB_URL")

# ⚡ Connect to MongoDB
client = pymongo.MongoClient(MONGO_URI)
db = client["telegram_bot"]
users_collection = db["users"]

ADMIN_ID = 6897739611  # Your Telegram ID

bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)

app = Flask('')

@app.route('/')
def home():
    return "I am alive"

def run_http_server():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run_http_server)
    t.start()

@bot.message_handler(commands=['start'])
def start(message):
    chat_id = message.chat.id

    # 📌 Ensure only user ID is saved
    if not users_collection.find_one({"chat_id": chat_id}):
        users_collection.insert_one({"chat_id": chat_id})  # Only storing chat_id

    welcome_text = (
        "👋 **Welcome to Image Uploader Bot!**\n\n"
        "📷 Send me an **image**, and I'll upload it and provide a direct **Shareable link**. 🔗\n\n"
        "⚡ *Fast, Simple & Free!*\n\n"
        "🔽 **Owner Information:**"
    )

    markup = InlineKeyboardMarkup()
    markup.row_width = 2
    markup.add(
        InlineKeyboardButton("🛠 Developer", url="https://t.me/botplays90"),
        InlineKeyboardButton("📢 Join Channel", url="https://t.me/join_hyponet")
    )

    bot.send_message(chat_id, welcome_text, parse_mode="Markdown", reply_markup=markup)

@bot.message_handler(commands=['users'])
def list_users(message):
    if message.chat.id != ADMIN_ID:
        bot.send_message(message.chat.id, "⛔ You are not authorized to use this command.")
        return

    users = users_collection.find()
    user_list = "\n".join([str(user.get("chat_id", "Unknown")) for user in users])  # Handle missing chat_id

    if user_list:
        bot.send_message(ADMIN_ID, f"📋 **Registered Users:**\n{user_list}")
    else:
        bot.send_message(ADMIN_ID, "⚠ No users found.")


@bot.message_handler(commands=['broadcast'])
def broadcast(message):
    if message.chat.id != ADMIN_ID:
        bot.send_message(message.chat.id, "⛔ You are not authorized to use this command.")
        return

    text = message.text.replace("/broadcast", "").strip()
    if not text:
        bot.send_message(ADMIN_ID, "⚠ Please provide a message to broadcast.")
        return

    users = users_collection.find()
    sent_count = 0
    failed_count = 0

    for user in users:
        chat_id = user.get("chat_id")  # Ensure chat_id exists
        if chat_id:
            try:
                bot.send_message(chat_id, f"📢 **Broadcast:**\n{text}")
                sent_count += 1
            except Exception as e:
                print(f"❌ Failed to send message to {chat_id}: {e}")
                failed_count += 1

    bot.send_message(ADMIN_ID, f"✅ Broadcast sent to {sent_count} users. ❌ Failed: {failed_count}.")



@bot.message_handler(content_types=['photo'])
def handle_image(message):
    chat_id = message.chat.id
    bot.send_chat_action(chat_id, "upload_photo")

    try:
        # 🔍 Get highest quality image from user
        file_info = bot.get_file(message.photo[-1].file_id)
        file_url = f"https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}/{file_info.file_path}"

        # 📥 Download the image
        response = requests.get(file_url)
        if response.status_code == 200:
            with open("temp.jpg", "wb") as file:
                file.write(response.content)

            # 📤 Upload to ImgBB
            with open("temp.jpg", "rb") as file:
                upload_response = requests.post(
                    f"https://api.imgbb.com/1/upload?key={IMGBB_API_KEY}",
                    files={"image": file}
                )

            os.remove("temp.jpg")  # 🗑 Delete local file after upload

            # ✅ Check and send back the link
            if upload_response.status_code == 200:
                json_data = upload_response.json()
                if "data" in json_data and "url" in json_data["data"]:
                    img_url = json_data["data"]["url"]
                    bot.send_message(chat_id, f"✅ **Image Uploaded!**\n🔗 [Click Here to View]({img_url})", parse_mode="Markdown")
                else:
                    bot.send_message(chat_id, "❌ **Upload Failed!** No valid URL returned from ImgBB.")
            else:
                bot.send_message(chat_id, "❌ **Upload Failed!** ImgBB API error.")

        else:
            bot.send_message(chat_id, "❌ **Failed to download the image from Telegram.**")

    except Exception as e:
        bot.send_message(chat_id, f"⚠ **Error:** `{str(e)}`", parse_mode="Markdown")

keep_alive()

while True:
    try:
        print("🚀 Bot is running...")
        bot.polling(none_stop=True, interval=0.1, timeout=30)
    except Exception as e:
        print(f"⚠️ Bot crashed due to: {e}")
        time.sleep(5)  # Wait 5 seconds before restarting
