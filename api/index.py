from flask import Flask, render_template
import feedparser
from datetime import datetime, timedelta
import pytz
from bs4 import BeautifulSoup
from transformers import pipeline
import os
TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'templates')
app = Flask(__name__, template_folder=TEMPLATE_DIR)


# RSS Feed sources
RSS_FEEDS = {
    'india': 'https://timesofindia.indiatimes.com/rssfeeds/-2128936835.cms',
    'global': 'https://timesofindia.indiatimes.com/rssfeeds/296589292.cms'
}

# Lazy initialization for summarizer
summarizer = None
HF_MODEL = os.getenv("HF_MODEL", "t5-small")  # default to t5-small

def get_summarizer():
    global summarizer
    if summarizer is None:
        summarizer = pipeline("summarization", model=HF_MODEL)
    return summarizer

# Fetch news articles (optionally filtering by last 24 hours)
def fetch_news(feed_url, only_last_24_hours=False):
    feed = feedparser.parse(feed_url)
    articles = []
    now = datetime.now(pytz.timezone('Asia/Kolkata'))
    cutoff = now - timedelta(days=1)

    for entry in feed.entries:
        if len(articles) >= 10:
            break  # Limit to 10 valid articles only

        try:
            pub_time = datetime(*entry.published_parsed[:6]) if 'published_parsed' in entry else datetime.utcnow()
            pub_time = pub_time.astimezone(pytz.timezone('Asia/Kolkata'))
            pub_time_str = pub_time.strftime('%b %d, %Y %I:%M %p')
        except:
            pub_time = datetime.utcnow()
            pub_time_str = "Not available"

        if only_last_24_hours and pub_time < cutoff:
            continue

        raw_summary = entry.get('summary', '')
        clean_summary = BeautifulSoup(raw_summary, "html.parser").get_text().strip()

        if not clean_summary or clean_summary.lower() in ['no summary available', '']:
            continue

        article = {
            'title': entry.get('title', 'No title'),
            'summary': clean_summary,
            'link': entry.get('link', '#'),
            'published': pub_time_str,
            'source': feed.feed.get('title', 'Unknown source')
        }

        articles.append(article)

    return articles

# Route: Daily 24-hour summary
@app.route('/report')
def daily_report():
    indian_articles = fetch_news(RSS_FEEDS['india'], only_last_24_hours=True)
    global_articles = fetch_news(RSS_FEEDS['global'], only_last_24_hours=True)

    def summarize_individual(articles):
        summarizer = get_summarizer()
        summarized = []
        for a in articles:
            input_text = a['title'] + ". " + a['summary']
            if len(input_text.strip()) < 40:
                summary = "Too short to summarize."
            else:
                summary = summarizer(input_text[:1024], max_length=60, min_length=20, do_sample=False)[0]['summary_text']
            summarized.append({
                "title": a['title'],
                "summary": summary,
                "published": a['published'],
                "link": a['link']
            })
        return summarized

    summarized_indian = summarize_individual(indian_articles)
    summarized_global = summarize_individual(global_articles)

    return render_template("report.html", indian_articles=summarized_indian, global_articles=summarized_global)

# Route: Home
@app.route('/')
def index():
    return render_template('index.html')

# Route: Indian news
@app.route('/india')
def india_news():
    articles = fetch_news(RSS_FEEDS['india'])
    return render_template('news.html', articles=articles, country='India')

# Route: Global news
@app.route('/global')
def global_news():
    articles = fetch_news(RSS_FEEDS['global'])
    return render_template('news.html', articles=articles, country='Global')

# Run locally
if __name__ == '__main__':
    app.run(debug=True)
