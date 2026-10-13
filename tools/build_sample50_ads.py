#!/usr/bin/env python3
"""Build Lab data from kai_ctr creative_sample_50 (real social ad assets).

Every ad card embeds the actual creative file (photo or short video)
from the sample pack. Copy is the matched Meta Ad Library body when it
verifiably matches the visible creative, otherwise transcribed from
the creative itself. Writes data/ads.json, data/answer_key.json
(pairing gold), data/brand_profiles.json, brand logo tiles, web-sized
media under media/ads/real/, and tools/sample50_manifest.json.
Run: python3 tools/build_sample50_ads.py  (needs ffmpeg + ImageMagick)
"""
import json, re, subprocess, zipfile, shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ZIP = Path("/Users/chrisjvargo/My Drive/2work/kai_ctr/creative_sample_50.zip")
SRC = Path("/tmp/bsl_sample50_src")
HATE="Hate Speech & Acts of Aggression"; DEBATED="Debated Sensitive Social Issues"
DEATH="Death, Injury or Military Conflict"; PIRACY="Online Piracy"
GORY="Obscenity & Profanity / Gory or Shocking"; DRUGS="Illegal Drugs / Tobacco / Vaping / Alcohol (youth)"
SPAM="Spam or Harmful Content (malware/phishing)"; MISINFO="Misinformation"

# post, file, ad_id, brand_key, brand, tagline(hint), headline, body, cta, url, lib_id|None, gold, garm, note
ROWS = [
 ("mmhs_0001","creative_05.mp4","stanley-jug","stanley","Stanley","Outdoor gear · creator ad",
  "Mountain mornings, handled.","Let’s go on an early morning mountain adventure with my new @Stanley_Brand IceFlow™ Flip Straw 40oz Jug. Made with recycled plastics from discarded fishing nets. #BuiltforLife #sponsored","Shop now","https://www.stanley1913.com","557593685226686","ACCEPTABLE",None,
  "Joyful race-night energy fits an outdoor creator ad — easy safe calibration."),
 ("mmhs_0184","creative_06.jpg","jwf-grant-wishes","jwf","Jewish Women's Foundation","Charity · community grants",
  "Grant Wishes Virtual Celebration","Announcing the JWF 2020 Grant Awards and Presentation of the JWF Leadership Award. Grant Wishes Virtual Celebration — sponsorships go toward granting.","Learn more","#",None,"UNSAFE",DEBATED,
  "Mocking political satire; a community charity avoids politicized adjacency."),
 ("mmhs_0521","creative_24.jpg","lowes-splash","lowes","Lowe's","Home retail · mainstream",
  "Add a splash of personality","New house? That's worth celebrating. Lowe's has paint, lights, gardening essentials, trending décor and everything else you need to make it yours.","Shop now","https://www.lowes.com","2327908864642210","UNSAFE",HATE,
  "Dehumanizing hate speech is Floor content — no brand funds this adjacency."),
 ("mmhs_0772","creative_11.mp4","goodrich-trailer","goodrich","Goodrich Trailer Sales","Local dealer · playful video",
  "When you get the new trailer before summer","Shop Wisconsin's Premier Trailer Dealership!","Learn more","#","1608595250199370","ACCEPTABLE",None,
  "Locker-room emphasis after a win; a playful local dealer video tolerates the tone."),
 ("mmhs_0945","creative_26.jpg","hockey-drama","hockeydrama","Where We Grew Up","Short-drama app · entertainment",
  "He chose her on the ice — Where We Grew Up","It was deadline day for college apps, and my childhood best friend Colton just completely screwed me over… Read more (Book ID: 28898).","Read now","#","1654103676084244","UNSAFE",PIRACY,
  "Post promotes a free illegal stream; entertainment apps block piracy adjacency."),
 ("mmhs_1010","creative_13.jpg","kopari-glow","kopari","Kopari","Beauty · sunscreen",
  "Sunscreen You'll Actually Want To Wear","Ultimate Glow Vault + Woven Tote. Bundle & Save $86.","Shop now","https://koparibeauty.com",None,"ACCEPTABLE",None,
  "Reclaimed language used with pride — do not keyword-block identity; beauty brand fits."),
 ("mmhs_1189","creative_33.mp4","openfarm-rawmix","openfarm","Open Farm","Pet food · wholesome",
  "RawMix Front Range Recipe","Open Farm RawMix — humanely raised & sustainably sourced dog food (video).","Shop now","https://openfarmpet.com","2281128402665987","UNSAFE",GORY,
  "Graphic accident imagery next to wholesome pet food is a gore and tone mismatch."),
 ("mmhs_1402","creative_48.jpg","integrity-home","integrityhome","Integrity Home Buyers","Cash home buyer · direct response",
  "Sell Your Wisconsin Home Fast For Cash","Get your free offer or use our free calculator to see your cash — no repairs or fees.","Get my offer","#","1421405029873679","UNSAFE",SPAM,
  "Even as a warning, the post details a live card-harvesting scam; a trust-based cash buyer cannot sit beside scam mechanics."),
 ("mmhs_1550","creative_23.jpg","reshline-chicken","reshline","Reshline","Novelty gifts · playful",
  "Is this a real chicken or a pillow?","Bring home the most adorable and viral plushie of the season: the Realistic 3D Chicken Plush Pillow! Ultra-soft, skin-friendly fabric with hyper-realistic 3D printing.","Shop now","#","1792013668385865","ACCEPTABLE",None,
  "Harmless absurd satire meets an absurd product — playful on playful."),
 ("mmhs_1661","creative_15.jpg","cinzia-outfit","cinzia","Cinzia Rocca","Fashion · outfit edit",
  "Bet your mood looks like this today","Green and blue can go soft, sharp, or playful — it depends on how you balance them. #outfitinspiration #styleedit","Shop now","#","1498041622114028","UNSAFE",DEATH,
  "Violent protest video is legitimate news, but a cheerful outfit edit is the wrong tone here."),
 ("vmu_0204","creative_38.jpg","feed-children","feedchildren","Feed the Children","Charity · families",
  "International Day of Families Benefit Special","Join Feed the Children for our first ever online benefit special for International Day of Families! For every $1 donated, we'll be able to provide $7 worth of food and essentials to struggling families.","Donate","https://www.feedthechildren.org","368818050743812","UNSAFE",MISINFO,
  "Viral fake shark photo presented as real; misinformation is Floor for a family charity."),
 ("vmu_0411","creative_14.mp4","nielsen-rewards","nielsen","Nielsen Panel","Research panel · gift-card rewards",
  "Your rewards. Your choice.","Nielsen Computer & Mobile Panel — earn rewards including Visa, Target, Starbucks and Apple gift cards (video).","Join now","https://www.nielsen.com",None,"UNSAFE",DEATH,
  "Hospital bombing footage with viewer discretion; gift-card celebration creative must not follow it."),
 ("vmu_0502","creative_21.jpg","kbb-home-value","kbb","Kelley Blue Book","Home values · trusted info",
  "Zillow said $475K. We said $514K.","Zillow said $475K. We said $514K — and delivered. Find out how.","Find out how","https://www.kbb.com","1531000831665539","ACCEPTABLE",None,
  "Rumor-control debunk next to a trusted-information brand is safe, valuable adjacency."),
 ("mmhs_1770","creative_27.jpg","airplane-cooking","airplanecooking","Airplane Cooking","Mobile game · playful",
  "Airplane Cooking","EMERGENCY! Chef is stranded on a plane and customers are FURIOUS! Tap to play now, no download needed, and help the chef restore peace in the skies!","Play now","#","1365741828890947","ACCEPTABLE",None,
  "Light food humor meets a silly cooking game — easy safe match."),
 ("mmhs_1855","creative_49.mp4","turftank-robot","turftank","Turf Tank","Sports tech · B2B robot",
  "Massive time savings? YES.","Athletic Directors, you've got a long list of tasks. Let's shorten it. Turf Tank is the autonomous robot that takes line marking off your list.","Request quote","https://turftank.com","1087084040639604","ACCEPTABLE",None,
  "Non-graphic documentary still; neutral professional sports-tech can sit in a serious feed. Compare the fashion protest pairing."),
 ("mmhs_1991","creative_09.mp4","deltaforce-pulse","deltaforce","Pulse Giftcards · Delta Force","Gaming · gift cards",
  "Delta Force — available now","Delta Force. Available now on Pulse Giftcards (video).","Get it now","#","1245714043721387","UNSAFE",PIRACY,
  "Explicit cracked-episode link ('no ads'); a games seller blocks piracy CTAs."),
 ("mmhs_2050","creative_12.jpg","mermaid-masterpieces","mermaid","Mermaid Masterpieces","Kids' painting · creator",
  "Welcome to Mermaid Masterpieces!","Good Morning! If you're new, welcome to Mermaid Masterpieces — I'm Becky! Thank you ALL so much for being here!!","Learn more","#",None,"UNSAFE",HATE,
  "Dehumanization is Floor hate — block for every brand, especially a kids' painting page."),
 ("mmhs_2121","creative_02.mp4","tattoo-2week","tattoo","2-Week Tattoos","Semi-permanent tattoos · youth-skewing",
  "This is a 2-Week Tattoo…","35% OFF NOW ON! Use code META35. 8,000+ 5-star reviews. Lasts 1–2 weeks. 100% organic / vegan. Fully customisable. Free shipping & returns.","Shop now","#","1296591922549995","UNSAFE",DRUGS,
  "Investigation is legitimate, but youth-vaping adjacency is high-risk beside a youth-skewing body product."),
 ("mmhs_2307","creative_45.mp4","grubbly-chickens","grubbly","Grubbly Farms","Chicken feed · sustainability",
  "Can our fluffy ones help sustain our planet?","Grubbly Farms — sustainably grown chicken feed (video).","Learn more","#","268507955175538","UNSAFE",GORY,
  "Wholesome farm creative cannot follow an uncut profanity slam reel."),
 ("mmhs_2450","creative_08.jpg","furlife-tickfree","furlife","FurLife","Pet care · protection",
  "Provide a tick-free life for your pet","Seeking a chemical-free way to protect your dogs from fleas and ticks? Secure your pet's protection with FurLife™ with code “TICKFREE” at checkout.","Shop now","#","1450284886844110","ACCEPTABLE",None,
  "Humanitarian relief with a care-and-protection tone fits a pet-protection brand. Compare the graphic-accident pairing."),
 ("mmhs_2602","creative_07.jpg","hometap-hei","hometap","Hometap","Home finance · mainstream",
  "A simple, flexible HELOC alternative","Get up to $600,000 of your home equity in cash without monthly payments. HELOC vs HEI: no monthly payments, simple process.","Learn more","https://www.hometap.com","1606464137525774","ACCEPTABLE",None,
  "Straight policy debate, no graphic or hateful content; mainstream finance tolerates it. Compare the charity satire pairing."),
 ("vmu_0620","creative_32.jpg","jeep-presidents","jeepdealer","Uptown CDJR (Jeep)","Auto dealer · mainstream retail",
  "Presidents' Day Event","Our Presidents' Day Sales Event Is On. UptownCDJR.com","Shop now","#","174595277463124","UNSAFE",MISINFO,
  "The clip itself is false-context footage; family auto retail blocks even when the caption calls it out."),
 ("vmu_0754","creative_41.mp4","waymaker-fabrics","waymaker","WayMaker Fabrics","Fabric · small business",
  "Still thinking about that fabric?","Still thinking about that fabric? Faith-inspired designs, printed in America and shipped fast (video).","Shop now","#","3273564069482902","ACCEPTABLE",None,
  "Straight ceasefire briefing without graphic imagery; small-business creative runs in news feeds. Compare the Aleppo pairing."),
 ("vmu_0801","creative_10.jpg","fitaumax-bras","fitaumax","Fit Au Max Lingerie","Apparel · fuller-bust bras",
  "Why choose us?","She threw out every bra she owned after trying these. Polish-made lace bras engineered for fuller busts — lift, support & comfort, wider straps for large cups. www.fitaumax.com","Learn more","https://www.fitaumax.com","1066966322587033","ACCEPTABLE",None,
  "Thread documents a fake charity with receipts; documented exposure is safe adjacency. Compare the scam-warning pairing."),
]
CATS=["Adult & Explicit Sexual Content","Arms & Ammunition","Crime & Harmful Acts / Human Rights Violations",DEATH,PIRACY,HATE,GORY,DRUGS,SPAM,"Terrorism",DEBATED,MISINFO]
def posture(*v): assert len(v)==12; return dict(zip(CATS,v))
STRICT=posture("FLOOR","HIGH","HIGH","HIGH","HIGH","FLOOR","HIGH","HIGH","FLOOR","FLOOR","HIGH","FLOOR")
MAIN=posture("HIGH","HIGH","HIGH","MEDIUM","HIGH","FLOOR","MEDIUM","HIGH","FLOOR","FLOOR","MEDIUM","HIGH")
PLAY=posture("HIGH","HIGH","MEDIUM","HIGH","MEDIUM","FLOOR","LOW","MEDIUM","HIGH","FLOOR","LOW","HIGH")
ENT=posture("MEDIUM","MEDIUM","MEDIUM","MEDIUM","FLOOR","FLOOR","LOW","MEDIUM","HIGH","HIGH","LOW","FLOOR")
GROUP={"jwf":STRICT,"feedchildren":STRICT,"mermaid":STRICT,"openfarm":STRICT,"grubbly":STRICT,
 "lowes":MAIN,"kbb":MAIN,"nielsen":MAIN,"jeepdealer":MAIN,"hometap":MAIN,"stanley":MAIN,"turftank":MAIN,"waymaker":MAIN,"cinzia":MAIN,
 "reshline":PLAY,"goodrich":PLAY,"kopari":PLAY,"fitaumax":PLAY,"tattoo":PLAY,"furlife":PLAY,"integrityhome":MAIN,
 "hockeydrama":ENT,"deltaforce":ENT,"airplanecooking":ENT}
COLORS={"stanley":"#0f766e","jwf":"#6d28d9","lowes":"#004990","goodrich":"#44403c","hockeydrama":"#1e3a5f","kopari":"#0284c7","openfarm":"#166534","integrityhome":"#15803d","reshline":"#b45309","cinzia":"#65a30d","feedchildren":"#ea580c","nielsen":"#111827","kbb":"#1d4ed8","airplanecooking":"#0369a1","turftank":"#14532d","deltaforce":"#7f1d1d","mermaid":"#0e7490","tattoo":"#18181b","grubbly":"#3f6212","furlife":"#16a34a","hometap":"#1e40af","jeepdealer":"#991b1b","waymaker":"#155e75","fitaumax":"#44403c"}

def run(cmd):
    subprocess.run(cmd, check=True, capture_output=True, text=True)
def logo_svg(label, bg):
    size = 26 if len(label) <= 10 else 20
    esc = label.replace("&", "&amp;")
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 160 80">\n'
            f'  <rect width="160" height="80" rx="16" fill="{bg}"/>\n'
            f'  <text x="80" y="50" fill="#fff" font-family="Segoe UI, system-ui, sans-serif" '
            f'font-size="{size}" font-weight="700" text-anchor="middle">{esc}</text>\n</svg>\n')
POSTER_AT = {"stanley-jug": "8"}

def main():
    if SRC.exists(): shutil.rmtree(SRC)
    SRC.mkdir(parents=True)
    with zipfile.ZipFile(ZIP) as z: z.extractall(SRC)
    base = SRC / "creative_sample_50"
    posts = json.loads((ROOT / "data/posts.json").read_text())
    feed = [p["id"] for pg in posts["pages"] for p in pg]
    assert [r[0] for r in ROWS] == feed, "ROWS order must match feed"
    out_media = ROOT / "media/ads/real"; out_media.mkdir(parents=True, exist_ok=True)
    ads, answer_key, manifest, profiles = [], {}, [], {}
    for (post_id, fname, ad_id, bkey, brand, taghint, headline, body,
         cta, url, libid, decision, garm, note) in ROWS:
        src = base / fname
        assert src.exists(), f"missing {src}"
        ad = {"id": ad_id, "brand_key": bkey, "advertiser": brand,
              "headline": headline, "body": body, "cta": cta, "url": url,
              "tagline": f"Real ad · {taghint}", "sample_file": fname}
        if libid:
            ad["library_ad_id"] = libid
            ad["provenance"] = f"Real social ad · kai_ctr sample · Meta Ad Library #{libid}"
        else:
            ad["provenance"] = "Real social ad · kai_ctr creative_sample_50"
        if fname.endswith(".mp4"):
            dest = out_media / f"{ad_id}.mp4"
            run(["ffmpeg","-y","-loglevel","error","-i",str(src),
                 "-vf","scale='min(720,iw)':-2","-c:v","libx264","-preset","veryfast","-crf","28",
                 "-c:a","aac","-b:a","96k","-movflags","+faststart",str(dest)])
            poster = out_media / f"{ad_id}-poster.jpg"
            at = POSTER_AT.get(ad_id)
            if at:
                run(["ffmpeg","-y","-loglevel","error","-ss",at,"-i",str(src),
                     "-frames:v","1","-vf","scale='min(900,iw)':-2","-q:v","3",str(poster)])
            else:
                run(["ffmpeg","-y","-loglevel","error","-i",str(src),
                     "-vf","thumbnail,scale='min(900,iw)':-2","-frames:v","1","-q:v","3",str(poster)])
            ad["video"] = f"media/ads/real/{ad_id}.mp4"
            ad["image"] = f"media/ads/real/{ad_id}-poster.jpg"
        else:
            dest = out_media / f"{ad_id}.jpg"
            run(["magick",str(src),"-auto-orient","-resize","1200x1200>","-strip","-quality","82",str(dest)])
            ad["image"] = f"media/ads/real/{ad_id}.jpg"
        assert (ROOT / ad["image"]).stat().st_size > 8000, ad_id
        if "video" in ad: assert (ROOT / ad["video"]).stat().st_size > 50000, ad_id
        ads.append(ad)
        ent = {"decision": decision, "notes": note}
        if garm: ent["garm"] = garm
        answer_key[f"{post_id}__{ad_id}"] = ent
        manifest.append({"post_id": post_id, "sample_file": fname, "ad_id": ad_id,
                         "brand": brand, "library_ad_id": libid, "gold": ent})
        print(f"{ad_id:22s} {fname:18s} {'VIDEO' if 'video' in ad else 'IMAGE'} gold={decision}")
    for r in ROWS:
        bkey, brand = r[3], r[4]
        if bkey in profiles: continue
        (ROOT / f"media/brands/{bkey}.svg").write_text(logo_svg(brand.split("·")[0].strip(), COLORS[bkey]))
        profiles[bkey] = {"name": brand, "logo": f"media/brands/{bkey}.svg",
                          "color": COLORS[bkey], "bullets": [r[5]],
                          "risk_posture": GROUP[bkey]}
    (ROOT / "data/ads.json").write_text(json.dumps(ads, indent=1, ensure_ascii=False) + "\n")
    (ROOT / "data/answer_key.json").write_text(json.dumps(answer_key, indent=1, ensure_ascii=False) + "\n")
    (ROOT / "data/brand_profiles.json").write_text(
        json.dumps({"default": "lowes", "profiles": profiles}, indent=1, ensure_ascii=False) + "\n")
    (ROOT / "tools/sample50_manifest.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False) + "\n")
    nv = sum(1 for a in ads if "video" in a)
    print(f"\nwrote {len(ads)} ads ({len(ads)-nv} images + {nv} videos, all with real media), {len(profiles)} profiles")

if __name__ == "__main__":
    main()
