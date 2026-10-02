from telethon import TelegramClient, events
import asyncio
import os
import re
import json
import base64
import requests
import time
import threading
from datetime import datetime
from urllib.parse import quote, urlparse
import aiohttp

# ================= INADINA TV YAYIN AYARLARI =================
# Bot, güncel platform deposuna ve aşağıdaki yayın adreslerine bağlanır.
REPO_NAME = "inadinatv/inadinatv-platform"
BRANCH = "main"
GITHUB_PAGES_URL = "https://inadinatv.github.io/inadinatv-platform/"
VERCEL_URL = "https://iptvbot-t6zv.vercel.app/"
SITE_URL = VERCEL_URL

# IPTV ARAÇLAR / AppCreator24 deep-link eşleştirmeleri.
# rectv şablonundaki menü ile aynı tutulmalıdır.
YAN_DNS_TOOLS = {
    "panel": {"label": 'Yan DNS Tarama "PANEL"', "go": "go:dns"},
    "user_pass": {"label": 'Yan DNS Tarama "USER:PAS"', "go": "go:dns2"},
    "m3u_link": {"label": 'Yan DNS Tarama "M3U LİNK"', "go": "go:yan3"},
}
# ==============================================================

# ================= GÜVENLİ AYARLAR =================
# Öncelik: ortam değişkeni > bot_config.json. bot_config.json GitHub'a gönderilmez.
_CONFIG_CANDIDATES = [
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "bot_config.json"),
    os.path.join(os.getcwd(), "bot_config.json"),
    "/storage/emulated/0/Download/bot_config.json",
    "/storage/emulated/0/Download/InadinaTV/bot_config.json",
    "/storage/emulated/0/InadinaTV/bot_config.json",
]
_PRIVATE_CONFIG = {}
_PRIVATE_CONFIG_PATH = ""
for _candidate in _CONFIG_CANDIDATES:
    try:
        with open(_candidate, "r", encoding="utf-8") as _f:
            _loaded = json.load(_f)
        if isinstance(_loaded, dict):
            _PRIVATE_CONFIG = _loaded
            _PRIVATE_CONFIG_PATH = _candidate
            break
    except (OSError, ValueError, TypeError):
        continue

def _setting(name, default=""):
    return os.getenv(name) or str(_PRIVATE_CONFIG.get(name, default))

GITHUB_TOKEN = _setting("GITHUB_TOKEN").strip()
ADMIN_PASSWORD = _setting("ADMIN_PASSWORD").strip()
TG_BOT_TOKEN = _setting("TG_BOT_TOKEN").strip()
TG_CHAT_ID = _setting("TG_CHAT_ID").strip()
try:
    API_ID = int(_setting("TELEGRAM_API_ID", "0") or 0)
except (TypeError, ValueError):
    API_ID = 0
API_HASH = _setting("TELEGRAM_API_HASH").strip()
AY_LIVE_API_KEY = _setting("AY_LIVE_API_KEY").strip()
if not API_ID or not API_HASH:
    raise RuntimeError(
        "Telegram API ayarı eksik. Pydroid'de bot_config.json dosyasını "
        "bot.py ile aynı klasöre veya /storage/emulated/0/Download/ klasörüne koyun; "
        "TELEGRAM_API_ID ve TELEGRAM_API_HASH alanlarını doldurun."
    )
# =================================================

# ================= INADINA TV TELEGRAM =================
BENIM_KANALIM = _setting("TG_CHANNEL", "inadinatv2").strip()
INADINATV_APK_LINK = _setting("INADINATV_APK_LINK", "https://t.me/inadinatv2/227").strip()
# =====================================================

os.environ['PYDROID_KEEP_SCREEN_ON'] = '1'

class IPTV_Bot_Pro:
    def __init__(self):
        print("\n╔══════════════════════════════════════╗")
        print("║   KİMLİK SEÇİMİ (ÇAKIŞMA ÖNLEYİCİ)   ║")
        print("╠══════════════════════════════════════╣")
        print("║ 1. ARKADAŞIN HESABI (Termux İçin)    ║")
        print("║    -> Sadece Gizli Grubu Dinler      ║")
        print("║ 2. KENDİ HESABIM (Pydroid İçin)      ║")
        print("║    -> Kendi Gruplarınızı Dinler      ║")
        print("╚══════════════════════════════════════╝")
        sec = input("  [?] Lütfen seçin (1 veya 2): ").strip()
        
        if sec == '1':
            self.session_name = "arkadas_oturum_2"
            self.hedef_gruplar = ["3977132631"]
            self.hedef_kanallar = []
            self.dinle_profesor = True
            print("\n  => AKTİF: Arkadaş Modu. Sadece gizli grup dinleniyor...")
        else:
            self.session_name = "benim_kendi_oturum"
            self.hedef_gruplar = [ "3657374256","2574341984"]
            self.hedef_kanallar = ["warsiptvpaylasim", "gelsindosyalar"]
            self.dinle_profesor = False
            print("\n  => AKTİF: Kendi Modunuz. Kendi gruplarınız dinleniyor...")
            
        time.sleep(2)

        self.html_output_subdir = "rectv"
        self.save_filename = "ozel_iptv_listem.json"
        self.max_list_limit = 300 
        self.default_icon_url = "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcS4yG_juMJsuYS1fMI3WD6l6yqJTAo80TL3k6NqS2G63PIwAxwarsjUuTE&s=10"
        self.api_key = AY_LIVE_API_KEY
        self.base_api_url = "https://ay.live/api/"
        self.telegram_link = f"https://t.me/{BENIM_KANALIM}"
        self.firebase_livescore_url = os.getenv("FIREBASE_LIVESCORE_URL", "https://iptvbotcoun-default-rtdb.firebaseio.com/extras/livescore.json").strip()

        if os.path.exists("/storage/emulated/0/Download"):
            self.download_path = "/storage/emulated/0/Download"
        else:
            self.download_path = os.path.dirname(os.path.abspath(__file__))

        self.save_filepath = os.path.join(self.download_path, self.save_filename)
        self.toplama_txt_path = os.path.join(self.download_path, "Telegram", "toplama.txt")
        
        if os.path.exists("/storage/emulated/0"):
            self.toplama_txt_path2 = "/storage/emulated/0/combo/toplama.txt"
            self.servers_txt_path = "/storage/emulated/0/InadinaTV/servers.txt"
        else:
            self.toplama_txt_path2 = os.path.join(os.path.dirname(os.path.abspath(__file__)), "combo", "toplama.txt")
            self.servers_txt_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "InadinaTV", "servers.txt")
            
        self.custom_iptv_list = []
        self.paste_lock = asyncio.Lock()
        
        self.load_from_file()
        
        session_file_path = os.path.join(self.download_path, self.session_name)
        self.client = TelegramClient(
            session_file_path,
            API_ID,
            API_HASH,
            connection_retries=-1,
            retry_delay=5,
            auto_reconnect=True,
        )
        self.client.add_event_handler(self.telegram_handler, events.NewMessage())

    def load_from_file(self):
        loaded_locally = False
        if os.path.exists(self.save_filepath):
            try:
                with open(self.save_filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if data and isinstance(data, list) and len(data) > 0:
                        self.custom_iptv_list = data
                        loaded_locally = True
            except: 
                pass

        if not loaded_locally:
            print("\n ⚠️ Lokal dosya boş veya eksik! GitHub'daki sağlam yedek indiriliyor...")
            try:
                url = f"https://api.github.com/repos/{REPO_NAME}/contents/{self.save_filename}?ref={BRANCH}"
                headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
                res = requests.get(url, headers=headers)
                if res.status_code == 200:
                    content_base64 = res.json().get("content", "")
                    content_str = base64.b64decode(content_base64).decode("utf-8")
                    self.custom_iptv_list = json.loads(content_str)
                    with open(self.save_filepath, "w", encoding="utf-8") as f:
                        json.dump(self.custom_iptv_list, f, indent=4, ensure_ascii=False)
                    print(" ✅ Yedek başarıyla telefona geri yüklendi!\n")
                else:
                    self.custom_iptv_list = []
            except Exception as e:
                print(f" [!] GitHub'dan kurtarma hatası: {e}")
                self.custom_iptv_list = []

    def shorten_url(self, long_url):
        if not long_url or long_url == "#": return "#"
        # Reklamsız istendiği için kısaltma işlemini iptal ettik, orijinal adresi döndürüyoruz
        return long_url

    def github_push(self, content_str, github_path):
        """GitHub Contents API'ye güvenli yazım; çakışmada SHA'yı yenileyip tekrar dener."""
        url = f"https://api.github.com/repos/{REPO_NAME}/contents/{github_path}"
        headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
        content_base64 = base64.b64encode(content_str.encode("utf-8")).decode("utf-8")
        for attempt in range(1, 4):
            try:
                res = requests.get(url, headers=headers, timeout=30)
                if res.status_code not in (200, 404):
                    print(f" [!] GitHub SHA okunamadı ({github_path}): HTTP {res.status_code}")
                    time.sleep(attempt)
                    continue
                sha = res.json().get("sha") if res.status_code == 200 else None
                data = {"message": f"Bot Sync: {datetime.now().strftime('%H:%M:%S')}", "content": content_base64, "branch": BRANCH}
                if sha: data["sha"] = sha
                put = requests.put(url, headers=headers, json=data, timeout=45)
                if put.status_code in (200, 201):
                    print(f" [V] GitHub Senkronize: {github_path}")
                    return True
                print(f" [!] GitHub yazma hatası ({github_path}): HTTP {put.status_code} (deneme {attempt}/3)")
                if put.status_code not in (409, 422):
                    print(f"     Ayrıntı: {put.text[:240]}")
                    return False
                time.sleep(attempt)
            except Exception as e:
                print(f" [!] GitHub bağlantı hatası ({github_path}, deneme {attempt}/3): {e}")
                time.sleep(attempt)
        print(f" [!] GitHub senkronizasyonu başarısız: {github_path}")
        return False

    def save_and_sync(self):
        if len(self.custom_iptv_list) > self.max_list_limit:
            silinen_sayi = len(self.custom_iptv_list) - self.max_list_limit
            self.custom_iptv_list = self.custom_iptv_list[:self.max_list_limit]
            print(f"🧹 Sistem Optimize Edildi: Limiti aşan en eski {silinen_sayi} IPTV kaydı silindi!")

        with open(self.save_filepath, "w", encoding="utf-8") as f:
            json.dump(self.custom_iptv_list, f, indent=4, ensure_ascii=False)
        json_str = json.dumps(self.custom_iptv_list, indent=4, ensure_ascii=False)
        self.github_push(json_str, self.save_filename)
        self.generate_iptv_html()

    def save_unique_lines(self, file_path, new_lines):
        existing_lines = set()
        try:
            if os.path.exists(file_path):
                with open(file_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            existing_lines.add(line)
            eklenecek_satirlar = new_lines - existing_lines
            if eklenecek_satirlar:
                os.makedirs(os.path.dirname(file_path), exist_ok=True)
                with open(file_path, "a", encoding="utf-8") as f:
                    for satir in eklenecek_satirlar:
                        f.write(f"{satir}\n")
        except Exception as e:
            print(f" [!] Kayıt hatası ({file_path}): {e}")

    async def check_iptv_link(self, session, link):
        default_resp = {
            "url": link,
            "durum": "Bilinmiyor",
            "son_kullanma": "Belirsiz",
            "kalan_sure": "?",
            "paket": "STANDART",
            "baglanti_aktif": "-",
            "baglanti_max": "-"
        }
        
        match = re.search(r'(https?://[^/]+).*?username=([^&]+).*?password=([^&\s]+)', link, re.IGNORECASE)
        
        if not match: 
            default_resp["durum"] = "Normal Link (Xtream Değil)"
            return default_resp 
            
        host, user, pwd = match.groups()
        api_url = f"{host.strip()}/player_api.php?username={user.strip()}&password={pwd.strip()}"
        
        headers = {
            "User-Agent": "Mozilla/5.0 (SmartHub; SMART-TV; U; Linux/SmartTV) AppleWebKit/531.2+ (KHTML, like Gecko) WebBrowser/1.0 SmartTV Widget/255",
            "Accept": "application/json, text/plain, */*"
        }
        
        try:
            async with session.get(api_url, headers=headers, timeout=5, allow_redirects=True) as resp:
                if resp.status != 200:
                    default_resp["durum"] = "Sunucu Yanıt Vermedi (Ölü)"
                    return default_resp
                    
                text = await resp.text()
                try: 
                    data = json.loads(text)
                except: 
                    default_resp["durum"] = "Hatalı Veri (JSON Değil)"
                    return default_resp

                if "user_info" not in data:
                    default_resp["durum"] = "Geçersiz Xtream Paneli"
                    return default_resp

                ui = data["user_info"]
                
                if str(ui.get("auth", "0")) == "0":
                    default_resp["durum"] = "Yanlış Kullanıcı Adı / Şifre"
                    return default_resp
                    
                status = str(ui.get("status", "")).lower()
                if status != "active":
                    default_resp["durum"] = f"Hesap {status.upper()}"
                    return default_resp
                    
                exp = ui.get("exp_date")
                son_kullanma = "Sınırsız"
                kalan_sure = "Sınırsız"
                
                if exp and str(exp) not in ["0", "", "null"]:
                    try:
                        exp_dt = datetime.fromtimestamp(int(exp))
                        kalan = (exp_dt - datetime.now()).days
                        
                        if kalan < 0:
                            default_resp["durum"] = "Süresi Dolmuş Hesap"
                            return default_resp
                            
                        son_kullanma = exp_dt.strftime('%d.%m.%Y %H:%M:%S')
                        kalan_sure = f"{kalan} Gün"
                    except:
                        pass 
                
                return {
                    "url": link,
                    "durum": "Aktif VIP",
                    "son_kullanma": son_kullanma,
                    "kalan_sure": kalan_sure,
                    "paket": "PREMIUM",
                    "baglanti_aktif": str(ui.get("active_cons", "0")),
                    "baglanti_max": str(ui.get("max_connections", "Sınırsız"))
                }
        except Exception as e:
            default_resp["durum"] = "Bağlantı Hatası / Zaman Aşımı"
            return default_resp 

    async def telegram_handler(self, event):
        chat = await event.get_chat()
        chat_title = getattr(chat, 'title', '')
        chat_username = getattr(chat, 'username', '')

        hedef_mi = (
            any(str(event.chat_id).endswith(gid) for gid in self.hedef_gruplar) or 
            (chat_username and any(chat_username.lower() == kanal.lower() for kanal in self.hedef_kanallar)) or
            (self.dinle_profesor and "profesör" in chat_title.lower())
        )

        if not hedef_mi: return

        zaman = datetime.now().strftime('%d.%m.%Y %H:%M:%S')
        mesaj = event.raw_text or ""
        dosya_metni = ""

        if getattr(event.message, 'file', None) and event.message.file.name and event.message.file.name.lower().endswith('.txt'):
            try:
                print(f"📥 [{zaman}] [{chat_title}] grubunda TXT dosyası tespit edildi, okunuyor...")
                dosya_byte = await asyncio.wait_for(event.message.download_media(file=bytes), timeout=30.0)
                dosya_metni = dosya_byte.decode('utf-8', errors='ignore')
            except asyncio.TimeoutError:
                print(f"❌ Ağ hatası: İnternet koptuğu için TXT dosyası indirilemedi (Zaman Aşımı)!")
            except Exception as e: 
                print(f"❌ Dosya okuma hatası: {e}")

        tam_metin = f"{mesaj}\n{dosya_metni}"

        if tam_metin and "http" in tam_metin.lower():
            tum_linkler = re.findall(r'(https?://[^\s\"\'<>]+)', tam_metin)
            
            temiz_linkler = []
            for l in tum_linkler:
                l = l.rstrip(',;.\n\r')
                if "username=" in l.lower() and "password=" in l.lower():
                    temiz_linkler.append(l)
                    
            iptv_linkleri = list(set(temiz_linkler))
            
            if iptv_linkleri:
                link_sayisi = len(iptv_linkleri)
                kisaltilmis_link = None
                kaynak = chat_title if chat_title else (chat_username if chat_username else "Bilinmeyen Grup")
                
                print(f"\n⏳ [{zaman}] [{kaynak}] - {link_sayisi} Link Yakalandı. FİLTRESİZ Modda Taranıyor...")

                print(f"🔍 Combo (User:Pass) ve Sunucu listesi çıkartılıyor...")
                userpass_set = set()
                server_set = set()
                for link in iptv_linkleri:
                    user_match = re.search(r'username=([^&\s]+)', link, re.IGNORECASE)
                    pass_match = re.search(r'password=([^&\s]+)', link, re.IGNORECASE)
                    if user_match and pass_match: 
                        userpass_set.add(f"{user_match.group(1)}:{pass_match.group(1)}")
                    
                    host_match = re.search(r'(https?://[^/]+)', link, re.IGNORECASE)
                    if host_match: 
                        server_set.add(host_match.group(1))

                if userpass_set:
                    self.save_unique_lines(self.toplama_txt_path, userpass_set)
                    self.save_unique_lines(self.toplama_txt_path2, userpass_set)
                if server_set:
                    self.save_unique_lines(self.servers_txt_path, server_set)
                    
                print(f"✅ BİLGİ KAYDEDİLDİ -> Combo: {len(userpass_set)} Adet | Sunucu: {len(server_set)} Adet")

                parsed_links = []
                
                async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as api_sess:
                    tasks = [self.check_iptv_link(api_sess, l) for l in iptv_linkleri]
                    results = await asyncio.gather(*tasks)
                    for res in results:
                        parsed_links.append(res)
                            
                if not parsed_links:
                    print("❌ Link yakalanamadı!")
                    return
                
                print(f"✅ Tarama tamamlandı! {len(parsed_links)} linkin tamamı sisteme dahil ediliyor...")

                domain_info = {}
                for item in parsed_links:
                    link = item['url']
                    try:
                        parsed = urlparse(link)
                        domain = parsed.netloc.split(':')[0].replace('www.', '')
                        if '.' in domain: domain = domain.rsplit('.', 1)[0]
                        if not domain: domain = "Bilinmeyen_Sunucu"
                    except: domain = "Bilinmeyen_Sunucu"
                    
                    if domain not in domain_info: domain_info[domain] = {'count': 1, 'first_link': link}
                    else: domain_info[domain]['count'] += 1

                print(f"⏳ Liste Telegra.ph'a yükleniyor (Reklamsız aktarım)...")

                try:
                    async with self.paste_lock:
                        await asyncio.sleep(2) 
                        timeout_ayar = aiohttp.ClientTimeout(total=60)
                        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False), timeout=timeout_ayar) as session:
                            
                            paste_url = None
                            
                            # --- 1. Telegra.ph API'sine Yükleme (SAYFALAMA SİSTEMİ) ---
                            try:
                                if not hasattr(self, 'telegraph_token') or not self.telegraph_token:
                                    account_payload = {"short_name": "InAdina TV", "author_name": "InAdina TV"}
                                    acc_resp = await session.post("https://api.telegra.ph/createAccount", json=account_payload)
                                    acc_data = await acc_resp.json()
                                    if acc_data.get("ok"):
                                        self.telegraph_token = acc_data["result"]["access_token"]
                                
                                if getattr(self, 'telegraph_token', None):
                                    CHUNK_SIZE = 100 
                                    chunks = [parsed_links[i:i + CHUNK_SIZE] for i in range(0, len(parsed_links), CHUNK_SIZE)]
                                    next_page_url = None
                                    
                                    for i, chunk in enumerate(reversed(chunks)):
                                        page_number = len(chunks) - i
                                        
                                        govde_satirlari = []
                                        for item in chunk:
                                            satir = []
                                            satir.append("╭─➤ ⚡✨ İNADİNA TV ✨⚡")
                                            satir.append(f"├─ Durum ➤ {item['durum']}")
                                            satir.append(f"├─ Bitiş Tarihi ➤ {item['son_kullanma']}")
                                            satir.append(f"├─ Kalan Gün ➤ {item['kalan_sure']}")
                                            satir.append(f"├─ Paket ➤ {item['paket']}")
                                            satir.append(f"├─ Aktif Bağlantılar ➤ {item['baglanti_aktif']}")
                                            satir.append(f"├─ Maksimum Bağlantılar ➤ {item['baglanti_max']}")
                                            satir.append("╰─➤ ⚡✨ İNADİNA TV ✨⚡")
                                            satir.append(f"●➤ {item['url']}")
                                            govde_satirlari.append("\n".join(satir))
                                        
                                        linkler_govde = "\n\n".join(govde_satirlari)
                                        
                                        sayfa_basligi = f"InAdina TV Liste - {zaman}"
                                        if len(chunks) > 1:
                                            sayfa_basligi += f" (Part {page_number}/{len(chunks)})"
                                            
                                        telegraph_baslik = (
                                            "╔══════════════════════════════════════════════════════╗\n"
                                            "║    🌟 İNADINA TV - SINIRLARI KALDIR! 🌟          ║\n"
                                            "╚══════════════════════════════════════════════════════╝\n\n"
                                            "📢 KESİNTİSİZ VIP YAYINLAR VE DAHA FAZLASI İÇİN;\n"
                                            "🔥 Hemen Telegram Kanalımıza Katılın: https://t.me/inadinatv2\n"
                                            "🚀 Her gün güncel, limitsiz maç ve dizi keyfi!\n"
                                            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                                            "👇 İŞTE SİZİN İÇİN TARANAN GÜNCEL LİSTENİZ 👇\n\n"
                                        )
                                        
                                        telegraph_alt_bilgi = "\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                                        if next_page_url:
                                            telegraph_alt_bilgi += f"👉 DEVAMI VAR! SONRAKİ SAYFAYA GEÇİN:\n{next_page_url}\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                                            
                                        telegraph_alt_bilgi += "📌 İNADINA TV AİLESİNE KATIL: https://t.me/inadinatv2\n📺 Bizi takipte kalın, yayında kalın!"
                                        
                                        linkler_metni = telegraph_baslik + linkler_govde + telegraph_alt_bilgi
                                        
                                        page_payload = {
                                            "access_token": self.telegraph_token,
                                            "title": sayfa_basligi,
                                            "content": [{"tag": "pre", "children": [linkler_metni]}]
                                        }
                                        
                                        retry_count = 0
                                        while retry_count < 3:
                                            page_resp = await session.post("https://api.telegra.ph/createPage", json=page_payload)
                                            page_data = await page_resp.json()
                                            
                                            if page_data.get("ok"):
                                                next_page_url = page_data["result"]["url"]
                                                if i == len(chunks) - 1: 
                                                    paste_url = next_page_url
                                                break
                                            else:
                                                error_msg = page_data.get('error', '')
                                                if 'FLOOD_WAIT' in error_msg:
                                                    try:
                                                        wait_time = int(error_msg.split('_')[-1]) + 1
                                                    except:
                                                        wait_time = 4
                                                    print(f"⏳ Telegra.ph sınırına ulaşıldı! {wait_time} saniye bekleniyor... (Sayfa {page_number})")
                                                    await asyncio.sleep(wait_time)
                                                    retry_count += 1
                                                else:
                                                    print(f"⚠️ Telegra.ph API Hatası (Sayfa {page_number}): {error_msg}")
                                                    break
                                                    
                                        await asyncio.sleep(1) 
                            except Exception as e:
                                print(f"⚠️ Telegra.ph bağlantı hatası, alternatife geçiliyor: {e}")
                                
                            # --- 2. Telegra.ph Çökerse Alternatif (Paste.rs) ---
                            if not paste_url or not paste_url.startswith("http"):
                                try:
                                    kisa_govde = []
                                    for item in parsed_links[:150]:
                                        kisa_govde.append(f"Durum: {item['durum']} | URL: {item['url']}")
                                    alt_metin = "İlk 150 Link (Limit Aşımı Engellendi):\n\n" + "\n".join(kisa_govde)
                                    alt_resp = await session.post("https://paste.rs/", data=alt_metin)
                                    if alt_resp.status in [200, 201, 206]:
                                        paste_url = (await alt_resp.text()).strip()
                                except Exception as e:
                                    print(f"❌ Alternatif paste hatası: {e}")

                            # Reklamsız aktarım istendiği için paste_url'i direkt kullanıyoruz
                            kisaltilmis_link = paste_url
                                    
                except Exception as e: 
                    print(f"❌ Yükleme genel hatası: {e}")
                    kisaltilmis_link = None

                if not kisaltilmis_link or not kisaltilmis_link.startswith("http"):
                    print(f"❌ Liste web'e yüklenemediği için UYGULAMAYA KART EKLENMEYECEK!")
                    return 

                print(f"✅ Liste başarıyla yüklendi: {kisaltilmis_link} - Şimdi Uygulamaya Ekleniyor...")
                
                # Telegram bildirim kodu blokları isteğiniz üzerine tamamen kaldırılmıştır.

                self.load_from_file()
                
                toplam_link_sayisi = len(parsed_links)
                domain_sayisi = len(domain_info)
                zaman_etiketi = datetime.now().strftime('%H:%M')
                
                ornek_play_link = parsed_links[0]['url'] if parsed_links else "#"
                
                kart_basligi = f"🔥 TOPLU LİSTE ({toplam_link_sayisi} Panel / {domain_sayisi} Sunucu) [{zaman_etiketi}]"
                
                self.custom_iptv_list.insert(0, {
                    "title": kart_basligi,
                    "m3u_url": ornek_play_link, 
                    "web_link_url": kisaltilmis_link if kisaltilmis_link else "#", 
                    "image": self.default_icon_url,
                    "added_date": datetime.now().strftime('%d.%m.%Y'),
                    "added_time": datetime.now().strftime('%H:%M')
                })
                
                print(f"🔄 Uygulamaya 1 Adet TOPLU KART Eklendi ({toplam_link_sayisi} Link tek bir çatıya toplandı). GitHub'a senkronize ediliyor...")
                self.save_and_sync()
                print(f"✅ Sistem Başarıyla Güncellendi!")

    def generate_iptv_html(self):
        now = datetime.now()
        items_for_html = []
        
        for item in self.custom_iptv_list:
            is_new_auto = False
            if item.get("added_date"):
                try:
                    added_dt = datetime.strptime(item["added_date"], '%d.%m.%Y')
                    if (now - added_dt).days <= 2: is_new_auto = True
                except: pass
            
            items_for_html.append({
                "title": item.get("title"), "url": item.get("m3u_url") or "#",
                "image": item.get("image", self.default_icon_url), 
                "web_link_url": item.get("web_link_url") or "#",
                "is_new": is_new_auto, 
                "added_date": item.get("added_date"),
                "added_time": item.get("added_time", "")
            })

        js_inj = f"const categoryData = {{ 'iptv_list': {{ 'items': {json.dumps(items_for_html, ensure_ascii=False)} }} }}; const activeCategoryKey = 'iptv_list';"
        template = self.get_html_template()
        
        if not template:
            print("❌ HTML Şablonu Eksik! Lütfen get_html_template kısmının dolu olduğundan emin olun.")
            return
            
        html = template.replace("{{DATA_PLACEHOLDER}}", js_inj)
        html = html.replace("{telegram_link}", self.telegram_link)
        html = html.replace("{site_url}", SITE_URL)
        html = html.replace("{{ADMIN_PASSWORD_PLACEHOLDER}}", ADMIN_PASSWORD)
        html = html.replace("{{TG_BOT_TOKEN_PLACEHOLDER}}", TG_BOT_TOKEN) 
        html = html.replace("{{TG_CHAT_ID_PLACEHOLDER}}", TG_CHAT_ID)

        # PyDroid arka planda HTML'i yeniden üretirken IPTV ARAÇLAR
        # menüsünün yanlışlıkla eski sürüme dönmesini engelle.
        required_yan_links = [
            f'href="{tool["go"]}"' for tool in YAN_DNS_TOOLS.values()
        ]
        missing_yan_links = [link for link in required_yan_links if link not in html]
        if missing_yan_links:
            print(f"❌ Yan DNS menü eşleştirmesi eksik; HTML GitHub'a gönderilmedi: {missing_yan_links}")
            return
        self.github_push(html, f"{self.html_output_subdir}/index.html")

    def add_list_interactive(self):
        print("\n [+] Yeni IPTV Kanalı Ekleniyor...")
        title = input("  > Kanal Başlığı: ").strip()
        if not title: return
        m3u = input("  > M3U/Stream Linki: ").strip()
        web = input("  > İndirme/Web Sayfası Linki: ").strip()
        img = input("  > İkon URL: ").strip()
        final_web = self.shorten_url(web)
        self.custom_iptv_list.insert(0, {"title": title, "m3u_url": m3u, "web_link_url": final_web, "image": img if img else self.default_icon_url, "added_date": datetime.now().strftime('%d.%m.%Y'), "added_time": datetime.now().strftime('%H:%M')})
        self.save_and_sync()

    def edit_list_interactive(self):
        self.view_lists()
        try:
            idx = int(input("\n  > Düzenlenecek No: ")) - 1
            item = self.custom_iptv_list[idx]
            item['title'] = input(f"  > Başlık [{item['title']}]: ") or item['title']
            item['m3u_url'] = input(f"  > URL [{item['m3u_url']}]: ") or item['m3u_url']
            new_web = input(f"  > Yeni Web Link: ").strip()
            if new_web: item['web_link_url'] = self.shorten_url(new_web)
            img_in = input(f"  > Yeni İkon: ").strip()
            if img_in: item['image'] = img_in
            if input("  > Tarihi Güncelle? (e/h): ").lower() == 'e': 
                item['added_date'] = datetime.now().strftime('%d.%m.%Y')
                item['added_time'] = datetime.now().strftime('%H:%M')
            self.save_and_sync()
        except: print(" [!] Hata.")

    def delete_list_interactive(self):
        self.view_lists()
        user_input = input("\n  > Silinecek No (Örn: 1,3): ").strip()
        if not user_input: return
        try:
            indices = sorted([int(i) - 1 for i in re.findall(r'\d+', user_input)], reverse=True)
            for idx in indices:
                if 0 <= idx < len(self.custom_iptv_list): self.custom_iptv_list.pop(idx)
            self.save_and_sync()
        except: pass

    def reorder_list_interactive(self):
        self.view_lists()
        try:
            src, dst = int(input("\n  > Taşınacak: ")) - 1, int(input("  > Yeni Sıra: ")) - 1
            self.custom_iptv_list.insert(dst, self.custom_iptv_list.pop(src))
            self.save_and_sync()
        except: pass

    def view_lists(self):
        print("\n" + "═"*45)
        if not self.custom_iptv_list: print("  Liste boş."); return
        for i, item in enumerate(self.custom_iptv_list):
            print(f"  {i+1:02d}. {item['title'][:25]:<25} | {item.get('added_date')}")
        print("═"*45)

    def start_auto_livescore(self):
        if hasattr(self, 'live_thread') and self.live_thread.is_alive():
            print("\n [!] Arka planda zaten çalışan bir otomatik skor takip botu var!")
            time.sleep(2)
            return

        print("\n [+] ⚽ OTOMATİK CANLI SKOR / GOL BOTU BAŞLATILIYOR...")
        print("     Bu özellik ücretsiz API üzerinden belirttiğiniz takımı bulur.")
        team_name_input = input("  > Takip Edilecek Takım (Örn: Galatasaray): ").strip().lower()
        if not team_name_input: return

        tr_to_eng = str.maketrans("çğıöşü", "cgiosu")
        team_name = team_name_input.translate(tr_to_eng)

        print("\n[Lig Seçimi]")
        print("  1. Türkiye Süper Lig")
        print("  2. İngiltere Premier Lig")
        print("  3. İspanya La Liga")
        print("  4. UEFA Şampiyonlar Ligi")
        print("  5. UEFA Avrupa Ligi")
        l_choice = input("  > Lig Seçimi (1-5)[Varsayılan: 1]: ").strip()
        league_map = {'1': 'tur.1', '2': 'eng.1', '3': 'esp.1', '4': 'uefa.champions', '5': 'uefa.europa'}
        league = league_map.get(l_choice, 'tur.1')

        def poller():
            api_url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{league}/scoreboard"
            last_score_a = -1
            last_score_b = -1
            
            init_payload = {
                "active": True, "teamA": team_name_input.title(), "teamB": "Aranıyor...",
                "scoreA": "-", "scoreB": "-",
                "minute": "Bekleniyor", "events": "🔍 Sistem maçı arıyor..."
            }
            try:
                requests.put(self.firebase_livescore_url, json=init_payload)
            except Exception as e:
                print(f" [!] Firebase Başlangıç Hatası: {e}")

            mac_bulundu_bir_kere = False

            while True:
                try:
                    res = requests.get(api_url, timeout=10)
                    if res.status_code == 200:
                        data = res.json()
                        events_data = data.get('events',[])
                        
                        hedef_mac = None
                        for ev in events_data:
                            name = ev.get('name', '').lower().translate(tr_to_eng)
                            if team_name in name:
                                hedef_mac = ev
                                break
                        
                        if hedef_mac:
                            mac_bulundu_bir_kere = True
                            comps = hedef_mac['competitions'][0]['competitors']
                            
                            t1 = comps[0]['team']['name']
                            s1 = int(comps[0].get('score', '0'))
                            t2 = comps[1]['team']['name']
                            s2 = int(comps[1].get('score', '0'))

                            status = hedef_mac['status']
                            minute = status.get('displayClock', "0'")
                            state = status['type']['state']
                            
                            if state == 'pre': minute = "Başlamadı"
                            elif state == 'post': minute = "Maç Sonu"
                            elif state == 'in': 
                                if not minute or minute == "0'":
                                    minute = "Canlı"

                            payload = {
                                "active": True, "teamA": t1, "teamB": t2,
                                "scoreA": str(s1), "scoreB": str(s2),
                                "minute": minute, "events": "🔴 Canlı Takip: " + hedef_mac.get('shortName', '')
                            }

                            requests.put(self.firebase_livescore_url, json=payload)
                            
                            if (last_score_a != -1) and (s1 > last_score_a or s2 > last_score_b):
                                print(f"\n\n[⚽ GOL GELDİ!] {t1} {s1} - {s2} {t2} ({minute})\n")

                            last_score_a = s1
                            last_score_b = s2
                            
                            if state == 'post':
                                print(f"\n [!] Maç bitti! Sonuç: {t1} {s1} - {s2} {t2}.")
                                time.sleep(180)
                                requests.patch(self.firebase_livescore_url, json={"active": False})
                                return 
                        else:
                            if not mac_bulundu_bir_kere:
                                fail_payload = {
                                    "active": True, "teamA": team_name_input.title(), "teamB": "Bulunamadı",
                                    "scoreA": "-", "scoreB": "-",
                                    "minute": "---", "events": "⚠️ Seçilen ligde bu takımın aktif maçı yok."
                                }
                                requests.put(self.firebase_livescore_url, json=fail_payload)
                except Exception as e: 
                    print(f" [!] Canlı Skor API Hatası: {e}")
                
                time.sleep(30)

        self.live_thread = threading.Thread(target=poller, daemon=True)
        self.live_thread.start()
        print(f"\n [V] Başarılı! {team_name_input.title()} takımı için otomatik takip arka planda başladı.")
        time.sleep(3)

    def run_main_loop(self):
        time.sleep(2) 
        while True:
            os.system('clear' if os.name == 'posix' else 'cls')
            print("\n" + "╔" + "═"*38 + "╗")
            print("║   🚀 IPTV BOT - V38 (UPPER ECHELON)  ║")
            print("╠" + "═"*38 + "╣")
            print("║  1. 🆕 YENİ KANAL EKLE                ║")
            print("║  2. ✏️  DÜZENLE                        ║")
            print("║  3. 🗑️  TOPLU SİL                      ║")
            print("║  4. ↕️  SIRALAMAYI DEĞİŞTİR            ║")
            print("║  5. 🔄 GİTHUB SYNC (YENİLE)            ║")
            print("║  6. 📋 LİSTEYİ GÖR                    ║")
            print("║  7. ⚽ OTOMATİK SKOR BOTU BAŞLAT      ║")
            print("║  0. ❌ ÇIKIŞ                          ║")
            print("╚" + "═"*38 + "╝")
            print("\n📡 TELEGRAM OTOMATİK DİNLEME ARKA PLANDA AKTİF!")
            choice = input("\n  [?] İşlem Seçiniz: ").strip()
            if choice == '1': self.add_list_interactive()
            elif choice == '2': self.edit_list_interactive()
            elif choice == '3': self.delete_list_interactive()
            elif choice == '4': self.reorder_list_interactive()
            elif choice == '5': self.save_and_sync(); input("\n  Sync Tamam. Enter...")
            elif choice == '6': self.view_lists(); input("\n  Enter...")
            elif choice == '7': self.start_auto_livescore()
            elif choice == '0': os._exit(0)

    def start_cli_thread(self):
        cli_thread = threading.Thread(target=self.run_main_loop, daemon=True)
        cli_thread.start()

    async def run_bot(self):
        print("🔌 Sistem Başlatılıyor. Telegram'a Bağlanılıyor...")
        await self.client.start()  
        self.start_cli_thread()    
        await self.client.run_until_disconnected()

    def get_html_template(self):
        return r"""<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>InAdina TV</title>
    <link rel="canonical" href="{site_url}">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;700;800&display=swap" rel="stylesheet">
    
    <script src="https://www.gstatic.com/firebasejs/9.23.0/firebase-app-compat.js"></script>
    <script src="https://www.gstatic.com/firebasejs/9.23.0/firebase-database-compat.js"></script>
    
    <link href="https://cdnjs.cloudflare.com/ajax/libs/video.js/8.10.0/video-js.min.css" rel="stylesheet">
    <script src="https://cdnjs.cloudflare.com/ajax/libs/video.js/8.10.0/video.min.js"></script>

    <script src="https://cdnjs.cloudflare.com/ajax/libs/hls.js/1.4.12/hls.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/mpegts.js@1.7.3/dist/mpegts.min.js"></script>

    <style>
        :root { --hue: 345; --primary: hsl(var(--hue), 100%, 50%); --bg: #0f0a1a; --surface: #1a1825; --text: #e8e6e3; --card-bg: rgba(255,255,255,0.06); --border: rgba(255,255,255,0.03); }
        body { background: var(--bg); color: var(--text); font-family: 'Poppins', sans-serif; margin: 0; padding-bottom: 20px; transition: background 0.3s, color 0.3s; overflow-x: hidden; }
        body.light-theme { --bg: #f5f5f5; --surface: #ffffff; --text: #1a1a1a; --card-bg: #ffffff; --border: #e0e0e0; }
        
        .quick-close-btn { display: none !important; position: absolute; top: 10px; right: 10px; font-size: 1rem; color: #fff; background: rgba(255, 0, 64, 0.8); border-radius: 50%; width: 26px; height: 26px; align-items: center; justify-content: center; cursor: pointer; z-index: 10; border: 1px solid rgba(255,255,255,0.3); transition: transform 0.2s; box-shadow: 0 2px 5px rgba(0,0,0,0.5); }
        body.admin-mode .quick-close-btn { display: flex !important; }
        .quick-close-btn:hover, .quick-close-btn.focused { transform: scale(1.15); background: #ff0040; border-color: #fff; }

        .focusable { outline: none; transition: transform 0.2s, box-shadow 0.2s, background 0.2s; border: 2px solid transparent; }
        .focusable:focus, .focusable.focused { transform: scale(1.05); box-shadow: 0 0 0 4px #ff0040, 0 0 20px rgba(255, 0, 64, 0.6) !important; z-index: 100; background-color: rgba(255, 255, 255, 0.15); border-color: #fff; }
        
        .brand-lockup { flex:0 1 86px; min-width:0; margin:0 4px 0 0; overflow:hidden; }
        .brand-lockup strong { display:block; color:#fff; font-size:.82rem; line-height:1; letter-spacing:.2px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
        .tools-label { display:inline; }
        .dropbtn { padding:8px 10px; font-size:.76rem; gap:5px; letter-spacing:.2px; }
        .dropbtn i { font-size:.95rem; }
        .top-bar { gap:7px; }
        @media (max-width:500px) { .brand-lockup { flex-basis:72px; } .brand-lockup strong { font-size:.72rem; } .tools-label { display:inline !important; } .dropbtn { min-width:42px; justify-content:center; padding:8px 10px; } .header-actions { gap:5px; } .online-badge { padding:6px 7px; font-size:.68rem; } .theme-btn { padding:7px 9px; } }
        .top-bar { padding: 10px 15px; background: var(--surface); display: flex; justify-content: space-between; align-items: center; position: sticky; top: 0; z-index: 100; box-shadow: 0 4px 10px rgba(0,0,0,0.3); transition: background 0.3s; }
        .header-actions { display: flex; align-items: center; gap: 12px; }
        
        @media (max-width: 500px) { .top-bar { padding: 8px 10px; } .dropbtn { font-size: 0.8rem; padding: 6px 10px; } .header-actions { gap: 8px; } .online-badge { padding: 4px 8px; font-size: 0.75rem; } }
        
        .dropdown { position: relative; display: inline-block; z-index: 200; }
        .dropbtn { background: linear-gradient(135deg, #00d2ff, #3a7bd5); border: 1px solid rgba(255, 255, 255, 0.3); color: #fff; padding: 8px 16px; border-radius: 8px; font-size: 0.95rem; font-weight: 800; cursor: pointer; display: flex; align-items: center; gap: 8px; transition: all 0.3s ease; white-space: nowrap; box-shadow: 0 4px 10px rgba(58, 123, 213, 0.4); text-transform: uppercase; letter-spacing: 0.5px; }
        .dropdown-content { display: none; position: absolute; background-color: var(--surface); min-width: 220px; box-shadow: 0px 8px 16px 0px rgba(0,0,0,0.5); z-index: 201; border-radius: 10px; overflow: hidden; border: 1px solid var(--border); top: 120%; left: 0; }
        .dropdown-content a { color: var(--text); padding: 12px 16px; text-decoration: none; display: flex; align-items: center; gap: 10px; font-size: 0.9rem; border-bottom: 1px solid var(--border); transition: background 0.2s, padding-left 0.2s; white-space: nowrap; }
        .dropdown-content a.yan-dns-link { font-weight: 700; border-left: 4px solid transparent; }
        .dropdown-content a.yan-dns-link strong { font-weight: 900; letter-spacing: .35px; padding: 3px 7px; border-radius: 6px; }
        .dropdown-content a.yan-dns-panel { border-left-color: #38bdf8; }
        .dropdown-content a.yan-dns-panel strong { color: #0c4a6e; background: #7dd3fc; }
        .dropdown-content a.yan-dns-user { border-left-color: #f59e0b; }
        .dropdown-content a.yan-dns-user strong { color: #78350f; background: #fbbf24; }
        .dropdown-content a.yan-dns-m3u { border-left-color: #22c55e; }
        .dropdown-content a.yan-dns-m3u strong { color: #14532d; background: #86efac; }
        .light-theme .dropdown-content a.yan-dns-panel strong { color: #075985; background: #bae6fd; }
        .light-theme .dropdown-content a.yan-dns-user strong { color: #92400e; background: #fde68a; }
        .light-theme .dropdown-content a.yan-dns-m3u strong { color: #166534; background: #bbf7d0; }
        .dropdown.open .dropdown-content { display: block; animation: fadeInMenu 0.18s ease; }
        @keyframes fadeInMenu { from { opacity: 0; transform: translateY(-10px); } to { opacity: 1; transform: translateY(0); } }

        .theme-btn { background: rgba(255, 255, 255, 0.08); border: 1px solid rgba(255, 255, 255, 0.1); color: #fff; padding: 8px 12px; border-radius: 8px; font-size: 1.2rem; cursor: pointer; display: flex; align-items: center; transition: all 0.3s; }
        .online-badge { display: flex; align-items: center; gap: 6px; padding: 6px 10px; background: rgba(0, 255, 127, 0.1); border: 1px solid rgba(0, 255, 127, 0.2); border-radius: 8px; font-size: 0.8rem; font-weight: bold; color: #00ff7f; animation: pulse-green 2s infinite; }
        @keyframes pulse-green { 0% { opacity: 0.8; } 50% { opacity: 1; text-shadow: 0 0 5px rgba(0,255,127,0.5); } 100% { opacity: 0.8; } }

        .announcement-bar { background: #ffeb3b; color: #000; overflow: hidden; white-space: nowrap; padding: 6px 0; font-weight: bold; font-size: 0.9rem; box-shadow: 0 2px 5px rgba(0,0,0,0.2); display: none; border-bottom: 2px solid #ff4d00; }
        .announcement-content { display: inline-block; padding-left: 100%; animation: scroll-left 15s linear infinite; }
        @keyframes scroll-left { 0% { transform: translateX(0); } 100% { transform: translateX(-100%); } }
        
        .container { padding: 15px; }
        .card { background: var(--card-bg); border-radius: 15px; padding: 10px; margin-bottom: 12px; display: flex; align-items: center; cursor: pointer; border: 1px solid var(--border); position: relative; transition: all 0.3s; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
        .card.hidden { display: none; }
        
        .force-hidden { display: none !important; }
        .admin-delete-btn { display: none; align-items: center; justify-content: center; padding: 15px; margin: 8px 0; border-radius: 12px; background: rgba(255,0,64,0.1); border: 1px solid #ff0040; gap: 10px; cursor: pointer; color: #ff4d4d; transition: background 0.3s; }
        .admin-delete-btn:hover { background: rgba(255,0,64,0.3); color: #fff; }
        body.admin-mode .admin-delete-btn { display: flex; }

        .img-box { position: relative; width: 55px; height: 55px; flex-shrink: 0; }
        .card-img { width: 100%; height: 100%; border-radius: 10px; object-fit: cover; }
        
        .badge { position: absolute; top: -10px; right: -10px; font-size: 0.75rem; padding: 4px 10px; border-radius: 8px; font-weight: 900; z-index: 10; box-shadow: 0 4px 10px rgba(0,0,0,0.4); text-transform: uppercase; border: 1px solid rgba(255,255,255,0.3); }
        .badge-yeni { background: linear-gradient(135deg, #ff0000, #ff4d00); color: #fff; animation: pulse-aggressive 1.5s infinite ease-in-out; }
        .badge-iptv { background: linear-gradient(135deg, #00d2ff, #3a7bd5); color: #fff; }
        @keyframes pulse-aggressive { 0% { transform: scale(1); box-shadow: 0 0 0 rgba(255, 0, 0, 0.7); } 50% { transform: scale(1.15); box-shadow: 0 0 15px rgba(255, 77, 0, 0.8); } 100% { transform: scale(1); box-shadow: 0 0 0 rgba(255, 0, 0, 0.7); } }

        .card-info { flex: 1; margin-left: 12px; }
        .card-name { font-weight: 700; font-size: 1rem; margin-bottom: 3px; color: var(--text); }
        .card-meta { font-size: 0.75rem; opacity: 0.5; color: var(--text); display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
        .stat-badge { display: inline-flex; align-items: center; gap: 4px; background: rgba(255, 255, 255, 0.05); padding: 2px 8px; border-radius: 8px; font-size: 0.7rem; font-weight: 600; border: 1px solid rgba(255, 255, 255, 0.1); }
        .stat-eye { color: var(--primary); }
        .stat-heart { color: #ff3d3d; cursor: pointer; transition: transform 0.2s; }
        .stat-heart.liked { color: #ff0000; text-shadow: 0 0 10px rgba(255,0,0,0.5); }
        .stat-report { color: #ff4d4d; cursor: pointer; transition: transform 0.2s; }
        .play-icon { color: var(--primary); font-size: 1.4rem; margin-left: 10px; }
        .load-more-btn { width: calc(100% - 30px); margin: 20px 15px; padding: 15px; border: none; border-radius: 15px; background: linear-gradient(135deg, var(--primary), #ff4d00); color: white; font-weight: 700; font-size: 1rem; cursor: pointer; display: flex; align-items: center; justify-content: center; gap: 10px; transition: all 0.3s; box-shadow: 0 4px 15px rgba(255, 0, 64, 0.3); }
        .load-more-btn.hidden { display: none; }
        
        .toast { visibility: hidden; min-width: 250px; background-color: #1a1825; border: 1px solid rgba(255,255,255,0.1); color: #fff; text-align: center; border-radius: 50px; padding: 16px; position: fixed; z-index: 2000; left: 50%; bottom: 80px; transform: translateX(-50%); font-size: 0.9rem; box-shadow: 0 5px 20px rgba(0,0,0,0.5); opacity: 0; transition: opacity 0.3s, bottom 0.3s; display: flex; align-items: center; justify-content: center; gap: 10px; }
        .toast.show { visibility: visible; opacity: 1; bottom: 90px; }
        
        .feature-container { margin: 15px; display: flex; flex-direction: column; gap: 15px; }
        
        .livescore-box { background: linear-gradient(135deg, #101010, #1a1825); border: 1px solid #00d2ff; border-radius: 15px; padding: 15px; text-align: center; position: relative; overflow: hidden; display: none; box-shadow: 0 5px 15px rgba(0, 210, 255, 0.15); transition: box-shadow 0.3s ease; }
        .ls-header { display: flex; justify-content: center; align-items: center; gap: 8px; font-size: 0.9rem; font-weight: bold; color: #fff; margin-bottom: 10px; }
        .ls-live-dot { width: 10px; height: 10px; background-color: #ff0040; border-radius: 50%; animation: blink 1s infinite; box-shadow: 0 0 8px #ff0040; }
        .ls-minute { color: #00d2ff; }
        .ls-row { display: flex; justify-content: space-between; align-items: center; margin: 10px 0; }
        .ls-team { flex: 1; font-size: 1.2rem; font-weight: 800; color: #fff; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; padding: 0 5px; }
        .ls-score-wrap { display: flex; align-items: center; justify-content: center; gap: 10px; background: rgba(255,255,255,0.1); padding: 5px 15px; border-radius: 10px; border: 1px solid rgba(255,255,255,0.2); }
        .ls-score { font-size: 2rem; font-weight: 900; color: #ffeb3b; text-shadow: 0 0 10px rgba(255, 235, 59, 0.5); transition: transform 0.2s ease; }
        .ls-score.goal-anim { transform: scale(1.5); color: #ff0040; text-shadow: 0 0 15px #ff0040; }
        .ls-divider { font-size: 1.5rem; color: #fff; opacity: 0.5; }
        .ls-events { font-size: 0.8rem; color: #aaa; margin-top: 10px; font-style: italic; min-height: 20px; }

        .stream-box { background: var(--surface); border: 1px solid var(--primary); border-radius: 15px; padding: 15px; display: none; position: relative; box-shadow: 0 5px 15px rgba(255, 0, 64, 0.2); }
        .iframe-container { position: relative; width: 100%; padding-bottom: 56.25%; height: 0; overflow: hidden; border-radius: 10px; background: #000; border: 1px solid rgba(255,255,255,0.1); margin-top: 5px;}
        .iframe-container iframe { position: absolute; top: 0; left: 0; width: 100%; height: 100%; border: 0; z-index: 10; background: #000; }
        
        .stream-channels { display: flex; justify-content: center; gap: 10px; margin-top: 15px; flex-wrap: wrap; }
        .ch-btn { flex: 1; min-width: 80px; padding: 10px; border-radius: 8px; border: 1px solid rgba(255,0,64,0.5); background: rgba(0,0,0,0.3); color: white; font-weight: bold; cursor: pointer; transition: all 0.3s; text-align: center; }
        .ch-btn.active, .ch-btn:focus, .ch-btn.focused { background: linear-gradient(135deg, #ff0040, #ff4d00); border-color: #fff; box-shadow: 0 4px 10px rgba(255, 0, 64, 0.5); transform: scale(1.05); }

        .video-js { width: 100% !important; height: 100% !important; background-color: #000 !important; position: absolute !important; top: 0 !important; left: 0 !important; z-index: 1 !important; }
        .video-js .vjs-tech { width: 100% !important; height: 100% !important; object-fit: contain !important; position: absolute !important; top: 0 !important; left: 0 !important; z-index: 1 !important; }
        .video-js .vjs-poster { background: transparent !important; display: none !important; }
        .video-js .vjs-big-play-button { z-index: 10; color: white; line-height: 66px; height: 70px; width: 70px; border: 2px solid #fff; border-radius: 90px; left: 50%; top: 50%; margin-top: -35px; margin-left: -35px; background-color: var(--primary); transition: 0.4s; }
        .video-js .vjs-control-bar { z-index: 10; background: linear-gradient(0deg, rgba(0,0,0,0.9) 0%, rgba(0,0,0,0) 100%); }
        .video-js .vjs-play-progress, .video-js .vjs-volume-level { background-color: var(--primary); }

        .countdown-box { background: linear-gradient(135deg, #1a1825, #000); border: 1px solid var(--primary); border-radius: 15px; padding: 15px; text-align: center; position: relative; overflow: hidden; display: none; }
        .countdown-title { color: var(--primary); font-weight: bold; margin-bottom: 10px; font-size: 1.1rem; text-transform: uppercase; letter-spacing: 1px; }
        .countdown-timer { display: flex; justify-content: center; gap: 10px; font-size: 1.5rem; font-weight: bold; color: white; font-family: monospace; }
        .time-unit { display: flex; flex-direction: column; align-items: center; background: rgba(255,255,255,0.1); padding: 5px 10px; border-radius: 8px; min-width: 40px; }
        .time-label { font-size: 0.6rem; opacity: 0.7; font-family: sans-serif; margin-top: 2px; }
        @keyframes blink { 0% { opacity: 1; } 50% { opacity: 0.3; } 100% { opacity: 1; } }

        .poll-box { background: var(--card-bg); border: 1px solid var(--border); border-radius: 15px; padding: 15px; display: none; position: relative; }
        .poll-question { font-weight: bold; margin-bottom: 10px; color: var(--text); display: block; }
        .poll-option { margin-bottom: 8px; position: relative; cursor: pointer; }
        .poll-bar-bg { background: rgba(255,255,255,0.1); height: 35px; border-radius: 8px; overflow: hidden; position: relative; }
        .poll-bar-fill { height: 100%; background: linear-gradient(90deg, var(--primary), #ff4d00); width: 0%; transition: width 0.5s ease; opacity: 0.7; }
        .poll-text { position: absolute; top: 0; left: 10px; height: 100%; display: flex; align-items: center; font-size: 0.9rem; font-weight: bold; color: white; z-index: 2; text-shadow: 0 0 3px black; }
        .poll-percent { position: absolute; top: 0; right: 10px; height: 100%; display: flex; align-items: center; font-size: 0.9rem; font-weight: bold; color: white; z-index: 2; text-shadow: 0 0 3px black; }

        @keyframes gradient-anim { 0% { background-position: 0% 50%; } 50% { background-position: 100% 50%; } 100% { background-position: 0% 50%; } }
        .chat-btn-container { position: fixed; bottom: 20px; right: 20px; z-index: 200; display:flex; flex-direction:column; align-items:center; gap:5px; }
        .chat-label { background: #ff0040; color:white; font-size:0.7rem; padding:3px 8px; border-radius:10px; font-weight:bold; box-shadow: 0 2px 5px rgba(0,0,0,0.5); animation: bounce 2s infinite; }
        @keyframes bounce { 0%, 20%, 50%, 80%, 100% {transform: translateY(0);} 40% {transform: translateY(-5px);} 60% {transform: translateY(-3px);} }

        .chat-btn { width: 65px; height: 65px; background: linear-gradient(45deg, #00d2ff, #3a7bd5, #ff0040); background-size: 200% 200%; border-radius: 50%; display: flex; justify-content: center; align-items: center; color: white; font-size: 1.8rem; box-shadow: 0 5px 20px rgba(0,210,255,0.4); cursor: pointer; animation: gradient-anim 3s ease infinite, pulse-beat 2s infinite; border: 2px solid rgba(255,255,255,0.2); }
        .chat-btn:hover { animation: gradient-anim 1s ease infinite; transform: scale(1.1); }
        @keyframes pulse-beat { 0% { transform: scale(1); box-shadow: 0 0 0 0 rgba(0, 210, 255, 0.7); } 70% { transform: scale(1.05); box-shadow: 0 0 0 15px rgba(0, 210, 255, 0); } 100% { transform: scale(1); box-shadow: 0 0 0 0 rgba(0, 210, 255, 0); } }

        .chat-modal { position: fixed; bottom: -100%; left: 0; width: 100%; height: 96%; background: var(--surface); border-radius: 20px 20px 0 0; z-index: 201; transition: bottom 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275); display: flex; flex-direction: column; box-shadow: 0 -5px 30px rgba(0,0,0,0.5); }
        .chat-modal.active { bottom: 0; }
        .chat-header { padding: 15px; background: rgba(0,0,0,0.2); display: flex; flex-direction: column; border-radius: 20px 20px 0 0; gap: 10px; }
        .chat-header-top { display: flex; justify-content: space-between; align-items: center; width: 100%; }
        .chat-close { font-size: 1.5rem; cursor: pointer; color: var(--text); }
        .chat-rules { background: rgba(255, 0, 64, 0.15); border-bottom: 1px solid rgba(255, 0, 64, 0.3); color: #ff4d4d; padding: 10px; font-size: 0.8rem; text-align: center; font-weight: bold; display: flex; align-items: center; justify-content: center; gap: 8px; transition: all 0.5s ease-in-out; opacity: 1; max-height: 100px; }
        .chat-rules.hidden { opacity: 0; max-height: 0; padding: 0; margin: 0; overflow: hidden; border: none; }
        
        .chat-tabs { display: flex; width: 100%; background: rgba(0,0,0,0.2); border-radius: 10px; padding: 2px; }
        .chat-tab { flex: 1; text-align: center; padding: 8px; font-size: 0.9rem; cursor: pointer; border-radius: 8px; transition: all 0.3s; position: relative; }
        .chat-tab.active { background: var(--primary); color: white; font-weight: bold; }
        .chat-tab-badge { position: absolute; top: 2px; right: 10px; background: red; color: white; font-size: 0.6rem; padding: 2px 5px; border-radius: 50%; display: none; }

        .chat-view { display: flex; flex-direction: column; flex: 1; overflow: hidden; }
        .chat-view.hidden { display: none; }

        .chat-messages { flex: 1; padding: 15px; overflow-y: auto; display: flex; flex-direction: column; gap: 10px; scroll-behavior: smooth; }
        .message-bubble { max-width: 85%; padding: 10px 14px; border-radius: 12px; font-size: 0.9rem; line-height: 1.4; position: relative; word-wrap: break-word; color: white; box-shadow: 0 2px 5px rgba(0,0,0,0.2); }
        .msg-left { align-self: flex-start; border-bottom-left-radius: 2px; }
        .msg-right { align-self: flex-end; background: var(--primary); border-bottom-right-radius: 2px; }
        .msg-user { font-size: 0.7rem; opacity: 0.8; margin-bottom: 2px; display: block; font-weight: bold; cursor: pointer; color: #ffeb3b; }
        .msg-admin { color: #ff4d4d; text-shadow: 0 0 5px rgba(0,0,0,0.5); }
        .msg-time { display: block; font-size: 0.65rem; text-align: right; opacity: 0.6; margin-top: 4px; }
        .chat-link { color: #00d2ff; text-decoration: underline; font-weight: bold; word-break: break-all; overflow-wrap: anywhere; }
        .msg-text { white-space: normal; overflow-wrap: anywhere; }
        .msg-text br { content: ''; display: block; margin-top: 3px; }
        .chat-file-block { display:flex; align-items:center; background: rgba(0,0,0,0.3); padding:8px; border-radius:8px; margin-top:5px; gap:10px; border:1px solid rgba(255,255,255,0.1); cursor:pointer; }
        .file-icon { font-size: 1.5rem; color: #ffeb3b; }
        .file-info { display:flex; flex-direction:column; overflow:hidden; }
        .file-name { font-size:0.8rem; font-weight:bold; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
        .file-dl { font-size:0.7rem; color:#00d2ff; }

        .quoted-msg { background: rgba(0,0,0,0.2); border-left: 3px solid #ff4d4d; padding: 5px 8px; border-radius: 4px; margin-bottom: 5px; font-size: 0.75rem; display: flex; flex-direction: column; opacity: 0.9; }
        .quote-user { font-weight: bold; color: #ffeb3b; margin-bottom: 2px; }
        .reply-preview-bar { background: #2a2a2a; border-top: 1px solid rgba(255,255,255,0.1); padding: 8px 15px; display: none; justify-content: space-between; align-items: center; font-size: 0.8rem; color: #ddd; border-left: 4px solid var(--primary); }
        
        .msg-actions { display: flex; gap: 10px; margin-top: 5px; justify-content: flex-end; font-size: 0.75rem; opacity: 0.9; }
        .action-btn { cursor: pointer; display: flex; align-items: center; gap: 3px; transition: all 0.2s; color: rgba(255,255,255,0.7); }
        .action-btn:hover { opacity: 1; color: white; }
        .action-btn.active-like { color: #ffeb3b; font-weight: bold; text-shadow: 0 0 5px rgba(0,0,0,0.5); transform: scale(1.1); }
        .action-btn.active-dislike { color: #f44336; font-weight: bold; text-shadow: 0 0 5px rgba(0,0,0,0.5); transform: scale(1.1); }
        
        .admin-controls { display: none; margin-top: 5px; gap: 5px; border-top: 1px solid rgba(255,255,255,0.2); padding-top: 5px; }
        .is-admin .admin-controls { display: flex; }
        .btn-del { background: #555; color: white; border: none; padding: 3px 8px; border-radius: 4px; font-size: 0.7rem; cursor: pointer; }

        .chat-input-area { padding: 10px; display: flex; gap: 10px; background: rgba(0,0,0,0.2); flex-direction: column; }
        .input-row { display: flex; gap: 10px; width: 100%; align-items: center; }
        .chat-input { flex: 1; padding: 10px; border-radius: 20px; border: none; outline: none; background: rgba(255,255,255,0.1); color: var(--text); }
        .light-theme .chat-input { background: white; color: black; }
        .chat-send { width: 40px; height: 40px; border-radius: 50%; background: var(--primary); color: white; border: none; display: flex; justify-content: center; align-items: center; cursor: pointer; flex-shrink: 0; }
        .chat-attach-btn { width: 40px; height: 40px; border-radius: 50%; background: rgba(255,255,255,0.1); color: white; border: none; display: flex; justify-content: center; align-items: center; cursor: pointer; flex-shrink: 0; }
        
        .chat-img { max-width: 100%; border-radius: 10px; margin-top: 5px; cursor: pointer; border: 1px solid rgba(255,255,255,0.1); }

        .private-chat-list { flex: 1; overflow-y: auto; padding: 10px; }
        .private-chat-item { background: rgba(255,255,255,0.05); padding: 12px; border-radius: 10px; margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center; cursor: pointer; transition: background 0.2s; }
        .pc-user { font-weight: bold; font-size: 1rem; }
        .pc-preview { font-size: 0.8rem; opacity: 0.6; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; max-width: 200px; }
        
        #userActionModal .modal-box { text-align: center; }
        .action-menu-btn { width: 100%; padding: 12px; margin: 5px 0; border-radius: 8px; border: none; background: rgba(255,255,255,0.1); color: var(--text); font-size: 1rem; cursor: pointer; text-align: left; display: flex; align-items: center; gap: 10px; }
        
        #imgPreviewModal { background: rgba(0,0,0,0.95); display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; z-index: 5000; justify-content: center; align-items: center; }
        #imgPreviewModal img { max-width: 95%; max-height: 90%; border-radius: 10px; box-shadow: 0 0 20px rgba(0,0,0,0.5); }
        #imgPreviewModal i { position: absolute; top: 20px; right: 20px; font-size: 2rem; color: white; cursor: pointer; }

        .modal { position: fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.9); z-index:1000; display:none; justify-content:center; align-items:center; }
        .modal-box { background: var(--surface); width: 85%; max-width: 380px; border-radius: 20px; padding: 20px; border: 1px solid var(--border); }
        .opt { display: flex; align-items: center; padding: 15px; margin: 8px 0; border-radius: 12px; background: rgba(255,255,255,0.05); gap: 15px; cursor: pointer; color: white; }
        .light-theme .opt { background: rgba(0,0,0,0.05); color: #1a1a1a; }
        
        .banned-screen { display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:black; z-index:5000; color:red; flex-direction:column; justify-content:center; align-items:center; text-align:center; font-size:1.5rem; font-weight:bold; }
        .btn-confirm { background: #ff0040; color: white; border: none; padding: 10px 20px; border-radius: 8px; font-weight: bold; cursor: pointer; }
        .btn-cancel { background: #444; color: white; border: none; padding: 10px 20px; border-radius: 8px; font-weight: bold; cursor: pointer; }
        .admin-panel-btn { position: fixed; bottom: 20px; left: 20px; width: 50px; height: 50px; background: #ff0040; border-radius: 50%; display: none; justify-content: center; align-items: center; color: white; box-shadow: 0 5px 15px rgba(0,0,0,0.5); cursor: pointer; z-index: 200; }
        
        #adminPanelModal .modal-box { display: flex; flex-direction: column; max-height: 90vh; position: relative; padding-bottom: 70px; }
        .admin-modal-body { overflow-y: auto; text-align: left; padding-right: 5px; flex: 1; }
        #modalCloseBtn2 { position: absolute; bottom: 20px; left: 5%; width: 90%; background: #333; box-shadow: 0 -2px 10px rgba(0,0,0,0.5); }
        
        .admin-menu-btn { background: rgba(255,255,255,0.08); padding: 12px; border-radius: 10px; margin-top: 15px; color: #ffeb3b; font-weight: bold; cursor: pointer; display: flex; justify-content: space-between; align-items: center; border: 1px solid rgba(255, 235, 59, 0.3); }
        .admin-submenu { display: none; margin-top: 10px; padding-left: 5px; border-left: 2px solid #ffeb3b; }
        .admin-submenu.active { display: block; animation: slideDown 0.3s; }
        @keyframes slideDown { from { opacity: 0; transform: translateY(-10px); } to { opacity: 1; transform: translateY(0); } }

        .report-item { background: rgba(255,255,255,0.05); padding: 10px; border-radius: 8px; margin-bottom: 8px; border: 1px solid rgba(255,0,64,0.3); }
        .report-header { display: flex; justify-content: space-between; font-size: 0.8rem; color: #aaa; margin-bottom: 5px; }
        .report-msg { font-weight: bold; color: white; }
        .delete-all-btn { background: #ff0040; color: white; border: none; padding: 8px; width: 100%; border-radius: 8px; margin-bottom: 10px; cursor: pointer; font-weight: bold; display: flex; align-items: center; justify-content: center; gap: 8px; }

        #nameChangeModal .modal-box { text-align: center; }
        .custom-input { width: 90%; padding: 12px; margin: 15px 0; border-radius: 12px; border: 1px solid rgba(255,255,255,0.1); background: rgba(0,0,0,0.3); color: white; outline: none; font-size: 1rem; text-align: center; }
        
        #maintenanceScreen { display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:#111; z-index:9000; color:#ffeb3b; flex-direction:column; justify-content:center; align-items:center; text-align:center; }
        .emergency-input { background: rgba(255,255,255,0.1); border: 1px solid #ffeb3b; color: #fff; padding: 10px; margin-top: 20px; border-radius: 5px; width: 200px; text-align: center; }
        .emergency-btn { background: #ffeb3b; color: #000; border: none; padding: 10px 20px; border-radius: 5px; font-weight: bold; margin-top: 10px; cursor: pointer; }

        /* Açık tema kontrast düzeni */
        .light-theme { --bg:#eef1f6; --surface:#ffffff; --text:#172033; --card-bg:#ffffff; --border:#cbd3df; }
        .light-theme .top-bar,.light-theme .chat-modal,.light-theme .chat-header,.light-theme .chat-input-area { background:#ffffff; color:#172033; }
        .light-theme .card { background:#ffffff; border-color:#cbd3df; box-shadow:0 2px 8px rgba(35,48,70,.12); }
        .light-theme .card-name,.light-theme .card-meta,.light-theme .dropdown-content a,.light-theme .chat-close { color:#172033; }
        .light-theme .card-meta { opacity:.9; }
        .light-theme .stat-badge { background:#edf1f6; border-color:#c3ccd9; color:#253149; }
        .light-theme .theme-btn { background:#edf1f6; border-color:#b8c2d1; color:#172033; }
        .light-theme .online-badge { background:#e7f8ef; border-color:#8bd8ad; color:#08783e; }
        .light-theme .dropdown-content { background:#fff; border-color:#cbd3df; box-shadow:0 8px 18px rgba(35,48,70,.18); }
        .light-theme .dropdown-content a:hover,.light-theme .dropdown-content a:focus { background:#eaf2ff; color:#0b4f9c; }
        .light-theme .message-bubble { background:#ffffff; color:#172033; border:1px solid #cbd3df; box-shadow:0 2px 8px rgba(35,48,70,.12); }
        .light-theme .msg-right { background:#ffe7ef; color:#341321; border-color:#f0a9bd; }
        .light-theme .msg-user { color:#7d1738; opacity:1; }
        .light-theme .msg-time { color:#536174; opacity:1; }
        .light-theme .msg-text { color:#172033; }
        .light-theme .action-btn { color:#42516a; }
        .light-theme .action-btn:hover { color:#b0003a; }
        .light-theme .chat-tab { color:#172033; }
        .light-theme .chat-tabs { background:#e8edf4; }
        .light-theme .chat-rules { background:#fff1c7; border-color:#e4b900; color:#6b4b00; }
        .light-theme .chat-input { background:#f7f9fc; color:#172033; border:1px solid #b8c2d1; }
        .light-theme .chat-attach-btn { background:#e8edf4; color:#172033; border:1px solid #c0cad8; }
        .light-theme .chat-link-group,.light-theme .chat-link-card { background:#f5f8fc; border-color:#c4cedc; }
        .light-theme .chat-link-count,.light-theme .link-domain,.light-theme .link-url { color:#253149; opacity:1; }
        .light-theme .copy-all-links { color:#124b88; background:#e4f1ff; border-color:#8ab8e5; }
        .light-theme .opt { background:#f5f7fa; color:#172033; border:1px solid #cbd3df; }
        .light-theme .action-menu-btn { background:#f0f3f7; color:#172033; }
        .light-theme .private-chat-item { background:#f5f7fa; border:1px solid #cbd3df; color:#172033; }
        .light-theme .reply-preview-bar { background:#eef2f7; color:#253149; border-color:#b8c2d1; }
        .brand-lockup { display:none !important; }
        .dropbtn { min-width:132px !important; justify-content:center; padding:10px 14px !important; font-size:.84rem !important; }
        .tools-label { display:inline !important; }
        @media (max-width:500px) { .dropbtn { min-width:118px !important; padding:9px 12px !important; font-size:.78rem !important; } .header-actions { gap:5px; } }

        .formatted-chat-text { display:block; width:100%; box-sizing:border-box; padding:10px 11px; border-radius:8px; background:#07090d; border:1px solid rgba(255,255,255,.16); border-left:3px solid #00d2ff; color:#f4f6f8; font-size:.86rem; line-height:1.52; letter-spacing:.01em; white-space:pre-wrap !important; overflow-wrap:anywhere; word-break:normal; }
        .formatted-chat-text br { display:block; content:""; margin-top:2px; }
        .light-theme .formatted-chat-text { background:#f7f9fc; border-color:#b9c5d4; border-left-color:#1476c9; color:#172033; }
        .light-theme .formatted-chat-text br { border-color:#cbd3df; }

        .formatted-chat-text .chat-inline-link { color:#54d8ff; text-decoration:underline; text-decoration-thickness:1px; text-underline-offset:2px; font-weight:700; cursor:pointer; overflow-wrap:anywhere; }
        .formatted-chat-text .chat-inline-link:visited { color:#b98cff; }
        .formatted-chat-text .chat-inline-link:hover,.formatted-chat-text .chat-inline-link:focus { color:#fff; background:rgba(0,210,255,.18); border-radius:3px; outline:none; }
        .formatted-chat-text.collapsed-chat-text { max-height:360px; overflow:hidden; position:relative; }
        .formatted-chat-text.collapsed-chat-text:after { content:""; position:absolute; left:0; right:0; bottom:0; height:58px; background:linear-gradient(transparent,#07090d); pointer-events:none; }
        .chat-expand-btn { display:block; width:100%; margin-top:6px; padding:7px 10px; border:1px solid rgba(84,216,255,.45); border-radius:7px; background:rgba(0,210,255,.12); color:#54d8ff; font-weight:700; cursor:pointer; }
        .light-theme .formatted-chat-text .chat-inline-link { color:#075fa8; }
        .light-theme .formatted-chat-text .chat-inline-link:visited { color:#7040a5; }
        .light-theme .formatted-chat-text .chat-inline-link:hover,.light-theme .formatted-chat-text .chat-inline-link:focus { color:#043b69; background:#dceeff; }
        .light-theme .formatted-chat-text.collapsed-chat-text:after { background:linear-gradient(transparent,#f7f9fc); }
        .light-theme .chat-expand-btn { background:#e4f1ff; border-color:#83b6e5; color:#075fa8; }

        /* Araçlar: tema yüzeyinden ayrışan okunaklı menü */
        .dropdown-content { background:#151b2b; border:2px solid #00d2ff; box-shadow:0 12px 30px rgba(0,0,0,.65),0 0 0 3px rgba(0,210,255,.12); min-width:270px; }
        .dropdown-content a { color:#f7fbff; background:#151b2b; padding:14px 16px; font-size:.94rem; font-weight:700; border-bottom:1px solid rgba(255,255,255,.12); }
        .dropdown-content a i { color:#55dcff; width:22px; text-align:center; font-size:1.05rem; }
        .dropdown-content a:hover,.dropdown-content a:focus { color:#fff; background:linear-gradient(90deg,#e90046,#bf155f); padding-left:20px; }
        .dropdown-content a:hover i,.dropdown-content a:focus i { color:#fff; }
        .dropdown.open .dropdown-content { display:block; animation:fadeInMenu .18s ease; }
        .dropdown.open .dropbtn { box-shadow:0 0 0 3px rgba(255,0,64,.35),0 5px 18px rgba(0,210,255,.35); }
        .light-theme .dropdown-content { background:#172a46; border-color:#1679bd; box-shadow:0 12px 30px rgba(20,45,75,.35),0 0 0 3px rgba(22,121,189,.12); }
        .light-theme .dropdown-content a { color:#f7fbff; background:#172a46; border-bottom-color:rgba(255,255,255,.16); }
        .light-theme .dropdown-content a i { color:#72ddff; }
        .light-theme .dropdown-content a:hover,.light-theme .dropdown-content a:focus { color:#fff; background:linear-gradient(90deg,#c9003d,#8e185d); }
        @media (max-width:500px) { .dropdown-content { min-width:calc(100vw - 30px); max-width:calc(100vw - 30px); } .dropdown-content a { padding:14px 16px; font-size:.9rem; } }

        .player-preference-bar { display:none; align-items:center; justify-content:space-between; gap:10px; margin:0 15px -5px; padding:9px 11px; border:1px solid rgba(0,210,255,.35); border-radius:11px; background:linear-gradient(100deg,rgba(0,210,255,.12),rgba(255,0,64,.10)); color:var(--text); font-size:.78rem; font-weight:700; }
        .player-preference-bar .player-pref-label { display:flex; align-items:center; gap:7px; min-width:0; }
        .player-preference-bar .player-pref-label i { color:#00d2ff; }
        .player-visibility-toggle { border:1px solid #00d2ff; border-radius:8px; padding:7px 10px; background:#102a3b; color:#9cecff; font-weight:800; font-size:.72rem; cursor:pointer; white-space:nowrap; }
        .player-visibility-toggle.is-off { border-color:#ff557c; background:#3a1422; color:#ffabc0; }
        .light-theme .player-preference-bar { background:linear-gradient(100deg,#e4f5ff,#fff0f4); border-color:#8ab8d9; color:#172033; }
        .light-theme .player-preference-bar .player-pref-label i { color:#1476c9; }
        .light-theme .player-visibility-toggle { background:#e4f1ff; border-color:#1476c9; color:#075fa8; }
        .light-theme .player-visibility-toggle.is-off { background:#fff0f4; border-color:#c83d63; color:#9b2044; }
        @media (max-width:500px){ .player-preference-bar{margin:0 10px -5px;font-size:.72rem;} .player-visibility-toggle{padding:7px 8px;font-size:.68rem;} }
        /* Açık tema: tüm form, sohbet ve yönetim bileşenleri için yüksek kontrast */
        body.light-theme,
        body.light-theme * { -webkit-tap-highlight-color: rgba(176,0,58,.12); }
        .light-theme .modal-box,
        .light-theme #adminPanelModal .modal-box,
        .light-theme #editMessageModal .modal-box,
        .light-theme #confirmModal .modal-box,
        .light-theme #userActionModal .modal-box,
        .light-theme #nameChangeModal .modal-box { background:#ffffff; color:#172033; border-color:#b9c5d4; }
        .light-theme .modal-box h1,
        .light-theme .modal-box h2,
        .light-theme .modal-box h3,
        .light-theme .modal-box h4,
        .light-theme .modal-box p,
        .light-theme .modal-box label,
        .light-theme .modal-box span,
        .light-theme .admin-modal-body { color:#172033; }
        .light-theme .custom-input,
        .light-theme #editMessageInput,
        .light-theme .modal-box input,
        .light-theme .modal-box textarea,
        .light-theme .modal-box select { background:#ffffff; color:#172033; caret-color:#b0003a; border:2px solid #b0003a; box-shadow:0 1px 4px rgba(23,32,51,.08); }
        .light-theme .custom-input::placeholder,
        .light-theme #editMessageInput::placeholder { color:#536174; opacity:1; }
        .light-theme .custom-input:focus,
        .light-theme #editMessageInput:focus { background:#ffffff; color:#172033; border-color:#8e185d; outline:none; box-shadow:0 0 0 3px rgba(176,0,58,.18); }
        .light-theme .emergency-input { background:#ffffff; color:#172033; border-color:#b0003a; }
        .light-theme .chat-header { border-bottom:1px solid #cbd3df; }
        .light-theme .chat-header h3,
        .light-theme #chatStatus,
        .light-theme .chat-close,
        .light-theme .chat-tab,
        .light-theme .private-chat-header,
        .light-theme #privateChatUserName { color:#172033; }
        .light-theme .chat-tabs { border:1px solid #cbd3df; }
        .light-theme .chat-tab.active { color:#ffffff; }
        .light-theme .chat-rules strong,
        .light-theme .chat-rules b { color:#5a3b00; }
        .light-theme .message-bubble { color:#172033; }
        .light-theme .message-bubble .msg-content,
        .light-theme .message-bubble .msg-text,
        .light-theme .message-bubble .formatted-chat-text { color:#172033; }
        .light-theme .message-bubble.msg-right { color:#341321; }
        .light-theme .message-bubble.msg-right .msg-content,
        .light-theme .message-bubble.msg-right .msg-text { color:#341321; }
        .light-theme .admin-msg { background:#fff1f5; border-color:#e58aa7; color:#401323; }
        .light-theme .admin-msg .msg-content,
        .light-theme .admin-msg .msg-text { color:#401323; }
        .light-theme .msg-admin { color:#a60036; font-weight:800; }
        .light-theme .msg-time { color:#536174; opacity:1; }
        .light-theme .msg-actions { color:#42516a; }
        .light-theme .action-btn { color:#42516a; }
        .light-theme .action-btn:hover { color:#a60036; }
        .light-theme .admin-controls { border-top-color:#cbd3df; }
        .light-theme .btn-edit { background:#fff1c7; color:#6b4b00; border:1px solid #d6a700; }
        .light-theme .btn-edit:hover,
        .light-theme .btn-edit:focus { background:#ffe49a; color:#4c3300; }
        .light-theme .btn-del { background:#465166; color:#ffffff; }
        .light-theme .btn-confirm { color:#ffffff; }
        .light-theme .btn-cancel { background:#465166; color:#ffffff; }
        .light-theme .action-menu-btn,
        .light-theme .admin-menu-btn,
        .light-theme .private-chat-item,
        .light-theme .report-item { background:#f3f6fa; color:#172033; border-color:#c1ccda; }
        .light-theme .action-menu-btn i,
        .light-theme .admin-menu-btn i { color:#7d1738; }
        .light-theme .report-msg,
        .light-theme .report-header,
        .light-theme #bannedList,
        .light-theme #adminReportsList { color:#172033; }
        .light-theme .chat-input-area { border-top:1px solid #cbd3df; }
        .light-theme .chat-input { color:#172033; background:#f7f9fc; }
        .light-theme .chat-input::placeholder { color:#536174; opacity:1; }
        .light-theme .chat-attach-btn { color:#172033; }
        .light-theme .chat-send { color:#ffffff; }
        .light-theme .chat-link-card,
        .light-theme .chat-link-group { color:#253149; }
        .light-theme .link-icon.web { background:#e6edf5; color:#245178; }
        .light-theme .link-action-btn { background:#e4f1ff; color:#124b88; border-color:#8ab8e5; }
        .light-theme .link-action-btn:hover,
        .light-theme .link-action-btn:focus { color:#ffffff; }
        .light-theme .chat-links-toggle { color:#075fa8; background:#e4f1ff; border-color:#83b6e5; }
        .light-theme .quoted-msg { color:#42516a; background:#eef2f7; border-color:#b8c2d1; }
        .light-theme .toast { background:#ffffff; color:#172033; border-color:#b9c5d4; box-shadow:0 5px 20px rgba(23,32,51,.22); }
        .light-theme #modalCloseBtn,
        .light-theme #modalCloseBtn2 { color:#172033 !important; background:#e3e8ef !important; }
</style>
</head>
<body>
    <div id="toast" class="toast"></div>
    
    <div id="maintenanceScreen">
        <i class="fas fa-tools" style="font-size:4rem; margin-bottom:20px;"></i>
        <h1>BAKIM MODU</h1>
        <p style="color:#fff; opacity:0.7;">Şu an sistem güncelleniyor.<br>Lütfen daha sonra tekrar deneyin.</p>
        <input type="password" id="emergencyPass" class="emergency-input focusable" placeholder="Yönetici Şifresi">
        <button onclick="emergencyLogin()" class="emergency-btn focusable">Giriş Yap</button>
    </div>

    <div id="bannedScreen" class="banned-screen">
        <i class="fas fa-ban" style="font-size:4rem; margin-bottom:20px;"></i>
        <div>ENGELLENDİNİZ</div>
        <div style="font-size:1rem; color:white; margin-top:10px;">Sohbet kurallarına uymadığınız için erişiminiz kapatıldı.</div>
    </div>

    <div id="imgPreviewModal" onclick="this.style.display='none'">
        <i class="fas fa-times"></i>
        <img id="imgPreview" src="">
    </div>

    <div id="fileViewerModal" class="modal">
        <div class="modal-box" style="width: 90%; max-width: 600px; height: 80%; display:flex; flex-direction:column;">
            <h3 id="fvTitle" style="margin-top:0; color:var(--primary); text-align:center;">Dosya İçeriği</h3>
            <textarea id="fvContent" style="flex:1; background:#222; color:#0f0; border:1px solid #444; padding:10px; resize:none; font-family:monospace; border-radius:10px;" readonly></textarea>
            <div style="display:flex; gap:10px; margin-top:10px;">
                <button class="btn-confirm focusable" onclick="copyFileContent()" style="flex:1;"><i class="fas fa-copy"></i> Kopyala</button>
                <button class="btn-cancel focusable" onclick="document.getElementById('fileViewerModal').style.display='none'" style="flex:1;">Kapat</button>
            </div>
        </div>
    </div>

    <div id="confirmModal" class="modal">
        <div class="modal-box" style="text-align:center;">
            <i class="fas fa-exclamation-circle" style="font-size:3rem; color:#ff4d4d; margin-bottom:15px;"></i>
            <h3 id="confirmTitle" style="color:var(--text); margin-bottom:10px;">Emin misin?</h3>
            <p id="confirmText" style="color:var(--text); opacity:0.8; margin-bottom:20px;">Bu işlem geri alınamaz.</p>
            <div style="display:flex; gap:10px; justify-content:center;">
                <button class="btn-cancel focusable" onclick="closeConfirm()">Vazgeç</button>
                <button class="btn-confirm focusable" id="btnConfirmAction">ONAYLA</button>
            </div>
        </div>
    </div>

    <div id="editMessageModal" class="modal">
        <div class="modal-box" style="width: min(92vw, 620px);">
            <h3 style="color:var(--primary); margin-top:0;"><i class="fas fa-pen"></i> Yönetici Mesajını Düzenle</h3>
            <textarea id="editMessageInput" class="custom-input focusable" rows="8" maxlength="5000" placeholder="Mesaj metni..."></textarea>
            <div style="display:flex; gap:10px; justify-content:flex-end; margin-top:12px;">
                <button class="btn-cancel focusable" onclick="closeEditMessage()">Vazgeç</button>
                <button class="btn-confirm focusable" onclick="saveEditedMessage()"><i class="fas fa-save"></i> Kaydet</button>
            </div>
        </div>
    </div>

    <div id="userActionModal" class="modal">
        <div class="modal-box">
            <h3 id="uaTitle" style="color:var(--primary); margin-top:0;">Kullanıcı İşlemleri</h3>
            <button class="action-menu-btn focusable" onclick="executeUserAction('reply')"><i class="fas fa-reply"></i> Yanıtla</button>
            <button class="action-menu-btn focusable" onclick="executeUserAction('private')"><i class="fas fa-lock"></i> Özel Mesaj At</button>
            <div id="adminUserActions" style="display:none; border-top:1px solid rgba(255,255,255,0.1); margin-top:5px; padding-top:5px;">
                <button class="action-menu-btn focusable" onclick="executeUserAction('ban')" style="color:#ff4d4d;"><i class="fas fa-ban"></i> Engelle</button>
                <button class="action-menu-btn focusable" onclick="executeUserAction('delete')" style="color:#aaa;"><i class="fas fa-trash"></i> Mesajı Sil</button>
            </div>
            <button class="btn-cancel focusable" onclick="document.getElementById('userActionModal').style.display='none'" style="width:100%; margin-top:10px;">Kapat</button>
        </div>
    </div>

    <div id="nameChangeModal" class="modal">
        <div class="modal-box">
            <h3 id="nameModalTitle" style="color:var(--primary); margin-top:0;">İsim Değiştir</h3>
            <p id="nameModalHint" style="opacity:0.7; font-size:0.9rem;">Sohbette görünecek adınızı yazın:</p>
            <input type="text" id="newNameInput" class="custom-input focusable" placeholder="Örn: Ahmet_Bey" maxlength="15" autocomplete="nickname" onkeydown="if(event.key === 'Enter') saveName()">
            <div style="display:flex; gap:10px; justify-content:center;">
                <button id="nameModalCancel" class="btn-cancel focusable" onclick="closeNameModal()">İptal</button>
                <button class="btn-confirm focusable" onclick="saveName()">Kaydet</button>
            </div>
        </div>
    </div>

    <div id="adminPanelModal" class="modal">
        <div class="modal-box">
            <h3 style="text-align:center; color:#ff0040; margin-top:0;">🛡️ Yönetici Paneli</h3>
            
            <div class="admin-modal-body">
                
                <div class="admin-menu-btn focusable" onclick="toggleSubMenu('streamAdmin')">
                    <span>📺 Maç Yayını (Iframe & Dahili Player)</span> <i class="fas fa-chevron-down"></i>
                </div>
                <div id="streamAdmin" class="admin-submenu">
                    <p style="font-size:0.8rem; color:#aaa; margin-bottom:5px;">Link video ise kendi Video.js oynatıcımızda, değilse Iframe olarak açılır.</p>
                    <input type="text" id="stream1Inp" class="custom-input focusable" placeholder="Kanal 1 Linki (Zorunlu)">
                    <input type="text" id="stream2Inp" class="custom-input focusable" placeholder="Kanal 2 Linki (Opsiyonel)">
                    <input type="text" id="stream3Inp" class="custom-input focusable" placeholder="Kanal 3 Linki (Opsiyonel)">
                    <input type="text" id="streamRefInp" class="custom-input focusable" placeholder="Referer (İsteğe Bağlı)" style="border-color:#00d2ff;">
                    <input type="text" id="streamUaInp" class="custom-input focusable" placeholder="User-Agent (İsteğe Bağlı)" style="border-color:#00d2ff;">
                    
                    <div style="display:flex; gap:5px;">
                        <button onclick="saveStreams()" class="btn-confirm focusable" style="flex:1;">Yayınla</button>
                        <button onclick="stopStreams()" class="btn-cancel focusable" style="flex:1;">Kapat</button>
                    </div>
                </div>

                <div class="admin-menu-btn focusable" onclick="toggleSubMenu('scoreAdmin')">
                    <span>⚽ Canlı Skor (Manuel)</span> <i class="fas fa-chevron-down"></i>
                </div>
                <div id="scoreAdmin" class="admin-submenu">
                    <p style="font-size:0.8rem; color:#aaa; margin-bottom:5px;">Otomatik takip Python botu (Menü: 7) ile arka planda yapılabilir.</p>
                    <input type="text" id="lsInpTeamA" class="custom-input focusable" placeholder="Ev Sahibi (Örn: Galatasaray)">
                    <input type="text" id="lsInpTeamB" class="custom-input focusable" placeholder="Deplasman (Örn: Fenerbahçe)">
                    <div style="display:flex; gap:5px;">
                        <input type="number" id="lsInpScoreA" class="custom-input focusable" placeholder="Skor A">
                        <input type="number" id="lsInpScoreB" class="custom-input focusable" placeholder="Skor B">
                    </div>
                    <input type="text" id="lsInpMinute" class="custom-input focusable" placeholder="Dakika (Örn: 45' veya IY)">
                    <input type="text" id="lsInpEvents" class="custom-input focusable" placeholder="Olaylar (Örn: ⚽ 12' Icardi)">
                    <div style="display:flex; gap:5px;">
                        <button onclick="saveLiveScore()" class="btn-confirm focusable" style="flex:1;">Manuel Yayınla</button>
                        <button onclick="stopLiveScore()" class="btn-cancel focusable" style="flex:1;">Kapat</button>
                    </div>
                </div>

                <div class="admin-menu-btn focusable" onclick="toggleSubMenu('pollAdmin')">
                    <span>📊 Anket Yönetimi</span> <i class="fas fa-chevron-down"></i>
                </div>
                <div id="pollAdmin" class="admin-submenu">
                    <input type="text" id="pollQuestion" class="custom-input focusable" placeholder="Soru: Örn. Kim Kazanır?">
                    <input type="text" id="pollOpt1" class="custom-input focusable" placeholder="Seçenek 1 (Örn. GS)">
                    <input type="text" id="pollOpt2" class="custom-input focusable" placeholder="Seçenek 2 (Örn. FB)">
                    <div style="display:flex; gap:5px;">
                        <button onclick="savePoll()" class="btn-confirm focusable" style="flex:1;">Başlat</button>
                        <button onclick="resetPoll()" class="btn-cancel focusable" style="flex:1;">Sıfırla</button>
                    </div>
                </div>

                <div class="admin-menu-btn focusable" onclick="toggleSubMenu('countdownAdmin')">
                    <span>⏳ Geri Sayım Yönetimi</span> <i class="fas fa-chevron-down"></i>
                </div>
                <div id="countdownAdmin" class="admin-submenu">
                    <input type="text" id="cdTitle" class="custom-input focusable" placeholder="Başlık: Örn. DERBİ MAÇI">
                    <input type="datetime-local" id="cdDate" class="custom-input focusable" style="color-scheme: dark;">
                    <div style="display:flex; gap:5px;">
                        <button onclick="saveCountdown()" class="btn-confirm focusable" style="flex:1;">Başlat</button>
                        <button onclick="stopCountdown()" class="btn-cancel focusable" style="flex:1;">Durdur</button>
                    </div>
                </div>

                <div class="admin-menu-btn focusable" onclick="toggleSubMenu('annoAdmin')">
                    <span>📢 Kayan Yazı Duyuru</span> <i class="fas fa-chevron-down"></i>
                </div>
                <div id="annoAdmin" class="admin-submenu">
                    <input type="text" id="annoInput" class="custom-input focusable" placeholder="Duyuru Metni: (Örn: Yayınlar Başladı!)">
                    <div style="display:flex; gap:5px;">
                        <button onclick="saveAnnouncement()" class="btn-confirm focusable" style="flex:1;">Yayınla</button>
                        <button onclick="stopAnnouncement()" class="btn-cancel focusable" style="flex:1;">Kaldır</button>
                    </div>
                </div>

                <div class="admin-menu-btn focusable" onclick="toggleSubMenu('settingsContainer')"><span>⚙️ Genel Ayarlar</span> <i class="fas fa-chevron-down"></i></div>
                <div id="settingsContainer" class="admin-submenu">
                    <div style="margin-bottom:10px;"><input type="checkbox" id="maintenanceToggle" class="focusable" onchange="toggleMaintenance()"> <label style="color:inherit">🚧 Bakım Modu</label></div>
                    <div><input type="checkbox" id="chatLockToggle" class="focusable" onchange="toggleChatLock()"> <label style="color:inherit">🔒 Sohbeti Kilitle</label></div>
                    <button class="delete-all-btn focusable" style="background:#555; margin-top:10px;" onclick="clearChat()">🧹 Sohbeti Temizle</button>
                </div>

                <div class="admin-menu-btn focusable" onclick="toggleSubMenu('toastContainer')"><span>📢 Açılış Mesajı</span> <i class="fas fa-chevron-down"></i></div>
                <div id="toastContainer" class="admin-submenu">
                    <input type="text" id="adminToastInput" class="custom-input focusable" placeholder="Mesajınız...">
                    <div style="display:flex; align-items:center; gap:10px; margin-top:5px;"><input type="checkbox" id="adminToastActive" style="width:20px; height:20px;"> <label for="adminToastActive" style="color:inherit">Aktif Et</label></div>
                    <button onclick="saveStartupMessage()" class="btn-confirm focusable" style="width:100%; margin-top:10px;">Kaydet</button>
                </div>

                <div class="admin-menu-btn focusable" onclick="toggleBannedList()"><span>🚫 Yasaklılar</span> <i class="fas fa-chevron-down"></i></div>
                <div id="bannedContainer" class="admin-submenu"><div id="bannedList"><p style="opacity:0.5">Yükleniyor...</p></div></div>

                <div class="admin-menu-btn focusable" onclick="toggleReports()"><span>⚠️ Bildirimler (<span id="reportCount">0</span>)</span> <i class="fas fa-chevron-down"></i></div>
                <div id="reportsContainer" class="admin-submenu">
                    <button class="delete-all-btn focusable" onclick="deleteAllReports()"><i class="fas fa-trash-alt"></i> TÜMÜNÜ SİL</button>
                    <div id="adminReportsList"><p style="opacity:0.5">Yükleniyor...</p></div>
                </div>
            </div>
            <button onclick="document.getElementById('adminPanelModal').style.display='none'" id="modalCloseBtn2" class="focusable">Kapat</button>
        </div>
    </div>

  <div class="top-bar">
    <div class="dropdown" id="toolsDropdown">
        <button type="button" class="dropbtn focusable" id="toolsToggle" onclick="toggleToolsMenu(event)" title="IPTV araçlarını aç/kapat" aria-label="IPTV araçlarını aç/kapat" aria-expanded="false"><span class="tools-label">IPTV ARAÇLAR</span> <i class="fas fa-tools"></i></button>
        <div class="dropdown-content">
            <a href="go:combo" class="focusable"><i class="fas fa-search"></i> Kombo Tarama 1</a>

            <a href="go:com2" class="focusable"><i class="fas fa-search"></i> Kombo Tarama 2</a>

            <a href="go:combo4" class="focusable"><i class="fas fa-search"></i> Kombo Tarama 3</a>
            
            <a href="go:combo5" class="focusable"><i class="fas fa-search"></i> Kombo Tarama 4</a>
            
            <a href="go:combo6" class="focusable"><i class="fas fa-search"></i> Kombo Tarama 5 </a>

            <a href="go:vegatta" class="focusable"><i class="fas fa-bolt"></i> Combo Tarama Vegatta</a>
            <a href="go:dns" class="focusable yan-dns-link yan-dns-panel"><i class="fas fa-server"></i> Yan DNS Tarama <strong>"PANEL"</strong></a>
            <a href="go:dns2" class="focusable yan-dns-link yan-dns-user"><i class="fas fa-user-lock"></i> Yan DNS Tarama <strong>"USER:PAS"</strong></a>
            <a href="go:yan3" class="focusable yan-dns-link yan-dns-m3u"><i class="fas fa-link"></i> Yan DNS Tarama <strong>"M3U LİNK"</strong></a>
            
            <a href="go:panel" class="focusable"><i class="fas fa-server"></i> IPTV Panel Kontrol</a>

            <a href="go:stb" class="focusable"><i class="fas fa-server"></i> Mac To M3u</a>
        </div>
    </div>

        <div class="header-actions">
            <div class="online-badge" title="Online Sayısı"><i class="fas fa-users"></i> <span id="onlineCount">0</span></div>
            <button class="theme-btn focusable" onclick="toggleTheme()" id="themeBtn"><i class="fas fa-moon"></i></button>
            <a href="{telegram_link}" id="telegramBtn" class="focusable" style="color:white; font-size:1.4rem; padding:5px;"><i class="fab fa-telegram"></i></a>
        </div>
    </div>

    <div id="announcementBar" class="announcement-bar">
        <div class="announcement-content" id="announcementText"></div>
    </div>

    <div class="feature-container" id="featureContainer">
        
        <div id="playerPreferenceBar" class="player-preference-bar">
            <span class="player-pref-label"><i class="fas fa-tv"></i> <span>Admin yayını: Player görünümü</span></span>
            <button type="button" id="playerVisibilityToggle" class="player-visibility-toggle focusable" onclick="toggleUserPlayerVisibility()" aria-pressed="true">Player Açık</button>
        </div>
        <div id="streamBox" class="stream-box">
            <div class="quick-close-btn focusable" onclick="stopStreams()" title="Yayını Kapat"><i class="fas fa-times"></i></div>
            
            <div class="iframe-container" id="playerWrapper">
                <iframe id="matchIframe" allowfullscreen allow="autoplay; encrypted-media" style="display:none; position:absolute; top:0; left:0; width:100%; height:100%; border:0; z-index:10; background:#000;"></iframe>
                
                <div id="matchVideoWrapper" style="display:none; width:100%; height:100%; position:absolute; top:0; left:0; z-index:1;">
                    <video id="matchVideo" playsinline crossorigin="anonymous" class="video-js vjs-default-skin vjs-big-play-centered" controls preload="auto"></video>
                </div>
            </div>

            <div class="stream-channels" id="streamChannelsContainer">
                <button id="btnCh1" class="ch-btn focusable" onclick="changeStream(1)">Kanal 1</button>
                <button id="btnCh2" class="ch-btn focusable" onclick="changeStream(2)">Kanal 2</button>
                <button id="btnCh3" class="ch-btn focusable" onclick="changeStream(3)">Kanal 3</button>
            </div>
        </div>

        <div id="liveScoreBox" class="livescore-box focusable" tabindex="0">
            <div class="quick-close-btn focusable" onclick="stopLiveScore()" title="Skoru Kapat"><i class="fas fa-times"></i></div>
            <div class="ls-header"><span class="ls-live-dot"></span> CANLI SKOR | <span id="lsMinute" class="ls-minute">45'</span></div>
            <div class="ls-row">
                <div class="ls-team" id="lsTeamA" style="text-align: right;">Takım A</div>
                <div class="ls-score-wrap">
                    <span class="ls-score" id="lsScoreA">0</span>
                    <span class="ls-divider">-</span>
                    <span class="ls-score" id="lsScoreB">0</span>
                </div>
                <div class="ls-team" id="lsTeamB" style="text-align: left;">Takım B</div>
            </div>
            <div class="ls-events" id="lsEvents">⚽ Otomatik Skor Takip Aktif</div>
        </div>

        <div id="countdownBox" class="countdown-box">
            <div class="quick-close-btn focusable" onclick="stopCountdown()" title="Sayacı Kapat"><i class="fas fa-times"></i></div>
            <div id="countdownTitle" class="countdown-title">GERİ SAYIM</div>
            <div id="countdownTimer" class="countdown-timer">
                <div class="time-unit"><span id="cdDays">00</span><span class="time-label">GÜN</span></div>:
                <div class="time-unit"><span id="cdHours">00</span><span class="time-label">SAAT</span></div>:
                <div class="time-unit"><span id="cdMins">00</span><span class="time-label">DAK</span></div>:
                <div class="time-unit"><span id="cdSecs">00</span><span class="time-label">SAN</span></div>
            </div>
        </div>

        <div id="pollBox" class="poll-box">
            <div class="quick-close-btn focusable" onclick="resetPoll()" title="Anketi Kapat"><i class="fas fa-times"></i></div>
            <span id="displayPollQuestion" class="poll-question">Anket Yükleniyor...</span>
            <div class="poll-option focusable" onclick="votePoll('opt1')">
                <div class="poll-bar-bg"><div id="bar1" class="poll-bar-fill"></div></div>
                <div class="poll-text" id="displayOpt1">A</div>
                <div class="poll-percent" id="percent1">0%</div>
            </div>
            <div class="poll-option focusable" onclick="votePoll('opt2')">
                <div class="poll-bar-bg"><div id="bar2" class="poll-bar-fill"></div></div>
                <div class="poll-text" id="displayOpt2">B</div>
                <div class="poll-percent" id="percent2">0%</div>
            </div>
        </div>
    </div>

    <div class="container"><div id="list"></div></div>
    
    <button class="load-more-btn focusable" id="loadMoreBtn" onclick="loadMore()">Daha Fazla Göster</button>

    <div class="chat-btn-container" onclick="toggleChat()">
        <span class="chat-label">FORUM/SOHBET</span>
        <div class="chat-btn focusable" tabindex="0">
            <i class="fas fa-comment-dots" id="chatIcon"></i>
        </div>
    </div>

    <div class="admin-panel-btn focusable" id="adminBtn" onclick="openAdminPanel()" tabindex="0"><i class="fas fa-shield-alt"></i></div>
    
    <div class="chat-modal" id="chatModal">
        <div class="chat-header">
            <div class="chat-header-top">
                <div style="display:flex; align-items:center; gap:10px;">
                    <span style="font-weight:bold;" id="chatStatus">Canlı Sohbet 🟢</span>
                    <i class="fas fa-edit focusable" onclick="openNameModal()" style="cursor:pointer; opacity:0.7; font-size:0.9rem; padding:5px;" title="İsim Değiştir"></i>
                </div>
                <i class="fas fa-times chat-close focusable" onclick="toggleChat()" style="padding:5px;"></i>
            </div>
            <div class="chat-tabs">
                <div class="chat-tab active focusable" id="tabGlobal" onclick="switchChatTab('global')">Genel</div>
                <div class="chat-tab focusable" id="tabPrivate" onclick="switchChatTab('private')">Özel Mesajlar <span id="pmBadge" class="chat-tab-badge">0</span></div>
            </div>
        </div>
        
        <div class="chat-rules" id="chatRulesBanner"><i class="fas fa-exclamation-triangle"></i> UYARI: Argo ve sohbet dışı mesaj atanlar SÜRESİZ banlanır!</div>
        
        <div id="viewGlobal" class="chat-view">
            <div class="chat-messages" id="chatContainer"></div>
        </div>
        
        <div id="viewPrivateList" class="chat-view hidden">
            <div class="private-chat-list" id="privateChatListContainer"></div>
        </div>
        
        <div id="viewPrivateConv" class="chat-view hidden">
            <div style="background:rgba(0,0,0,0.3); padding:8px; display:flex; align-items:center;">
                <button onclick="backToPrivateList()" class="focusable" style="background:none; border:none; color:white; font-size:1.2rem; cursor:pointer;"><i class="fas fa-arrow-left"></i></button>
                <span id="privateChatUserName" style="margin-left:15px; font-weight:bold;">Kullanıcı</span>
            </div>
            <div class="chat-messages" id="privateChatContainer"></div>
        </div>

        <div id="replyPreviewBar" class="reply-preview-bar">
            <div style="display:flex; align-items:center; gap:10px;">
                <i class="fas fa-reply"></i> 
                <div>
                    <b id="replyToUser">Kullanıcı</b>
                    <div id="replyToText" style="font-size:0.8rem; font-style:italic;">Mesaj...</div>
                </div>
            </div>
            <i class="fas fa-times focusable" onclick="cancelReply()" style="cursor:pointer; font-size:1.2rem;"></i>
        </div>
        <div class="chat-input-area">
            <div class="input-row">
                <button class="chat-attach-btn focusable" onclick="document.getElementById('fileUpload').click()"><i class="fas fa-paperclip"></i></button>
                <button class="chat-attach-btn focusable" onclick="document.getElementById('imgUpload').click()"><i class="fas fa-image"></i></button>
                
                <input type="file" id="imgUpload" accept="image/*" style="display:none" onchange="handleImageUpload(event)">
                <input type="file" id="fileUpload" accept=".txt,.html,.xml,.m3u" style="display:none" onchange="handleFileUpload(event)">
                
                <input type="text" class="chat-input focusable" id="msgInput" placeholder="Mesaj yaz veya link yapıştır...">
                <button class="chat-send focusable" onclick="sendMsg()"><i class="fas fa-paper-plane"></i></button>
            </div>
        </div>
    </div>
    
    <div class="modal" id="modal">
        <div class="modal-box">
            <h3 id="mTitle" style="text-align:center; margin-top:0; color:var(--primary);"></h3>
            <div class="opt focusable" id="wuffy"><i class="fas fa-play" style="color:var(--primary)"></i> <b>Wuffy Player</b></div>
            <div class="opt focusable" id="xpola"><i class="fas fa-rocket" style="color:var(--primary)"></i> <b>Xpola Player</b></div>
            <div class="opt focusable" id="externalWeb" style="background: rgba(255,171,0,0.1); border: 1px solid #ffab00;">
                <i class="fas fa-external-link-alt" style="color:#ffab00"></i> <b style="color:#ffab00">Tarayıcıda Aç / İndir</b>
            </div>
            
            <div class="admin-delete-btn focusable" id="adminDeleteCardBtn" onclick="deleteCurrentCard()">
                <i class="fas fa-trash-alt"></i> <b>SİSTEMDEN SİL (Herkes İçin)</b>
            </div>

            <button onclick="document.getElementById('modal').style.display='none'" style="width:100%; padding:12px; border-radius:10px; border:none; background:#333; color:white; margin-top:10px; cursor:pointer; font-weight:bold;" id="modalCloseBtn" class="focusable">Vazgeç</button>
        </div>
    </div>

    <div id="fullPlayerContainer" style="display:none; position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; background-color: black; z-index: 3000;">
        <button id="closeFullPlayerBtn" tabindex="0" class="focusable" style="position: absolute; top: 20px; right: 20px; z-index: 4000; background: rgba(227, 10, 23, 0.8); color: white; border: 2px solid rgba(255,255,255,0.2); padding: 8px 16px; border-radius: 8px; font-size: 1rem; font-weight: 600; cursor: pointer;"><i class="fas fa-times"></i> Yayını Kapat</button>
        
        <iframe id="fullIframe" allowfullscreen allow="autoplay; encrypted-media" style="display:none; position:absolute; top:0; left:0; width:100%; height:100%; border:0; z-index:10; background:#000;"></iframe>
        
        <div id="fullVideoWrapper" style="width:100%; height:100%; position:absolute; top:0; left:0; z-index:1;">
            <video id="fullVideo" playsinline crossorigin="anonymous" class="video-js vjs-default-skin vjs-big-play-centered" controls preload="auto"></video>
        </div>
    </div>

    <script>{{DATA_PLACEHOLDER}}</script>

    <script>
        const firebaseConfig = {
          apiKey: "AIzaSyCZFwiLcV4K3EnRDWpPPlXPrXSJxAuMfaQ",
          authDomain: "iptvbotcoun.firebaseapp.com",
          databaseURL: "https://iptvbotcoun-default-rtdb.firebaseio.com",
          projectId: "iptvbotcoun",
          storageBucket: "iptvbotcoun.firebasestorage.app",
          messagingSenderId: "229841892818",
          appId: "1:229841892818:web:a91dd3792919140a5d440b"
        };

        firebase.initializeApp(firebaseConfig);
        const database = firebase.database();

        let current = {};
        let itemsPerPage = 50; 
        let currentlyShown = itemsPerPage;
        let globalViewCounts = {};
        let globalLikeCounts = {};
        let myLikes = JSON.parse(localStorage.getItem('my_likes') || "[]");
        let myUserName = localStorage.getItem('chat_username');
        let myUUID = localStorage.getItem('user_uuid');
        let isAdmin = localStorage.getItem('is_admin') === 'true';
        let currentReply = null; 
        let isChatLocked = false;
        let countdownInterval;
        let rulesTimeout;
        let lastFocusedElement = null;
        window.hiddenCards = {};

        let currentTab = 'global'; 
        let currentPrivateRoom = null;
        let currentTargetUser = null;
        let activePrivateListener = null;

        let lastScoreA = -1;
        let lastScoreB = -1;
        
        let matchVjsPlayer = null;
        let fullVjsPlayer = null;

        window.countdownData = { active: false, target: 0 };
        window.livescoreDataActive = false;
        window.streamDataActive = false;
        window.currentStreams = { ch1: '', ch2: '', ch3: '', referer: '', userAgent: '' };

        const ADMIN_PASS = "{{ADMIN_PASSWORD_PLACEHOLDER}}";

        if(!myUUID) { myUUID = 'user_' + Date.now() + '_' + Math.floor(Math.random() * 1000); localStorage.setItem('user_uuid', myUUID); }
        // Yeni cihazlarda otomatik Misafir adı oluşturulmaz; sohbet için gerçek nick zorunludur.
        if(myUserName && /^Misafir_\\d+$/.test(myUserName)) { myUserName = null; localStorage.removeItem('chat_username'); }
        let nameModalRequired = false;

        function openNameModal(required = false) {
            nameModalRequired = required;
            const modal = document.getElementById('nameChangeModal');
            const input = document.getElementById('newNameInput');
            const cancel = document.getElementById('nameModalCancel');
            const title = document.getElementById('nameModalTitle');
            const hint = document.getElementById('nameModalHint');
            title.innerText = required ? 'Sohbete Hoş Geldiniz' : 'İsim Değiştir';
            hint.innerText = required ? 'Sohbete katılmak için lütfen bir nick yazın. Bu nick cihazınıza kaydedilecektir.' : 'Sohbette görünecek adınızı yazın:';
            cancel.style.display = required ? 'none' : 'inline-block';
            input.value = required ? '' : (myUserName || '');
            modal.style.display = 'flex';
            setTimeout(() => input.focus(), 50);
        }
        function closeNameModal() {
            if(nameModalRequired) { document.getElementById('newNameInput').focus(); return; }
            document.getElementById('nameChangeModal').style.display = 'none';
        }
        function saveName() {
            const input = document.getElementById('newNameInput');
            const inputVal = input.value.trim().replace(/\s+/g, ' ');
            if(inputVal.length < 2) { showToast('Lütfen en az 2 karakterli bir nick yazın.', 'fa-exclamation'); input.focus(); return; }
            myUserName = inputVal.substring(0, 15);
            localStorage.setItem('chat_username', myUserName);
            const wasRequired = nameModalRequired;
            nameModalRequired = false;
            document.getElementById('nameChangeModal').style.display = 'none';
            showToast(wasRequired ? 'Nick kaydedildi: ' + myUserName : 'İsim Değiştirildi: ' + myUserName, 'fa-check');
        }
        function getUserColor(username) { let hash = 0; for (let i = 0; i < username.length; i++) { hash = username.charCodeAt(i) + ((hash << 5) - hash); } const hue = Math.abs(hash % 360); return `hsl(${hue}, 70%, 45%)`; }
        function initPresence() { const onlineRef = database.ref('online_users'); const myCon = onlineRef.push(); myCon.onDisconnect().remove(); myCon.set(true); onlineRef.on('value', (s) => { document.getElementById('onlineCount').innerText = s.numChildren(); }); }
        function showToast(message, icon="fa-info-circle") { const t = document.getElementById('toast'); t.innerHTML = `<i class="fas ${icon}"></i> <span>${message}</span>`; t.className = "toast show"; setTimeout(() => { t.className = t.className.replace("show", ""); }, 5000); }
        function formatTime(ts) { const d = new Date(ts); return d.getHours().toString().padStart(2, '0') + ':' + d.getMinutes().toString().padStart(2, '0'); }

        function processText(text) {
            if(!text) return "";
            const urlRegex = /(https?:\/\/[^\s]+)/g;
            return text.replace(urlRegex, function(url) { return `<a href="${url}" target="_blank" class="chat-link focusable">${url}</a>`; });
        }
        
        function openInAppViewer(base64Data, fileName) {
            if(base64Data.startsWith('data:image')) { showImagePreview(base64Data); return; }
            try {
                var content = base64Data.split(',')[1];
                var decodedText = "";
                try { decodedText = decodeURIComponent(escape(atob(content))); } catch(e) { decodedText = atob(content); }
                document.getElementById('fvTitle').innerText = fileName;
                document.getElementById('fvContent').value = decodedText;
                document.getElementById('fileViewerModal').style.display = 'flex';
            } catch(e) { console.error("Viewer error:", e); showToast("Dosya okunamadı!", "fa-exclamation"); }
        }

        function copyFileContent() {
            var copyText = document.getElementById("fvContent");
            copyText.select(); copyText.setSelectionRange(0, 99999);
            document.execCommand("copy"); showToast("Kopyalandı!", "fa-check");
        }

        let selectedUserForAction = null;
        function openUserActionModal(targetUUID, targetName, msgId, textContent, imgContent) {
            if(targetUUID === myUUID) return; 
            selectedUserForAction = { uuid: targetUUID, name: targetName, msgId: msgId, text: textContent, image: imgContent };
            document.getElementById('uaTitle').innerText = targetName;
            document.getElementById('userActionModal').style.display = 'flex';
            if(isAdmin) document.getElementById('adminUserActions').style.display = 'block';
            else document.getElementById('adminUserActions').style.display = 'none';
        }

        function executeUserAction(action) {
            document.getElementById('userActionModal').style.display = 'none';
            if(!selectedUserForAction) return;
            if(action === 'reply') { startReply(selectedUserForAction.name, selectedUserForAction.text, selectedUserForAction.image); } 
            else if (action === 'private') { startPrivateChat(selectedUserForAction.uuid, selectedUserForAction.name); } 
            else if (action === 'ban') { openConfirmModal('ban', selectedUserForAction.uuid); } 
            else if (action === 'delete') { openConfirmModal('del', selectedUserForAction.msgId); }
        }

        function switchChatTab(tab) {
            currentTab = tab;
            document.querySelectorAll('.chat-tab').forEach(t => t.classList.remove('active'));
            document.getElementById(tab === 'global' ? 'tabGlobal' : 'tabPrivate').classList.add('active');
            
            document.getElementById('viewGlobal').classList.add('hidden');
            document.getElementById('viewPrivateList').classList.add('hidden');
            document.getElementById('viewPrivateConv').classList.add('hidden');
            
            if(tab === 'global') {
                document.getElementById('viewGlobal').classList.remove('hidden');
                document.getElementById('msgInput').placeholder = "Genel sohbete yaz...";
                currentPrivateRoom = null;
            } else {
                if(currentPrivateRoom) {
                     document.getElementById('viewPrivateConv').classList.remove('hidden');
                     document.getElementById('msgInput').placeholder = "Özel mesaj yaz...";
                } else {
                    document.getElementById('viewPrivateList').classList.remove('hidden');
                    document.getElementById('msgInput').placeholder = "Bir sohbet seç...";
                }
                document.getElementById('pmBadge').style.display = 'none';
                document.getElementById('pmBadge').innerText = '0';
            }
        }

        function getRoomId(uid1, uid2) { const sorted =[uid1, uid2].sort(); return sorted[0] + "_" + sorted[1]; }

        function startPrivateChat(targetUUID, targetName) {
            toggleChat(); 
            document.getElementById('chatModal').classList.add('active');
            currentTargetUser = { uuid: targetUUID, name: targetName };
            currentPrivateRoom = getRoomId(myUUID, targetUUID);
            switchChatTab('private');
            document.getElementById('viewPrivateList').classList.add('hidden');
            document.getElementById('viewPrivateConv').classList.remove('hidden');
            document.getElementById('privateChatUserName').innerText = targetName;
            document.getElementById('privateChatContainer').innerHTML = '<p style="text-align:center; opacity:0.5; margin-top:20px;">Sohbet yükleniyor...</p>';
            listenToPrivateRoom(currentPrivateRoom);
        }

        function backToPrivateList() { currentPrivateRoom = null; if(activePrivateListener) activePrivateListener.off(); switchChatTab('private'); }

        function listenToPrivateRoom(roomId) {
            if(activePrivateListener) activePrivateListener.off();
            const ref = database.ref('private_chats/' + roomId);
            activePrivateListener = ref;
            document.getElementById('privateChatContainer').innerHTML = '';
            ref.limitToLast(50).on('child_added', (snapshot) => { const msg = snapshot.val(); appendPrivateMessage(msg); });
        }

        function appendPrivateMessage(msg) {
            const container = document.getElementById('privateChatContainer');
            const div = document.createElement('div');
            let isMe = msg.user === myUserName;
            let bgColor = isMe ? '' : `background-color: ${getUserColor(msg.user)};`;
            div.className = `message-bubble ${isMe ? 'msg-right' : 'msg-left'} ${isAdmin ? 'is-admin' : ''}`;
            if(!isMe) div.style.cssText = bgColor;
            
            let contentHTML = "";
            if(msg.image) contentHTML = `<img src="${msg.image}" class="chat-img" onclick="showImagePreview('${msg.image}')">`;
            else if(msg.file) contentHTML = `<div class="chat-file-block" onclick="openInAppViewer('${msg.file.data}', '${msg.file.name}')"><i class="fas fa-file-alt file-icon"></i><div class="file-info"><span class="file-name">${msg.file.name}</span><span class="file-dl">Görüntüle/Kopyala</span></div></div>`;
            else contentHTML = processText(msg.text);
            
            let timeHTML = `<span class="msg-time">${formatTime(msg.time || Date.now())}</span>`;
            div.innerHTML = `<span class="msg-user">${msg.user}</span>${contentHTML}${timeHTML}`;
            container.appendChild(div);
            container.scrollTop = container.scrollHeight;
        }

        function listenToAllPrivateChats() {
            database.ref('user_inbox/' + myUUID).on('value', (s) => {
                const listContainer = document.getElementById('privateChatListContainer');
                listContainer.innerHTML = '';
                let count = 0;
                if(!s.exists()) { listContainer.innerHTML = '<p style="text-align:center; opacity:0.6; margin-top:20px;">Henüz özel mesajın yok.</p>'; return; }
                s.forEach(child => {
                    const data = child.val();
                    const targetUUID = child.key;
                    count++;
                    const div = document.createElement('div');
                    div.className = 'private-chat-item focusable';
                    div.onclick = () => startPrivateChat(targetUUID, data.name);
                    div.innerHTML = `<div style="flex:1;"><div class="pc-user">${data.name}</div><div class="pc-preview">${data.lastMsg || "Ek"}</div></div><div style="font-size:0.7rem; opacity:0.5;">${formatTime(data.timestamp)}</div>`;
                    listContainer.appendChild(div);
                });
                if(currentTab === 'global') { const badge = document.getElementById('pmBadge'); badge.innerText = count > 0 ? "!" : "0"; badge.style.display = count > 0 ? 'inline-block' : 'none'; }
            });
        }

        let userPlayerVisible = localStorage.getItem('user_player_visible') !== 'false';

        function updatePlayerVisibilityButton() {
            const bar = document.getElementById('playerPreferenceBar');
            const button = document.getElementById('playerVisibilityToggle');
            if(!button) return;
            button.textContent = userPlayerVisible ? 'Player Açık' : 'Player Kapalı';
            button.classList.toggle('is-off', !userPlayerVisible);
            button.setAttribute('aria-pressed', userPlayerVisible ? 'true' : 'false');
            if(bar) bar.style.display = window.streamDataActive && !(window.countdownData && window.countdownData.active) ? 'flex' : 'none';
        }

        function toggleUserPlayerVisibility() {
            userPlayerVisible = !userPlayerVisible;
            localStorage.setItem('user_player_visible', userPlayerVisible ? 'true' : 'false');
            if(!userPlayerVisible) {
                const iframe = document.getElementById('matchIframe');
                if(iframe) iframe.src = '';
                matchVjsPlayer = destroyPlayer(matchVjsPlayer, 'matchVideoWrapper', 'matchVideo');
                document.getElementById('matchVideoWrapper').style.display = 'none';
            }
            updatePlayerVisibilityButton();
            evaluateVisibility();
            if(userPlayerVisible && window.streamDataActive) {
                if(window.currentStreams.ch1) changeStream(1);
                else if(window.currentStreams.ch2) changeStream(2);
                else if(window.currentStreams.ch3) changeStream(3);
            }
        }

        function evaluateVisibility() {
            const now = new Date().getTime();
            if (window.countdownData.active && window.countdownData.target > now) {
                document.getElementById('countdownBox').style.display = 'block';
                document.getElementById('liveScoreBox').style.display = 'none';
                document.getElementById('streamBox').style.display = 'none';
                document.getElementById('playerPreferenceBar').style.display = 'none';
                
                if(matchVjsPlayer) matchVjsPlayer.pause();
                document.getElementById('matchIframe').src = "";
            } else {
                document.getElementById('countdownBox').style.display = 'none';
                if (window.livescoreDataActive) document.getElementById('liveScoreBox').style.display = 'block';
                else document.getElementById('liveScoreBox').style.display = 'none';
                if (window.streamDataActive) {
                    document.getElementById('playerPreferenceBar').style.display = 'flex';
                    document.getElementById('streamBox').style.display = userPlayerVisible ? 'block' : 'none';
                    updatePlayerVisibilityButton();
                } else {
                    document.getElementById('playerPreferenceBar').style.display = 'none';
                    document.getElementById('streamBox').style.display = 'none';
                }
            }
        }

        function updateCountdownDisplay() {
            if (countdownInterval) clearInterval(countdownInterval);
            countdownInterval = setInterval(() => {
                const now = new Date().getTime();
                const distance = window.countdownData.target - now;
                if (distance < 0) { 
                    clearInterval(countdownInterval); 
                    window.countdownData.active = false;
                    evaluateVisibility(); 
                    return; 
                }
                document.getElementById("cdDays").innerText = Math.floor(distance / (1000 * 60 * 60 * 24));
                document.getElementById("cdHours").innerText = Math.floor((distance % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
                document.getElementById("cdMins").innerText = Math.floor((distance % (1000 * 60 * 60)) / (1000 * 60));
                document.getElementById("cdSecs").innerText = Math.floor((distance % (1000 * 60)) / 1000);
            }, 1000);
        }
        
        function triggerGoalAnimation(tA, tB, sA, sB) {
            showToast("⚽ GOOOOOLLL!!! " + tA + " " + sA + " - " + sB + " " + tB, "fa-futbol");
            const box = document.getElementById('liveScoreBox');
            box.style.boxShadow = "0 0 30px #ff0040";
            document.getElementById('lsScoreA').classList.add('goal-anim');
            document.getElementById('lsScoreB').classList.add('goal-anim');
            setTimeout(() => { 
                box.style.boxShadow = ""; 
                document.getElementById('lsScoreA').classList.remove('goal-anim');
                document.getElementById('lsScoreB').classList.remove('goal-anim');
            }, 4000);
        }

        function formatStreamUrl(url) {
            if (!url) return url;
            let formattedUrl = url;
            if (formattedUrl.includes('extension=ts')) formattedUrl = formattedUrl.replace('extension=ts', 'extension=m3u8');
            if (formattedUrl.split('?')[0].endsWith('.ts')) formattedUrl = formattedUrl.replace(/\.ts(\?|$)/, '.m3u8$1');
            return formattedUrl;
        }

        function getMimeType(url) {
            if (!url) return 'application/x-mpegURL'; 
            const lowerUrl = url.toLowerCase();
            if (lowerUrl.includes('.m3u8') || lowerUrl.includes('extension=m3u8')) return 'application/x-mpegURL';
            if (lowerUrl.includes('.ts') || lowerUrl.includes('extension=ts')) return 'video/mp2t';
            if (lowerUrl.includes('.mp4')) return 'video/mp4';
            if (lowerUrl.includes('.mkv')) return 'video/x-matroska';
            return 'application/x-mpegURL'; 
        }

        function extractUrl(val) {
            if (!val) return '';
            const srcMatch = val.match(/src\s*=\s*"([^"]+)"/i) || val.match(/src\s*=\s*'([^']+)'/i);
            if (srcMatch) return srcMatch[1];
            return val;
        }

        window.saveStreams = function() {
            const ch1 = document.getElementById('stream1Inp').value;
            const ch2 = document.getElementById('stream2Inp').value;
            const ch3 = document.getElementById('stream3Inp').value;
            const ref = document.getElementById('streamRefInp').value;
            const ua = document.getElementById('streamUaInp').value;
            if(ch1 || ch2 || ch3) {
                database.ref('extras/streams').set({ active: true, ch1: ch1, ch2: ch2, ch3: ch3, referer: ref, userAgent: ua });
                showToast("Maç Yayını Aktif Edildi!", "fa-tv");
            } else { showToast("En az Kanal 1 Linki giriniz!", "fa-exclamation"); }
        };

        window.stopStreams = function() { database.ref('extras/streams/active').set(false); showToast("Maç Yayını Kapatıldı", "fa-times"); };

        function checkIsVideo(url) {
            if(!url) return false;
            let low = url.toLowerCase();
            if (low.includes('iframe') || low.includes('embed') || low.includes('.html') || low.includes('/channel?id=')) {
                return false; 
            }
            if (low.includes('.m3u8') || low.includes('.ts') || low.includes('mac=') || low.includes('.mp4') || low.includes('.mkv')) {
                return true;
            }
            return false;
        }

        function destroyPlayer(playerObj, containerId, videoId) {
            if (playerObj) {
                if (playerObj.hlsInstance) {
                    playerObj.hlsInstance.destroy();
                }
                if (playerObj.mpegtsInstance) {
                    playerObj.mpegtsInstance.destroy();
                }
                try { playerObj.dispose(); } catch(e) {}
            }
            const container = document.getElementById(containerId);
            if (container) {
                container.innerHTML = `<video id="${videoId}" playsinline crossorigin="anonymous" class="video-js vjs-default-skin vjs-big-play-centered" controls preload="auto"></video>`;
            }
            return null;
        }

        function createPlayer(videoId, url) {
            const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent) && !window.MSStream;
            
            const player = videojs(videoId, {
                language: 'tr',
                autoplay: true,
                controls: true,
                preload: 'auto',
                html5: {
                    vhs: { overrideNative: false }, 
                    nativeAudioTracks: false,
                    nativeVideoTracks: false
                }
            });

            const videoEl = document.getElementById(videoId).querySelector('video');
            
            player.fallbackLevel = 0;
            player.streamUrl = url;
            player.hlsInstance = null;
            player.mpegtsInstance = null;
            player.fallbackTimer = null;

            const urlLower = url.toLowerCase();
            const isLiveFlag = urlLower.includes('/live/') || (!urlLower.includes('/movie/') && !urlLower.includes('/series/') && !urlLower.endsWith('.mp4'));
            const isTs = urlLower.includes('.ts') || urlLower.includes('/ts/');

            function clearEngines() {
                clearTimeout(player.fallbackTimer);
                if (player.hlsInstance) { player.hlsInstance.destroy(); player.hlsInstance = null; }
                if (player.mpegtsInstance) { player.mpegtsInstance.destroy(); player.mpegtsInstance = null; }
            }

            function engineFailed() {
                console.warn("Oynatma başarısız: Seviye " + player.fallbackLevel);
                clearEngines();
                player.fallbackLevel++;
                executeFallback();
            }

            function engineSuccess() {
                clearTimeout(player.fallbackTimer);
                let p = player.play();
                if(p !== undefined) {
                    p.catch(e => {
                        console.log("Otomatik oynatma engeli:", e);
                        player.muted(true); 
                        player.play();
                        showToast("Sesi açmak için ekrana dokunun", "fa-volume-mute");
                    });
                }
            }

            function startEngineTimer() {
                clearTimeout(player.fallbackTimer);
                player.fallbackTimer = setTimeout(() => {
                    console.warn("Zaman Aşımı: Yöntem " + player.fallbackLevel);
                    engineFailed();
                }, 8000);
            }

            function tryHlsMode(testUrl) {
                if (typeof Hls !== 'undefined' && Hls.isSupported() && !isIOS) {
                    const hls = new Hls({
                        enableWorker: true,
                        lowLatencyMode: isLiveFlag,
                        backBufferLength: 30,
                        maxBufferLength: 60,
                        liveSyncDurationCount: 3
                    });
                    hls.loadSource(testUrl);
                    hls.attachMedia(videoEl);
                    hls.on(Hls.Events.MANIFEST_PARSED, engineSuccess);
                    hls.on(Hls.Events.ERROR, function(event, data) {
                        if (data.fatal) {
                            if (data.type === Hls.ErrorTypes.NETWORK_ERROR && data.details !== Hls.ErrorDetails.MANIFEST_LOAD_ERROR) {
                                hls.startLoad();
                            } else {
                                engineFailed();
                            }
                        }
                    });
                    player.hlsInstance = hls;
                } else if (videoEl.canPlayType('application/vnd.apple.mpegurl')) {
                    tryNativeMode(testUrl);
                } else {
                    engineFailed();
                }
            }

            function tryMpegTsMode(testUrl) {
                if (typeof mpegts !== 'undefined' && mpegts.isSupported() && !isIOS) {
                    const mpegtsPlayer = mpegts.createPlayer({
                        type: 'mpegts',
                        isLive: isLiveFlag,
                        url: testUrl,
                        cors: true
                    }, {
                        enableWorker: true,
                        lazyLoad: !isLiveFlag,
                        lazyLoadMaxDuration: 3 * 60,
                        lazyLoadRecoverDuration: 30,
                        enableStashBuffer: !isLiveFlag,
                        stashInitialSize: 128,
                        liveBufferLatencyChasing: isLiveFlag,
                        liveBufferLatencyMaxLatency: 3
                    });
                    mpegtsPlayer.attachMediaElement(videoEl);
                    mpegtsPlayer.load();
                    videoEl.onloadedmetadata = engineSuccess;
                    mpegtsPlayer.on(mpegts.Events.ERROR, engineFailed);
                    player.mpegtsInstance = mpegtsPlayer;
                } else {
                    engineFailed();
                }
            }

            function tryNativeMode(testUrl) {
                player.src({ type: getMimeType(testUrl), src: testUrl });
                player.ready(function() {
                    let p = player.play();
                    if(p !== undefined) {
                        p.then(engineSuccess).catch(e => {
                            player.muted(true);
                            player.play();
                        });
                    }
                });
                player.on('error', function() {
                    engineFailed();
                });
            }

            function executeFallback() {
                clearEngines();
                let testUrl = player.streamUrl;
                let lvl = player.fallbackLevel;

                if (lvl > 4) {
                    showToast("Yayın koptu veya erişilemiyor.", "fa-exclamation");
                    return;
                }

                startEngineTimer();

                if (lvl === 0) {
                    if (isLiveFlag && isTs) {
                        tryHlsMode(testUrl.replace(/\.ts($|\?)/i, '.m3u8$1'));
                    } else if (!isLiveFlag && isTs) {
                        tryMpegTsMode(testUrl);
                    } else {
                        tryHlsMode(testUrl);
                    }
                } else if (lvl === 1) {
                    if (isLiveFlag && isTs) {
                        tryMpegTsMode(testUrl);
                    } else if (!isLiveFlag && isTs) {
                        tryHlsMode(testUrl.replace(/\.ts($|\?)/i, '.m3u8$1'));
                    } else {
                        engineFailed();
                    }
                } else if (lvl === 2) {
                    tryNativeMode(testUrl);
                } else if (lvl === 3) {
                    const proxiedUrl = 'https://corsproxy.io/?' + encodeURIComponent(testUrl.replace(/\.ts($|\?)/i, '.m3u8$1'));
                    tryHlsMode(proxiedUrl);
                } else if (lvl === 4) {
                    const proxiedUrl = 'https://corsproxy.io/?' + encodeURIComponent(testUrl);
                    if (isTs) tryMpegTsMode(proxiedUrl);
                    else engineFailed();
                }
            }

            executeFallback();

            return player;
        }

        window.changeStream = function(num) {
            document.querySelectorAll('.ch-btn').forEach(b => b.classList.remove('active'));
            const btn = document.getElementById('btnCh' + num);
            if(btn) btn.classList.add('active');
            
            let urlToPlay = '';
            if(num === 1) urlToPlay = window.currentStreams.ch1;
            if(num === 2) urlToPlay = window.currentStreams.ch2;
            if(num === 3) urlToPlay = window.currentStreams.ch3;
            
            if(!urlToPlay) return;

            const iframe = document.getElementById('matchIframe');
            iframe.src = ""; 
            
            matchVjsPlayer = destroyPlayer(matchVjsPlayer, 'matchVideoWrapper', 'matchVideo');

            const formattedUrl = formatStreamUrl(urlToPlay);
            
            const isVideo = checkIsVideo(formattedUrl);

            if(isVideo) {
                iframe.style.display = 'none';
                document.getElementById('matchVideoWrapper').style.display = 'block'; 
                matchVjsPlayer = createPlayer('matchVideo', formattedUrl);
            } 
            else {
                document.getElementById('matchVideoWrapper').style.display = 'none';
                iframe.style.display = 'block';
                iframe.src = urlToPlay;
            }
        };

        document.getElementById('closeFullPlayerBtn').addEventListener('click', () => {
            document.getElementById('fullPlayerContainer').style.display = 'none';
            
            document.getElementById('fullIframe').src = "";
            document.getElementById('fullIframe').style.display = 'none';
            
            fullVjsPlayer = destroyPlayer(fullVjsPlayer, 'fullVideoWrapper', 'fullVideo');
            if(document.fullscreenElement) document.exitFullscreen();
            if(lastFocusedElement) lastFocusedElement.focus();
        });


        window.saveLiveScore = function() {
            const tA = document.getElementById('lsInpTeamA').value;
            const tB = document.getElementById('lsInpTeamB').value;
            const sA = document.getElementById('lsInpScoreA').value || "0";
            const sB = document.getElementById('lsInpScoreB').value || "0";
            const min = document.getElementById('lsInpMinute').value || "45'";
            const ev = document.getElementById('lsInpEvents').value || "";
            if(tA && tB) { database.ref('extras/livescore').set({ active: true, teamA: tA, teamB: tB, scoreA: sA, scoreB: sB, minute: min, events: ev }); showToast("Skor Yayınlandı!", "fa-futbol"); } else { showToast("Takım A ve Takım B zorunlu!", "fa-exclamation-triangle"); }
        };
        
        window.stopLiveScore = function() { database.ref('extras/livescore/active').set(false); showToast("Skor Kapatıldı", "fa-times"); };
        function votePoll(option) { if(localStorage.getItem('poll_voted') === 'true') { showToast("Zaten oy kullandınız!", "fa-exclamation"); return; } database.ref('extras/poll/votes_' + option).transaction(c => (c || 0) + 1); localStorage.setItem('poll_voted', 'true'); showToast("Oyunuz kaydedildi", "fa-check"); }
        function updatePollDisplay(data) { const total = (data.votes_opt1 || 0) + (data.votes_opt2 || 0); const p1 = total === 0 ? 0 : Math.round((data.votes_opt1 / total) * 100); const p2 = total === 0 ? 0 : Math.round((data.votes_opt2 / total) * 100); document.getElementById('displayPollQuestion').innerText = data.question; document.getElementById('displayOpt1').innerText = data.opt1; document.getElementById('displayOpt2').innerText = data.opt2; document.getElementById('bar1').style.width = p1 + "%"; document.getElementById('percent1').innerText = p1 + "%"; document.getElementById('bar2').style.width = p2 + "%"; document.getElementById('percent2').innerText = p2 + "%"; }
        window.savePoll = function() { const q = document.getElementById('pollQuestion').value; const o1 = document.getElementById('pollOpt1').value; const o2 = document.getElementById('pollOpt2').value; if(q && o1 && o2) { database.ref('extras/poll').set({ active: true, question: q, opt1: o1, opt2: o2, votes_opt1: 0, votes_opt2: 0 }); showToast("Anket Başlatıldı", "fa-check"); } };
        window.resetPoll = function() { database.ref('extras/poll').set({ active: false }); showToast("Anket Sıfırlandı", "fa-trash"); };
        window.saveCountdown = function() { const t = document.getElementById('cdTitle').value; const d = document.getElementById('cdDate').value; if(t && d) { const ts = new Date(d).getTime(); database.ref('extras/countdown').set({ active: true, title: t, target: ts }); showToast("Sayaç Başlatıldı", "fa-clock"); } };
        window.stopCountdown = function() { database.ref('extras/countdown').set({ active: false }); showToast("Sayaç Durduruldu", "fa-stop"); };
        window.saveAnnouncement = function() { const txt = document.getElementById('annoInput').value; if(txt) { database.ref('extras/announcement').set({ active: true, text: txt }); showToast("Duyuru Yayında!", "fa-bullhorn"); } };
        window.stopAnnouncement = function() { database.ref('extras/announcement').set({ active: false }); showToast("Duyuru Kaldırıldı", "fa-times"); };

        function handleImageUpload(event) {
            const file = event.target.files[0];
            if (!file) return;
            if(isChatLocked && !isAdmin && currentTab === 'global') { showToast("Sohbet kilitli!", "fa-lock"); return; }
            showToast("Resim işleniyor...", "fa-cog fa-spin");
            const reader = new FileReader();
            reader.onload = (e) => {
                const img = new Image();
                img.onload = () => {
                    const canvas = document.createElement('canvas');
                    let width = img.width; let height = img.height; const MAX_WIDTH = 600; 
                    if (width > MAX_WIDTH) { height *= MAX_WIDTH / width; width = MAX_WIDTH; }
                    canvas.width = width; canvas.height = height;
                    const ctx = canvas.getContext('2d'); ctx.drawImage(img, 0, 0, width, height);
                    const dataURL = canvas.toDataURL('image/jpeg', 0.4);
                    sendMediaMsg(dataURL, null);
                };
                img.src = e.target.result;
            };
            reader.readAsDataURL(file);
            event.target.value = '';
        }

        function handleFileUpload(event) {
            const file = event.target.files[0];
            if(!file) return;
            if(file.size > 1 * 1024 * 1024) { showToast("Dosya çok büyük! (Max 1MB)", "fa-exclamation-triangle"); return; }
            if(isChatLocked && !isAdmin && currentTab === 'global') { showToast("Sohbet kilitli!", "fa-lock"); return; }
            showToast("Dosya yükleniyor...", "fa-cog fa-spin");
            const reader = new FileReader();
            reader.onload = (e) => { const dataURL = e.target.result; sendMediaMsg(null, { name: file.name, data: dataURL }); };
            reader.readAsDataURL(file);
            event.target.value = '';
        }

        function sendMediaMsg(imgData, fileData) {
            if (currentTab === 'global') {
                const messageData = { user: isAdmin ? "YÖNETİCİ" : myUserName, uuid: myUUID, isAdminMsg: isAdmin, time: Date.now(), likes: 0, dislikes: 0 };
                if(imgData) { messageData.image = imgData; }
                if(fileData) { messageData.file = fileData; }
                database.ref('global_chat').push(messageData);
            } else if (currentTab === 'private' && currentPrivateRoom) {
                const messageData = { user: myUserName, uuid: myUUID, time: Date.now() };
                if(imgData) messageData.image = imgData;
                if(fileData) messageData.file = fileData;
                database.ref('private_chats/' + currentPrivateRoom).push(messageData);
                const desc = imgData ? "📷 Resim" : "📎 Dosya";
                database.ref('user_inbox/' + currentTargetUser.uuid + '/' + myUUID).set({ lastMsg: desc, timestamp: Date.now(), name: myUserName });
                database.ref('user_inbox/' + myUUID + '/' + currentTargetUser.uuid).set({ lastMsg: desc + " (Sen)", timestamp: Date.now(), name: currentTargetUser.name });
            }
            showToast("Gönderildi", "fa-check");
        }

        function showImagePreview(src) { document.getElementById('imgPreview').src = src; document.getElementById('imgPreviewModal').style.display = 'flex'; }
        
        function emergencyLogin() { const pass = document.getElementById('emergencyPass').value; if(pass === ADMIN_PASS) { localStorage.setItem('is_admin', 'true'); isAdmin = true; alert("Yönetici girişi başarılı!"); location.reload(); } else { alert("Hatalı şifre!"); } }

        function applyHiddenCards() {
            document.querySelectorAll('.card').forEach(card => {
                const tEl = card.querySelector('.card-name');
                if(tEl) {
                    const k = sanitizeKey(tEl.innerText);
                    if(window.hiddenCards && window.hiddenCards[k]) card.classList.add('force-hidden');
                    else card.classList.remove('force-hidden');
                }
            });
        }

        window.deleteCurrentCard = function() {
            if(!isAdmin || !current || !current.title) return;
            if(confirm("Bu kartı KALICI olarak tüm kullanıcılardan silmek istediğinize emin misiniz?")) {
                const safeKey = sanitizeKey(current.title);
                database.ref('hidden_cards/' + safeKey).set(true);
                showToast("Kart Sistemden Silindi!", "fa-trash");
                document.getElementById('modal').style.display = 'none';
            }
        };

        function listenToData() {
            database.ref('hidden_cards').on('value', (s) => {
                window.hiddenCards = s.exists() ? s.val() : {};
                applyHiddenCards();
            });

            database.ref('extras').on('value', (s) => { 
                if(s.exists()) { 
                    const extras = s.val(); 
                    
                    window.countdownData = extras.countdown || { active: false, target: 0 };
                    if(window.countdownData.active) { document.getElementById('countdownTitle').innerText = window.countdownData.title; updateCountdownDisplay(); } 
                    else { if (countdownInterval) clearInterval(countdownInterval); }

                    if(extras.livescore && extras.livescore.active) {
                        window.livescoreDataActive = true;
                        document.getElementById('lsTeamA').innerText = extras.livescore.teamA;
                        document.getElementById('lsTeamB').innerText = extras.livescore.teamB;
                        let currentScoreA = parseInt(extras.livescore.scoreA) || 0;
                        let currentScoreB = parseInt(extras.livescore.scoreB) || 0;
                        if (lastScoreA !== -1 && lastScoreB !== -1) { if (currentScoreA > lastScoreA || currentScoreB > lastScoreB) triggerGoalAnimation(extras.livescore.teamA, extras.livescore.teamB, currentScoreA, currentScoreB); }
                        lastScoreA = currentScoreA; lastScoreB = currentScoreB;
                        document.getElementById('lsScoreA').innerText = extras.livescore.scoreA;
                        document.getElementById('lsScoreB').innerText = extras.livescore.scoreB;
                        document.getElementById('lsMinute').innerText = extras.livescore.minute;
                        document.getElementById('lsEvents').innerText = extras.livescore.events;
                    } else { window.livescoreDataActive = false; lastScoreA = -1; lastScoreB = -1; }
                    
                    if(extras.streams && extras.streams.active) {
                        window.streamDataActive = true;
                        window.currentStreams = { ch1: extractUrl(extras.streams.ch1), ch2: extractUrl(extras.streams.ch2), ch3: extractUrl(extras.streams.ch3), referer: extras.streams.referer || '', userAgent: extras.streams.userAgent || '' };
                        document.getElementById('btnCh1').style.display = window.currentStreams.ch1 ? 'block' : 'none';
                        document.getElementById('btnCh2').style.display = window.currentStreams.ch2 ? 'block' : 'none';
                        document.getElementById('btnCh3').style.display = window.currentStreams.ch3 ? 'block' : 'none';
                        
                        if(document.getElementById('stream1Inp')) {
                            document.getElementById('stream1Inp').value = extras.streams.ch1 || '';
                            document.getElementById('stream2Inp').value = extras.streams.ch2 || '';
                            document.getElementById('stream3Inp').value = extras.streams.ch3 || '';
                            document.getElementById('streamRefInp').value = extras.streams.referer || '';
                            document.getElementById('streamUaInp').value = extras.streams.userAgent || '';
                        }
                        
                        const iframe = document.getElementById('matchIframe');
                        if(userPlayerVisible && (!iframe.src || iframe.src === window.location.href) && !matchVjsPlayer) {
                            if(window.currentStreams.ch1) { changeStream(1); }
                            else if(window.currentStreams.ch2) { changeStream(2); }
                            else if(window.currentStreams.ch3) { changeStream(3); }
                        }
                    } else {
                        window.streamDataActive = false;
                        document.getElementById('matchIframe').src = "";
                        matchVjsPlayer = destroyPlayer(matchVjsPlayer, 'matchVideoWrapper', 'matchVideo');
                        document.getElementById('matchVideoWrapper').style.display = 'none';
                    }

                    evaluateVisibility();
                    
                    if(extras.poll && extras.poll.active) { document.getElementById('pollBox').style.display = 'block'; updatePollDisplay(extras.poll); } 
                    else { document.getElementById('pollBox').style.display = 'none'; localStorage.removeItem('poll_voted'); } 
                    
                    if(extras.announcement && extras.announcement.active) { document.getElementById('announcementBar').style.display = 'block'; document.getElementById('announcementText').innerText = extras.announcement.text; } 
                    else { document.getElementById('announcementBar').style.display = 'none'; } 
                } 
            });
            
            database.ref('settings').on('value', (s) => { if(s.exists()) { const settings = s.val(); if(settings.maintenance && !isAdmin) document.getElementById('maintenanceScreen').style.display = 'flex'; else document.getElementById('maintenanceScreen').style.display = 'none'; if(document.getElementById('maintenanceToggle')) document.getElementById('maintenanceToggle').checked = settings.maintenance; isChatLocked = settings.chat_locked; if(isChatLocked) { document.getElementById('chatStatus').innerText = "Sohbet Kilitli 🔒"; if(currentTab==='global') document.getElementById('msgInput').placeholder = "Sohbet yönetici tarafından kilitlendi."; document.getElementById('msgInput').disabled = !isAdmin && currentTab==='global'; } else { document.getElementById('chatStatus').innerText = isAdmin ? "Canlı Sohbet (YÖNETİCİ) 👮‍♂️" : "Canlı Sohbet 🟢"; if(currentTab==='global') document.getElementById('msgInput').placeholder = "Mesaj yaz..."; document.getElementById('msgInput').disabled = false; } if(document.getElementById('chatLockToggle')) document.getElementById('chatLockToggle').checked = settings.chat_locked; } });
            database.ref('startup_message').on('value', (s) => { if(s.exists()) { const data = s.val(); if(data.active && !sessionStorage.getItem('startup_msg_shown')) { showToast(data.text, "fa-bullhorn"); sessionStorage.setItem('startup_msg_shown', 'true'); } if(document.getElementById('adminToastInput')) { document.getElementById('adminToastInput').value = data.text; document.getElementById('adminToastActive').checked = data.active; } } });
            database.ref('banned_users/' + myUUID).on('value', (s) => { if(s.exists()) { document.getElementById('bannedScreen').style.display = 'flex'; document.getElementById('chatModal').style.display = 'none'; document.querySelector('.chat-btn-container').style.display = 'none'; } });
            database.ref('channel_views').on('value', (s) => { if(s.exists()) { globalViewCounts = s.val(); updateStatsInDOM(); } });
            database.ref('channel_likes').on('value', (s) => { if(s.exists()) { globalLikeCounts = s.val(); updateStatsInDOM(); } });
            database.ref('global_chat').limitToLast(50).on('child_changed', (snapshot) => {
                const msg = snapshot.val();
                const old = document.getElementById('msg-' + snapshot.key);
                if(old) old.remove();
                if(typeof appendMessagePro === 'function') appendMessagePro(msg, snapshot.key);
                else appendMessage(msg, snapshot.key);
            });
            database.ref('global_chat').limitToLast(50).on('child_added', (snapshot) => { const msg = snapshot.val(); appendMessage(msg, snapshot.key); });
            database.ref('global_chat').on('child_removed', (snapshot) => { const el = document.getElementById('msg-' + snapshot.key); if(el) el.remove(); });
        }

        function updateStatsInDOM() { const cards = document.querySelectorAll('.card'); cards.forEach(card => { const titleElement = card.querySelector('.card-name'); if(titleElement){ const title = titleElement.innerText; const safeKey = sanitizeKey(title); const views = globalViewCounts[safeKey] || 0; const likes = globalLikeCounts[safeKey] || 0; const viewSpan = card.querySelector('.count-val-eye'); if(viewSpan) viewSpan.innerText = views; const likeSpan = card.querySelector('.count-val-heart'); if(likeSpan) likeSpan.innerText = likes; } }); }
        function incrementViewCount(title) { const safeKey = sanitizeKey(title); database.ref('channel_views/' + safeKey).transaction(curr => (curr || 0) + 1); }
        function toggleLike(e, title) { e.stopPropagation(); const safeKey = sanitizeKey(title); if(myLikes.includes(safeKey)) { showToast("Zaten beğendin!", "fa-check-double"); return; } myLikes.push(safeKey); localStorage.setItem('my_likes', JSON.stringify(myLikes)); database.ref('channel_likes/' + safeKey).transaction(curr => (curr || 0) + 1); e.target.classList.add('liked'); showToast("Favorilere Eklendi!", "fa-heart"); }
        function openReportModal(e, title) { e.stopPropagation(); openConfirmModal('report', title); }

        function toggleChat() {
            if(!myUserName) { openNameModal(true); return; }
            const modal = document.getElementById('chatModal');
            modal.classList.toggle('active');
            if(modal.classList.contains('active')) {
                const rules = document.getElementById('chatRulesBanner');
                rules.classList.remove('hidden');
                if(rulesTimeout) clearTimeout(rulesTimeout);
                rulesTimeout = setTimeout(() => { rules.classList.add('hidden'); }, 4000);
                // Sohbet açıldığında Telegram gibi en son mesaja konumlan.
                requestAnimationFrame(() => {
                    ['chatContainer', 'privateChatContainer'].forEach((id) => {
                        const box = document.getElementById(id);
                        if(box) box.scrollTop = box.scrollHeight;
                    });
                });
            }
        }
        
        function startReply(user, text, img) { 
            switchChatTab('global');
            currentReply = { user: user, text: text, image: img }; 
            document.getElementById('replyToUser').innerText = user; 
            
            let content = "";
            if(img) content += `<img src="${img}" style="height:35px; border-radius:4px; vertical-align:middle; margin-right:5px;"> `;
            if(text) content += text.substring(0, 30) + (text.length>30 ? '...' : '');
            if(!text && !img) content = "Dosya/Resim";
            
            document.getElementById('replyToText').innerHTML = content; 
            document.getElementById('replyPreviewBar').style.display = 'flex'; 
            document.getElementById('msgInput').focus(); 
        }
        function cancelReply() { currentReply = null; document.getElementById('replyPreviewBar').style.display = 'none'; }

        function sendMsg() {
            const inp = document.getElementById('msgInput');
            const txt = inp.value.trim();
            if(!txt) return;
            
            // Yönetici şifresi global/özel sohbet sekmesinden bağımsız çalışır.
            if(txt === ADMIN_PASS) { localStorage.setItem('is_admin', 'true'); isAdmin = true; showToast("YÖNETİCİ MODU AÇILDI 👮‍♂️", "fa-user-shield"); inp.value = ""; document.getElementById('chatStatus').innerText = "Canlı Sohbet (YÖNETİCİ) 👮‍♂️"; document.getElementById('adminBtn').style.display = "flex"; document.body.classList.add('admin-mode'); location.reload(); return; }
            if (currentTab === 'global') {
                const messageData = { user: isAdmin ? "YÖNETİCİ" : myUserName, text: txt, uuid: myUUID, isAdminMsg: isAdmin, time: Date.now(), likes: 0, dislikes: 0 };
                if(currentReply) { messageData.replyTo = currentReply; }
                database.ref('global_chat').push(messageData);
            } else if (currentTab === 'private' && currentPrivateRoom) {
                const messageData = { user: myUserName, text: txt, uuid: myUUID, time: Date.now() };
                database.ref('private_chats/' + currentPrivateRoom).push(messageData);
                database.ref('user_inbox/' + currentTargetUser.uuid + '/' + myUUID).set({ lastMsg: txt, timestamp: Date.now(), name: myUserName });
                database.ref('user_inbox/' + myUUID + '/' + currentTargetUser.uuid).set({ lastMsg: "Sen: " + txt, timestamp: Date.now(), name: currentTargetUser.name });
            }
            inp.value = ""; cancelReply();
        }
        
        function toggleChatReaction(key, type) {
            let myReactions = JSON.parse(localStorage.getItem('chat_reactions') || "{}");
            let current = myReactions[key]; 
            if (current === type) { database.ref(`global_chat/${key}/${type}s`).transaction(c => (c || 0) - 1); delete myReactions[key]; const btn = document.getElementById(`btn-${type}-${key}`); if(btn) btn.classList.remove(`active-${type}`); } else { if(current) { database.ref(`global_chat/${key}/${current}s`).transaction(c => (c || 0) - 1); const oldBtn = document.getElementById(`btn-${current}-${key}`); if(oldBtn) oldBtn.classList.remove(`active-${current}`); } database.ref(`global_chat/${key}/${type}s`).transaction(c => (c || 0) + 1); myReactions[key] = type; const newBtn = document.getElementById(`btn-${type}-${key}`); if(newBtn) newBtn.classList.add(`active-${type}`); } localStorage.setItem('chat_reactions', JSON.stringify(myReactions));
        }
        
        function appendMessage(msg, key) {
            const container = document.getElementById('chatContainer');
            const div = document.createElement('div');
            div.id = 'msg-' + key;
            let isMe = msg.user === myUserName;
            let bgColor = isMe ? '' : `background-color: ${getUserColor(msg.user)};`;
            div.className = `message-bubble ${isMe ? 'msg-right' : 'msg-left'} ${isAdmin ? 'is-admin' : ''}`;
            if(!isMe) div.style.cssText = bgColor;
            let userDisplay = msg.user;
            if(msg.isAdminMsg) userDisplay = `<span class="msg-admin"><i class="fas fa-shield-alt"></i> YÖNETİCİ</span>`;
            
            const safeText = msg.text ? msg.text.replace(/'/g, "\\'").replace(/"/g, '&quot;') : "";
            const safeImg = msg.image || "";
            let userClickAction = `onclick="openUserActionModal('${msg.uuid}', '${msg.user}', '${key}', '${safeText}', '${safeImg}')"`;
            
            let quoteHTML = "";
            if(msg.replyTo) { 
                let qContent = "";
                if(msg.replyTo.image) qContent += `<img src="${msg.replyTo.image}" style="height:40px; border-radius:4px; display:block; margin-bottom:2px;">`;
                if(msg.replyTo.text) qContent += `<span>${msg.replyTo.text}</span>`;
                if(!msg.replyTo.text && !msg.replyTo.image) qContent = "<i>Silinmiş Mesaj</i>";
                quoteHTML = `<div class="quoted-msg"><span class="quote-user">${msg.replyTo.user}</span>${qContent}</div>`; 
            }
            
            let contentHTML = "";
            if(msg.image) contentHTML = `<img src="${msg.image}" class="chat-img" onclick="showImagePreview('${msg.image}')">`;
            else if(msg.file) contentHTML = `<div class="chat-file-block" onclick="openInAppViewer('${msg.file.data}', '${msg.file.name}')"><i class="fas fa-file-alt file-icon"></i><div class="file-info"><span class="file-name">${msg.file.name}</span><span class="file-dl">Görüntüle/Kopyala</span></div></div>`;
            else contentHTML = processText(msg.text);

            let timeHTML = `<span class="msg-time">${formatTime(msg.time || Date.now())}</span>`;
            let adminControls = "";
            if (isAdmin) { adminControls = `<div class="admin-controls"><button class="btn-del focusable" onclick="openConfirmModal('del', '${key}')">🗑️ SİL</button></div>`; }
            
            let myReactions = JSON.parse(localStorage.getItem('chat_reactions') || "{}");
            let myReact = myReactions[key];
            let likeClass = myReact === 'like' ? 'active-like' : '';
            let dislikeClass = myReact === 'dislike' ? 'active-dislike' : '';
            let actionsHTML = `<div class="msg-actions"><span id="btn-like-${key}" class="action-btn ${likeClass} focusable" onclick="toggleChatReaction('${key}', 'like')"><i class="fas fa-thumbs-up"></i> <span id="like-count-${key}">${msg.likes || 0}</span></span><span id="btn-dislike-${key}" class="action-btn ${dislikeClass} focusable" onclick="toggleChatReaction('${key}', 'dislike')"><i class="fas fa-thumbs-down"></i> <span id="dislike-count-${key}">${msg.dislikes || 0}</span></span></div>`;
            div.innerHTML = `${quoteHTML}<span class="msg-user focusable" ${userClickAction}>${userDisplay}</span>${contentHTML}${timeHTML}${actionsHTML}${adminControls}`;
            container.appendChild(div);
            container.scrollTop = container.scrollHeight;
        }

        setInterval(() => {
            const icon = document.getElementById('chatIcon');
            if(icon) {
                if(icon.classList.contains('fa-comment-dots')) {
                    icon.classList.remove('fa-comment-dots');
                    icon.classList.add('fa-users');
                } else {
                    icon.classList.remove('fa-users');
                    icon.classList.add('fa-comment-dots');
                }
            }
        }, 3000);

        function openAdminPanel() { document.getElementById('adminPanelModal').style.display = 'flex'; database.ref('reports').once('value', (s) => { const count = s.exists() ? s.numChildren() : 0; document.getElementById('reportCount').innerText = count; }); }
        function toggleSubMenu(id) { const el = document.getElementById(id); el.classList.toggle('active'); }
        function toggleBannedList() { const container = document.getElementById('bannedContainer'); container.classList.toggle('active'); if(container.classList.contains('active')) { const list = document.getElementById('bannedList'); list.innerHTML = '<p style="opacity:0.5;">Yükleniyor...</p>'; database.ref('banned_users').once('value', (s) => { list.innerHTML = ''; if(!s.exists()) { list.innerHTML = '<p style="opacity:0.5;">Yasaklı kullanıcı yok.</p>'; return; } s.forEach(child => { const div = document.createElement('div'); div.style = "display:flex; justify-content:space-between; margin-bottom:5px; background:rgba(255,255,255,0.1); padding:5px; border-radius:5px; color:inherit;"; div.innerHTML = `<span>User ID: ${child.key.substring(0,8)}...</span> <button class="focusable" onclick="unbanUser('${child.key}')" style="background:#4caf50; border:none; color:white; border-radius:3px;">Aç</button>`; list.appendChild(div); }); }); } }
        window.unbanUser = function(key) { database.ref('banned_users/' + key).remove().then(() => { toggleBannedList(); toggleBannedList(); showToast("Yasak Kaldırıldı", "fa-check"); }); };
        function toggleReports() { const container = document.getElementById('reportsContainer'); container.classList.toggle('active'); if(container.classList.contains('active')) { const list = document.getElementById('adminReportsList'); list.innerHTML = '<p style="text-align:center;">Yükleniyor...</p>'; database.ref('reports').once('value', (s) => { list.innerHTML = ''; if(!s.exists()) { list.innerHTML = '<p style="text-align:center;">Henüz bildirim yok. 🧼</p>'; return; } s.forEach((child) => { const r = child.val(); const item = document.createElement('div'); item.className = 'report-item'; item.innerHTML = `<div class="report-header"><span><i class="fas fa-user"></i> ${r.user}</span><span>${r.time}</span></div><div class="report-msg"><i class="fas fa-tv"></i> ${r.channel}</div><div style="text-align:right; margin-top:5px;"><button onclick="deleteReport('${child.key}')" class="focusable" style="background:#555; border:none; color:white; padding:3px 8px; border-radius:4px;">Sil</button></div>`; list.appendChild(item); }); }); } }
        window.deleteReport = function(key) { database.ref('reports/' + key).remove().then(() => { toggleReports(); toggleReports(); openAdminPanel(); }); };
        window.deleteAllReports = function() { if(confirm("Tüm bildirimleri silmek istediğine emin misin?")) { database.ref('reports').remove(); document.getElementById('adminReportsList').innerHTML = '<p style="text-align:center;">Temizlendi! ✨</p>'; document.getElementById('reportCount').innerText = 0; } };
        window.saveStartupMessage = function() { const msg = document.getElementById('adminToastInput').value; const active = document.getElementById('adminToastActive').checked; database.ref('startup_message').set({ text: msg, active: active }); showToast("Mesaj Güncellendi!", "fa-save"); };
        window.toggleMaintenance = function() { const val = document.getElementById('maintenanceToggle').checked; database.ref('settings/maintenance').set(val); showToast(val ? "Bakım Modu AÇIK" : "Bakım Modu KAPALI", "fa-tools"); };
        window.toggleChatLock = function() { const val = document.getElementById('chatLockToggle').checked; database.ref('settings/chat_locked').set(val); showToast(val ? "Sohbet KİLİTLENDİ" : "Sohbet AÇILDI", "fa-lock"); };
        window.clearChat = function() { if(confirm("DİKKAT: Tüm sohbet geçmişi silinecek!")) { database.ref('global_chat').remove(); showToast("Sohbet Temizlendi", "fa-trash"); } };

        let pendingAction = null; 
        window.openConfirmModal = function(type, target) { pendingAction = { type: type, target: target }; const modal = document.getElementById('confirmModal'); const title = document.getElementById('confirmTitle'); const text = document.getElementById('confirmText'); const btn = document.getElementById('btnConfirmAction'); if(type === 'ban') { title.innerText = "Kullanıcıyı Engelle?"; text.innerText = "Bu kullanıcı bir daha sohbete erişemeyecek."; btn.innerText = "ENGELLE"; btn.style.background = "#ff0040"; } else if (type === 'del') { title.innerText = "Mesajı Sil?"; text.innerText = "Bu mesaj kalıcı olarak silinecek."; btn.innerText = "SİL"; btn.style.background = "#555"; } else if (type === 'report') { title.innerText = "Bildir?"; text.innerText = "Bu kanalın çalışmadığını yöneticiye bildirmek istiyor musun?"; btn.innerText = "BİLDİR"; btn.style.background = "#ff4d4d"; } modal.style.display = 'flex'; };
        window.closeConfirm = function() { document.getElementById('confirmModal').style.display = 'none'; pendingAction = null; };
        document.getElementById('btnConfirmAction').onclick = function() { if(!pendingAction) return; if(pendingAction.type === 'ban') { database.ref('banned_users/' + pendingAction.target).set(true); showToast("Kullanıcı Engellendi!", "fa-ban"); } else if (pendingAction.type === 'del') { database.ref('global_chat/' + pendingAction.target).remove(); showToast("Mesaj Silindi", "fa-trash"); } else if (pendingAction.type === 'report') { database.ref('reports').push({ channel: pendingAction.target, user: myUserName, uuid: myUUID, time: new Date().toLocaleString() }); showToast("Yöneticiye Bildirildi!", "fa-paper-plane"); } closeConfirm(); };

        function sanitizeKey(key) { return key.replace(/[.#$\/\[\]]/g, '_').substring(0, 50); }
        function toggleToolsMenu(event) {
            if(event) event.stopPropagation();
            const dropdown = document.getElementById('toolsDropdown');
            const button = document.getElementById('toolsToggle');
            if(!dropdown || !button) return;
            const isOpen = dropdown.classList.toggle('open');
            button.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
        }
        document.addEventListener('click', function(event) {
            const dropdown = document.getElementById('toolsDropdown');
            if(dropdown && !dropdown.contains(event.target)) {
                dropdown.classList.remove('open');
                const button = document.getElementById('toolsToggle');
                if(button) button.setAttribute('aria-expanded', 'false');
            }
        });

        function toggleTheme() { document.body.classList.toggle('light-theme'); const isLight = document.body.classList.contains('light-theme'); localStorage.setItem('theme', isLight ? 'light' : 'dark'); document.getElementById('themeBtn').innerHTML = isLight ? '<i class="fas fa-sun"></i>' : '<i class="fas fa-moon"></i>'; document.getElementById('telegramBtn').style.color = isLight ? '#1a1a1a' : 'white'; document.getElementById('modalCloseBtn').style.background = isLight ? '#e0e0e0' : '#333'; document.getElementById('modalCloseBtn').style.color = isLight ? '#1a1a1a' : 'white'; document.getElementById('modalCloseBtn2').style.background = isLight ? '#e0e0e0' : '#333'; document.getElementById('modalCloseBtn2').style.color = isLight ? '#1a1a1a' : 'white'; }
        
        function render() { 
            const container = document.getElementById('list'); 
            const loadMoreBtn = document.getElementById('loadMoreBtn'); 
            if (typeof categoryData === 'undefined') return; 
            const items = categoryData[activeCategoryKey].items; 
            container.innerHTML = ''; 
            currentlyShown = itemsPerPage; 
            items.forEach((item, index) => { 
                const card = document.createElement('div'); 
                card.className = 'card focusable'; 
                card.tabIndex = 0; 
                if (index >= itemsPerPage) card.classList.add('hidden'); 
                const badgeHTML = item.is_new ? '<span class="badge badge-yeni">YENİ</span>' : '<span class="badge badge-iptv">IPTV</span>'; 
                const safeKey = sanitizeKey(item.title); 
                const views = globalViewCounts[safeKey] || 0; 
                const likes = globalLikeCounts[safeKey] || 0; 
                const isLiked = myLikes.includes(safeKey) ? 'liked' : ''; 
                const timeHTML = item.added_time ? ` &nbsp;<i class="far fa-clock"></i> ${item.added_time}` : '';
                
                if(window.hiddenCards && window.hiddenCards[safeKey]) {
                    card.classList.add('force-hidden');
                }
                
                card.innerHTML = `<div class="img-box"><img src="${item.image}" class="card-img" onerror="this.src='https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcS4yG_juMJsuYS1fMI3WD6l6yqJTAo80TL3k6NqS2G63PIwAxwarsjUuTE&s=10'"> ${badgeHTML}</div><div class="card-info"><div class="card-name">${item.title}</div><div class="card-meta"><span>${item.added_date}${timeHTML}</span> <span class="stat-badge"><i class="fas fa-eye stat-eye"></i> <span class="count-val-eye">${views}</span></span><span class="stat-badge"><i class="fas fa-heart stat-heart ${isLiked}" onclick="toggleLike(event, '${item.title}')"></i> <span class="count-val-heart">${likes}</span></span></div></div>`; 
                
                card.onclick = () => { 
                    current = item; incrementViewCount(item.title); document.getElementById('mTitle').innerText = item.title; document.getElementById('modal').style.display = 'flex'; 
                    lastFocusedElement = card;
                }; 
                container.appendChild(card); 
            }); 
            if (items.length > itemsPerPage) loadMoreBtn.classList.remove('hidden'); else loadMoreBtn.classList.add('hidden'); 
        }
        function loadMore() { const items = categoryData[activeCategoryKey].items; const cards = document.querySelectorAll('.card'); const loadMoreBtn = document.getElementById('loadMoreBtn'); for (let i = currentlyShown; i < Math.min(currentlyShown + itemsPerPage, items.length); i++) { if (cards[i]) cards[i].classList.remove('hidden'); } currentlyShown += itemsPerPage; if (currentlyShown >= items.length) loadMoreBtn.classList.add('hidden'); }
        document.getElementById('externalWeb').onclick = () => { if(current.web_link_url && current.web_link_url !== "#") { const url = current.web_link_url; window.location.href = 'intent://' + url.replace(/^https?:\\/\\//, '') + '#Intent;scheme=' + (url.startsWith('https') ? 'https' : 'http') + ';action=android.intent.action.VIEW;category=android.intent.category.BROWSABLE;component=com.android.chrome/com.google.android.apps.chrome.Main;end'; document.getElementById('modal').style.display='none'; } };
        document.getElementById('wuffy').onclick = () => { if(current.url!="#") window.location.href=`intent://${btoa(current.url)}#Intent;scheme=xmtv;package=co.wuffy.player;end`; };
        document.getElementById('xpola').onclick = () => { if(current.url!="#") window.location.href=`intent://${btoa(current.url)}#Intent;scheme=xmtv-m3u;package=com.xpola.player;end`; };
        window.onclick = (e) => { if(e.target == document.getElementById('modal')) { document.getElementById('modal').style.display='none'; if(lastFocusedElement) lastFocusedElement.focus(); } if(e.target == document.getElementById('confirmModal')) closeConfirm(); if(e.target == document.getElementById('adminPanelModal')) document.getElementById('adminPanelModal').style.display='none'; if(e.target == document.getElementById('nameChangeModal') && !nameModalRequired) document.getElementById('nameChangeModal').style.display='none'; if(e.target == document.getElementById('userActionModal')) document.getElementById('userActionModal').style.display='none'; }

        function handleRemoteControl() {
            document.addEventListener('keydown', function(e) {
                const key = e.key;
                const focusable = Array.from(document.querySelectorAll('.focusable, .card:not(.hidden)'));
                
                const visibleFocusables = focusable.filter(el => {
                    return el.offsetParent !== null && window.getComputedStyle(el).display !== 'none';
                });

                const currentFocus = document.activeElement;
                const currentIndex = visibleFocusables.indexOf(currentFocus);

                if (key === 'Enter') {
                    if (currentFocus && visibleFocusables.includes(currentFocus)) {
                        if(currentFocus.tagName !== 'INPUT') {
                            e.preventDefault();
                            currentFocus.click();
                        }
                    }
                } else if (key === 'ArrowDown' || key === 'ArrowUp' || key === 'ArrowLeft' || key === 'ArrowRight') {
                    e.preventDefault();
                    if (currentIndex === -1) {
                        if (visibleFocusables.length > 0) visibleFocusables[0].focus();
                    } else {
                        const currentRect = currentFocus.getBoundingClientRect();
                        let bestCandidate = null;
                        let minDistance = Infinity;

                        visibleFocusables.forEach(candidate => {
                            if (candidate === currentFocus) return;
                            const candRect = candidate.getBoundingClientRect();
                            
                            let isDirectionCorrect = false;
                            if (key === 'ArrowDown') isDirectionCorrect = candRect.top >= currentRect.top + (currentRect.height/2);
                            if (key === 'ArrowUp') isDirectionCorrect = candRect.bottom <= currentRect.top + (currentRect.height/2);
                            if (key === 'ArrowRight') isDirectionCorrect = candRect.left >= currentRect.left + (currentRect.width/2);
                            if (key === 'ArrowLeft') isDirectionCorrect = candRect.right <= currentRect.left + (currentRect.width/2);

                            if (isDirectionCorrect) {
                                const dx = (candRect.left + candRect.width/2) - (currentRect.left + currentRect.width/2);
                                const dy = (candRect.top + candRect.height/2) - (currentRect.top + currentRect.height/2);
                                const dist = Math.sqrt(dx*dx + dy*dy);
                                
                                if (dist < minDistance) {
                                    minDistance = dist;
                                    bestCandidate = candidate;
                                }
                            }
                        });

                        if (bestCandidate) {
                            bestCandidate.focus();
                            bestCandidate.scrollIntoView({behavior: "smooth", block: "center"});
                            document.querySelectorAll('.focused').forEach(el => el.classList.remove('focused'));
                            bestCandidate.classList.add('focused');
                        }
                    }
                } else if (key === 'Backspace' || key === 'Escape' || e.keyCode === 461 || e.keyCode === 8) {
                    const tag = document.activeElement.tagName.toLowerCase();
                    if ((key === 'Backspace' || e.keyCode === 8) && (tag === 'input' || tag === 'textarea')) {
                        return; 
                    }

                    if (document.getElementById('fullPlayerContainer').style.display === 'block') {
                        e.preventDefault();
                        document.getElementById('closeFullPlayerBtn').click();
                        return;
                    }

                    const openModals = document.querySelectorAll('.modal[style*="display: flex"]');
                    if(openModals.length > 0) {
                        e.preventDefault();
                        openModals.forEach(m => m.style.display = 'none');
                        if(lastFocusedElement) lastFocusedElement.focus();
                    } else if (document.getElementById('chatModal').classList.contains('active')) {
                        toggleChat();
                    }
                }
            });
        }

        (function() { 
            const savedTheme = localStorage.getItem('theme'); 
            if (savedTheme === 'light') toggleTheme(); 
            if(isAdmin) { 
                document.getElementById('chatStatus').innerText = "Canlı Sohbet (YÖNETİCİ) 👮‍♂️"; 
                document.getElementById('adminBtn').style.display = "flex"; 
                document.body.classList.add('admin-mode'); 
            } 
            render(); 
            setTimeout(listenToData, 500); 
            setTimeout(initPresence, 1000); 
            setTimeout(listenToAllPrivateChats, 1500);
            setTimeout(handleRemoteControl, 1000); 
        })();
    </script>
</body>
</html>"""

# ===================== SOHBET PRO V2 GÜNCELLEMESİ =====================
CHAT_UPGRADE_V2 = r"""
<style>
.chat-message-row{display:flex;align-items:flex-end;gap:8px;margin-bottom:10px;animation:chatMsgIn .18s ease;}
.chat-message-row.me{flex-direction:row-reverse;}
@keyframes chatMsgIn{from{opacity:0;transform:translateY(6px);}to{opacity:1;transform:none;}}
.chat-avatar{width:32px;height:32px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:800;font-size:.8rem;color:#fff;flex-shrink:0;border:1px solid rgba(255,255,255,.14);box-shadow:0 2px 6px rgba(0,0,0,.25);}
.chat-avatar.admin-avatar{background:#ff0040;}
.chat-message-row .message-bubble{margin:0;max-width:82%;align-self:auto;}
.msg-content{margin-top:2px;}
.msg-text{white-space:pre-wrap;word-break:break-word;line-height:1.35;}
.chat-link-group{margin-top:8px;background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.08);border-radius:12px;padding:8px;}
.light-theme .chat-link-group{background:rgba(0,0,0,.03);border-color:rgba(0,0,0,.08);}
.chat-link-header{display:flex;justify-content:space-between;align-items:center;gap:8px;margin-bottom:8px;}
.chat-link-count{font-size:.78rem;font-weight:700;opacity:.9;display:flex;align-items:center;gap:6px;}
.copy-all-links{border:none;background:linear-gradient(135deg,var(--primary),#ff4d00);color:#fff;border-radius:8px;padding:6px 10px;font-size:.75rem;font-weight:700;cursor:pointer;display:flex;align-items:center;gap:6px;white-space:nowrap;}
.chat-link-cards{display:flex;flex-direction:column;gap:8px;}
.chat-link-cards.collapsed{max-height:190px;overflow:hidden;position:relative;}
.chat-link-cards.collapsed::after{content:'';position:absolute;left:0;right:0;bottom:0;height:36px;background:linear-gradient(transparent, rgba(0,0,0,.35));pointer-events:none;}
.light-theme .chat-link-cards.collapsed::after{background:linear-gradient(transparent, rgba(255,255,255,.9));}
.chat-links-toggle{width:100%;margin-top:8px;background:rgba(255,255,255,.06);border:1px dashed rgba(255,255,255,.18);color:inherit;border-radius:8px;padding:7px;font-size:.8rem;cursor:pointer;display:flex;align-items:center;justify-content:center;gap:6px;}
.chat-link-card{display:flex;align-items:center;gap:8px;background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.09);border-radius:10px;padding:8px;}
.light-theme .chat-link-card{background:#fff;border-color:#ddd;box-shadow:0 1px 4px rgba(0,0,0,.05);}
.link-icon{width:34px;height:34px;border-radius:9px;display:flex;align-items:center;justify-content:center;flex-shrink:0;font-size:.95rem;}
.link-icon.xtream{background:rgba(255,0,64,.16);color:#ff4d6d;}
.link-icon.hls{background:rgba(0,210,255,.16);color:#00d2ff;}
.link-icon.m3u{background:rgba(0,255,127,.14);color:#00ff7f;}
.link-icon.ts{background:rgba(255,235,59,.14);color:#ffeb3b;}
.link-icon.mp4,.link-icon.mkv{background:rgba(156,39,176,.16);color:#ce93d8;}
.link-icon.telegram{background:rgba(0,136,204,.16);color:#29b6f6;}
.link-icon.web{background:rgba(255,255,255,.10);color:#fff;}
.link-info{flex:1;min-width:0;}
.link-line1{display:flex;align-items:center;gap:6px;margin-bottom:3px;flex-wrap:wrap;}
.link-badge{font-size:.62rem;font-weight:900;padding:2px 6px;border-radius:6px;letter-spacing:.4px;background:rgba(255,255,255,.12);}
.link-badge.xtream{background:rgba(255,0,64,.2);color:#ff8fa3;}
.link-badge.hls{background:rgba(0,210,255,.18);color:#7deaff;}
.link-badge.m3u{background:rgba(0,255,127,.15);color:#8effc1;}
.link-badge.ts{background:rgba(255,235,59,.15);color:#fff176;}
.link-badge.mp4,.link-badge.mkv{background:rgba(156,39,176,.18);color:#e1bee7;}
.link-badge.telegram{background:rgba(0,136,204,.18);color:#81d4fa;}
.link-badge.web{background:rgba(255,255,255,.12);color:#eee;}
.link-domain{font-size:.78rem;font-weight:700;opacity:.95;word-break:break-all;}
.link-url{font-size:.72rem;opacity:.72;word-break:break-all;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;}
.link-btns{display:flex;align-items:center;gap:6px;flex-shrink:0;}
.link-action-btn{width:32px;height:32px;border-radius:8px;border:1px solid rgba(255,255,255,.14);background:rgba(255,255,255,.08);color:#fff;display:flex;align-items:center;justify-content:center;cursor:pointer;text-decoration:none;transition:.2s;}
.link-action-btn:hover,.link-action-btn:focus{transform:scale(1.07);background:var(--primary);border-color:#fff;}
.chat-link-more{font-size:.75rem;opacity:.7;margin-top:8px;text-align:center;}
.chat-link-group{margin-top:8px;padding:7px;border-radius:12px;background:linear-gradient(145deg,rgba(0,210,255,.08),rgba(255,0,64,.06));border-color:rgba(0,210,255,.18);}
.chat-link-header{margin-bottom:6px;min-height:28px;}
.chat-link-count{font-size:.72rem;color:#9deeff;}
.copy-all-links{border:1px solid rgba(0,210,255,.3);background:rgba(0,210,255,.1);color:#dffbff;border-radius:7px;padding:5px 7px;font-size:.68rem;white-space:nowrap;cursor:pointer;}
.chat-link-cards{gap:5px;}
.chat-link-card{min-width:0;padding:6px 7px;gap:6px;border-radius:9px;background:rgba(0,0,0,.18);}
.link-icon{width:28px;height:28px;flex:0 0 28px;border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:.78rem;}
.link-info{min-width:0;flex:1;overflow:hidden;}
.link-line1{display:flex;align-items:center;gap:5px;min-width:0;}
.link-badge{font-size:.58rem;padding:2px 4px;border-radius:4px;flex:0 0 auto;}
.link-domain{font-size:.68rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;opacity:.75;}
.link-url{font-size:.66rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;opacity:.72;max-width:100%;}
.link-btns{display:flex;gap:3px;flex:0 0 auto;}
.link-action-btn{width:27px;height:27px;padding:0;border-radius:7px;display:flex;align-items:center;justify-content:center;font-size:.7rem;}
.msg-text{line-height:1.45;word-break:break-word;}
.msg-content > .msg-text + .chat-link-group{margin-top:9px;}
@media (max-width:500px){.chat-messages{padding:10px 8px;gap:8px}.chat-message-row .message-bubble{max-width:92%;}.chat-link-card{padding:5px 6px}.link-action-btn{width:25px;height:25px}.copy-all-links{font-size:.62rem;padding:5px 6px}.chat-link-count{font-size:.68rem;}}
.msg-actions .action-btn{user-select:none;}
.chat-scroll-btn{position:absolute;right:14px;bottom:14px;width:38px;height:38px;border-radius:50%;border:none;background:var(--primary);color:#fff;display:none;align-items:center;justify-content:center;cursor:pointer;z-index:50;box-shadow:0 4px 12px rgba(0,0,0,.35);}
.chat-view{position:relative;}
.chat-media-image{cursor:pointer;}
.admin-msg{background:rgba(255,0,64,.12);border:1px solid rgba(255,0,64,.35);box-shadow:0 0 14px rgba(255,0,64,.12);}
.chat-quote-image{max-height:45px;border-radius:6px;display:block;margin-bottom:4px;cursor:pointer;}
@media (max-width:520px){
.chat-message-row .message-bubble{max-width:86%;}
.link-action-btn{width:30px;height:30px;}
}
</style>
<script>
(function(){
  window.chatMessageCache = window.chatMessageCache || {};
  window.chatLinkGroups = window.chatLinkGroups || {};
  window.chatMediaCache = window.chatMediaCache || {};

  function escapeHtml(value){
    return String(value || '').replace(/[&<>"']/g, function(c){
      return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];
    });
  }

  function escapeAttr(value){
    return escapeHtml(value);
  }

  function nlToBr(value){
    return escapeHtml(value).split(String.fromCharCode(10)).join('<br>');
  }

  function fallbackCopyText(text, done, fail){
    var ta = document.createElement('textarea');
    ta.value = text;
    ta.style.position = 'fixed';
    ta.style.opacity = '0';
    document.body.appendChild(ta);
    ta.focus();
    ta.select();
    try{
      document.execCommand('copy');
      done();
    }catch(e){
      fail();
    }
    document.body.removeChild(ta);
  }

  function copyTextToClipboard(text){
    if(!text){
      if(typeof showToast === 'function') showToast('Kopyalanacak içerik yok', 'fa-exclamation');
      return;
    }
    var done = function(){ if(typeof showToast === 'function') showToast('Kopyalandı ✅', 'fa-check'); };
    var fail = function(){ if(typeof showToast === 'function') showToast('Kopyalanamadı', 'fa-exclamation'); };

    if(navigator.clipboard && window.isSecureContext){
      navigator.clipboard.writeText(text).then(done).catch(function(){
        fallbackCopyText(text, done, fail);
      });
    }else{
      fallbackCopyText(text, done, fail);
    }
  }

  function cleanTrailingUrl(url){
    return String(url || '').replace(/[.,;:!?)>'"]+$/, '');
  }

  function maskSensitiveUrl(url){
    try{
      var u = new URL(url);
      if(u.searchParams.has('password')) u.searchParams.set('password', '****');
      return u.toString();
    }catch(e){
      return url;
    }
  }

  function getDisplayUrl(url){
    var masked = maskSensitiveUrl(url);
    masked = String(masked);
    if(masked.length > 160) masked = masked.substring(0, 160) + '…';
    return masked;
  }

  function getLinkDomain(url){
    try{
      return new URL(url).hostname.replace(/^www\./, '');
    }catch(e){
      var m = String(url).match(/^https?:\/\/([^\/]+)/i);
      return m ? m[1].replace(/^www\./, '') : 'Bağlantı';
    }
  }

  function detectLinkType(url){
    var u = String(url || '').toLowerCase();
    if(u.indexOf('username=') !== -1 && u.indexOf('password=') !== -1) return {label:'XTREAM', cls:'xtream', icon:'fa-key', playable:false};
    if(u.indexOf('.m3u8') !== -1) return {label:'HLS', cls:'hls', icon:'fa-broadcast-tower', playable:true};
    if(u.indexOf('.m3u') !== -1) return {label:'M3U', cls:'m3u', icon:'fa-list', playable:false};
    if(u.indexOf('.ts') !== -1) return {label:'TS', cls:'ts', icon:'fa-film', playable:true};
    if(u.indexOf('.mp4') !== -1) return {label:'MP4', cls:'mp4', icon:'fa-file-video', playable:true};
    if(u.indexOf('.mkv') !== -1) return {label:'MKV', cls:'mkv', icon:'fa-file-video', playable:true};
    if(u.indexOf('t.me/') !== -1 || u.indexOf('telegram.me/') !== -1) return {label:'TELEGRAM', cls:'telegram', icon:'fa-telegram', playable:false};
    return {label:'LINK', cls:'web', icon:'fa-link', playable:false};
  }

  function xtreamToM3u(url){
    try{
      var u = new URL(url);
      var username = u.searchParams.get('username');
      var password = u.searchParams.get('password');
      if(username && password){
        return u.origin + '/get.php?username=' + encodeURIComponent(username) + '&password=' + encodeURIComponent(password) + '&type=m3u_plus&output=mpegts';
      }
    }catch(e){}
    return url;
  }

  function buildLinkCard(url){
    var type = detectLinkType(url);
    var domain = getLinkDomain(url);
    var safeUrl = escapeAttr(url);
    var display = escapeHtml(getDisplayUrl(url));
    var playable = type.playable || (typeof checkIsVideo === 'function' && checkIsVideo(url));
    var playBtn = playable ? '<button type="button" class="link-action-btn play-link-btn focusable" title="Oynat"><i class="fas fa-play"></i></button>' : '';
    var m3uBtn = type.label === 'XTREAM' ? '<button type="button" class="link-action-btn copy-m3u-btn focusable" title="M3U olarak kopyala"><i class="fas fa-list-ul"></i></button>' : '';

    return '<div class="chat-link-card" data-url="' + safeUrl + '">' +
      '<div class="link-icon ' + type.cls + '"><i class="fas ' + type.icon + '"></i></div>' +
      '<div class="link-info">' +
        '<div class="link-line1">' +
          '<span class="link-badge ' + type.cls + '">' + type.label + '</span>' +
          '<span class="link-domain">' + escapeHtml(domain) + '</span>' +
        '</div>' +
        '<div class="link-url" title="' + escapeAttr(maskSensitiveUrl(url)) + '">' + display + '</div>' +
      '</div>' +
      '<div class="link-btns">' +
        m3uBtn +
        '<button type="button" class="link-action-btn copy-link-btn focusable" title="Linki kopyala"><i class="fas fa-copy"></i></button>' +
        playBtn +
        '<a class="link-action-btn open-link-btn focusable" href="' + safeUrl + '" target="_blank" rel="noopener" title="Aç"><i class="fas fa-external-link-alt"></i></a>' +
      '</div>' +
    '</div>';
  }

  function buildLinkGroup(urls){
    var groupId = 'lg_' + Date.now() + '_' + Math.floor(Math.random() * 100000);
    window.chatLinkGroups[groupId] = urls;

    var displayLimit = 100;
    var displayUrls = urls.slice(0, displayLimit);
    var collapsed = urls.length > 5;

    var html = '<div class="chat-link-group" data-group-id="' + groupId + '" data-link-count="' + urls.length + '">';
    html += '<div class="chat-link-header">';
    html += '<span class="chat-link-count"><i class="fas fa-link"></i> ' + urls.length + ' bağlantı</span>';
    html += '<button type="button" class="copy-all-links focusable"><i class="fas fa-copy"></i> Tümünü Kopyala</button>';
    html += '</div>';

    html += '<div class="chat-link-cards' + (collapsed ? ' collapsed' : '') + '">';
    displayUrls.forEach(function(u){
      html += buildLinkCard(u);
    });
    html += '</div>';

    if(urls.length > displayLimit){
      html += '<div class="chat-link-more">+' + (urls.length - displayLimit) + ' bağlantı daha var. Tümünü Kopyala ile hepsini alabilirsin.</div>';
    }

    if(collapsed){
      html += '<button type="button" class="chat-links-toggle focusable"><i class="fas fa-chevron-down"></i> Tümünü Göster (' + urls.length + ')</button>';
    }

    html += '</div>';
    return html;
  }

  function nlToBrWithLinks(value){
    var safe = escapeHtml(value);
    safe = safe.replace(/https?:\/\/[^\s<]+/gi, function(token){
      var trailing = '';
      while(/[.,;:!?)\]}]+$/.test(token)){
        trailing = token.slice(-1) + trailing;
        token = token.slice(0, -1);
      }
      return '<a class="chat-inline-link" data-copy-url="' + token + '" href="' + token + '" target="_blank" rel="noopener noreferrer">' + token + '</a>' + trailing;
    });
    return safe.split(String.fromCharCode(10)).join('<br>');
  }

  function formatCopiedChatText(value){
    var text = String(value || '').replace(/\r\n?/g, '\n').replace(/\u00a0/g, ' ');
    text = text.replace(/[ \t]+\n/g, '\n').trim();
    // Kopyalanan hesap çıktısındaki alanları dosya görünümündeki gibi satırlara ayırır.
    text = text.replace(/([^\n])\s+(?=🔥\s*INADINATV)/g, '$1\n');
    text = text.replace(/\s+(?=👤|📅|📡|📌|🌍|📺|🎬|🔗|📁|🔍)/g, '\n');
    text = text.replace(/\n{4,}/g, '\n\n\n');
    return text;
  }

  function renderRichMessageText(text){
    var raw = String(text || '');
    if(!raw.trim()) return '<div class="msg-text"></div>';
    var formatted = formatCopiedChatText(raw);
    var structured = /M3U:|JSON:|Bitiş:|Deep Scan:|INADINATV/i.test(formatted) || formatted.indexOf('\n') !== -1;
    var longMessage = structured && (formatted.length > 1800 || formatted.split('\n').length > 24);
    var classes = 'msg-text' + (structured ? ' formatted-chat-text' : '') + (longMessage ? ' collapsed-chat-text' : '');
    var html = '<div class="' + classes + '">' + nlToBrWithLinks(formatted) + '</div>';
    if(longMessage) html += '<button type="button" class="chat-expand-btn focusable">Devamını göster <i class="fas fa-chevron-down"></i></button>';
    return html;
  }

  function buildFileBlock(file, fileId){
    return '<div class="chat-file-block focusable" data-file-id="' + fileId + '" role="button" tabindex="0">' +
      '<i class="fas fa-file-alt file-icon"></i>' +
      '<div class="file-info">' +
        '<span class="file-name">' + escapeHtml((file && file.name) ? file.name : 'dosya') + '</span>' +
        '<span class="file-dl">Görüntüle/Kopyala</span>' +
      '</div>' +
    '</div>';
  }

  function isNearBottom(el){
    return el && (el.scrollHeight - el.scrollTop - el.clientHeight < 140);
  }

  function updateChatScrollButton(container){
    if(!container || !container.parentElement) return;
    var btn = container.parentElement.querySelector('.chat-scroll-btn');
    if(btn){
      var show = container.scrollHeight - container.scrollTop - container.clientHeight > 160;
      btn.style.display = show ? 'flex' : 'none';
    }
  }

  function smartAppend(container, node){
    if(!container) return;
    var stick = container.childElementCount === 0 || isNearBottom(container);
    container.appendChild(node);
    if(stick) container.scrollTop = container.scrollHeight;
    updateChatScrollButton(container);
  }

  function createScrollButton(container){
    if(!container || container.dataset.scrollBtnReady) return;
    container.dataset.scrollBtnReady = '1';

    var parent = container.parentElement;
    if(!parent) return;
    parent.style.position = 'relative';

    var btn = document.createElement('button');
    btn.className = 'chat-scroll-btn focusable';
    btn.innerHTML = '<i class="fas fa-arrow-down"></i>';
    btn.title = 'Aşağı kaydır';
    parent.appendChild(btn);

    container.addEventListener('scroll', function(){
      updateChatScrollButton(container);
    });

    btn.addEventListener('click', function(){
      try{
        container.scrollTo({top: container.scrollHeight, behavior: 'smooth'});
      }catch(e){
        container.scrollTop = container.scrollHeight;
      }
    });

    updateChatScrollButton(container);
  }

  function playChatLink(url){
    if(!url) return;

    current = {
      title: 'Sohbet Yayını',
      url: url,
      web_link_url: '#',
      image: ''
    };

    var chatModal = document.getElementById('chatModal');
    if(chatModal) chatModal.classList.remove('active');

    var fullContainer = document.getElementById('fullPlayerContainer');
    if(fullContainer) fullContainer.style.display = 'block';

    var finalUrl = (typeof formatStreamUrl === 'function') ? formatStreamUrl(url) : url;
    var type = detectLinkType(url);
    var isVideo = type.playable || (typeof checkIsVideo === 'function' && checkIsVideo(finalUrl));

    fullVjsPlayer = destroyPlayer(fullVjsPlayer, 'fullVideoWrapper', 'fullVideo');

    if(isVideo){
      document.getElementById('fullIframe').style.display = 'none';
      document.getElementById('fullIframe').src = '';
      document.getElementById('fullVideoWrapper').style.display = 'block';
      fullVjsPlayer = createPlayer('fullVideo', finalUrl);
    }else{
      document.getElementById('fullVideoWrapper').style.display = 'none';
      document.getElementById('fullIframe').style.display = 'block';
      document.getElementById('fullIframe').src = url;
    }

    setTimeout(function(){
      var b = document.getElementById('closeFullPlayerBtn');
      if(b) b.focus();
    }, 120);

    if(typeof showToast === 'function') showToast('Oynatıcı açılıyor...', 'fa-play');
  }

  function appendMessagePro(msg, key){
    var container = document.getElementById('chatContainer');
    if(!container || !msg) return;

    window.chatMessageCache[key] = msg;

    var row = document.createElement('div');
    row.className = 'chat-message-row';

    var isMe = (msg.uuid && msg.uuid === myUUID) || msg.user === myUserName;
    if(isMe) row.classList.add('me');

    var adminMessage = !!msg.isAdminMsg;
    var rawName = msg.user || 'Misafir';
    var displayName = adminMessage ? 'YÖNETİCİ' : rawName;

    var avatar = adminMessage
      ? '<div class="chat-avatar admin-avatar"><i class="fas fa-shield-alt"></i></div>'
      : '<div class="chat-avatar" style="background:' + getUserColor(displayName) + '">' + escapeHtml((displayName || '?').trim().charAt(0).toUpperCase()) + '</div>';

    var bubble = document.createElement('div');
    bubble.className = 'message-bubble ' + (isMe ? 'msg-right' : 'msg-left') + ((typeof isAdmin !== 'undefined' && isAdmin) ? ' is-admin' : '') + (adminMessage ? ' admin-msg' : '');

    if(!isMe && !adminMessage){
      bubble.style.backgroundColor = getUserColor(displayName);
    }

    var quoteHTML = '';
    if(msg.replyTo){
      var qContent = '';
      if(msg.replyTo.image){
        qContent += '<img src="' + escapeAttr(msg.replyTo.image) + '" class="chat-quote-image chat-media-image" alt="quote image">';
      }
      if(msg.replyTo.text){
        qContent += '<span>' + nlToBr(msg.replyTo.text) + '</span>';
      }
      if(!msg.replyTo.text && !msg.replyTo.image){
        qContent = '<i>Silinmiş Mesaj</i>';
      }
      quoteHTML = '<div class="quoted-msg"><span class="quote-user">' + escapeHtml(msg.replyTo.user || '') + '</span>' + qContent + '</div>';
    }

    var contentHTML = '';
    if(msg.image){
      if(msg.text) contentHTML += renderRichMessageText(msg.text);
      contentHTML += '<img src="' + escapeAttr(msg.image) + '" class="chat-img chat-media-image focusable" tabindex="0" alt="resim">';
    }else if(msg.file){
      var fileId = 'file_' + key;
      window.chatMediaCache[fileId] = msg.file;
      if(msg.text) contentHTML += renderRichMessageText(msg.text);
      contentHTML += buildFileBlock(msg.file, fileId);
    }else{
      contentHTML = renderRichMessageText(msg.text);
    }

    var userHtml = '<span class="msg-user focusable" data-msg-user="' + key + '" title="Kullanıcı işlemleri">' +
      (adminMessage ? '<span class="msg-admin"><i class="fas fa-shield-alt"></i> YÖNETİCİ</span>' : escapeHtml(displayName)) +
    '</span>';

    var timeHTML = '<span class="msg-time">' + formatTime(msg.time || Date.now()) + (msg.editedAt ? ' · düzenlendi' : '') + '</span>';

    var myReactions = {};
    try{
      myReactions = JSON.parse(localStorage.getItem('chat_reactions') || '{}');
    }catch(e){}

    var myReact = myReactions[key];
    var likeClass = myReact === 'like' ? 'active-like' : '';
    var dislikeClass = myReact === 'dislike' ? 'active-dislike' : '';

    var actionsHTML = '<div class="msg-actions">' +
      '<span class="action-btn focusable" data-action="copy-message" title="Mesajı kopyala"><i class="fas fa-copy"></i> Kopyala</span>' +
      '<span id="btn-like-' + key + '" class="action-btn ' + likeClass + ' focusable" data-action="like" data-msg-key="' + key + '" title="Beğen"><i class="fas fa-thumbs-up"></i> <span id="like-count-' + key + '">' + (msg.likes || 0) + '</span></span>' +
      '<span id="btn-dislike-' + key + '" class="action-btn ' + dislikeClass + ' focusable" data-action="dislike" data-msg-key="' + key + '" title="Beğenme"><i class="fas fa-thumbs-down"></i> <span id="dislike-count-' + key + '">' + (msg.dislikes || 0) + '</span></span>' +
    '</div>';

    var adminControls = '';
    if(typeof isAdmin !== 'undefined' && isAdmin){
      var editButton = (adminMessage && typeof msg.text === 'string')
        ? '<button class="btn-edit focusable" data-action="edit-message" data-msg-key="' + key + '">✏️ DÜZENLE</button>'
        : '';
      adminControls = '<div class="admin-controls">' + editButton + '<button class="btn-del focusable" data-action="delete-message" data-msg-key="' + key + '">🗑️ SİL</button></div>';
    }

    bubble.innerHTML = quoteHTML + userHtml + '<div class="msg-content">' + contentHTML + '</div>' + timeHTML + actionsHTML + adminControls;

    row.innerHTML = avatar;
    row.appendChild(bubble);

    smartAppend(container, row);
  }

  function appendPrivateMessagePro(msg){
    var container = document.getElementById('privateChatContainer');
    if(!container || !msg) return;

    var row = document.createElement('div');
    var isMe = (msg.uuid && msg.uuid === myUUID) || msg.user === myUserName;
    row.className = 'chat-message-row' + (isMe ? ' me' : '');

    var name = msg.user || 'Misafir';
    var avatar = '<div class="chat-avatar" style="background:' + getUserColor(name) + '">' + escapeHtml((name || '?').trim().charAt(0).toUpperCase()) + '</div>';

    var bubble = document.createElement('div');
    bubble.className = 'message-bubble ' + (isMe ? 'msg-right' : 'msg-left');

    if(!isMe){
      bubble.style.backgroundColor = getUserColor(name);
    }

    var contentHTML = '';
    if(msg.image){
      if(msg.text) contentHTML += renderRichMessageText(msg.text);
      contentHTML += '<img src="' + escapeAttr(msg.image) + '" class="chat-img chat-media-image focusable" tabindex="0" alt="resim">';
    }else if(msg.file){
      var fileId = 'pf_' + Date.now() + '_' + Math.floor(Math.random() * 100000);
      window.chatMediaCache[fileId] = msg.file;
      if(msg.text) contentHTML += renderRichMessageText(msg.text);
      contentHTML += buildFileBlock(msg.file, fileId);
    }else{
      contentHTML = renderRichMessageText(msg.text);
    }

    var timeHTML = '<span class="msg-time">' + formatTime(msg.time || Date.now()) + (msg.editedAt ? ' · düzenlendi' : '') + '</span>';
    var actionsHTML = '<div class="msg-actions"><span class="action-btn focusable" data-action="copy-message" title="Kopyala"><i class="fas fa-copy"></i> Kopyala</span></div>';

    bubble.innerHTML = '<span class="msg-user">' + escapeHtml(name) + '</span><div class="msg-content">' + contentHTML + '</div>' + timeHTML + actionsHTML;

    row.innerHTML = avatar;
    row.appendChild(bubble);

    smartAppend(container, row);
  }

  var editingMessageKey = null;
  window.openEditMessage = function(key){
    if(typeof isAdmin === 'undefined' || !isAdmin) return;
    var msg = window.chatMessageCache[key];
    if(!msg || !msg.isAdminMsg || typeof msg.text !== 'string') return;
    editingMessageKey = key;
    var input = document.getElementById('editMessageInput');
    if(!input) return;
    input.value = msg.text;
    document.getElementById('editMessageModal').style.display = 'flex';
    setTimeout(function(){ input.focus(); input.setSelectionRange(input.value.length, input.value.length); }, 40);
  };
  window.closeEditMessage = function(){
    editingMessageKey = null;
    var modal = document.getElementById('editMessageModal');
    if(modal) modal.style.display = 'none';
  };
  window.saveEditedMessage = function(){
    if(!editingMessageKey || typeof isAdmin === 'undefined' || !isAdmin) return;
    var input = document.getElementById('editMessageInput');
    var text = input ? input.value.trim() : '';
    if(!text){ if(typeof showToast === 'function') showToast('Mesaj boş bırakılamaz', 'fa-exclamation'); return; }
    var key = editingMessageKey;
    database.ref('global_chat/' + key).update({text: text, editedAt: Date.now(), editedBy: (typeof myUUID !== 'undefined' ? myUUID : '')})
      .then(function(){ closeEditMessage(); if(typeof showToast === 'function') showToast('Mesaj güncellendi', 'fa-check'); })
      .catch(function(){ if(typeof showToast === 'function') showToast('Mesaj güncellenemedi', 'fa-exclamation'); });
  };

  window.appendMessage = appendMessagePro;
  try{ appendMessage = appendMessagePro; }catch(e){}

  window.appendPrivateMessage = appendPrivateMessagePro;
  try{ appendPrivateMessage = appendPrivateMessagePro; }catch(e){}

  var longPressTimer = null;
  var suppressInlineLinkClick = false;
  document.addEventListener('pointerdown', function(e){
    var link = e.target.closest ? e.target.closest('.chat-inline-link') : null;
    if(!link) return;
    suppressInlineLinkClick = false;
    longPressTimer = setTimeout(function(){
      suppressInlineLinkClick = true;
      copyTextToClipboard(link.dataset.copyUrl || link.href);
      link.classList.add('link-long-pressed');
      setTimeout(function(){ link.classList.remove('link-long-pressed'); }, 700);
    }, 650);
  }, {passive:true});
  ['pointerup','pointercancel','pointerleave'].forEach(function(type){
    document.addEventListener(type, function(){
      if(longPressTimer){ clearTimeout(longPressTimer); longPressTimer = null; }
    }, {passive:true});
  });
  document.addEventListener('contextmenu', function(e){
    var link = e.target.closest ? e.target.closest('.chat-inline-link') : null;
    if(link){ e.preventDefault(); copyTextToClipboard(link.dataset.copyUrl || link.href); }
  });

  document.addEventListener('click', function(e){
    var inlineLink = e.target.closest ? e.target.closest('.chat-inline-link') : null;
    if(inlineLink){
      if(suppressInlineLinkClick){ e.preventDefault(); suppressInlineLinkClick = false; }
      return;
    }
    var expandBtn = e.target.closest ? e.target.closest('.chat-expand-btn') : null;
    if(expandBtn){
      var block = expandBtn.previousElementSibling;
      if(block) block.classList.remove('collapsed-chat-text');
      expandBtn.remove();
      return;
    }
    var img = e.target.closest('.chat-media-image');
    if(img){
      if(typeof showImagePreview === 'function') showImagePreview(img.src);
      return;
    }

    var fileBlock = e.target.closest('.chat-file-block');
    if(fileBlock){
      var file = window.chatMediaCache[fileBlock.dataset.fileId];
      if(file && typeof openInAppViewer === 'function') openInAppViewer(file.data, file.name);
      return;
    }

    var copyLinkBtn = e.target.closest('.copy-link-btn');
    if(copyLinkBtn){
      var linkCard = copyLinkBtn.closest('.chat-link-card');
      if(linkCard) copyTextToClipboard(linkCard.dataset.url);
      return;
    }

    var copyM3uBtn = e.target.closest('.copy-m3u-btn');
    if(copyM3uBtn){
      var xtreamCard = copyM3uBtn.closest('.chat-link-card');
      if(xtreamCard) copyTextToClipboard(xtreamToM3u(xtreamCard.dataset.url));
      return;
    }

    var playLinkBtn = e.target.closest('.play-link-btn');
    if(playLinkBtn){
      var playCard = playLinkBtn.closest('.chat-link-card');
      if(playCard) playChatLink(playCard.dataset.url);
      return;
    }

    var copyAllBtn = e.target.closest('.copy-all-links');
    if(copyAllBtn){
      var group = copyAllBtn.closest('.chat-link-group');
      if(group){
        var urls = window.chatLinkGroups[group.dataset.groupId] || Array.from(group.querySelectorAll('.chat-link-card')).map(function(c){ return c.dataset.url; });
        copyTextToClipboard(urls.join(String.fromCharCode(10)));
      }
      return;
    }

    var toggleBtn = e.target.closest('.chat-links-toggle');
    if(toggleBtn){
      var toggleGroup = toggleBtn.closest('.chat-link-group');
      var cards = toggleGroup ? toggleGroup.querySelector('.chat-link-cards') : null;
      if(cards){
        var isNowCollapsed = cards.classList.toggle('collapsed');
        toggleBtn.innerHTML = isNowCollapsed
          ? '<i class="fas fa-chevron-down"></i> Tümünü Göster (' + (toggleGroup.dataset.linkCount || '') + ')'
          : '<i class="fas fa-chevron-up"></i> Daralt';
      }
      return;
    }

    var copyMsgBtn = e.target.closest('[data-action="copy-message"]');
    if(copyMsgBtn){
      var bubble = copyMsgBtn.closest('.message-bubble');
      if(bubble){
        var linkGroup = bubble.querySelector('.chat-link-group');
        var copyText = '';
        if(linkGroup){
          var gid = linkGroup.dataset.groupId;
          var groupUrls = window.chatLinkGroups[gid] || Array.from(linkGroup.querySelectorAll('.chat-link-card')).map(function(c){ return c.dataset.url; });
          copyText = groupUrls.join(String.fromCharCode(10));
        }else{
          var content = bubble.querySelector('.msg-content');
          copyText = content ? content.innerText.trim() : '';
        }
        copyTextToClipboard(copyText);
      }
      return;
    }

    var reactBtn = e.target.closest('[data-action="like"],[data-action="dislike"]');
    if(reactBtn){
      var msgKey = reactBtn.dataset.msgKey;
      var type = reactBtn.dataset.action === 'like' ? 'like' : 'dislike';
      if(typeof toggleChatReaction === 'function') toggleChatReaction(msgKey, type);
      return;
    }

    var editBtn = e.target.closest('[data-action="edit-message"]');
    if(editBtn){
      if(typeof openEditMessage === 'function') openEditMessage(editBtn.dataset.msgKey);
      return;
    }

    var delBtn = e.target.closest('[data-action="delete-message"]');
    if(delBtn){
      if(typeof openConfirmModal === 'function') openConfirmModal('del', delBtn.dataset.msgKey);
      return;
    }

    var userEl = e.target.closest('[data-msg-user]');
    if(userEl){
      var cachedMsg = window.chatMessageCache[userEl.dataset.msgUser];
      if(cachedMsg && cachedMsg.uuid !== myUUID && cachedMsg.user !== myUserName && typeof openUserActionModal === 'function'){
        openUserActionModal(cachedMsg.uuid, cachedMsg.user, userEl.dataset.msgUser, cachedMsg.text || '', cachedMsg.image || '');
      }
      return;
    }
  });

  var msgInput = document.getElementById('msgInput');
  if(msgInput){
    msgInput.addEventListener('keydown', function(e){
      if(e.key === 'Enter'){
        e.preventDefault();
        if(typeof sendMsg === 'function') sendMsg();
      }
    });
  }

  createScrollButton(document.getElementById('chatContainer'));
  createScrollButton(document.getElementById('privateChatContainer'));
})();
</script>
"""

_original_get_html_template = IPTV_Bot_Pro.get_html_template

def _patched_get_html_template(self):
    html = _original_get_html_template(self)
    upgrade = CHAT_UPGRADE_V2.strip()
    if upgrade and "</body>" in html:
        return html.replace("</body>", upgrade + "\n</body>")
    return html

IPTV_Bot_Pro.get_html_template = _patched_get_html_template
# ===================== SOHBET PRO V2 SONU =====================

if __name__ == "__main__":
    bot = IPTV_Bot_Pro()
    asyncio.run(bot.run_bot())
