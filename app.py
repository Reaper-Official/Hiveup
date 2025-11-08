#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Benchmark Video Analyzer — Production-ready for Codespaces/Docker
- Multi-threaded download + processing pipeline
- Incremental save (JSON + CSV)
- Optional FastAPI server mode (if fastapi is installed)
- Tunable via env vars and CLI args
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import queue
import re
import shutil
import signal
import sys
import threading
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import yt_dlp
import cv2
import torch
import easyocr
import pandas as pd
from tqdm import tqdm

# Optional FastAPI server
try:
    from fastapi import FastAPI, BackgroundTasks
    from pydantic import BaseModel
    from uvicorn import run as uvicorn_run
    HAVE_FASTAPI = True
except Exception:
    HAVE_FASTAPI = False

# ------------------------- CONFIG -------------------------
BASE_DIR = Path(os.environ.get('WORKSPACE', '/workspace/Hiveup')).resolve()
TEMP_DIR = BASE_DIR / 'temp'
OUT_DIR = BASE_DIR / 'output'
LOG_DIR = BASE_DIR / 'logs'

for d in (TEMP_DIR, OUT_DIR, LOG_DIR):
    d.mkdir(parents=True, exist_ok=True)

OUTPUT_JSON = OUT_DIR / 'bench_results.json'
OUTPUT_CSV = OUT_DIR / 'bench_results.csv'

# Tunables (env or defaults)
MAX_VIDEOS_PER_GAME = int(os.environ.get('MAX_VIDEOS_PER_GAME', 5))
MAX_VIDEO_DURATION = float(os.environ.get('MAX_VIDEO_DURATION', 600))
FRAMES_PER_SECOND = float(os.environ.get('FRAMES_PER_SECOND', 1))
MAX_DOWNLOAD_THREADS = int(os.environ.get('MAX_DOWNLOAD_THREADS', 3))
MAX_PROCESS_THREADS = int(os.environ.get('MAX_PROCESS_THREADS', 2))
MAX_STORAGE_GB = float(os.environ.get('MAX_STORAGE_GB', 15))
YTDLP_RETRIES = int(os.environ.get('YTDLP_RETRIES', 2))
SAMPLE_MAX_FRAMES = int(os.environ.get('SAMPLE_MAX_FRAMES', 300))

DEVICE = 'cuda' if torch.cuda.is_available() else 'cpu'
OCR_LANGS = ['en']

# Logging (file + console)
logging.basicConfig(
    filename=str(LOG_DIR / 'app.log'),
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
console = logging.StreamHandler()
console.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
console.setFormatter(formatter)
logging.getLogger('').addHandler(console)

# ------------------------- UTIL -------------------------
def get_dir_size_gb(path: Path) -> float:
    try:
        total = sum(f.stat().st_size for f in path.rglob('*') if f.is_file())
        return total / (1024**3)
    except Exception:
        return 0.0

def ensure_storage_available() -> bool:
    """Return True if temp storage under configured threshold."""
    if get_dir_size_gb(TEMP_DIR) >= MAX_STORAGE_GB:
        logging.warning('TEMP storage exceeds limit (%.2fGB >= %.2fGB)', get_dir_size_gb(TEMP_DIR), MAX_STORAGE_GB)
        return False
    return True

# ------------------------- OCR & PARSING -------------------------
reader = easyocr.Reader(OCR_LANGS, gpu=torch.cuda.is_available(), verbose=False)

FPS_PATTERNS = [r'(\d{1,3}(?:\.\d+)?)\s*fps', r'fps[:\s]*(\d{1,3}(?:\.\d+)?)', r'(\d{2,3})\s*FPS']
RES_PATTERNS = [r'(\d{3,4})[x×](\d{3,4})', r'(\d{3,4})p']
GPU_PATTERNS = [r'(RTX\s*\d{3,4}(?:\s*Ti)?(?:\s*SUPER)?)', r'(GTX\s*\d{3,4}(?:\s*Ti)?)', r'(RX\s*\d{3,4}(?:\s*XT)?)']
CPU_PATTERNS = [r'(Intel\s*Core\s*i[3579]-?\d{3,5}[A-Z]*)', r'(AMD\s*Ryzen\s*[3579]\s*\d{3,5}[A-Z]*)']
RAM_PATTERN = r'(\d{1,3})\s*GB(?:\s*RAM)?'
SETTINGS_KEYWORDS = ['ultra', 'high', 'medium', 'low', 'maximum', 'epic']
API_KEYWORDS = ['directx 12', 'dx12', 'directx 11', 'dx11', 'vulkan']

def extract_all_data(text: str) -> dict:
    data = {"fps": None, "resolution": None, "gpu": None, "cpu": None, "ram": None, "settings": None, "api": None}
    if not text or len(text.strip()) < 2:
        return data

    # fps
    for p in FPS_PATTERNS:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            try:
                fps_val = float(m.group(1))
                if 5 <= fps_val <= 1000:
                    data['fps'] = fps_val
                    break
            except Exception:
                pass

    # resolution
    for p in RES_PATTERNS:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            if 'p' in p:
                h = m.group(1)
                if h == '1080': data['resolution'] = '1920x1080'
                elif h == '1440': data['resolution'] = '2560x1440'
                elif h in ['2160', '4k']: data['resolution'] = '3840x2160'
            else:
                data['resolution'] = f"{m.group(1)}x{m.group(2)}"
            break

    # gpu
    for p in GPU_PATTERNS:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            data['gpu'] = m.group(1).strip()
            break

    # cpu
    for p in CPU_PATTERNS:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            data['cpu'] = m.group(1).strip()
            break

    # ram
    m = re.search(RAM_PATTERN, text, re.IGNORECASE)
    if m:
        ram_val = int(m.group(1))
        if 2 <= ram_val <= 1024:
            data['ram'] = f"{ram_val}GB"

    # settings
    for kw in SETTINGS_KEYWORDS:
        if kw in text.lower():
            data['settings'] = kw.capitalize()
            break

    # api
    for api in API_KEYWORDS:
        if api in text.lower():
            data['api'] = api.upper().replace(' ', '').replace('DIRECTX', 'DX')
            break

    return data

def ocr_frame_full(frame) -> dict:
    h, w = frame.shape[:2]
    zones = {
        "top_left": frame[0:h//3, 0:w//3],
        "top_right": frame[0:h//3, 2*w//3:w],
        "bottom_left": frame[2*h//3:h, 0:w//3],
        "bottom_right": frame[2*h//3:h, 2*w//3:w],
    }

    all_data = []
    for zone_img in zones.values():
        try:
            result = reader.readtext(zone_img, detail=0)
            combined = " ".join(result)
            if combined.strip():
                data = extract_all_data(combined)
                all_data.append(data)
        except Exception:
            continue

    merged = {"fps": None, "resolution": None, "gpu": None, "cpu": None, "ram": None, "settings": None, "api": None}
    for key in merged.keys():
        values = [d[key] for d in all_data if d.get(key) is not None]
        if values:
            if key == "fps":
                merged[key] = values[0]
            else:
                merged[key] = Counter(values).most_common(1)[0][0]
    return merged

# ------------------------- VIDEO PROCESSING -------------------------
def process_video(video_path: Path, game_name: str, video_url: str) -> Optional[dict]:
    try:
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            logging.error('Cannot open video %s', video_path)
            return None

        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        video_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        duration = frame_count / video_fps if video_fps > 0 else 0

        if duration > MAX_VIDEO_DURATION:
            logging.info('Skipping long video: %s (%.0fs)', video_path.name, duration)
            cap.release()
            return None

        fps_values = []
        resolutions = []
        gpus = []
        cpus = []
        rams = []
        settings = []
        apis = []

        sample_interval = max(1, int(video_fps // FRAMES_PER_SECOND))
        frames_to_process = list(range(0, frame_count, sample_interval))

        if len(frames_to_process) > SAMPLE_MAX_FRAMES:
            step = max(1, len(frames_to_process) // SAMPLE_MAX_FRAMES)
            frames_to_process = frames_to_process[::step]

        for idx in tqdm(frames_to_process, desc=f"[OCR] {game_name[:25]}", leave=False):
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ret, frame = cap.read()
            if not ret:
                continue

            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            data = ocr_frame_full(frame_rgb)

            if data["fps"]: fps_values.append(data["fps"])
            if data["resolution"]: resolutions.append(data["resolution"])
            if data["gpu"]: gpus.append(data["gpu"])
            if data["cpu"]: cpus.append(data["cpu"])
            if data["ram"]: rams.append(data["ram"])
            if data["settings"]: settings.append(data["settings"])
            if data["api"]: apis.append(data["api"])

        cap.release()

        if len(fps_values) < 5:
            logging.warning('Insufficient FPS samples (%d) in %s', len(fps_values), video_path.name)
            return None

        fps_sorted = sorted(fps_values)
        result = {
            "game": game_name,
            "video_url": video_url,
            "duration_seconds": round(duration, 2),
            "frames_analyzed": len(frames_to_process),
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "fps": {
                "avg": round(sum(fps_values)/len(fps_values), 2),
                "min": round(min(fps_values), 2),
                "max": round(max(fps_values), 2),
                "1_percent_low": round(fps_sorted[max(0, len(fps_sorted)//100)], 2) if len(fps_sorted) > 10 else None,
                "samples": len(fps_values)
            },
            "resolution": Counter(resolutions).most_common(1)[0][0] if resolutions else None,
            "gpu": Counter(gpus).most_common(1)[0][0] if gpus else None,
            "cpu": Counter(cpus).most_common(1)[0][0] if cpus else None,
            "ram": Counter(rams).most_common(1)[0][0] if rams else None,
            "settings": Counter(settings).most_common(1)[0][0] if settings else None,
            "api": Counter(apis).most_common(1)[0][0] if apis else None
        }
        return result

    except Exception:
        logging.exception('Error processing video %s', video_path)
        return None

# ------------------------- DOWNLOAD -------------------------
def download_video(youtube_url: str, outdir: Path, retries: int = YTDLP_RETRIES) -> Optional[Path]:
    if not ensure_storage_available():
        logging.error('No storage available to download %s', youtube_url)
        return None

    ydl_opts = {
        "outtmpl": str(outdir / "%(id)s.%(ext)s"),
        "format": "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/best",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "ignoreerrors": True,
        "concurrent_fragment_downloads": 3
    }

    attempt = 0
    while attempt <= retries:
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(youtube_url, download=True)
                if info:
                    filename = ydl.prepare_filename(info)
                    return Path(filename)
        except Exception as e:
            logging.warning('yt-dlp download failed (attempt %d/%d) for %s: %s', attempt+1, retries+1, youtube_url, e)
            attempt += 1
            time.sleep(1 + attempt*2)
    return None

# ------------------------- SEARCH -------------------------
def search_youtube(query: str, max_results: int = 5) -> List[str]:
    urls: List[str] = []
    search_query = f"ytsearch{max_results}:{query}"
    ydl_opts = {"quiet": True, "no_warnings": True, "ignoreerrors": True}
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(search_query, download=False)
            if info and 'entries' in info:
                for entry in info['entries']:
                    if entry and 'id' in entry:
                        urls.append(f"https://www.youtube.com/watch?v={entry['id']}")
    except Exception:
        logging.exception('search_youtube error for query: %s', query)
    return urls

# ------------------------- PIPELINE -------------------------
download_queue = queue.Queue()
process_queue = queue.Queue()
results = []
results_lock = threading.Lock()
stop_event = threading.Event()

def download_worker(name: str):
    logging.info('Download worker %s started', name)
    while not stop_event.is_set():
        try:
            game_name, url = download_queue.get(timeout=3)
        except queue.Empty:
            break
        try:
            logging.info('[DL] %s -> %s', game_name, url)
            video_file = download_video(url, TEMP_DIR)
            if video_file and video_file.exists():
                logging.info('[OK-DL] %s (%.1fMB)', video_file.name, video_file.stat().st_size / (1024**2))
                process_queue.put((game_name, url, video_file))
            else:
                logging.warning('[SKIP-DL] failed to download %s', url)
        finally:
            download_queue.task_done()
    logging.info('Download worker %s exiting', name)

def process_worker(name: str):
    logging.info('Process worker %s started', name)
    while not stop_event.is_set():
        try:
            item = process_queue.get(timeout=5)
        except queue.Empty:
            break
        game_name, url, video_file = item
        try:
            logging.info('[PROCESS] %s', video_file.name)
            data = process_video(video_file, game_name, url)
            if data and data.get('fps', {}).get('avg'):
                with results_lock:
                    results.append(data)
                    try:
                        with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
                            json.dump(results, f, indent=2, ensure_ascii=False)
                        logging.info('[SAVE] %d results', len(results))
                    except Exception:
                        logging.exception('Failed incremental save')
                logging.info('[OK-PROC] %s | FPS: %.1f | Res: %s | GPU: %s', game_name[:25], data['fps']['avg'], data['resolution'], data['gpu'] or 'N/A')
            else:
                logging.info('[SKIP] insufficient data for %s', game_name)
        except Exception:
            logging.exception('Processing error')
        finally:
            try:
                if video_file.exists():
                    video_file.unlink()
                    logging.info('[DEL] %s', video_file.name)
            except Exception:
                logging.exception('Failed deleting file')
            process_queue.task_done()
    logging.info('Process worker %s exiting', name)

# ------------------------- EXPORT -------------------------
def export_results():
    try:
        if results:
            with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
            df = pd.json_normalize(results)
            df.to_csv(OUTPUT_CSV, index=False, encoding='utf-8-sig')

            avg_fps = sum(r['fps']['avg'] for r in results if r['fps']['avg']) / max(1, len([r for r in results if r['fps']['avg']]))
            total_samples = sum(r['fps']['samples'] for r in results if r['fps']['samples'])
            unique_games = len(set(r['game'] for r in results))
            logging.info('Exported %d results | Games: %d | Avg FPS: %.1f | Samples: %d', len(results), unique_games, avg_fps, total_samples)
        else:
            logging.warning('No results to export')
    except Exception:
        logging.exception('Export failed')

# ------------------------- CLEANUP -------------------------
def cleanup_temp():
    try:
        for f in TEMP_DIR.glob('*'):
            try:
                if f.is_file():
                    f.unlink()
            except Exception:
                logging.exception('Cleanup: cannot remove %s', f)
        logging.info('Temp cleaned')
    except Exception:
        logging.exception('Cleanup failed')

# ------------------------- MAIN / ENTRY -------------------------
def run_pipeline(games: List[str], keywords: List[str], max_videos_per_game: int = MAX_VIDEOS_PER_GAME):
    total = 0
    for game in games:
        count = 0
        for kw in keywords:
            if count >= max_videos_per_game: break
            urls = search_youtube(f"{game} {kw}", max_results=2)
            for u in urls:
                if count >= max_videos_per_game: break
                download_queue.put((game, u))
                count += 1
                total += 1
            time.sleep(0.2)
        logging.info('%s -> %d videos queued', game, count)

    logging.info('Total queued: %d', total)

    # start process workers first
    proc_threads = []
    for i in range(MAX_PROCESS_THREADS):
        t = threading.Thread(target=process_worker, args=(f'P{i+1}',), daemon=True)
        t.start(); proc_threads.append(t)

    dl_threads = []
    for i in range(MAX_DOWNLOAD_THREADS):
        t = threading.Thread(target=download_worker, args=(f'DL{i+1}',), daemon=True)
        t.start(); dl_threads.append(t)

    # wait
    download_queue.join()
    logging.info('Download queue completed')
    process_queue.join()
    logging.info('Process queue completed')

    time.sleep(0.5)
    export_results()
    cleanup_temp()

# Optional FastAPI endpoints
if HAVE_FASTAPI:
    app = FastAPI(title='Benchmark Video Analyzer')

    class RunRequest(BaseModel):
        games: List[str]
        keywords: Optional[List[str]] = None

    @app.post('/run')
    def run_request(req: RunRequest, background: BackgroundTasks):
        k = req.keywords or ['benchmark', 'fps test', 'performance test']
        background.add_task(run_pipeline, req.games, k)
        return {'status': 'started', 'games': len(req.games)}

# Signals
def handle_signal(sig, frame):
    logging.info('Received signal %s, shutting down...', sig)
    stop_event.set()

signal.signal(signal.SIGINT, handle_signal)
signal.signal(signal.SIGTERM, handle_signal)

def load_games_from_file(path: Path) -> List[str]:
    if not path.exists():
        return []
    return [line.strip() for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=['cli', 'server'], default='cli')
    parser.add_argument('--games-file', type=str, default=None)
    parser.add_argument('--max-videos', type=int, default=MAX_VIDEOS_PER_GAME)
    parser.add_argument('--download-threads', type=int, default=MAX_DOWNLOAD_THREADS)
    parser.add_argument('--process-threads', type=int, default=MAX_PROCESS_THREADS)
    args = parser.parse_args()
    MAX_DOWNLOAD_THREADS = args.download_threads
    MAX_PROCESS_THREADS = args.process_threads

    if args.mode == 'server':
        if not HAVE_FASTAPI:
            logging.error('FastAPI not available. Install fastapi[all] to enable server mode.')
            sys.exit(1)
        logging.info('Starting server on 0.0.0.0:8000')
        uvicorn_run('app:app', host='0.0.0.0', port=8000, log_level='info')
        return

    if args.games_file:
        games = load_games_from_file(Path(args.games_file))
    else:
        games = [
            'Cyberpunk 2077', 'Red Dead Redemption 2', 'Elden Ring', 'GTA V', 'Forza Horizon 5',
        ]

    keywords = ['benchmark', 'fps test', 'performance test']

    logging.info('Starting pipeline: %d DL threads, %d PROC threads, device=%s', MAX_DOWNLOAD_THREADS, MAX_PROCESS_THREADS, DEVICE)
    run_pipeline(games, keywords, max_videos_per_game=args.max_videos)

if __name__ == '__main__':
    main()
