#!/usr/bin/env python3
"""Build Lab data from real kai_ctr creatives.

Reads creative copy verbatim from kai_ctr/creative_ctr.parquet (Meta Ad
Library crosswalk), retries each ad's original image URLs (banked bytes
first, then live CDN), and writes data/ads.json, data/answer_key.json
(pairing gold), data/brand_profiles.json, media/brands/*.svg, and
tools/real_ads_manifest.json. No panel outcomes (impressions/CTR) are
written to the repo. Run: UV_CACHE_DIR=/tmp/uv-cache-bsl uv run
--with duckdb python tools/build_real_ads.py
"""
import json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PARQUET = "/Users/chrisjvargo/My Drive/2work/kai_ctr/creative_ctr.parquet"
BANK_MANIFEST = Path("/Users/chrisjvargo/My Drive/2work/ctr_creatives_release/build/media_manifest.jsonl")
BANK_ROOT = Path("/Users/chrisjvargo/My Drive/2work/ctr_creatives_release")

HATE = "Hate Speech & Acts of Aggression"
DEBATED = "Debated Sensitive Social Issues"
DEATH = "Death, Injury or Military Conflict"
PIRACY = "Online Piracy"
GORY = "Obscenity & Profanity / Gory or Shocking"
DRUGS = "Illegal Drugs / Tobacco / Vaping / Alcohol (youth)"
SPAM = "Spam or Harmful Content (malware/phishing)"
MISINFO = "Misinformation"

# post_id, brand_key, creative_id, ad_id, headline_override(None=library title),
# gold decision, gold garm (None if safe), rationale shown after judging
PAIRINGS = [
 ("mmhs_0001","crocs","aff4bbe63108f5e4","crocs-classic-clog",None,"ACCEPTABLE",None,
  "Joyful race-night post; Crocs' playful comfort fits everyday sports buzz."),
 ("mmhs_0184","lego","e9c8298dabf880ca","lego-momoa-play",None,"UNSAFE",DEBATED,
  "Political satire mocking a leader; LEGO's kid-safe profile avoids politicized content."),
 ("mmhs_0521","walmart","27abd4dbf913617b","walmart-free-assembly","New season, new classics","UNSAFE",HATE,
  "Dehumanizing hate speech is Floor content — no brand funds this adjacency."),
 ("mmhs_0772","dominos","388d836b0e667e3c","dominos-half-off",None,"ACCEPTABLE",None,
  "Locker-room emphasis after a win, not targeted abuse; Domino's playful voice tolerates mild profanity."),
 ("mmhs_0945","netflix","602e057261ad8921","netflix-set-it-up",None,"UNSAFE",PIRACY,
  "Post promotes an illegal stream; Netflix blocks piracy adjacency on sight."),
 ("mmhs_1010","ulta","3d7836a955c483a2","ulta-self-care",None,"ACCEPTABLE",None,
  "Reclaimed language used with pride by the community itself — do not keyword-block identity."),
 ("mmhs_1189","chewy","93998f7c7faa4605","chewy-dreambone",None,"UNSAFE",GORY,
  "Graphic accident imagery next to wholesome pet treats is a tone and gore mismatch."),
 ("mmhs_1402","temu","268b3fdcaa9cb1e5","temu-bow-sweater","Unbelievable discounts on fashion, home & more!","UNSAFE",SPAM,
  "Even as a warning, the post details a live card-harvesting scam; marketplace Temu cannot sit beside scam mechanics."),
 ("mmhs_1550","doordash","0d58583ed988d0f0","doordash-come-back",None,"ACCEPTABLE",None,
  "Harmless absurd satire with no target; DoorDash humor fits."),
 ("mmhs_1661","target","34e6410fe0957643","target-home-decor","Discover home décor at Target","UNSAFE",DEATH,
  "Violent protest video is legitimate news, but cheerful home-décor creative is the wrong tone for Target here."),
 ("vmu_0204","disney","e53d436f94767368","disneyplus-student-deal",None,"UNSAFE",MISINFO,
  "Viral fake shark photo presented as real; misinformation is Floor for Disney."),
 ("vmu_0411","starbucks","9d046b533479a6fb","starbucks-gift-card",None,"UNSAFE",DEATH,
  "Hospital bombing footage with viewer discretion; gift-card celebration creative must not follow it."),
 ("vmu_0502","walmart","f6db6ca40987f805","walmart-spark",None,"ACCEPTABLE",None,
  "Rumor-control post debunks a recycled video; corrections are safe, valuable adjacency."),
 ("mmhs_1770","dominos","5869b5741b7905a4","dominos-party-of-one",None,"ACCEPTABLE",None,
  "Light food humor; easy safe match for Domino's."),
 ("mmhs_1855","netflix","613316fd3789e175","netflix-lizzie-borden",None,"ACCEPTABLE",None,
  "Documentary still in a film-release context; adult streamer Netflix accepts non-graphic conflict storytelling. Compare the Target protest pairing."),
 ("mmhs_1991","disney","157267c51c89db38","disneystore-halloween",None,"UNSAFE",PIRACY,
  "Explicit cracked-episode link ('no ads'); Disney protects its IP and blocks piracy CTAs."),
 ("mmhs_2050","lego","e81de7adb3db81cd","lego-fearless",None,"UNSAFE",HATE,
  "Dehumanization ('monsters', 'no mercy') is Floor hate — block for every brand, especially LEGO."),
 ("mmhs_2121","ulta","72df9397580fc9c4","ulta-woke-up",None,"UNSAFE",DRUGS,
  "Investigation is legitimate, but youth-vaping adjacency is high-risk for Ulta's young beauty audience."),
 ("mmhs_2307","crocs","43d2c0b0aced8da5","crocs-toy-story",None,"UNSAFE",GORY,
  "Crocs tolerates edge — but this Toy Story kids'-collection creative cannot follow an uncut profanity reel."),
 ("mmhs_2450","chewy","bb64a98f6662e67e","chewy-fuel-for-life",None,"ACCEPTABLE",None,
  "Humanitarian relief with a pro-social tone; Chewy's community-care voice can sit here. Compare the graphic-accident pairing."),
 ("mmhs_2602","temu","4e949109ec1680e4","temu-app-deals","Upgrade your shopping game with our Temu app!","ACCEPTABLE",None,
  "Straight policy debate, no graphic or hateful content; price-first Temu tolerates debated-issue adjacency. Compare the LEGO satire pairing."),
 ("vmu_0620","target","f9a6c3f94d08cf33","target-pokemon","The new Pokémon x Target collection","UNSAFE",MISINFO,
  "The clip itself is false-context footage; family retail blocks even when the caption calls it out — skimmers still absorb the fake."),
 ("vmu_0754","starbucks","bc2ce1eb7be8b1bb","starbucks-refreshers",None,"ACCEPTABLE",None,
  "Straight ceasefire news briefing without graphic imagery; mainstream Starbucks allows hard-news adjacency. Compare the Aleppo pairing."),
 ("vmu_0801","doordash","d17b6b2fb1ff2311","doordash-curry",None,"ACCEPTABLE",None,
  "Thread documents and exposes a fake charity with receipts; exposure/reporting is safe for DoorDash. Compare the Temu scam-warning pairing."),
]

CATS = ["Adult & Explicit Sexual Content","Arms & Ammunition",
 "Crime & Harmful Acts / Human Rights Violations",DEATH,PIRACY,HATE,GORY,DRUGS,SPAM,
 "Terrorism",DEBATED,MISINFO]
def posture(*vals):
    assert len(vals) == 12, vals
    return dict(zip(CATS, vals))

# key: name, logo label, logo bg, site, cta, bullets, posture
BRANDS = {
 "lego": ("LEGO","LEGO","#c62828","https://www.lego.com","Shop now",
   ["Family-first, global kid-safe experience","Strict avoidance of explicit, violent, or adult themes","Prefers neutral, joyful cultural adjacency","Low tolerance for debated or politicized content"],
   posture("FLOOR","FLOOR","FLOOR","FLOOR","HIGH","FLOOR","FLOOR","FLOOR","FLOOR","FLOOR","HIGH","FLOOR")),
 "disney": ("Disney","Disney","#113ccf","https://www.disney.com","Learn more",
   ["Family entertainment across Disney+ and Disney Store","Protects its IP: zero tolerance for piracy adjacency","Kid-and-family trust rules out graphic or adult edges","Avoids politicized debate next to family creative"],
   posture("FLOOR","HIGH","HIGH","HIGH","FLOOR","FLOOR","HIGH","FLOOR","FLOOR","FLOOR","HIGH","FLOOR")),
 "walmart": ("Walmart","Walmart","#0071ce","https://www.walmart.com","Shop now",
   ["Mass mainstream: everyday value for every household","Comfortable in straight news, not graphic tragedy","Labor and community stories need careful tone","Blocks scams and misinformation that erode trust"],
   posture("HIGH","MEDIUM","HIGH","MEDIUM","HIGH","FLOOR","MEDIUM","HIGH","FLOOR","FLOOR","MEDIUM","HIGH")),
 "target": ("Target","Target","#cc0000","https://www.target.com","Shop now",
   ["Mainstream style retail with a cheerful, design-led voice","Lifestyle creative clashes with violent or graphic moments","Family collections run stricter than general retail","Straight news is fine; misleading clips are not"],
   posture("HIGH","HIGH","HIGH","MEDIUM","HIGH","FLOOR","MEDIUM","HIGH","FLOOR","FLOOR","MEDIUM","HIGH")),
 "dominos": ("Domino's Pizza","Domino's","#0b648f","https://www.dominos.com","Order now",
   ["Playful, meme-literate pizza voice","Comfortable with mild profanity and sports trash-talk","Cheerful food creative avoids tragedy adjacency","Everyday humor and satire are welcome"],
   posture("HIGH","HIGH","MEDIUM","HIGH","MEDIUM","FLOOR","LOW","MEDIUM","HIGH","FLOOR","MEDIUM","HIGH")),
 "doordash": ("DoorDash","DoorDash","#eb1700","https://www.doordash.com","Order now",
   ["Playful delivery voice built on cravings and local gems","Community and mutual-aid stories fit the brand","Mild edge and humor fine; graphic tragedy is not","Trust matters: documented fraud exposure differs from live scams"],
   posture("HIGH","HIGH","MEDIUM","HIGH","MEDIUM","FLOOR","LOW","MEDIUM","HIGH","FLOOR","MEDIUM","HIGH")),
 "chewy": ("Chewy","Chewy","#128ced","https://www.chewy.com","Shop now",
   ["Wholesome pet-parent community voice","Pro-social and relief stories fit; gore never does","Avoids politicized debate next to pet creative","Warm tone must not follow graphic harm"],
   posture("HIGH","HIGH","HIGH","HIGH","HIGH","FLOOR","MEDIUM","HIGH","FLOOR","FLOOR","HIGH","HIGH")),
 "ulta": ("Ulta Beauty","Ulta Beauty","#e91e63","https://www.ulta.com","Shop now",
   ["Beauty mainstream with a young, creator-led audience","Self-care voice avoids tragedy and graphic harm","Youth-substance topics are high-risk even in reporting","Pride and identity celebration are on-brand"],
   posture("HIGH","HIGH","HIGH","HIGH","HIGH","FLOOR","MEDIUM","HIGH","HIGH","FLOOR","MEDIUM","HIGH")),
 "netflix": ("Netflix","Netflix","#141414","https://www.netflix.com","Join now",
   ["Adult entertainment: sells dark drama and true crime itself","Documentary conflict storytelling can fit; graphic news still needs care","Piracy is existential: Floor, no exceptions","Profanity and edgy humor are native to the catalog"],
   posture("MEDIUM","MEDIUM","MEDIUM","MEDIUM","FLOOR","FLOOR","LOW","MEDIUM","HIGH","HIGH","LOW","FLOOR")),
 "temu": ("Temu","Temu","#fb7701","https://www.temu.com","Shop now",
   ["Price-first marketplace with broad suitability tolerance","Fighting scam perception: live-scam adjacency is toxic","Policy debate and everyday edge are acceptable","Hate, terrorism, and misinformation still block"],
   posture("HIGH","HIGH","HIGH","MEDIUM","MEDIUM","FLOOR","LOW","HIGH","FLOOR","FLOOR","LOW","HIGH")),
 "crocs": ("Crocs","Crocs","#6ab844","https://www.crocs.com","Shop now",
   ["Playful, irreverent comfort voice","Core brand tolerates edge and mild profanity","Kids' collab creatives run much stricter than core Crocs","Joyful sports and fandom moments are home turf"],
   posture("HIGH","HIGH","MEDIUM","HIGH","MEDIUM","FLOOR","LOW","MEDIUM","HIGH","FLOOR","LOW","HIGH")),
 "starbucks": ("Starbucks","Starbucks","#00704a","https://www.starbucks.com","Learn more",
   ["Mainstream coffeehouse: warm, everyday, community-led","Hard-news briefings fine; graphic suffering is not","Celebration creative must not follow tragedy","Corrections and civic information fit the third-place role"],
   posture("HIGH","HIGH","HIGH","MEDIUM","HIGH","FLOOR","MEDIUM","HIGH","FLOOR","FLOOR","MEDIUM","HIGH")),
}
EXPECTED_ADVERTISER = {"lego":"LEGO","disney":None,"walmart":"Walmart","target":"Target",
 "dominos":"Domino's Pizza","doordash":"DoorDash","chewy":"Chewy","ulta":"Ulta Beauty",
 "netflix":"Netflix","temu":"Temu","crocs":"Crocs","starbucks":"Starbucks"}

def clean(s):
    return re.sub(r"\s+", " ", str(s or "")).strip()

def banked_map():
    m = {}
    if BANK_MANIFEST.exists():
        for line in BANK_MANIFEST.read_text().splitlines():
            try: o = json.loads(line)
            except Exception: continue
            if o.get("status") == "hit" and o.get("path"):
                m[o["url"]] = BANK_ROOT / o["path"].replace("release/", "", 1)
    return m

def fetch_image(urls, dest, bank):
    import shutil, urllib.request
    for u in urls:
        if u in bank and bank[u].exists() and bank[u].stat().st_size > 8000:
            shutil.copyfile(bank[u], dest)
            return ("banked", u)
    for u in urls:
        try:
            req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=20) as r:
                ct = r.headers.get_content_type()
                data = r.read()
            if ct.startswith("image/") and len(data) > 8000:
                dest.write_bytes(data)
                return ("live", u)
        except Exception:
            continue
    return (None, None)

def logo_svg(label, bg):
    size = 30 if len(label) <= 7 else 24
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 160 80">\n'
            f'  <rect width="160" height="80" rx="16" fill="{bg}"/>\n'
            f'  <text x="80" y="50" fill="#fff" font-family="Segoe UI, system-ui, sans-serif" '
            f'font-size="{size}" font-weight="700" text-anchor="middle">{label}</text>\n</svg>\n')

def main():
    import duckdb
    con = duckdb.connect()
    posts = json.loads((ROOT / "data/posts.json").read_text())
    feed = [p["id"] for pg in posts["pages"] for p in pg]
    assert [p[0] for p in PAIRINGS] == feed, "pairing order must match posts feed order"
    bank = banked_map()
    (ROOT / "media/ads/real").mkdir(parents=True, exist_ok=True)
    ads, answer_key, manifest = [], {}, []
    for post_id, bkey, cid, ad_id, hov, decision, garm, note in PAIRINGS:
        row = con.execute(f"""
          SELECT advertiser, library_ad_id, library_title, library_caption, library_body,
                 services, media_image_urls_json, format_proxy
          FROM '{PARQUET}' WHERE creative_id = ?""", [cid]).fetchone()
        assert row, f"creative {cid} not found"
        adv, libid, title, cap, body, services, imgs_json, fmt = row
        exp = EXPECTED_ADVERTISER[bkey]
        if exp: assert adv == exp, f"{ad_id}: advertiser {adv!r} != {exp!r}"
        else: assert adv in ("Disney+", "Disney Store"), f"{ad_id}: {adv!r}"
        title, cap, body = clean(title), clean(cap), clean(body)
        assert len(body) >= 30 and "{{" not in body, f"{ad_id}: bad body {body[:80]!r}"
        headline = hov or title
        assert headline and "{{" not in headline, f"{ad_id}: bad headline"
        name, label, bg, site, cta, bullets, post = BRANDS[bkey]
        url = site
        if re.fullmatch(r"[a-z0-9.-]+\.[a-z]{2,}", cap.lower()) and cap.lower() not in (
                "play.google.com", "itunes.apple.com", "fb.me", "channelsight.com"):
            url = "https://" + cap.lower()
        try: img_urls = json.loads(imgs_json) if imgs_json else []
        except Exception: img_urls = []
        dest = ROOT / f"media/ads/real/{ad_id}.jpg"
        how, src_url = fetch_image(img_urls, dest, bank) if img_urls else (None, None)
        ad = {"id": ad_id, "brand_key": bkey, "advertiser": adv,
              "headline": headline, "body": body, "cta": cta, "url": url,
              "tagline": f"Real ad · {adv}",
              "provenance": f"Real ad copy · Meta Ad Library #{libid} · seen on {services}",
              "library_ad_id": str(libid), "creative_id": cid}
        if how: ad["image"] = f"media/ads/real/{ad_id}.jpg"
        ads.append(ad)
        key = f"{post_id}__{ad_id}"
        ent = {"decision": decision, "notes": note}
        if garm: ent["garm"] = garm
        answer_key[key] = ent
        manifest.append({"post_id": post_id, "ad_id": ad_id, "brand_key": bkey,
            "advertiser": adv, "creative_id": cid, "library_ad_id": str(libid),
            "library_title": title, "library_caption": cap, "body": body,
            "format_proxy": fmt, "image": how, "gold": ent})
        print(f"{ad_id:26s} {adv:16s} img={how or 'tile':6s} gold={decision}")
    profiles = {}
    for k, (name, label, bg, site, cta, bullets, post) in BRANDS.items():
        (ROOT / f"media/brands/{k}.svg").write_text(logo_svg(label, bg))
        profiles[k] = {"name": name, "logo": f"media/brands/{k}.svg", "color": bg,
                       "bullets": bullets, "risk_posture": post}
    (ROOT / "data/ads.json").write_text(json.dumps(ads, indent=1, ensure_ascii=False) + "\n")
    (ROOT / "data/answer_key.json").write_text(json.dumps(answer_key, indent=1, ensure_ascii=False) + "\n")
    (ROOT / "data/brand_profiles.json").write_text(
        json.dumps({"default": "walmart", "profiles": profiles}, indent=1, ensure_ascii=False) + "\n")
    (ROOT / "tools/real_ads_manifest.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False) + "\n")
    n_img = sum(1 for m in manifest if m["image"])
    print(f"\nwrote {len(ads)} ads ({n_img} with photos, {len(ads)-n_img} tiles), "
          f"{len(answer_key)} pairing golds, {len(profiles)} profiles")

if __name__ == "__main__":
    main()
