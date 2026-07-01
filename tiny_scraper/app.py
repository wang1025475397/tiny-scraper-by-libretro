import ssl
import concurrent.futures
import threading
from pathlib import Path
from typing import List, Optional
from main import hw_info, system_lang
from graphic import screen_resolutions
from language import Translator
import graphic as gr
import input
import sys
import time
import socket
from anbernic import Anbernic
from scraper import Scraper
from systems import get_system_id
from thumbnail_matcher import matcher as thumbnail_matcher, DEF_SCORE as THUMBNAIL_DEF_SCORE, find_media_by_crc
from thumbnail_matcher import find_merged_game_by_name, merged_game_media_names, load_platform_aliases, normalize_platform_alias
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO

translator = Translator(system_lang)
selected_position = 0
roms_selected_position = 0
selected_system = ""
current_window = "console"
an = Anbernic()
scraper = Scraper()
skip_input_check = False
missing_media_cache = {}
cached_storage_path = None

# 刮削历史记录 (最多4条): [(game_name, img_path), ...]
scrape_history = []

# 多线程刮削时的全局锁，用于保护控制台输出和状态计数
scrape_lock = threading.Lock()
scrape_progress = {"success": 0, "failure": 0, "completed": 0}

x_size, y_size, max_elem = screen_resolutions.get(hw_info, (640, 480, 11))

button_x = x_size - 110
button_y = y_size - 30
ratio = y_size / x_size


def is_connected():
    try:
        sock = socket.create_connection(("1.1.1.1", 53), timeout=3)
        sock.close()
        return True
    except (socket.timeout, socket.error):
        return False


def rebuild_missing_media_cache() -> None:
    """Rebuild the cache of missing media counts for all systems"""
    global missing_media_cache, cached_storage_path
    
    storage_path = an.get_sd_storage_path()
    available_systems = scraper.get_available_systems(storage_path)
    
    missing_media_cache = {}
    for system in available_systems:
        roms_list = scraper.get_roms(storage_path, system)
        imgs_folder = Path(f"{storage_path}/{system}/Imgs")
        
        if not imgs_folder.exists():
            missing_count = len(roms_list)
        else:
            imgs_files = set(scraper.get_image_files_without_extension(imgs_folder))
            missing_count = len([rom for rom in roms_list if rom.name not in imgs_files])

        
        missing_media_cache[system] = (missing_count, len(roms_list))
    
    cached_storage_path = storage_path


def start(config_path: str) -> None:
    print("Starting Tiny Scraper...")
    if not is_connected():
        gr.draw_log(
            f"{translator.translate('No internet connection')}", fill=gr.colorBlue, outline=gr.colorBlueD1
        )
        gr.draw_paint()
        time.sleep(3)
        sys.exit(1)
    scraper.load_config_from_json(config_path)
    load_console_menu()


def update() -> None:
    global current_window, selected_position, skip_input_check

    if skip_input_check:
        input.reset_input()
        skip_input_check = False
    else:
        input.check()

    if input.key("MENUF"):
        gr.draw_end()
        print("Exiting Tiny Scraper...")
        sys.exit()

    if current_window == "console":
        load_console_menu()
    elif current_window == "roms":
        load_roms_menu()
    else:
        load_console_menu()


def load_console_menu() -> None:
    global selected_position, selected_system, current_window, skip_input_check, missing_media_cache, cached_storage_path

    storage_path = an.get_sd_storage_path()
    available_systems = scraper.get_available_systems(storage_path)

    # Rebuild cache if storage path changed
    if cached_storage_path != storage_path:
        rebuild_missing_media_cache()

    if available_systems:
        if input.key("DY"):
            selected_position += input.value
            if selected_position < 0:
                selected_position = len(available_systems) - 1
            elif selected_position >= len(available_systems):
                selected_position = 0
        elif input.key("A"):
            selected_system = available_systems[selected_position]
            current_window = "roms"
            gr.draw_log(
                f"{translator.translate('Checking existing media...')}", fill=gr.colorBlue, outline=gr.colorBlueD1
            )
            gr.draw_paint()
            skip_input_check = True
            return

    if input.key("Y"):
        an.switch_sd_storage()
        selected_position = 0
        available_systems = scraper.get_available_systems(an.get_sd_storage_path())
        rebuild_missing_media_cache()

    gr.draw_clear()

    gr.draw_rectangle_r([10, 40, x_size - 10, y_size - 40], 15, fill=gr.colorGrayD2, outline=None)
    gr.draw_text((x_size / 2, 20), f"{translator.translate('Tiny Scraper')}", font=17, anchor="mm")

    if len(available_systems) > 1:
        start_idx = int(selected_position / max_elem) * max_elem
        end_idx = start_idx + max_elem
        for i, system in enumerate(available_systems[start_idx:end_idx]):
            # Get cached missing media count
            missing_count, total_count = missing_media_cache.get(system, (0, 0))
            system_display = f"{system} (Missing {missing_count} / {total_count})"
            row_list(
                system_display, (20, 50 + (i * 35)), x_size - 40, i == (selected_position % max_elem)
            )
        button_circle((30, button_y), "A", f"{translator.translate('Select')}")
    else:
        gr.draw_text(
            (x_size / 2, y_size / 2), f"{translator.translate('No roms found in TF')} {an.get_sd_storage()}", anchor="mm"
        )

    button_circle((button_x-110, button_y), "Y", f"TF: {an.get_sd_storage()}")
    button_circle((button_x, button_y), "M", f"{translator.translate('Exit')}")

    gr.draw_paint()
    render_bottom_screen()


def load_roms_menu() -> None:
    global \
        selected_position, \
        current_window, \
        roms_selected_position, \
        skip_input_check, \
        selected_system

    exit_menu = False
    scraped = False
    roms_list = scraper.get_roms(an.get_sd_storage_path(), selected_system)
    system_path = Path(an.get_sd_storage_path()) / selected_system
    imgs_folder = Path(f"{an.get_sd_storage_path()}/{selected_system}/Imgs")

    if not imgs_folder.exists():
        imgs_folder.mkdir()
        imgs_files = set()
    else:
        imgs_files = set(scraper.get_image_files_without_extension(imgs_folder))

    roms_without_image = [rom for rom in roms_list if rom.name not in imgs_files]
    roms_without_image.sort(key=lambda x: x.name)

    system_id = get_system_id(selected_system)

    if len(roms_without_image) < 1:
        current_window = "console"
        selected_system = ""
        gr.draw_log(
            f"{translator.translate('No roms missing media found...')}", fill=gr.colorBlue, outline=gr.colorBlueD1
        )
        gr.draw_paint()
        time.sleep(2)
        gr.draw_clear()
        exit_menu = True

    if input.key("B"):
        exit_menu = True
    elif input.key("A"):
        gr.draw_log(f"{translator.translate('Scraping...')}", fill=gr.colorBlue, outline=gr.colorBlueD1)
        gr.draw_paint()
        rom = roms_without_image[roms_selected_position]
        rom.set_crc(scraper.get_crc32_from_file(system_path / rom.filename))
        
        screenshot = scrape_with_sources(
            rom.name, rom.crc, system_id, system_path / rom.filename, selected_system
        )
        
        if screenshot:
            img_path: Path = imgs_folder / f"{rom.name}.png"
            save_screenshot(img_path, screenshot)
            add_to_scrape_history(rom.name, img_path)
            gr.draw_log(
                f"{translator.translate('Scraping completed')}", fill=gr.colorBlue, outline=gr.colorBlueD1
            )
            print(f"Done scraping {rom.name}. Saved file to {img_path}")
        else:
            gr.draw_log(f"{translator.translate('Scraping failed!')}", fill=gr.colorBlue, outline=gr.colorBlueD1)
            print(f"Failed to get screenshot for {rom.name}")
        gr.draw_paint()
        time.sleep(3)
        scraped = True
        exit_menu = True
    elif input.key("START"):
        progress: int = 0
        success: int = 0
        failure: int = 0
        gr.draw_log(
            f"{translator.translate('Scraping')} {progress} {translator.translate('of')} {len(roms_without_image)}",
            fill=gr.colorBlue,
            outline=gr.colorBlueD1,
        )
        gr.draw_paint()
        
        # 根据首选数据源类型选择处理方式
        primary_source = scraper.preferred_sources[0] if scraper.preferred_sources else "libretro"
        
        if primary_source == "libretro":
            # libretro 数据源：使用多线程（最多3个线程）+ screenscraper 单线程回退
            roms_to_scrape = [rom for rom in roms_without_image if rom.name not in imgs_files]
            total_roms = len(roms_to_scrape)
            
            # 第一阶段：libretro 多线程并行处理
            failed_roms = []  # 收集 libretro 失败的 ROM
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                # 提交所有 libretro 刮削任务
                futures = {
                    executor.submit(
                        scrape_single_rom,
                        rom,
                        system_id,
                        system_path,
                        imgs_folder,
                        selected_system,
                        "libretro"
                    ): rom for rom in roms_to_scrape
                }
                
                # 处理完成的任务
                for future in concurrent.futures.as_completed(futures):
                    rom = futures[future]
                    rom_name, success_flag, img_path_str = future.result()
                    if success_flag:
                        success += 1
                        add_to_scrape_history(rom_name, Path(img_path_str))
                    else:
                        failed_roms.append(rom)
                        failure += 1
                    progress += 1
                    gr.draw_log(
                        f"{translator.translate('Scraping')} {progress} {translator.translate('of')} {total_roms}",
                        fill=gr.colorBlue,
                        outline=gr.colorBlueD1,
                    )
                    gr.draw_paint()
            
            # 第二阶段：screenscraper 单线程处理失败的 ROM（回退机制）
            if failed_roms and "screenscraper" in scraper.preferred_sources:
                print(f"Retrying {len(failed_roms)} ROM(s) with screenscraper...")
                # 显示第二阶段开始的提示
                gr.draw_log(
                    f"{translator.translate('Retrying')} {len(failed_roms)} {translator.translate('ROM(s) with screenscraper...')}",
                    fill=gr.colorYellow,
                    outline=gr.colorYellowD1,
                )
                gr.draw_paint()
                
                for i, rom in enumerate(failed_roms, 1):
                    rom.set_crc(scraper.get_crc32_from_file(system_path / rom.filename))
                    
                    # 使用 screenscraper 数据源（单线程）
                    screenshot: Optional[bytes] = scrape_with_sources(
                        rom.name, rom.crc, system_id, system_path / rom.filename, selected_system,
                        source_filter="screenscraper"
                    )
                    
                    if screenshot:
                        img_path: Path = imgs_folder / f"{rom.name}.png"
                        save_screenshot(img_path, screenshot)
                        add_to_scrape_history(rom.name, img_path)
                        print(f"Done scraping {rom.name} with screenscraper. Saved file to {img_path}")
                        success += 1
                        failure -= 1
                    else:
                        print(f"Failed to get screenshot for {rom.name} with screenscraper")
                    
                    # 更新第二阶段的进度显示
                    gr.draw_log(
                        f"{translator.translate('Retrying')} {i} {translator.translate('of')} {len(failed_roms)}",
                        fill=gr.colorYellow,
                        outline=gr.colorYellowD1,
                    )
                    gr.draw_paint()
        else:
            # screenscraper 数据源：保持单线程
            for rom in roms_without_image:
                if rom.name not in imgs_files:
                    rom.set_crc(scraper.get_crc32_from_file(system_path / rom.filename))
                    
                    screenshot: Optional[bytes] = scrape_with_sources(
                        rom.name, rom.crc, system_id, system_path / rom.filename, selected_system
                    )
                    
                    if screenshot:
                        img_path: Path = imgs_folder / f"{rom.name}.png"
                        save_screenshot(img_path, screenshot)
                        add_to_scrape_history(rom.name, img_path)
                        print(f"Done scraping {rom.name}. Saved file to {img_path}")
                        success += 1
                    else:
                        print(f"Failed to get screenshot for {rom.name}")
                        failure += 1
                    progress += 1
                    gr.draw_log(
                        f"{translator.translate('Scraping')} {progress} {translator.translate('of')} {len(roms_without_image)}",
                        fill=gr.colorBlue,
                        outline=gr.colorBlueD1,
                    )
                    gr.draw_paint()
        
        gr.draw_log(
            f"{translator.translate('Scraping completed! Success:')} {success} {translator.translate('Errors:')} {failure}",
            fill=gr.colorBlue,
            outline=gr.colorBlueD1,
            width=800,
        )
        gr.draw_paint()
        time.sleep(4)
        scraped = True
        exit_menu = True
    elif input.key("DY"):
        roms_selected_position += input.value
        if roms_selected_position < 0:
            roms_selected_position = len(roms_without_image) - 1
        elif roms_selected_position >= len(roms_without_image):
            roms_selected_position = 0
    elif input.key("L1"):
        if roms_selected_position > 0:
            roms_selected_position = max(0, roms_selected_position - max_elem)
    elif input.key("R1"):
        if roms_selected_position < len(roms_without_image) - 1:
            roms_selected_position = min(
                len(roms_without_image) - 1, roms_selected_position + max_elem
            )
    elif input.key("L2"):
        if roms_selected_position > 0:
            roms_selected_position = max(0, roms_selected_position - 100)
    elif input.key("R2"):
        if roms_selected_position < len(roms_without_image) - 1:
            roms_selected_position = min(
                len(roms_without_image) - 1, roms_selected_position + 100
            )

    if exit_menu:
        current_window = "console"
        selected_system = ""
        gr.draw_clear()
        roms_selected_position = 0
        skip_input_check = True
        if scraped:
            rebuild_missing_media_cache()
        return

    gr.draw_clear()

    gr.draw_rectangle_r([10, 40, x_size - 10, y_size - 40], 15, fill=gr.colorGrayD2, outline=None)
    gr.draw_text(
        (x_size / 2, 20),
        f"{selected_system} - {translator.translate('Roms:')} {len(roms_list)} {translator.translate('Missing media:')} {len(roms_without_image)}",
        anchor="mm",
    )

    start_idx = int(roms_selected_position / max_elem) * max_elem
    end_idx = start_idx + max_elem
    for i, rom in enumerate(roms_without_image[start_idx:end_idx]):
        row_list(
            rom.name[:48] + "..." if len(rom.name) > 50 else rom.name,
            (20, 50 + (i * 35)),
            x_size -40,
            i == (roms_selected_position % max_elem),
        )

    button_rectangle((20, button_y), "Start", f"{translator.translate('D. All')}")
    button_circle((190, button_y), "A", f"{translator.translate('Download')}")
    button_circle((320, button_y), "B", f"{translator.translate('Back')}")
    button_circle((button_x, button_y), "M", f"{translator.translate('Exit')}")

    gr.draw_paint()
    render_bottom_screen()

def scrape_with_sources(game_name: str, crc: str, system_id: int, rom_path: Path, system: str, source_filter: str = None) -> bytes | None:
    """根据配置的数据源优先级依次尝试获取截图
    
    Args:
        source_filter: 可选，限制只使用特定数据源（"libretro" 或 "screenscraper"）
                      为 None 时使用所有配置的数据源
    """
    print(f"{'='*60}")
    print(f"Scraping: {game_name}")
    print(f"CRC: {crc}")
    print(f"System: {system}")
    
    # 先将系统别名转换为规范名称
    aliases = load_platform_aliases()
    normalized_system = aliases.get(normalize_platform_alias(system), system)
    
    # 先从 merged_games.json 中查找游戏名称
    merged_game = find_merged_game_by_name(game_name, normalized_system)
    if merged_game:
        media_names = merged_game_media_names(merged_game)
        if media_names:
            search_name = media_names[0]
            print(f"[INFO] Found merged game: {game_name} -> {search_name}")
        else:
            search_name = game_name
    else:
        search_name = game_name
    
    available_sources = [s for s in scraper.preferred_sources if not source_filter or s == source_filter]
    print(f"[INFO] Sources to try: {available_sources}")
    
    for source in scraper.preferred_sources:
        if source_filter and source != source_filter:
            continue
            
        print(f"[TRY] {source.upper()} for '{search_name}'...")
        start_time = time.time()
        
        if source == "libretro":
            result = scrape_screenshot_from_thumbnail_matcher(search_name, rom_path, system, crc)
            elapsed = time.time() - start_time
            if result:
                screenshot, score = result
                if screenshot:
                    print(f"[OK] {source.upper()} succeeded in {elapsed:.1f}s (score: {score:.1f})")
                    return screenshot
                else:
                    print(f"[FAIL] {source.upper()} failed in {elapsed:.1f}s (score: {score:.1f})")
            else:
                print(f"[FAIL] {source.upper()} failed in {elapsed:.1f}s (score: 0.0)")
        elif source == "screenscraper":
            screenshot = scraper.scrape_screenshot(game_name=search_name, crc=crc, system_id=system_id)
            elapsed = time.time() - start_time
            if screenshot:
                print(f"[OK] {source.upper()} succeeded in {elapsed:.1f}s")
                return screenshot
            else:
                print(f"[FAIL] {source.upper()} failed in {elapsed:.1f}s")
        else:
            print(f"[SKIP] Unknown source: {source}")
    
    print(f"[END] All sources failed for {game_name}")
    print(f"{'='*60}")
    return None


def scrape_single_rom(rom, system_id, system_path, imgs_folder, selected_system, source_type) -> tuple[str, bool, str]:
    """单个ROM刮削处理函数，供多线程调用。返回 (rom_name, success, img_path_str)"""
    rom.set_crc(scraper.get_crc32_from_file(system_path / rom.filename))
    
    screenshot = scrape_with_sources(
        rom.name, rom.crc, system_id, system_path / rom.filename, selected_system,
        source_filter=source_type
    )
    
    with scrape_lock:
        if screenshot:
            img_path = imgs_folder / f"{rom.name}.png"
            save_screenshot(img_path, screenshot)
            print(f"Done scraping {rom.name}. Saved file to {img_path}")
            return (rom.name, True, str(img_path))
        else:
            print(f"Failed to get screenshot for {rom.name}")
            return (rom.name, False, "")

def scrape_screenshot_from_thumbnail_matcher(game_name: str, rom_path: Path, system: str, crc: str = "") -> tuple[bytes, float] | tuple[None, float]:
    """从 thumbnail_matcher 数据源获取截图，返回(图片bytes, 相似度分数)或(None, 分数)
    
    当提供 CRC 时，优先用 CRC 查 metadata（避免重复读取 ROM 文件，省去 SD 卡 I/O）。
    下载失败时自动重试最多 2 次（共 3 次尝试），递增等待 3s/6s。
    """
    try:
        # 第一阶段：CRC 优先查找（避免重复读取 ROM 文件，提速多线程）
        game_media = None
        if crc:
            try:
                game_media = find_media_by_crc(crc, system, min_score=0)
            except Exception:
                pass  # CRC 查找失败则回退到完整路径查找
        
        # 第二阶段：CRC 未命中时回退到完整路径查找（会读取 ROM 文件计算 CRC）
        if not game_media or not game_media.media:
            game_media = thumbnail_matcher.find_game_media(rom_path, system, min_score=0)
        
        # 获取最佳匹配分数（即使低于阈值也要显示分数）
        score = 0.0
        if game_media and game_media.media:
            score = game_media.media[0].score
        
        # 检查分数是否达到阈值
        if score < THUMBNAIL_DEF_SCORE:
            print(f"[MATCH] {game_media.media[0].name if game_media and game_media.media else game_name} (score: {score:.1f}) - Score below threshold ({THUMBNAIL_DEF_SCORE}), skipping download")
            return (None, score)
        
        if game_media and game_media.media:
            best_match = game_media.media[0]
            
            url = None
            for thumb_type in scraper.thumbnail_priority:
                if thumb_type in best_match.urls:
                    url = best_match.urls[thumb_type]
                    break
            
            if not url:
                print(f"[MATCH] {best_match.name} (score: {score:.1f}) - No suitable URL found")
                return (None, score)
            
            print(f"[MATCH] {best_match.name} (score: {score:.1f})")
            print(f"[URL] {url}")
            
            # 下载图片，最多重试 3 次（首次 + 2 次重试），递增等待 3s/6s
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            
            from urllib.request import Request, urlopen
            for attempt in range(3):
                try:
                    request = Request(url, headers={"User-Agent": "thumbnail-matcher/1.0"})
                    with urlopen(request, context=ctx, timeout=15) as response:
                        return (response.read(), score)
                except Exception as e:
                    if attempt < 2:
                        wait = (attempt + 1) * 3
                        print(f"[RETRY] Download attempt {attempt+1}/3 failed ({e}), retrying in {wait}s...")
                        time.sleep(wait)
                    else:
                        print(f"[ERROR] Download failed after 3 attempts: {e}")
            return (None, score)
        else:
            print(f"[INFO] No media found for {game_name} (best score: {score:.1f})")
            return (None, score)
    except Exception as e:
        print(f"[ERROR] thumbnail_matcher failed: {e}")
        return (None, 0.0)

def save_screenshot(img_path: Path, screenshot: bytes) -> None:
    if scraper.resize:
        print("Resizing image...")
        img = Image.open(BytesIO(screenshot))
        target_size = (320, 240)
        img = img.resize(target_size, Image.LANCZOS)
        img.save(img_path)
    else:
        img_path.write_bytes(screenshot)

def row_list(text: str, pos: tuple[int, int], width: int, selected: bool) -> None:
    gr.draw_rectangle_r(
        [pos[0], pos[1], pos[0] + width, pos[1] + 32],
        5,
        fill=(gr.colorBlue if selected else gr.colorGrayL1),
    )
    gr.draw_text((pos[0] + 5, pos[1] + 5), text)


def button_circle(pos: tuple[int, int], button: str, text: str) -> None:
    gr.draw_circle(pos, 25, fill=gr.colorBlueD1)
    gr.draw_text((pos[0] + 12, pos[1] + 12), button, anchor="mm")
    gr.draw_text((pos[0] + 30, pos[1] + 12), text, font=13, anchor="lm")


def button_rectangle(pos: tuple[int, int], button: str, text: str) -> None:
    gr.draw_rectangle_r(
        (pos[0], pos[1], pos[0] + 60, pos[1] + 25), 5, fill=gr.colorGrayL1
    )
    gr.draw_text((pos[0] + 30, pos[1] + 12), button, anchor="mm")
    gr.draw_text((pos[0] + 65, pos[1] + 12), text, font=13, anchor="lm")


def add_to_scrape_history(game_name: str, img_path: Path) -> None:
    """记录刮削成功的游戏到下屏历史 (最多保存8条, 循环覆盖)"""
    global scrape_history
    
    # 去重: 如果已存在同名记录，移除旧的
    scrape_history = [(n, p) for n, p in scrape_history if n != game_name]
    
    # 插入到最前面
    scrape_history.insert(0, (game_name, str(img_path)))
    
    # 只保留最新8条 (超出则循环覆盖)
    if len(scrape_history) > 8:
        scrape_history = scrape_history[:8]
    
    render_bottom_screen()


def render_bottom_screen() -> None:
    """渲染下屏: 2行×4列展示最近刮削的8个游戏封面+名称 (循环覆盖)"""
    if not gr.window2 or not gr.renderer2:
        return
    
    global scrape_history
    
    bw, bh = gr.screen_width, gr.screen_height  # 下屏尺寸 (通常640x480)
    
    # 创建下屏 PIL 图像
    img = Image.new("RGBA", (bw, bh), color=(20, 20, 20, 255))
    draw = ImageDraw.Draw(img)
    
    # 字体
    try:
        font_title = ImageFont.truetype(
            "/usr/share/fonts/source-han-sans-cn/SourceHanSansCN-Regular.otf", 18
        )
        font_name = ImageFont.truetype(
            "/usr/share/fonts/source-han-sans-cn/SourceHanSansCN-Regular.otf", 12
        )
        font_empty = ImageFont.truetype(
            "/usr/share/fonts/source-han-sans-cn/SourceHanSansCN-Regular.otf", 10
        )
    except:
        try:
            font_title = ImageFont.truetype("/usr/share/fonts/dejavu/DejaVuSansMono.ttf", 16)
            font_name = ImageFont.truetype("/usr/share/fonts/dejavu/DejaVuSansMono.ttf", 11)
            font_empty = ImageFont.truetype("/usr/share/fonts/dejavu/DejaVuSansMono.ttf", 9)
        except:
            font_title = font_name = font_empty = ImageFont.load_default()
    
    # 标题栏 (多语言)
    title = translator.translate("Recent Scrapes")
    title_text = f"★ {title}"
    draw.rectangle([0, 0, bw, 28], fill=(41, 41, 41, 255))
    bbox = draw.textbbox((0, 0), title_text, font=font_title)
    tw = bbox[2] - bbox[0]
    draw.text(((bw - tw) // 2, 4), title_text, fill="white", font=font_title)
    
    # 刮削计数
    subtitle = f"{len(scrape_history)} / 8"
    draw.text((bw - 45, 6), subtitle, fill=(150, 150, 150, 255), font=font_name)
    
    # 底部提示栏 (多语言)
    hint_y = bh - 24
    draw.rectangle([0, hint_y, bw, bh], fill=(41, 41, 41, 255))
    hint_text = translator.translate("Lower screen: recently scraped game previews")
    hb = draw.textbbox((0, 0), hint_text, font=font_empty)
    hw = hb[2] - hb[0]
    draw.text(((bw - hw) // 2, hint_y + 5), hint_text, fill=(150, 150, 150, 255), font=font_empty)
    
    # 2行×4列 槽位布局
    cols = 4
    rows = 2
    slot_w = 148       # 每个槽位宽度
    slot_h = 195       # 每个槽位高度 (含图片+名称)
    img_h = 145        # 缩略图区域高度
    gap_x = 12         # 水平间距
    gap_y = 8          # 垂直间距
    total_w = cols * slot_w + (cols - 1) * gap_x  # 4*148 + 3*12 = 628
    start_x = (bw - total_w) // 2
    start_y = 34       # 标题栏下方
    
    for idx in range(cols * rows):
        col = idx % cols
        row = idx // cols
        sx = start_x + col * (slot_w + gap_x)
        sy = start_y + row * (slot_h + gap_y)
        
        # 槽位背景
        draw.rounded_rectangle([sx, sy, sx + slot_w, sy + slot_h], 6,
                               fill=(41, 41, 41, 255), outline=(56, 56, 56, 255))
        
        if idx < len(scrape_history):
            game_name, img_path_str = scrape_history[idx]
            img_path = Path(img_path_str)
            
            # 加载并绘制缩略图
            try:
                if img_path.exists():
                    thumb = Image.open(img_path).convert("RGBA")
                    tw_orig, th_orig = thumb.size
                    scale = min((slot_w - 4) / tw_orig, img_h / th_orig, 1.0)
                    new_w = int(tw_orig * scale)
                    new_h = int(th_orig * scale)
                    thumb = thumb.resize((new_w, new_h), Image.LANCZOS)
                    
                    paste_x = sx + (slot_w - new_w) // 2
                    paste_y = sy + 3 + (img_h - new_h) // 2
                    img.paste(thumb, (paste_x, paste_y), thumb)
                else:
                    _draw_placeholder(draw, sx, sy, slot_w, img_h, font_empty)
            except Exception:
                _draw_placeholder(draw, sx, sy, slot_w, img_h, font_empty)
            
            # 游戏名称 (截断过长名称, 12号字体约17字符)
            name_display = game_name if len(game_name) <= 15 else game_name[:14] + "…"
            name_bbox = draw.textbbox((0, 0), name_display, font=font_name)
            nw = name_bbox[2] - name_bbox[0]
            draw.text((sx + (slot_w - nw) // 2, sy + img_h + 6),
                      name_display, fill="white", font=font_name)
        else:
            # 空槽位
            _draw_placeholder(draw, sx, sy, slot_w, img_h, font_empty)
            
            empty_text = "--"
            eb = draw.textbbox((0, 0), empty_text, font=font_name)
            ew = eb[2] - eb[0]
            draw.text((sx + (slot_w - ew) // 2, sy + img_h + 6),
                      empty_text, fill=(100, 100, 100, 255), font=font_name)
    
    # 保存并渲染到下屏
    gr.bottomImage = img
    gr.bottomDraw = ImageDraw.Draw(gr.bottomImage)
    gr.draw_paint_bottom()


def _draw_placeholder(draw, sx: int, sy: int, slot_w: int, img_h: int, font) -> None:
    """画空槽位占位符 (虚线框 + 问号)"""
    # 虚线边框效果: 用圆角矩形
    draw.rounded_rectangle(
        [sx + 8, sy + 4, sx + slot_w - 8, sy + 4 + img_h], 4,
        outline=(80, 80, 80, 255)
    )
    # 问号
    q_text = "?"
    qb = draw.textbbox((0, 0), q_text, font=font)
    qw = qb[2] - qb[0]
    qh = qb[3] - qb[1]
    draw.text((sx + (slot_w - qw) // 2, sy + 4 + (img_h - qh) // 2),
              q_text, fill=(100, 100, 100, 255), font=font)
