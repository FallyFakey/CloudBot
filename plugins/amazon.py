import requests
import re
from bs4 import BeautifulSoup

from cloudbot import hook
from cloudbot.util import web, formatting


SEARCH_URL = "https://www.amazon.{}/s/"
PAGE_URL = "https://www.amazon.{}/{}/{}"
REGION = "com"

AMAZON_RE = re.compile(""".*ama?zo?n\.(com|co\.uk|com\.au|de|fr|ca|cn|es|it)/.*/(?:exec/obidos/ASIN/|o/|gp/product/|
(?:(?:[^"\'/]*)/)?dp/|)(B[A-Z0-9]{9})""", re.I)


@hook.regex(AMAZON_RE)
def amazon_url(match):
    cc = match.group(1)
    asin = match.group(2)
    return amazon(asin, _parsed=cc)


@hook.command("amazon", "az", "amzn")
def amazon(text, _parsed=False):
    """<query> -- Searches Amazon for query"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.36 (KHTML, '
                      'like Gecko) Chrome/41.0.2228.0 Safari/537.36',
        'Referer': 'https://www.amazon.com/'
    }
    params = {
        'url': 'search-alias',
        'field-keywords': text.strip()
    }
    if _parsed:
        # input is from a link parser, we need a specific URL
        request = requests.get(SEARCH_URL.format(_parsed), params=params, headers=headers)
    else:
        request = requests.get(SEARCH_URL.format(REGION), params=params, headers=headers)

    soup = BeautifulSoup(request.text)

    # check if there are any results on the amazon page
    results = soup.find('div', {'id': 'atfResults'})
    if not results:
        if not _parsed:
            return "No results found."
        else:
            return

    # get the first item from the results on the amazon page
    results = results.find('ul', {'id': 's-results-list-atf'}).find_all('li', {'class': 's-result-item'})
    item = results[0]
    asin = item['data-asin']

    # here we use dirty html scraping to get everything we need
    title = formatting.truncate(item.find('h2', {'class': 's-access-title'}).text, 200)
    tags = []

    # tags!
    if item.find('i', {'class': 'a-icon-prime'}):
        tags.append("Prime")

    if item.find('i', {'class': 'sx-bestseller-badge-primary'}):
        tags.append("Bestseller")

    # we use regex because we need to recognise text for this part
    # the other parts detect based on html tags, not text
    if re.search(r"(Kostenlose Lieferung|Livraison gratuite|FREE Shipping|Envío GRATIS"
                 r"|Spedizione gratuita)", item.text, re.I):
        tags.append("Free Shipping")

    price = item.find('span', {'class': 'sx-price-whole'})
    if price:
        price = '{}{}.{}'.format(item.find('sup', {'class': 'sx-price-currency'}).text,
                                 item.find('span', {'class': 'sx-price-whole'}).text,
                                 item.find('sup', {'class': 'sx-price-fractional'}).text)
    else:
        price = item.find('span', {'class': ['s-price', 'a-color-price']})
        if price:
            price = price.text
        else:
            price = item.find('span', {'class': ['s-price', 'a-color-base']}).text

    # use a whole lot of BS4 and regex to get the ratings
    try:
        # get the rating
        rating = item.find('i', {'class': 'a-icon-star'}).find('span', {'class': 'a-icon-alt'}).text
        rating = re.search(r"([0-9]+(?:(?:\.|,)[0-9])?).*5", rating).group(1).replace(",", ".")
        # get the rating count
        pattern = re.compile(r"(product-reviews|#customerReviews)")
        num_ratings = item.find('a', {'href': pattern}).text.replace(".", ",")
        # format the rating and count into a nice string
        rating_str = "{}/5 ({} ratings)".format(rating, num_ratings)
    except AttributeError:
        rating_str = "No Ratings"

    # join all the tags into a string
    tag_str = " [div] " + ", ".join(tags) if tags else ""

    # generate a short url
    url = "[h3]https://www.amazon.com/dp/{}/[/h3]".format(asin)
    #url = web.try_shorten(url)

    # finally, assemble everything into the final string, and return it!
    out = "[h1]Amazon:[/h1] {} [div] {} [div] {}{}".format(title, price, rating_str, tag_str)
    if not _parsed:
        out +=  " [div] " + url
    return out
