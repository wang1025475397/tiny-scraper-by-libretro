import os
import binascii
import json
import base64
import time
from pathlib import Path
import ssl
from urllib.request import urlopen, Request
import urllib.parse
from systems import get_system_extension, systems

DEFAULT_REGION = 'wor'

def retry_on_network_error(max_retries=3, delay=2):
    """Decorator to retry on network errors"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if "Temporary failure in name resolution" in str(e) or \
                       "Connection refused" in str(e) or \
                       "timed out" in str(e).lower():
                        last_exception = e
                        if attempt < max_retries - 1:
                            print(f"Network error, retrying {attempt + 1}/{max_retries}...")
                            time.sleep(delay * (attempt + 1))
                            continue
                    raise
            raise last_exception
        return wrapper
    return decorator


class Rom:
    def __init__(self, name, filename, crc=""):
        self.name = name
        self.filename = filename
        self.crc = crc

    def set_crc(self, crc):
        self.crc = crc


class Scraper:
    def __init__(self):
        self.user = ""
        self.password = ""
        self.devid = "cmVhdmVu"
        self.devpassword = "MDZXZUY5bTBldWs="
        self.media_type = "ss"
        self.region = DEFAULT_REGION
        self.resize = False
        self.preferred_sources = ["libretro", "screenscraper"]
        self.thumbnail_priority = ["Named_Snaps", "Named_Titles", "Named_Boxarts"]

    def load_config_from_json(self, filepath) -> bool:
        if not os.path.exists(filepath):
            print(f"Config file {filepath} not found")
            return False

        with open(filepath, "r") as file:
            config = json.load(file)
            self.user = config.get("user")
            self.password = config.get("password")
            self.media_type = config.get("media_type") or "ss"
            self.region = config.get("region") or "wor"
            self.resize = config.get("resize") is True
            self.preferred_sources = config.get("preferred_sources") or ["libretro", "screenscraper"]
            self.thumbnail_priority = config.get("thumbnail_priority") or ["Named_Snaps", "Named_Titles", "Named_Boxarts"]
        return True

    def get_crc32_from_file(self, rom, chunk_size = 65536):
        crc32 = 0
        with rom.open(mode="rb") as file:
            while chunk := file.read(chunk_size):
                crc32 = binascii.crc32(chunk, crc32)
        crc32 = crc32 & 0xFFFFFFFF
        return "%08X" % crc32

    def get_files_without_extension(self, folder):
        return [f.stem for f in Path(folder).glob("*") if f.is_file()]

    def get_image_files_without_extension(self, folder):
        image_extensions = (".jpg", ".jpeg", ".png")
        return [
            f.stem for f in folder.glob("*") if f.suffix.lower() in image_extensions
        ]

    def get_roms(self, path, system: str) -> list[Rom]:
        roms = []
        system_path = Path(path) / system
        system_extensions = get_system_extension(system)
        if not system_extensions:
            print(f"No extensions found for system: {system}")
            return roms

        for file in os.listdir(system_path):
            file_path = Path(system_path) / file
            if file.startswith(".") or file.startswith("-"):
                continue
            if file_path.is_file():
                file_extension = file_path.suffix.lower().lstrip(".")
                if file_extension in system_extensions:
                    name = file_path.stem
                    rom = Rom(filename=file, name=name)
                    roms.append(rom)

        return roms

    def get_available_systems(self, roms_path: str) -> list[str]:
        all_systems = [system["name"] for system in systems]
        available_systems = []
        for system in all_systems:
            system_path = Path(roms_path) / system
            if system_path.exists() and any(system_path.iterdir()):
                available_systems.append(system)

        return available_systems

    def _get_ssl_context(self):
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx

    def _extract_screenshot_from_game(self, game_data, game_name) -> bytes | None:
        """从游戏数据中提取截图，返回图片bytes"""
        medias = [media for media in game_data.get("medias", [])
                  if media.get("type") == self.media_type]

        screenshot_url = ""
        regions_to_try = [self.region]
        if DEFAULT_REGION not in regions_to_try:
            regions_to_try.append(DEFAULT_REGION)

        for target in regions_to_try:
            for media in medias:
                if media.get("region") == target:
                    screenshot_url = media.get("url")
                    print(f"Found screenshot for media type '{self.media_type}' in region '{target}'")
                    break
            if screenshot_url:
                break

        if not screenshot_url and medias:
            screenshot_url = medias[0].get("url")
            print(f"No match for preferred regions. Using fallback region '{medias[0].get('region')}'")

        if screenshot_url:
            ctx = self._get_ssl_context()
            img_request = Request(screenshot_url)
            with urlopen(img_request, context=ctx, timeout=30) as img_response:
                if img_response.headers.get("Content-Type") == "image/png":
                    return img_response.read()
                else:
                    print(f"Invalid image format for {game_name}")
        else:
            print(f"No screenshot URL found for {game_name}")
        return None

    def scrape_screenshot(
        self, crc: str, game_name: str, system_id: int
    ) -> bytes | None:
        """总入口：先按hash刮削，失败则按名称刮削"""
        return self.scrape_screenshot_by_hash(crc, game_name, system_id)
        # if result is not None:
        #     return result
        # print(f"Hash scrape failed for {game_name}, trying by name...")
        # return self.scrape_screenshot_by_name(game_name, system_id)

    @retry_on_network_error(max_retries=3, delay=2)
    def scrape_screenshot_by_hash(
        self, crc: str, game_name: str, system_id: int
    ) -> bytes | None:
        """通过CRC哈希刮削截图 (jeuInfos.php)"""
        ctx = self._get_ssl_context()

        decoded_devid = base64.b64decode(self.devid).decode()
        decoded_devpassword = base64.b64decode(self.devpassword).decode()
        encoded_game_name = urllib.parse.quote(game_name)
        url = f"https://api.screenscraper.fr/api2/jeuInfos.php?devid={decoded_devid}&devpassword={decoded_devpassword}&softname=tiny-scraper&output=json&ssid={self.user}&sspassword={self.password}&crc={crc}&systemeid={system_id}&romtype=rom&romnom={encoded_game_name}"

        print(f"Scraping screenshot by hash for {game_name}...")
        request = Request(url)
        try:
            with urlopen(request, context=ctx, timeout=30) as response:
                if response.status == 200:
                    try:
                        data = json.loads(response.read())
                        game_data = data.get("response").get("jeu")
                        if game_data:
                            return self._extract_screenshot_from_game(game_data, game_name)
                        else:
                            print(f"No game data found for {game_name}")
                    except ValueError:
                        print(f"Invalid JSON response for {game_name}")
                else:
                    print(f"Failed to get screenshot for {game_name}")
            return None
        except Exception as e:
            print(f"[ERROR] Hash scrape failed for: {game_name}")
            print(f"[URL] {url}")
            print(f"[EXCEPTION] {type(e).__name__}: {e}")
            return None

    @retry_on_network_error(max_retries=3, delay=2)
    def scrape_screenshot_by_name(
        self, game_name: str, system_id: int
    ) -> bytes | None:
        """通过游戏名称刮削截图 (jeuRecherche.php)"""
        ctx = self._get_ssl_context()

        decoded_devid = base64.b64decode(self.devid).decode()
        decoded_devpassword = base64.b64decode(self.devpassword).decode()
        encoded_game_name = urllib.parse.quote(game_name)
        url = f"https://api.screenscraper.fr/api2/jeuRecherche.php?devid={decoded_devid}&devpassword={decoded_devpassword}&softname=tiny-scraper&output=json&ssid={self.user}&sspassword={self.password}&recherche={encoded_game_name}&systemeid={system_id}"

        print(f"Scraping screenshot by name for {game_name}...")
        request = Request(url)
        try:
            with urlopen(request, context=ctx, timeout=30) as response:
                if response.status == 200:
                    try:
                        data = json.loads(response.read())
                        jeux = data.get("response").get("jeux", [])
                        if not jeux:
                            print(f"No games found by name for {game_name}")
                            return None
                        # 取搜索结果中的第一个游戏
                        game_data = jeux[0]
                        return self._extract_screenshot_from_game(game_data, game_name)
                    except ValueError:
                        print(f"Invalid JSON response for {game_name}")
                else:
                    print(f"Failed to get screenshot by name for {game_name}")
            return None
        except Exception as e:
            print(f"Error scraping screenshot by name for {game_name}: {e}")
            return None
