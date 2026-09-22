import os
import asyncio
import re
import requests
import base64
import time
import uuid
import zipfile
import random
from collections import defaultdict
import aiohttp
from pyrogram import Client, enums

# ================== GitHub-only configuration ==================
SESSION_STRING = os.environ.get("MY_SESSION_STRING", "").strip()
GITHUB_TOKEN = os.environ.get("MY_GITHUB_TOKEN", "").strip()
GITHUB_REPOSITORY = os.environ.get("GITHUB_REPOSITORY", "").strip()

if not SESSION_STRING:
    raise SystemExit("MY_SESSION_STRING is missing.")
if not GITHUB_TOKEN:
    raise SystemExit("MY_GITHUB_TOKEN is missing.")
if "/" not in GITHUB_REPOSITORY:
    raise SystemExit("GITHUB_REPOSITORY is missing or invalid.")

GITHUB_USER, REPO_NAME = GITHUB_REPOSITORY.split("/", 1)

MAX_FILE_SIZE_MB = 150
MIN_CHANNELS_REQUIRED = 300 

# ================== إعدادات السرعة القصوى (TURBO MODE) ==================
MAX_PARALLEL_DIALOGS = 5          
MAX_PARALLEL_FETCHES = 25         
MAX_PARALLEL_UPLOADS = 6          
HISTORY_LIMIT = 400               
FETCH_TIMEOUT = 30.0              
ALIVE_CHECK_SAMPLE = 5            

DIALOG_SEM = None  
FETCH_SEM = None
UPLOAD_SEM = None

TARGET_KEYWORDS = ["iptv", "m3u", "xtream", "mac", "portal", "sat", "tv", "server", "stb", "cccam", "streaming", "restream", "codes", "vip", "app"]

ADULT_WORDS = ["xxx", "porn", "adult", "adults", "sex", "18+", "+18", "erotic", "playboy", "amateur", "onlyfans", "brazzers", "vivid", "hustler", "penthouse", "babes", "realitykings", "naughty", "bangbros", "milf", "lesbian", "gay", "cam", "nsfw", "x-art", "babe", "pussy", "dick", "matures", "hardcore", "xnxx", "xvideos", "pornhub", "redtube", "kamasutra", "peep"]
ADULT_REGEX = re.compile(r'(?i)(?:' + '|'.join(map(re.escape, ADULT_WORDS)) + r')')
GROUP_TITLE_REGEX = re.compile(r'group-title="([^"]*)"')

# ============== نظام البحث الذكي الصارم (Strict Smart Sniper) ==============
SMART_ALIASES_REGEX = {
    "arab": re.compile(r'(?i)(\barab\w*|\bmena\b|\barb\b|\|ar\||\[ar\]|\bar\b|-ar-|^ar\s)'),
    "ar": re.compile(r'(?i)(\barab\w*|\bmena\b|\barb\b|\|ar\||\[ar\]|\bar\b|-ar-|^ar\s)'),
    "bein": re.compile(r'(?i)(\bbein\b|\bbe\s*in\b|\bbe-in\b)'),
    "bein sport": re.compile(r'(?i)(\bbein\s*sports?\b|\bbe\s*in\s*sports?\b)'),
    "fr": re.compile(r'(?i)(\bfrance\b|\bfrench\b|\bfr\b|\|fr\||\[fr\]|-fr-)'),
    "france": re.compile(r'(?i)(\bfrance\b|\bfrench\b|\bfr\b|\|fr\||\[fr\]|-fr-)'),
    "uk": re.compile(r'(?i)(\benglish\b|\beng\b|\buk\b|\|uk\||\[uk\]|-uk-)'),
    "en": re.compile(r'(?i)(\benglish\b|\beng\b|\ben\b|\|en\||\[en\]|-en-)')
}

def is_smart_match(keyword, g_name, extinf):
    kw = keyword.lower().strip()
    text_to_search = f" {g_name} {extinf} ".lower()
    
    if kw in SMART_ALIASES_REGEX:
        return bool(SMART_ALIASES_REGEX[kw].search(text_to_search))
        
    if len(kw) <= 2:
        return bool(re.search(r'\b' + re.escape(kw) + r'\b', text_to_search))
        
    parts = kw.split()
    return all(p in text_to_search for p in parts)
# ============================================================================

WARNING_TEXT = """<blockquote>⚠️ <b>ATTENTION / انتباه:</b>
Links are valid for <b>10 HOURS</b> from publishing, then they will be deleted automatically. Download them NOW!
مدة الروابط 10 ساعات فقط من وقت النشر ثم سيتم حذفها. يرجى التحميل أو النسخ الآن!</blockquote>\n\n"""

# ============== القالب الأصلي للروابط ==============
LINK_POST_CAPTION = """🔗 𝗗𝗜𝗥𝗘𝗖𝗧 𝗜𝗣𝗧𝗩 𝗟𝗜𝗡𝗞𝗦 🔗
🌍 𝗙𝗥𝗘𝗘 𝗜𝗣𝗧𝗩 𝗪𝗢𝗥𝗟𝗗 🌍

<blockquote>⚠️ <b>إبراء ذمة:</b>
نبرأ إلى الله من أي استخدام سيء أو الدخول لقنوات غير لائقة. 🤲</blockquote>

🚀 𝗛𝗶𝗴𝗵-𝗦𝗽𝗲𝗲𝗱 𝗟𝗶𝗻𝗸𝘀:
{links}

<blockquote>📊 𝗦𝗲𝗿𝘃𝗲𝗿 𝗗𝗲𝘁𝗮𝗶𝗹𝘀:
├ 📦 𝗖𝗼𝗻𝘁𝗲𝗻𝘁: Premium Channels & VODs
├ ⚡ 𝗙𝗼𝗿𝗺𝗮𝘁: M3U & Xtream Codes
├ ⚽️ 𝗦𝗽𝗼𝗿𝘁𝘀: beIN, SSC, Sky, TNT
├ 🎬 𝗠𝗼𝘃𝗶𝗲𝘀: Netflix, OSN, Disney+
└ 📱 𝗗𝗲𝘃𝗶𝗰𝗲𝘀: Smart TV, Android, iOS, PC

🌍 𝗪𝗼𝗿𝗹𝗱𝘄𝗶𝗱𝗲 𝗖𝗵𝗮𝗻𝗻𝗲𝗹𝘀 (𝗩𝗜𝗣):
🇩🇿 الجزائر | 🇲🇦 المغرب | 🇹🇳 تونس | 🇪🇬 مصر | 🇸🇦 السعودية | 🇦🇪 الإمارات
🇫🇷 France | 🇬🇧 UK | 🇺🇸 USA | 🇩🇪 Germany | 🇮🇹 Italy | 🇪🇸 Spain
🇨🇦 Canada | 🇳🇱 Netherlands | 🇧🇪 Belgium | 🇸🇪 Sweden | 🇨🇭 Swiss
🇹🇷 Türkiye |
... <b>And Many More!</b> 🔥</blockquote>

⚙️ 𝗛𝗼𝘄 𝘁𝗼 𝘂𝘀𝗲?
1️⃣ Copy the link above.
2️⃣ Open your IPTV Player (Smarters, Tivimate, VLC).
3️⃣ Select "Add Playlist / M3U URL".
4️⃣ Paste & Enjoy! 🍿

♻️ 𝘗𝘭𝘦𝘢𝘴𝘦 𝘚𝘩𝘢𝘳𝘦 & 𝘚𝘶𝘱𝘱𝘰𝘳𝘵 𝘜𝘴!"""

IMAGE_SIMPLE_CAPTION = """🌍 <b>𝗙𝗥𝗘𝗘 𝗜𝗣𝗧𝗩 𝗪𝗢𝗥𝗟𝗗</b> 🌍
━━━━━━━━━━━━━━━━━━

🔥 <b>{title}</b>

📦 عدد السيرفرات: <b>{count}</b>
⚡ الجودة: <b>4K / FHD / HD</b>
🛰️ التحديث: <b>{date}</b>

🎬 Movies • ⚽ Sports • 📺 Live TV
🌐 Worldwide Channels (VIP)

━━━━━━━━━━━━━━━━━━
👇 <i>الروابط في المنشور التالي</i> 👇"""

def safe_delete(filepath):
    try:
        if os.path.exists(filepath): os.remove(filepath)
    except: pass

async def is_link_working(url):
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=8)) as session:
            async with session.get(url, headers={'User-Agent': 'Mozilla/5.0'}) as response:
                return response.status == 200
    except: return False


def cleanup_old_github_files():
    api_url = f"https://api.github.com/repos/{GITHUB_USER}/{REPO_NAME}/contents/"
    headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
    try:
        resp = requests.get(api_url, headers=headers)
        if resp.status_code == 200:
            for file in resp.json():
                name = file.get("name", "")
                if name.startswith("FIW_") and name.endswith(".m3u"):
                    try:
                        if int(time.time()) - int(name.split("_")[1]) > 36000:
                            requests.delete(file.get("url"), json={"message": f"Auto-delete: {name}", "sha": file.get("sha")}, headers=headers)
                    except: continue
    except: pass

async def upload_to_cloud(filename, selected_api="github"):
    if selected_api != "github" or not os.path.exists(filename) or os.path.getsize(filename) == 0:
        return None

    size_mb = os.path.getsize(filename) / (1024 * 1024)
    if size_mb > 95:
        print(f"GitHub upload skipped: {filename} is {size_mb:.1f} MB.")
        return None

    base_name = os.path.basename(filename)
    safe_name = f"FIW_{int(time.time())}_{uuid.uuid4().hex[:6]}_{base_name}"
    api_url = f"https://api.github.com/repos/{GITHUB_USER}/{REPO_NAME}/contents/{safe_name}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }

    for attempt in range(1, 3):
        try:
            cleanup_old_github_files()
            with open(filename, "rb") as f:
                encoded_content = base64.b64encode(f.read()).decode("utf-8")
            payload = {
                "message": f"Auto Upload {safe_name}",
                "content": encoded_content
            }
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=90)) as session:
                async with session.put(api_url, json=payload, headers=headers) as response:
                    if response.status in [200, 201]:
                        return f"https://raw.githubusercontent.com/{GITHUB_USER}/{REPO_NAME}/main/{safe_name}"
                    print(f"GitHub upload failed: HTTP {response.status}")
        except Exception as e:
            print(f"GitHub upload attempt {attempt} failed: {e}")
        await asyncio.sleep(attempt * 2)
    return None

async def upload_to_cloud_sem(filename, selected_api="github"):
    global UPLOAD_SEM
    if UPLOAD_SEM is None:
        return await upload_to_cloud(filename, selected_api)
    async with UPLOAD_SEM:
        return await upload_to_cloud(filename, selected_api)

def analyze_file(filepath):
    groups = defaultdict(list)
    seen_urls_hashes = set()
    total, adult, live, vod, series = 0, 0, 0, 0, 0
    current_extinf = ""
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#EXTM3U"): continue
            if line.startswith("#EXTINF"): current_extinf = line
            elif line.startswith("#"):
                if current_extinf: current_extinf += "\n" + line
            else:
                if current_extinf:
                    url = line
                    total += 1
                    match = GROUP_TITLE_REGEX.search(current_extinf)
                    group = match.group(1) if match else "Unknown"
                    is_adult = bool(ADULT_REGEX.search(current_extinf)) or bool(ADULT_REGEX.search(url)) or bool(ADULT_REGEX.search(group))
                    if is_adult: adult += 1
                    else:
                        url_hash = hash(url)
                        if url_hash not in seen_urls_hashes:
                            seen_urls_hashes.add(url_hash)
                            groups[group].append((current_extinf, url, False))
                            
                            g_lower = group.lower()
                            if 'vod' in g_lower or 'movie' in g_lower or 'film' in g_lower or 'افلام' in g_lower or 'أفلام' in g_lower:
                                vod += 1
                            elif 'series' in g_lower or 'serie' in g_lower or 'مسلسلات' in g_lower:
                                series += 1
                            else:
                                live += 1
                                
                    current_extinf = ""
    clean_groups = defaultdict(list)
    for g_name, entries in groups.items():
        if not bool(ADULT_REGEX.search(g_name)): clean_groups[g_name] = entries
    return clean_groups, total, adult, live, vod, series

async def analyze_async(filepath): return await asyncio.to_thread(analyze_file, filepath)

def get_clean_size_mb(groups):
    size_bytes = len("#EXTM3U\r\n")
    for g in groups.values():
        for extinf, url, _ in g:
            size_bytes += len(extinf.replace('\n', '\r\n').encode('utf-8')) + len(url.encode('utf-8')) + 4
    return size_bytes / (1024 * 1024)

def write_m3u_and_get_count(groups, filename):
    count = 0
    with open(filename, "w", encoding="utf-8-sig") as f:
        f.write("#EXTM3U\r\n")
        for g in groups.keys():
            for extinf, url, _ in groups[g]:
                extinf_fixed = extinf.replace('\n', '\r\n')
                if ',' in extinf_fixed:
                    parts = extinf_fixed.rsplit(',', 1)
                    if "FREE IPTV WORLD" not in parts[1]: extinf_branded = f"{parts[0]},{parts[1]} | 🌟 FREE IPTV WORLD 🌟"
                    else: extinf_branded = extinf_fixed
                else: extinf_branded = extinf_fixed
                f.write(extinf_branded + "\r\n" + url + "\r\n")
                count += 1
    return count

def compress_if_large(filename):
    if not os.path.exists(filename): return filename
    if os.path.getsize(filename) / (1024 * 1024) > MAX_FILE_SIZE_MB:
        zip_filename = filename.replace(".m3u", ".zip")
        with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf: zipf.write(filename, os.path.basename(filename))
        return zip_filename
    return filename

async def is_playlist_alive(groups):
    all_valid_urls = [curl for g in groups.values() for _, curl, _ in g if curl.lower().startswith("http")]
    if not all_valid_urls: return False
    test_urls = random.sample(all_valid_urls, min(ALIVE_CHECK_SAMPLE, len(all_valid_urls)))
    headers = {"User-Agent": "TiviMate/4.7.0 (Linux; Android 11)"}
    async with aiohttp.ClientSession(headers=headers, timeout=aiohttp.ClientTimeout(sock_connect=2, sock_read=3)) as session:
        async def check(url):
            try:
                async with session.get(url, allow_redirects=True) as resp:
                    if resp.status in [200, 206, 301, 302, 307]:
                        chunk = await resp.content.read(256)
                        if chunk and b"<html>" not in chunk.lower() and b"<!doctype" not in chunk.lower(): return True
            except: pass
            return False
        results = await asyncio.gather(*[check(u) for u in test_urls])
        return any(results)

async def fetch_and_analyze(session, url, idx):
    global FETCH_SEM
    async def _fetch():
        try:
            async with session.get(url, headers={"User-Agent": "Mozilla/5.0"}, allow_redirects=True) as response:
                if response.status in [200, 206]:
                    temp = f"temp_{uuid.uuid4().hex}.m3u"
                    with open(temp, 'wb') as f:
                        async for chunk in response.content.iter_chunked(4 * 1024 * 1024):
                            f.write(chunk)
                    groups, total, adult, live, vod, series = await analyze_async(temp)
                    safe_delete(temp)
                    if total < MIN_CHANNELS_REQUIRED or not await is_playlist_alive(groups): return {"id": idx, "success": False}
                    return {"id": idx, "groups": groups, "total": total, "size_mb": get_clean_size_mb(groups), "live": live, "vod": vod, "series": series, "success": True}
        except: pass
        return {"id": idx, "success": False}

    try:
        if FETCH_SEM is not None:
            async with FETCH_SEM:
                return await asyncio.wait_for(_fetch(), timeout=FETCH_TIMEOUT)
        return await asyncio.wait_for(_fetch(), timeout=FETCH_TIMEOUT)
    except: return {"id": idx, "success": False}

async def extract_urls_from_chat(app, chat_id_pyro, limit=HISTORY_LIMIT):
    urls = set()
    try:
        async for msg in app.get_chat_history(chat_id_pyro, limit=limit):
            text = str(msg.text or msg.caption or "")
            if not text:
                continue
            found = re.findall(r'(https?://[^\s]+)', text)
            for u in found:
                lu = u.lower()
                if 'm3u' in lu or 'get.php' in lu:
                    urls.add(u)
    except:
        pass
    return urls

# ================== 1. دالة الصيد التلقائي والموازي (TURBO) ==================
if __name__ == "__main__":
    asyncio.run(main())

# ================== GitHub-only execution ==================

async def github_hunt(keyword="", target_count=5):
    app = Client(
        "github_iptv_scraper",
        api_id=24974564,
        api_hash="b87511de89b42178862e13e84147952b",
        session_string=SESSION_STRING
    )
    await app.start()
    found_count = 0
    tested_urls = set()
    connector = aiohttp.TCPConnector(limit=100, limit_per_host=20, ttl_dns_cache=300, use_dns_cache=True)

    try:
        async with aiohttp.ClientSession(connector=connector) as session_req:
            target_chats = []
            async for dialog in app.get_dialogs():
                chat = dialog.chat
                if chat.type not in [enums.ChatType.CHANNEL, enums.ChatType.SUPERGROUP, enums.ChatType.GROUP]:
                    continue
                chat_name = chat.title or str(chat.id)
                if any(kw in chat_name.lower() for kw in TARGET_KEYWORDS):
                    target_chats.append((chat.id, chat_name))

            async def process_chat(chat_id, chat_name):
                nonlocal found_count
                if found_count >= target_count:
                    return

                async with DIALOG_SEM:
                    urls = await extract_urls_from_chat(app, chat_id, HISTORY_LIMIT)
                    urls = [u for u in urls if u not in tested_urls]
                    tested_urls.update(urls)
                    if not urls:
                        return

                    results = await asyncio.gather(*[
                        fetch_and_analyze(session_req, u, i)
                        for i, u in enumerate(urls)
                    ])

                    for res in results:
                        if found_count >= target_count or not res.get("success"):
                            continue

                        groups = res["groups"]
                        if keyword:
                            filtered = defaultdict(list)
                            for g_name, entries in groups.items():
                                for extinf, curl, _ in entries:
                                    if is_smart_match(keyword, g_name, extinf):
                                        filtered[g_name].append((extinf, curl, False))
                            groups = filtered

                        if not groups:
                            continue

                        fname = f"Hunter_{uuid.uuid4().hex[:4].upper()}.m3u"
                        write_m3u_and_get_count(groups, fname)
                        final_file = compress_if_large(fname)
                        link = await upload_to_cloud_sem(final_file, "github")
                        safe_delete(fname)
                        if final_file != fname:
                            safe_delete(final_file)

                        if link:
                            found_count += 1
                            print(f"GitHub published: {link}")

            await asyncio.gather(*[
                process_chat(cid, name) for cid, name in target_chats
            ])
    finally:
        await app.stop()

    print(f"Done: {found_count}/{target_count} published to GitHub.")
    return found_count


async def github_hunttxt(keyword="", target_count=5):
    app = Client(
        "github_iptv_scraper",
        api_id=24974564,
        api_hash="b87511de89b42178862e13e84147952b",
        session_string=SESSION_STRING
    )
    await app.start()
    found = []
    tested_urls = set()
    connector = aiohttp.TCPConnector(limit=100, limit_per_host=20, ttl_dns_cache=300, use_dns_cache=True)

    try:
        async with aiohttp.ClientSession(connector=connector) as session_req:
            target_chats = []
            async for dialog in app.get_dialogs():
                chat = dialog.chat
                if chat.type not in [enums.ChatType.CHANNEL, enums.ChatType.SUPERGROUP, enums.ChatType.GROUP]:
                    continue
                chat_name = chat.title or str(chat.id)
                if any(kw in chat_name.lower() for kw in TARGET_KEYWORDS):
                    target_chats.append((chat.id, chat_name))

            async def process_chat(chat_id, chat_name):
                nonlocal found
                if len(found) >= target_count:
                    return

                async with DIALOG_SEM:
                    urls = await extract_urls_from_chat(app, chat_id, HISTORY_LIMIT)
                    urls = [u for u in urls if u not in tested_urls]
                    tested_urls.update(urls)
                    if not urls:
                        return

                    results = await asyncio.gather(*[
                        fetch_and_analyze(session_req, u, i)
                        for i, u in enumerate(urls)
                    ])

                    for res in results:
                        if len(found) >= target_count or not res.get("success"):
                            continue

                        groups = res["groups"]
                        if keyword:
                            filtered = defaultdict(list)
                            for g_name, entries in groups.items():
                                for extinf, curl, _ in entries:
                                    if is_smart_match(keyword, g_name, extinf):
                                        filtered[g_name].append((extinf, curl, False))
                            groups = filtered

                        if not groups:
                            continue

                        fname = f"Hunter_{uuid.uuid4().hex[:4].upper()}.m3u"
                        write_m3u_and_get_count(groups, fname)
                        final_file = compress_if_large(fname)
                        link = await upload_to_cloud_sem(final_file, "github")
                        safe_delete(fname)
                        if final_file != fname:
                            safe_delete(final_file)

                        if link:
                            found.append(link)
                            print(f"GitHub published: {link}")

            await asyncio.gather(*[
                process_chat(cid, name) for cid, name in target_chats
            ])
    finally:
        await app.stop()

    txt_filename = f"Cloud_Links_{len(found)}_{uuid.uuid4().hex[:4]}.txt"
    with open(txt_filename, "w", encoding="utf-8") as f:
        f.write("\n".join(found))
    link = await upload_to_cloud_sem(txt_filename, "github")
    safe_delete(txt_filename)
    print(f"GitHub link index published: {link}")
    return link


async def github_scrape(target_count=100):
    app = Client(
        "github_iptv_scraper",
        api_id=24974564,
        api_hash="b87511de89b42178862e13e84147952b",
        session_string=SESSION_STRING
    )
    await app.start()
    all_links = set()

    try:
        async def scrape_chat(chat_id):
            async with DIALOG_SEM:
                all_links.update(await extract_urls_from_chat(app, chat_id, HISTORY_LIMIT))

        chat_ids = []
        async for dialog in app.get_dialogs():
            chat = dialog.chat
            if chat.type in [enums.ChatType.CHANNEL, enums.ChatType.SUPERGROUP, enums.ChatType.GROUP]:
                chat_ids.append(chat.id)

        await asyncio.gather(*[scrape_chat(cid) for cid in chat_ids])
    finally:
        await app.stop()

    final_links = list(all_links)[:target_count]
    filename = f"Scraped_{len(final_links)}.txt"
    with open(filename, "w", encoding="utf-8") as f:
        f.write("\n".join(final_links))
    link = await upload_to_cloud_sem(filename, "github")
    safe_delete(filename)
    print(f"GitHub scrape result published: {link}")
    return link


async def main():
    global DIALOG_SEM, FETCH_SEM, UPLOAD_SEM
    DIALOG_SEM = asyncio.Semaphore(MAX_PARALLEL_DIALOGS)
    FETCH_SEM = asyncio.Semaphore(MAX_PARALLEL_FETCHES)
    UPLOAD_SEM = asyncio.Semaphore(MAX_PARALLEL_UPLOADS)

    action = os.environ.get("ACTION", "hunt").strip().lower()
    keyword = os.environ.get("KEYWORD", "").strip()
    try:
        count = max(1, int(os.environ.get("COUNT", "5")))
    except ValueError:
        count = 5

    if action == "hunt":
        await github_hunt(keyword, count)
    elif action == "hunttxt":
        await github_hunttxt(keyword, count)
    elif action == "scrape":
        await github_scrape(count)
    else:
        raise SystemExit(f"Unsupported ACTION: {action}")


if __name__ == "__main__":
    asyncio.run(main())
