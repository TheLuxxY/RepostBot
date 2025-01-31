import time
import tweepy
import json
import os
import threading
from flask import Flask
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("API_SECRET")
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
ACCESS_TOKEN_SECRET = os.getenv("ACCESS_TOKEN_SECRET")
BEARER_TOKEN = os.getenv("BEARER_TOKEN")
TARGET_USERS = os.getenv("TARGET_USERS").split(",")  # Comma-separated list of usernames
POST_TO = os.getenv("POST_TO")
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", 1800))  # Interval between each cycle in seconds

# Authenticate with Twitter
CLIENT = tweepy.Client(bearer_token=BEARER_TOKEN,
                       consumer_key=API_KEY,
                       consumer_secret=API_SECRET,
                       access_token=ACCESS_TOKEN,
                       access_token_secret=ACCESS_TOKEN_SECRET)

# Flask Web Server (For Render)
app = Flask(__name__)

@app.route("/")
def home():
    return "Repost Bot is Running!"

# Load reposted tweet IDs
def load_reposted_ids():
    try:
        with open("reposted.json", "r") as file:
            return json.load(file)
    except FileNotFoundError:
        return {}

# Save reposted tweet IDs
def save_reposted_ids(reposted):
    with open("reposted.json", "w") as file:
        json.dump(reposted, file, indent=4)

# Fetch new tweets for a user
def get_new_tweets(username):
    try:
        username = username.lstrip('@')
        user = CLIENT.get_user(username=username)
        if not user.data:
            raise ValueError(f"User @{username} not found")

        user_id = user.data.id
        tweets = CLIENT.get_users_tweets(id=user_id,
                                         exclude=["retweets", "replies"],
                                         max_results=5,
                                         tweet_fields=["created_at"])
        return tweets.data or []
    except tweepy.TooManyRequests as e:
        reset_time = int(e.response.headers.get("x-rate-limit-reset", time.time() + 900))
        sleep_time = reset_time - int(time.time())
        print(f"Rate limit hit. Sleeping for {sleep_time} seconds.")
        time.sleep(sleep_time)
        return []
    except Exception as e:
        print(f"Error fetching tweets for @{username}: {str(e)}")
        return []

# Create repost text with link to original post
def create_repost_text(tweet, username):
    tweet_url = f"https://twitter.com/{username}/status/{tweet.id}"
    return f"Reposting from @{username}:\n\n{tweet.text}\n\nOriginal Post: {tweet_url}"

# Main function
def bot_runner():
    reposted = load_reposted_ids()
    user_index = 0  # To track which user is next

    while True:
        try:
            username = TARGET_USERS[user_index].lstrip('@')
            print(f"Fetching tweets for @{username}...")

            new_tweets = get_new_tweets(username)
            if not new_tweets:
                print(f"No new tweets found for @{username}. Moving to the next user.")
            else:
                for tweet in new_tweets:
                    if str(tweet.id) not in reposted.get('users', {}).get(username, []):
                        try:
                            # Post to your account
                            repost_text = create_repost_text(tweet, username)
                            CLIENT.create_tweet(text=repost_text)
                            print(f"Reposted tweet {tweet.id} from @{username} to {POST_TO}")

                            # Track reposted tweets
                            reposted.setdefault('users', {}).setdefault(username, []).append(str(tweet.id))
                            save_reposted_ids(reposted)
                            break
                        except tweepy.TooManyRequests:
                            print("Rate limit hit. Waiting 15 minutes.")
                            time.sleep(900)
                            continue

            # Move to the next user in the cycle
            user_index = (user_index + 1) % len(TARGET_USERS)

            # Wait for the next cycle
            print(f"Waiting {CHECK_INTERVAL // 60} minutes before the next repost...")
            time.sleep(CHECK_INTERVAL)

        except KeyboardInterrupt:
            print("Bot stopped safely.")
            break
        except Exception as e:
            print(f"Unexpected error: {str(e)}")
            time.sleep(60)

# Start Flask and Bot in Separate Threads
if __name__ == "__main__":
    threading.Thread(target=bot_runner, daemon=True).start()
    app.run(host="0.0.0.0", port=8080)
