import json, datetime as dt, random, requests
from pytrends.request import TrendReq

def get_daily(locale="IT"):
    """
    Ritorna la lista degli argomenti di tendenza giornalieri.
    Se la chiamata fallisce o il JSON non è valido, torna lista vuota.
    """
    try:
        url = (
            "https://trends.google.com/trends/api/dailytrends"
            f"?hl=it&geo={locale}&ed={dt.date.today():%Y%m%d}"
        )
        resp = requests.get(url, timeout=30)
        # Se la risposta non è OK, falliamo subito
        resp.raise_for_status()
        txt = resp.text
        # Rimuoviamo il prefisso anti-XSSI ")]}',"
        if txt.startswith(")]}',"):
            txt = txt[5:]
        data = json.loads(txt)
        items = data['default']['trendingSearchesDays'][0]['trendingSearches']
        return [i['title']['query'] for i in items]
    except Exception:
        return []

def get_weekly(locale="IT"):
    """
    Ritorna la top 5 delle ricerche settimanali in Italia via pytrends.
    """
    try:
        pytrends = TrendReq(hl='it-IT', tz=360)
        df = pytrends.trending_searches(pn='italy')
        return df[0].head(5).tolist()
    except Exception:
        return []

def pick_topic():
    """
    Pesca casualmente da daily + weekly trends.
    Se daily è vuoto, pesca solo da weekly.
    """
    daily = get_daily()
    weekly = get_weekly()
    pool = daily + weekly
    if not pool:
        # fallback generico
        return "curiosità"
    return random.choice(pool)

if __name__ == "__main__":
    print(pick_topic())
