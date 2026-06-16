# Tiny Scraper

> A fork of [Julioevm/tiny-scraper](https://github.com/Julioevm/tiny-scraper) with enhanced features.

---

## Added Features

- **Libretro Data Source Support**: Added Libretro Thumbnails as a data source, supporting fetching game covers from locally cached thumbnail library
- **Multi-Source Automatic Fallback**: Supports configuring multiple data sources, prioritizes Libretro, automatically falls back to Screenscraper on failure
- **Multi-Threaded Scraping**: Libretro data source supports multi-threaded parallel scraping (up to 3 threads), significantly improving scraping speed
- **Smart Game Name Matching**: Intelligent mapping from Chinese game names to English names via merged_games.json
- **Detailed Scraping Logs**: Prints detailed logs during each scrape, including data source, time spent, success/failure status
- **Startup Log Clear**: Automatically clears log file on program startup, avoiding accumulation of old logs
- **Network Retry Mechanism**: Automatically retries on temporary network errors (DNS failure, timeout, etc.), up to 3 attempts


---

## Platform

![Platform](https://img.shields.io/badge/platform-Anbernic-orange.svg)

## Features

- **Easy Downloads:** Download cover media directly onto your Anbernic device.
- **User-Friendly Interface:** Simple and intuitive interface designed specifically for Anbernic devices.
- **Wide Compatibility:** Supports various ROM file types and multiple Anbernic models.

## Supported Devices

Personally tested: **RG35XX H**

Theoretically supported: RG40XXV, RGcubeXX, RG28xx

Possibly compatible: Any Anbernic handheld with Python >= 3.7

## Installation

1. **Download Latest Release:**
   - Navigate to the [Releases](https://github.com/Julioevm/tiny-scraper/releases) page and download the latest version.

2. **Transfer to Device:**
   - Extract and copy the content of the downloaded zip to the `APPS` directory of your Anbernic.
   - SD2: `/mnt/sdcard/Roms/APPS`
   - SD1: `/mnt/mmc/Roms/APPS`

3. **Setup config.json:**
   Create a `config.json` file inside the `tiny_scraper` folder:

```json
{
    "user": "your_user",
    "password": "your_password",
    "media_type": "sstitle",
    "region": "wor",
    "resize": false,
    "preferred_sources": ["libretro", "screenscraper"]
}
```

**Configuration Details:**

| Parameter | Description |
|-----------|-------------|
| `user` / `password` | Your account registered at [screenscraper.fr](https://www.screenscraper.fr) |
| `media_type` | Media type: `ss` (screenshot), `sstitle` (title screen), `box-2D`/`box-3D` (box art), `mixrbv1`/`mixrbv2` (mixed) |
| `region` | Region priority: `wor`, `jp`, `eu`, `asi`, `kr`, `ss`, `us` |
| `resize` | `true`/`false` - Resize to 320x240 |
| `preferred_sources` | Data source priority: `libretro` (local cache), `screenscraper` (online) |

4. **Start Tiny Scraper:**
   From the main menu, go to App Center, select Apps and launch Tiny Scraper.

## Data Source Description

This program supports two data sources:

### Libretro Thumbnails

- **Advantages**: Fast (multi-threaded), no network required, stable quality
- **Disadvantages**: Requires downloading thumbnail library in advance, some games may be missing

### Screenscraper

- **Advantages**: Rich resources, covering almost all games
- **Disadvantages**: Slower (single-threaded), requires account, requires network

## Troubleshooting

Old version of stock OS might cause issues. V 1.0.3 (20240511) is reported to miss some necessary libraries: No module named 'PIL'. Try to update in this case.

Any issue should be logged in the `tiny_scraper/log.txt` file.

---

## Original Project

[Julioevm/tiny-scraper](https://github.com/Julioevm/tiny-scraper)
