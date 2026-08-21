"""
Fetches topic RSS feeds from Finnish and Estonian news outlets, filters out
negative-keyword items, and compiles the result into data/feed.json for the
static dashboard (index.html) to render.

Run manually:  python scripts/fetch_feed.py
Run in CI:     see .github/workflows/update-feed.yml
"""
import datetime
import json
import re
import sys
from pathlib import Path

import feedparser
import requests

USER_AGENT = "positive-news-dashboard/1.0 (+personal, non-commercial RSS reader)"
REQUEST_TIMEOUT = 15
ITEMS_PER_SOURCE = 6
OUTPUT_PATH = Path(__file__).resolve().parent.parent / "data" / "feed.json"

# Each category pulls from a list of (outlet, language, feed_url, mode).
# mode "topic"   -> feed is already about this topic, only apply the negative blocklist.
# mode "general" -> feed is a general/mixed feed, require an allowlist keyword match too.
CATEGORIES = [
    {
        "key": "tiede",
        "label": "Tiede",
        "sources": [
            ("Helsingin Sanomat", "fi", "https://www.hs.fi/rss/tiede.xml", "topic"),
            ("Postimees", "et", "https://teadus.postimees.ee/rss", "topic"),
        ],
    },
    {
        "key": "terveys",
        "label": "Terveys ja hyvinvointi",
        "sources": [
            ("Iltasanomat", "fi", "https://www.is.fi/rss/hyvaolo.xml", "topic"),
            ("Iltalehti", "fi", "https://www.iltalehti.fi/rss/terveys.xml", "topic"),
            ("Aamulehti", "fi", "https://www.aamulehti.fi/rss/terveys.xml", "topic"),
            ("Postimees", "et", "https://tervis.postimees.ee/rss", "topic"),
            ("Õhtuleht", "et", "https://www.ohtuleht.ee/tervis/rss", "topic"),
        ],
    },
    {
        "key": "robotiikka_ja_tekoaly",
        "label": "Robotiikka ja tekoäly",
        "sources": [
            ("Iltasanomat", "fi", "https://www.is.fi/rss/digitoday.xml", "topic"),
            ("Iltalehti", "fi", "https://www.iltalehti.fi/rss/bitti.xml", "topic"),
            ("Postimees", "et", "https://tehnika.postimees.ee/rss", "topic"),
        ],
    },
    {
        "key": "ymparisto",
        "label": "Ympäristö ja luonto",
        "sources": [
            ("Iltasanomat", "fi", "https://www.is.fi/rss/kotimaa.xml", "general"),
            ("Helsingin Sanomat", "fi", "https://www.hs.fi/rss/suomi.xml", "general"),
            ("Postimees", "et", "https://www.postimees.ee/rss", "general"),
            ("Õhtuleht", "et", "https://www.ohtuleht.ee/rss", "general"),
        ],
    },
    {
        "key": "yhteiso",
        "label": "Yhteisö ja hyvät teot",
        "sources": [
            ("Iltasanomat", "fi", "https://www.is.fi/rss/kotimaa.xml", "general"),
            ("Iltalehti", "fi", "https://www.iltalehti.fi/rss/perhe.xml", "general"),
            ("Aamulehti", "fi", "https://www.aamulehti.fi/rss/perhe.xml", "general"),
            ("Postimees", "et", "https://www.postimees.ee/rss", "general"),
            ("Õhtuleht", "et", "https://www.ohtuleht.ee/rss", "general"),
        ],
    },
    {
        "key": "uudet_yritykset",
        "label": "Uudet yritykset ja innovaatiot",
        "sources": [
            ("Iltasanomat", "fi", "https://www.is.fi/rss/taloussanomat.xml", "general"),
            ("Helsingin Sanomat", "fi", "https://www.hs.fi/rss/talous.xml", "general"),
            ("Postimees", "et", "https://www.postimees.ee/rss", "general"),
        ],
    },
    {
        "key": "urheilu",
        "label": "Urheilusaavutukset",
        "sources": [
            ("Iltasanomat", "fi", "https://www.is.fi/rss/urheilu.xml", "topic"),
            ("Helsingin Sanomat", "fi", "https://www.hs.fi/rss/urheilu.xml", "topic"),
            ("Iltalehti", "fi", "https://www.iltalehti.fi/rss/urheilu.xml", "topic"),
            ("Aamulehti", "fi", "https://www.aamulehti.fi/rss/urheilu.xml", "topic"),
            ("Postimees", "et", "https://sport.postimees.ee/rss", "topic"),
            ("Õhtuleht", "et", "https://www.ohtuleht.ee/sport/rss", "topic"),
        ],
    },
    {
        "key": "kulttuuri",
        "label": "Kulttuurihelmet",
        "sources": [
            ("Iltasanomat", "fi", "https://www.is.fi/rss/musiikki.xml", "topic"),
            ("Helsingin Sanomat", "fi", "https://www.hs.fi/rss/kulttuuri.xml", "topic"),
            ("Postimees", "et", "https://kultuur.postimees.ee/rss", "topic"),
            ("Õhtuleht", "et", "https://www.ohtuleht.ee/kultuur/rss", "topic"),
        ],
    },
]

# Drop any item whose title or summary matches these (case-insensitive, word-boundary-ish).
NEGATIVE_KEYWORDS_FI = [
    "sota", "sodan", "sotaa", "hyökkäys", "hyökkäsi", "kuoli", "kuolivat", "kuolema",
    "kuollut", "surma", "murha", "tappoi", "tapettiin", "rikos", "rikollinen",
    "onnettomuus", "tulipalo", "katastrofi", "pandemia", "kriisi", "skandaali",
    "raiskaus", "väkivalta", "ammuskelu", "räjähdys", "terrori", "sieppaus",
    "kaappaus", "itsemurha", "loukkaantui", "loukkaantuivat", "vangittiin",
    "pidätettiin", "syyte", "oikeudenkäynti", "eroaa", "erosi", "irtisanomiset",
    "konkurssi", "korruptio",
]
NEGATIVE_KEYWORDS_ET = [
    "sõda", "sõja", "rünnak", "ründas", "suri", "surid", "surm", "hukkus", "hukkusid",
    "mõrv", "tappis", "tapeti", "kuritegu", "kurjategija", "õnnetus", "tulekahju",
    "katastroof", "pandeemia", "kriis", "skandaal", "vägivald", "vägistamine",
    "tulistamine", "plahvatus", "terror", "röövimine", "enesetapp", "vigastada",
    "vigastatud", "vahistati", "kohtuprotsess", "süüdistus", "pankrot", "korruptsioon",
    "koondamine",
]

# For "general" mode feeds, an item must ALSO match one of these to be considered on-topic.
POSITIVE_KEYWORDS = {
    "ymparisto": {
        "fi": ["ympäristö", "luonto", "ilmasto", "uusiutuva energia", "kierrätys",
              "suojelu", "eläinkanta", "metsä", "luonnonsuojelu", "päästö", "aurinkovoima",
              "tuulivoima", "biodiversiteetti"],
        "et": ["keskkond", "loodus", "kliima", "taastuvenergia", "ringlussevõtt",
              "looduskaitse", "mets", "elustik", "päikeseenergia", "tuuleenergia",
              "elurikkus"],
    },
    "yhteiso": {
        "fi": ["vapaaehtois", "hyväntekeväisyys", "yhteisö", "lahjoit", "auttoi",
              "auttavat", "hyvä teko", "keräys", "talkoot", "tukiverkko"],
        "et": ["vabatahtlik", "heategevus", "kogukond", "annetas", "aitas",
              "abistas", "hea tegu", "korje", "talgud"],
    },
    "uudet_yritykset": {
        "fi": ["perusti", "perustivat", "käynnisti", "startup", "kasvuyritys",
              "innovaatio", "keksintö", "uusi yritys", "sijoitus", "rahoituskierros"],
        "et": ["asutas", "asutasid", "käivitas", "idufirma", "kasvufirma",
              "innovatsioon", "leiutis", "uus ettevõte", "investeering", "rahastusvoor"],
    },
}


def matches_any(text, keywords):
    text_lower = text.lower()
    return any(kw in text_lower for kw in keywords)


def is_negative(title, summary):
    text = f"{title} {summary}"
    return matches_any(text, NEGATIVE_KEYWORDS_FI) or matches_any(text, NEGATIVE_KEYWORDS_ET)


def is_on_topic(category_key, lang, title, summary):
    rules = POSITIVE_KEYWORDS.get(category_key)
    if not rules:
        return True
    text = f"{title} {summary}"
    return matches_any(text, rules.get(lang, []))


def strip_html(text):
    return re.sub(r"<[^>]+>", "", text or "").strip()


def fetch_source(outlet, lang, url):
    headers = {"User-Agent": USER_AGENT}
    try:
        resp = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
    except requests.RequestException as exc:
        print(f"  ! failed to fetch {outlet} ({url}): {exc}", file=sys.stderr)
        return []
    parsed = feedparser.parse(resp.content)
    return parsed.entries


def build_category(category):
    key = category["key"]
    entries = []
    for outlet, lang, url, mode in category["sources"]:
        raw_entries = fetch_source(outlet, lang, url)
        kept = 0
        for entry in raw_entries:
            if kept >= ITEMS_PER_SOURCE:
                break
            title = strip_html(entry.get("title", ""))
            summary = strip_html(entry.get("summary", entry.get("description", "")))
            link = entry.get("link", "")
            if not title or not link:
                continue
            if is_negative(title, summary):
                continue
            if mode == "general" and not is_on_topic(key, lang, title, summary):
                continue
            pub_date = entry.get("published", entry.get("updated", ""))
            entries.append({
                "outlet": outlet,
                "lang": lang,
                "title": title,
                "summary": summary[:280],
                "link": link,
                "published": pub_date,
            })
            kept += 1
        print(f"  {outlet} [{key}]: kept {kept}/{len(raw_entries)}")
    return entries


def main():
    result = {
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "categories": [],
    }
    for category in CATEGORIES:
        print(f"Fetching category: {category['label']}")
        entries = build_category(category)
        result["categories"].append({
            "key": category["key"],
            "label": category["label"],
            "entries": entries,
        })

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
