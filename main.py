import os
import tweepy
import time
import json
import threading
from flask import Flask
from datetime import datetime
from dotenv import load_dotenv

# --- Load environment variables ---
load_dotenv()

# --- Flask Web Server (For Render) ---
app = Flask(__name__)

@app.route("/")
def home():
    return "Repost Bot is Running!"

# --- Configuration ---
CONFIG = {
    "check_interval": 1800,  # 30 minutes
    "target_users": ["@EgoDriv", "@DejaRu22", "@DentesLeo"],
    "post_to": "@BotMusashi_",
    "max_tweets_per_check": 15,
    "delay_between_posts": 900,
    "storage_file": "reposted_ids.json"
}

# --- Twitter API Authentication ---
auth = tweepy.OAuth1UserHandler(
    consumer_key=os.getenv("API_KEY"),
    consumer_secret=os.getenv("API_SECRET"),
    access_token=os.getenv("ACCESS_TOKEN"),
    access_token_secret=os.getenv("ACCESS_TOKEN_SECRET")  # Keeping same secret name
)
api = tweepy.API(auth)

CLIENT = tweepy.Client(
    consumer_key=os.getenv("API_KEY"),
    consumer_secret=os.getenv("API_SECRET"),
    access_token=os.getenv("ACCESS_TOKEN"),
    access_token_secret=os.getenv("ACCESS_TOKEN_SECRET")  # Keeping same secret name
)

def load_reposted_ids():
    try:
        with open(CONFIG['storage_file'], 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {"users": {}}

def save_reposted_ids(data):
    with open(CONFIG['storage_file'], 'w') as f:
        json.dump(data, f)

def get_new_tweets(username):
    try:
        username = username.lstrip('@')
        user = CLIENT.get_user(username=username)
        if not user.data:
            raise ValueError(f"User @{username} not found")

        user_id = user.data.id
        tweets = CLIENT.get_users_tweets(
            id=user_id,
            exclude=["retweets", "replies"],
            max_results=CONFIG['max_tweets_per_check'],
            tweet_fields=["created_at"]
        )
        return tweets.data or []

    except tweepy.errors.Unauthorized:
        print("Unauthorized: Check API credentials")
        return []
    except Exception as e:
        print(f"Error fetching tweets: {str(e)}")
        return []

def create_repost_text(tweet, username):
    return (
        f"Reposting from @{username}:\n\n"
        f"{tweet.text}\n\n"
        f"Original Post: https://twitter.com/{username}/status/{tweet.id}"
    )

def repost_bot():
    reposted = load_reposted_ids()

    while True:
        try:
            for user in CONFIG['target_users']:
                username = user.lstrip('@')
                new_tweets = get_new_tweets(username)

                if not new_tweets:
                    continue

                for tweet in reversed(new_tweets):
                    if str(tweet.id) not in reposted.get('users', {}).get(username, []):
                        try:
                            repost_text = create_repost_text(tweet, username)
                            CLIENT.create_tweet(text=repost_text)
                            print(f"Reposted {tweet.id} from @{username} to {CONFIG['post_to']}")

                            reposted.setdefault('users', {}).setdefault(username, []).append(str(tweet.id))
                            save_reposted_ids(reposted)

                            time.sleep(CONFIG['delay_between_posts'])  # Wait before reposting next
                        except tweepy.TooManyRequests:
                            print("Rate limit hit. Waiting 15 minutes.")
                            time.sleep(900)
                            continue

            print(f"Sleeping for {CONFIG['check_interval']//60} minutes...")
            time.sleep(CONFIG['check_interval'])

        except KeyboardInterrupt:
            print("Bot stopped safely.")
            break

# --- Start Flask & Bot in Separate Threads ---
if __name__ == "__main__":
    threading.Thread(target=repost_bot, daemon=True).start()
    app.run(host="0.0.0.0", port=8080)                            
