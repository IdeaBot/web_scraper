from bs4 import BeautifulSoup
from libs import dataloader, plugin, embed
import time, logging, discord, traceback, sys, random
from addons.web_scraper.scraperlibs import pageRet

THRESHOLD = 'threshold'
CHANNEL = 'channel'
TWITTER_URL = r"https://twitter.com/AnIdeaHere"
TWITTER_PROFILE_ICON = r"https://pbs.twimg.com/profile_images/885416009062117378/Iin-FmpQ_400x400.jpg"
TWITTER_LOGO = r"https://pbs.twimg.com/profile_images/875087697177567232/Qfy0kRIP_400x400.jpg"

def tweetLogging():
    '''() -> Logger class
    set ups main log so that it outputs to ./scrapert.log and then returns the log'''
    logger = logging.getLogger('twitter-idea')
    logger.setLevel(logging.DEBUG)
    handler = logging.FileHandler(filename='scrapertidea.log', encoding='utf-8', mode='w')
    handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s: %(message)s'))
    logger.addHandler(handler)
    return logger

twitLog = tweetLogging()

class Plugin(plugin.ThreadedPlugin):
    '''Provides ideas when a channel goes a long time
without being spoken in. The length of time allowed to pass before an idea is
sent depends on the configuration file of Idea, but it is usually set to 24 hours

To learn how to enable/disable ideas in a channel, use
```@Idea help watcher```

**NOTE:** This used to scrape the @AnIdeaHere twitter account, which is banned, so **this plugin does not work** '''
    def __init__(self, **kwargs):
        super().__init__(should_spawn_thread=False, **kwargs)
        self.data = dataloader.loadfile_safe('potato.txt') #self.config["datafilepath"])
        self.author = self.get_author_from_url(self.config["url"])
        self.THRESHOLD = float(self.config[THRESHOLD])
        self.spawn_process()
        self.tweets = list()

    async def action(self):
        while not self.queue.empty():
            self.tweets.append(self.queue.get())
        if len(self.tweets)>0:
            for channel in self.public_namespace.last_messages_time:
                if time.time()-self.public_namespace.last_messages_time[channel] > self.THRESHOLD:
                    choice = random.randint(0, len(self.tweets)-1)
                    await self.send_message(discord.Object(id=channel), self.tweets[choice]['content'])
                    if len(self.tweets)!=1: # so channels after this will always have an idea to use
                        del(self.tweets[choice]) # reduce repeats

    def threaded_action(self, q, **kwargs):
        '''(ThreadedPlugin, Queue ) -> None
        Checks continuously for new tweets from the official twitter. A [url (str), tweet (str)] object is reported through q when anything changes
        This should be run in a different thread since it is blocking (it's a while loop ffs)
        stop.put(anything) will stop the loop'''

        twitLog.info("Starting scraping run")
        mostrecentrunstart = time.time()
        try:
            rss = BeautifulSoup(pageRet.pageRet(self.config["url"]).decode(), "html.parser") # rss page
            items = rss.find_all("item")
            #print(items)
            tweets = [[self.get_url(x), self.get_tweet(x), x] for x in items] # create list of [url to tweet, tweet content]
            pinned_tweet = tweets[0]
            tweets = tweets[1:] # remove first tweet since it's pinned

            if len(tweets)>1 and self.is_new_tweet(tweets[0][0]) and self.is_new_tweet(tweets[1][0], second=True):
                for i in tweets:
                    if self.is_new_tweet(i[0]):
                        twitLog.info("New tweet found: " + i[0])
                        tweet_author = self.get_author(i[2])
                        q_entry = {"url":i[0], "content":i[1], "author":tweet_author, "retweet":False}
                        if self.author != tweet_author:
                            q_entry["retweet"] = True
                        else: # NOTE: prevents retweets from being used as ideas - I wouldn't trust them to be ideas
                            q.put(q_entry)
                    else:
                        break
                self.delete_entry("most recent tweet:")
                self.data.content.append("most recent tweet:"+tweets[0][0])
                self.data.content.append("second most recent tweet:"+tweets[1][0])
                # self.data.save()
                twitLog.info("Most recent tweet is now: " + tweets[0][0])
                twitLog.info("Second most recent tweet is now: " + tweets[1][0])
            twitLog.info("Finished scraping run in "+ str(time.time() - mostrecentrunstart))
        except:
            # Prevent a failed run from crashing the whole thread
            twitLog.warning("Scraping run failed. Either the page has changed or the page is unavailable...")
            # traceback.print_exc()

    def get_tweet(self, bso):
        '''(BeautifulSoup object) -> str
        gets the text from title'''
        return bso.find("title").get_text()
    def get_url(self, bso):
        '''(BeautifulSoup object) -> str
        gets the text from guid'''
        return bso.find("guid").get_text()


    def is_new_tweet(self, url, second=False):
        '''(str [, bool]) -> bool
        returns True if the url is new, False otherwise'''
        is_new = True
        if len(self.data.content) > 0:
            for i in range(len(self.data.content)):
                if self.data.content[i][:len("Most Recent Tweet:")].lower() == "most recent tweet:" and not second: # if it's the file line about most recent thread
                    if url == self.data.content[i][len("Most Recent Tweet:"):len("Most Recent Tweet:")+len(url)]:
                        is_new = False
                if self.data.content[i][:len("Second Most Recent Tweet:")].lower() == "second most recent tweet:" :
                    if url == self.data.content[i][len("Second Most Recent Tweet:"):len("Second Most Recent Tweet:")+len(url)]:
                        is_new = False

        return is_new
    def delete_entry(self, string):
        '''(str)->bool
        delete the first entry in self.data.content that contains string, if it exists'''
        for i in range(len(self.data.content)):
            if string.lower() in self.data.content[i].lower():
                del(self.data.content[i])
                return True
        return False

    def get_author(self, bso):
        '''(BeautifulSoup object) -> str
        find the author's twitter handle '''
        return bso.find("dc:creator").get_text().strip(" (@)")

    def get_author_from_url(self, url):
        '''(str) -> str
        find the author's twitter handle in the url'''
        return url.split("=")[-1].strip("/")
