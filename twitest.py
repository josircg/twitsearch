import tweepy

from core.models import Tweet, TweetUser

auth = tweepy.OAuthHandler(consumer_key='f8zhOblkBUPOHd5QfvsHR3Nw7',
                           consumer_secret='gxgvNEYy6ZlV7JsAwztEeOIeFgjXNjC9RjZsQWbN44qjYfDnFo')
auth.set_access_token('16040246-FoaJx9DS3xIf1X7OSCw5KitsXMqn0VO9T8QJVgctg',
                      'W7bdNyHBNEp8rK4FJX8L9PDn4f8cFct4gEpu0KoDMUgYu')
api = tweepy.API(auth)

public_tweets = api.home_timeline()
for tweet in public_tweets:
    print(tweet.text)
    Tweet.objects.create(text=)

#search = api.GetSearch("divulgação científica")
#for tweet in search:
#    print(tweet.id, tweet.user.name, tweet.text)
