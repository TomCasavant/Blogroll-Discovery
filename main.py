from typing import List

import requests
from bs4 import BeautifulSoup
import listparser as lp
import feedparser
import urllib.parse

from listparser.common import SuperDict
import toml

class Feed:
    url: str = None
    feed: None
    blogroll: None

    def __init__(self, url):
        self.url = url
        # URL is an xml/rss url
        self.feed = feedparser.parse(url)
        self.blogroll = self.find_blogroll()

    def find_blogroll(self):
        print(f'Checking {self.url} for blogroll link')
        # Check if blogroll link is in RSS/XML feed
        if 'source_blogroll' in self.feed.feed:
            blogroll_url = self.feed.feed['source_blogroll']
            if not blogroll_url.startswith('http'):
                blogroll_url = urllib.parse.urljoin(base_url, blogroll_url)
            return Blogroll(blogroll_url)

        # If not found in feed, check the HTML of the base_url
        base_url = urllib.parse.urlparse(self.url).scheme + '://' + urllib.parse.urlparse(self.url).netloc
        print(f"Blogroll not in RSS feed, try checking meta tags at {base_url}")

        try:
            response = requests.get(base_url)
            if response.status_code != 200:
                return None

            soup = BeautifulSoup(response.text, 'html.parser')
            blogroll_link = soup.find_all('link', rel='blogroll')
            if blogroll_link:
                # Blogroll URL may be relative or absolute
                blogroll_url = blogroll_link[0]['href']
                if not blogroll_url.startswith('http'):
                    blogroll_url = urllib.parse.urljoin(base_url, blogroll_url)
                return Blogroll(blogroll_url)
            print("No blogroll found")
        except Exception as e:
            print(e)
        return None


class Blogroll:
    url: str = None
    opml: SuperDict = None
    feeds: List[Feed] = None

    def __init__(self, url):
        self.url = url
        self.opml = lp.parse(url)

    def get_feeds(self):
        if self.feeds is None:
            self.feeds = self.set_feeds()
        return self.feeds

    def set_feeds(self):
        feeds = []
        for feed in self.opml.feeds:
            feeds.append(Feed(feed.url))
        return feeds

    def get_blogroll_tree(self, depth=0, max_depth=0, feed_scores={}):
        # Loop through all feeds in blogroll, find their blogrolls and associated feeds The score of the feed is
        # determined by (1/depth+1) + (1/depth+1)... for each time the feed.url appears in the blogroll tree
        if depth == max_depth:
            return [self]
        else:
            blogroll_tree = [self]
            for feed in self.get_feeds():
                if feed.url in feed_scores:
                    feed_scores[feed.url] += 1/(depth+1)
                else:
                    # Feed already in blogroll, no need to search again
                    feed_scores[feed.url] = 1/(depth+1)
                    blogroll = feed.blogroll
                    if blogroll:
                        blogroll_tree.extend(blogroll.get_blogroll_tree(depth + 1, max_depth, feed_scores))

            print(feed_scores)

            return blogroll_tree


class GReader:
    url: str = None
    api_key: str = None

    def __init__(self, url, api_key):
        self.url = url
        self.api_key = api_key

    def add_feed(self, feed: Feed, category: str):
        headers = {
            'Authorization': f'Bearer auth={self.api_key}',
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        data = {
            'ac': 'subscribe',
            's': f"feed/{feed.url}",
            'a': 'user/-/label/' + category
        }

        response = requests.post(self.url, headers=headers, data=data)
        response.raise_for_status()

if __name__ == '__main__':
    with open('config.toml', 'r') as f:
        config = toml.load(f)
    
    greader_config = config['greader']
    greader = GReader(greader_config['url'], greader_config['api_key'])
    feed = Feed(config['feed']['url'])

    if feed.blogroll:
        feed_scores = {}
        tree = feed.blogroll.get_blogroll_tree(max_depth=10, feed_scores=feed_scores)
        sorted_scores = sorted(feed_scores.items(), key=lambda x: x[1], reverse=True)
    
        print("Sorted Feed Scores:")
        for url, score in sorted_scores:
            print(f"{url}: {score}")
        
        print("Blogroll Tree:")
        print(tree)
