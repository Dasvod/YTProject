import json, datetime as dt, random, requests
from pytrends.request import TrendReq

def get_daily(locale="IT"):
    url = ("https://trends.google.com/trends/api/dailytrends"
           f"?hl=it&geo={locale}&ed={dt.date.today():%Y%m%d}")
    txt = requests.get(url, timeout=30).text[6:]           # elimina ")]}',"
    data = json.loads(txt)
    items = data['default']['trendingSearchesDays'][0]['trendingSearches']
    return [i['title']['query'] for i in items]

def get_weekly(locale="IT"):
    pytrends = TrendReq(hl='it-IT', tz=360)
    df = pytrends.trending_searches(pn='italy')
    return df[0].head(5).tolist()

def pick_topic():
    return random.choice(get_daily() + get_weekly())

if __name__ == "__main__":
    print(pick_topic())
