import json
import requests
import os

# 平台标识: 接口目录名
PLATFORM_INFO = [
    ("fc", "fc"),
    ("n64", "n64"),
    ("md", "md"),
    ("mdcd", "mdcd"),
    ("ss", "ss"),
    ("dc", "dc"),
    ("photocd", "photocd"),
    ("pcecd", "pcecd"),
    ("pcfx", "pcfx"),
    ("3do", "3do"),
    ("gba", "gba"),
    ("nds", "nds"),
    ("3ds", "3ds"),
    ("psp", "psp"),
    ("psv_all", "psvall"),
    ("psv_dlc", "psvdlc")
]

BASE_URL = "http://emu.jy6d.com/dz/{dir_name}/{file_name}.json"
OUTPUT_DIR = "./game_maps"

def fetch_single_plat(plat_tag: str, dir_name: str):
    url = BASE_URL.format(dir_name=dir_name, file_name=plat_tag)
    print(f"正在抓取: {url}")

    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        game_list = resp.json()
    except Exception as e:
        print(f"❌ 抓取失败 {plat_tag}：{str(e)}")
        return None

    # 不做任何名称清理，原样保存
    name_map = {}
    for item in game_list:
        cn_name = item.get("ch_name", "")
        en_name = item.get("game_name", "")
        if cn_name and en_name:
            name_map[cn_name] = en_name

    # 保存单平台独立文件
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    out_file = os.path.join(OUTPUT_DIR, f"zh2en_{plat_tag}.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(name_map, f, ensure_ascii=False, indent=2)

    print(f"✅ {plat_tag} 完成，共 {len(name_map)} 条映射\n")
    return plat_tag, name_map

def merge_all_map():
    """合并为嵌套结构总表：{平台: {中文: 英文}}"""
    full_mapping = {}
    for plat_tag, _ in PLATFORM_INFO:
        file_path = os.path.join(OUTPUT_DIR, f"zh2en_{plat_tag}.json")
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                full_mapping[plat_tag] = json.load(f)

    total_file = os.path.join(OUTPUT_DIR, "zh2en_ALL_nested.json")
    with open(total_file, "w", encoding="utf-8") as f:
        json.dump(full_mapping, f, ensure_ascii=False, indent=2)

    # 统计总条数
    total_cnt = sum(len(v) for v in full_mapping.values())
    print(f"🎉 嵌套格式总表生成完成，总计 {total_cnt} 条映射 → zh2en_ALL_nested.json")

if __name__ == "__main__":
    print("=== 开始批量抓取游戏中英文映射表 ===\n")
    for plat_tag, dir_name in PLATFORM_INFO:
        fetch_single_plat(plat_tag, dir_name)
    
    merge_all_map()
    print("\n=== 全部任务执行完毕 ===")