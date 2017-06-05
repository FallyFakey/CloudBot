import re
import random
from datetime import datetime

import tweepy
from cloudbot import hook

from cloudbot.util import timeformat


TWITTER_RE = re.compile(r"(?:(?:www.twitter.com|twitter.com)/(?:[-_a-zA-Z0-9]+)/status/)([0-9]+)", re.I)
TCO_RE = re.compile(r"https?://t\.co/\w+", re.I)


@hook.on_start()
def load_api(bot):
    global tw_api

    consumer_key = bot.config.get("api_keys", {}).get("twitter_consumer_key", None)
    consumer_secret = bot.config.get("api_keys", {}).get("twitter_consumer_secret", None)

    oauth_token = bot.config.get("api_keys", {}).get("twitter_access_token", None)
    oauth_secret = bot.config.get("api_keys", {}).get("twitter_access_secret", None)

    if not all((consumer_key, consumer_secret, oauth_token, oauth_secret)):
        tw_api = None
        return
    else:
        auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
        auth.set_access_token(oauth_token, oauth_secret)

        tw_api = tweepy.API(auth)


def format_tweet(tweet):
    user = tweet.user

    # Format the return the text of the tweet
    text = " ".join(tweet.text.split())

    urls = {}
    if tweet.entities.get("urls"):
        for item in tweet.entities["urls"]:
            urls[item["url"]] = item["expanded_url"]

    if "extended_entities" in tweet._json:
        for item in tweet._json["extended_entities"]["media"]:
            # check for video, use mp4
            if "video_info" in item:
                urls[item["url"]] = item["video_info"]["variants"][0]["url"]
                continue
            urls[item["url"]] = item["media_url_https"]

    # First link seems to be the media element
    while True:
        m = TCO_RE.search(text)
        if not m:
            break
        if m.group() not in urls:
            # This is the t.co url for the tweet. remove this
            text = TCO_RE.sub("", text, count=1)
            continue
        text = TCO_RE.sub(urls[m.group()], text, count=1)

    verified = "\u2713" if user.verified else ""

    time = timeformat.time_since(tweet.created_at, datetime.utcnow(), simple=True)

    return "{} ({}@{}) [div] {} ago [div] {}".format(user.name, verified, user.screen_name, time, text.strip())


@hook.regex(TWITTER_RE)
def twitter_url(match):
    # Find the tweet ID from the URL
    tweet_id = match.group(1)

    # Get the tweet using the tweepy API
    if tw_api is None:
        return

    try:
        tweet = tw_api.get_status(tweet_id)
    except tweepy.error.TweepError:
        return

    return format_tweet(tweet)


@hook.command("twitter", "tw", "twatter")
def twitter(text):
    """twitter <user> [n] -- Gets last/[n]th tweet from <user>"""

    if tw_api is None:
        return "This command requires a twitter API key."

    if re.match(r'^\d+$', text):
        # user is getting a tweet by id

        try:
            # get tweet by id
            tweet = tw_api.get_status(text)
        except tweepy.error.TweepError as e:
            if "404" in e.reason:
                return "Could not find tweet."
            else:
                return "Error: {}".format(e.reason)

    elif re.match(r'^\w{1,15}$', text) or re.match(r'^\w{1,15}\s+\d+$', text):
        # user is getting a tweet by name

        if text.find(' ') == -1:
            username = text
            tweet_number = 0
        else:
            username, tweet_number = text.split()
            tweet_number = int(tweet_number) - 1

        if tweet_number > 200:
            return "This command can only find the last \x02200\x02 tweets."

        try:
            # try to get user by username
            user = tw_api.get_user(username)
        except tweepy.error.TweepError as e:
            if "404" in e.reason:
                return "Could not find user."
            else:
                return "Error: {}".format(e.reason)

        # get the users tweets
        user_timeline = tw_api.user_timeline(id=user.id, count=tweet_number + 1)

        # if the timeline is empty, return an error
        if not user_timeline:
            return "@{} has no tweets.".format(user.screen_name)

        # grab the newest tweet from the users timeline
        try:
            tweet = user_timeline[tweet_number]
        except IndexError:
            tweet_count = len(user_timeline)
            return "@{} only has {} tweets.".format(user.screen_name, tweet_count)

    elif re.match(r'^#\w+$', text):
        # user is searching by hashtag
        search = tw_api.search(text)

        if not search:
            return "No tweets found."

        tweet = random.choice(search)
    else:
        # ???
        return "Invalid Input"

    return format_tweet(tweet)


@hook.command("twuser", "twinfo")
def twuser(text):
    """twuser <user> -- Get info on the Twitter user <user>"""

    if tw_api is None:
        return

    try:
        # try to get user by username
        user = tw_api.get_user(text)
    except tweepy.error.TweepError as e:
        if "404" in e.reason:
            return "Could not find user."
        else:
            return "Error: {}".format(e.reason)

    
    verified = "\u2713" if user.verified else ""

    tf = lambda l, s: "[h1]{}:[/h1] {}".format(l, s)

    out = []
    if user.location:
        out.append(tf("Loc", user.location))
    if user.description:
        out.append(tf("Desc", user.description))
    if user.url:
        out.append(tf("URL", user.url))
    out.append(tf("Tweets", user.statuses_count))
    out.append(tf("Followers", user.followers_count))

    return "{}@{} ({}) [div] {}".format(verified, user.screen_name, user.name, " [div] ".join(out))

