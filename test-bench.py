#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Benchmark Video Analyzer - Extracteur de donnees de performance gaming
Version sans emojis pour compatibilite Windows
"""

import os
import sys

# Force UTF-8 pour eviter les problemes d'encodage
try:
    import io
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

except:
    pass

# Supprimer TOUS les warnings avant imports
import warnings
warnings.filterwarnings("ignore")
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
os.environ['PYTHONWARNINGS'] = 'ignore'
os.environ['PYTHONIOENCODING'] = 'utf-8'

print("[INIT] Chargement des modules...")

# Imports standards
try:
    import re
    import json
    import shutil
    import queue
    import threading
    import tempfile
    from pathlib import Path
    from time import sleep
    from collections import Counter
    from datetime import datetime
    print("  [OK] Modules standards")
except Exception as e:
    print(f"  [ERREUR] Modules standards: {e}")
    sys.exit(1)

# tqdm
try:
    from tqdm import tqdm
    print("  [OK] tqdm")
except Exception as e:
    print(f"  [ERREUR] pip install tqdm")
    sys.exit(1)

# yt_dlp
try:
    import yt_dlp
    print("  [OK] yt_dlp")
except Exception as e:
    print(f"  [ERREUR] pip install yt-dlp")
    sys.exit(1)

# cv2
try:
    import cv2
    print(f"  [OK] cv2 v{cv2.__version__}")
except Exception as e:
    print(f"  [ERREUR] cv2: {e}")
    print(f"  [FIX] pip install opencv-python")
    sys.exit(1)

# torch
try:
    import torch
    print(f"  [OK] torch v{torch.__version__}")
except Exception as e:
    print(f"  [ERREUR] torch: {e}")
    print(f"  [FIX] pip install torch")
    sys.exit(1)

# easyocr
try:
    import easyocr
    print("  [OK] easyocr")
except Exception as e:
    print(f"  [ERREUR] easyocr: {e}")
    print(f"  [FIX] pip install easyocr")
    sys.exit(1)

# pandas
try:
    import pandas as pd
    print("  [OK] pandas")
except Exception as e:
    print(f"  [ERREUR] pip install pandas")
    sys.exit(1)

print("[OK] Tous les modules charges!\n")

# ------------------- CONFIG -------------------
GAMES = [
    "Cyberpunk 2077", "Red Dead Redemption 2", "Shadow of the Tomb Raider",
    "The Witcher 3", "Assassin's Creed Valhalla", "Call of Duty Modern Warfare",
    "Battlefield 2042", "GTA V", "Forza Horizon 5", "Microsoft Flight Simulator",
    "God of War", "Elden Ring", "Hogwarts Legacy", "Starfield", "Spider-Man",
    "The Last of Us", "Horizon Forbidden West", "Final Fantasy XVI",
    "Resident Evil 4 Remake", "Dead Space Remake", "Alan Wake 2",
    "Counter-Strike 2", "Valorant", "Apex Legends", "Overwatch 2",
    "League of Legends", "Dota 2", "Fortnite", "PUBG", "Warzone 2",
    "Minecraft", "Roblox", "Palworld", "Baldur's Gate 3", "Diablo IV",
    "Path of Exile", "Lost Ark", "Black Myth Wukong", "Lies of P",
    "Armored Core VI", "Street Fighter 6", "Mortal Kombat 1",
    "Tekken 8", "Dragon's Dogma 2", "Sons of the Forest",
    "Atomic Heart", "Dead Island 2", "Remnant 2", "Lords of the Fallen",
    "Robocop Rogue City", "Avatar Frontiers of Pandora"
]

KEYWORDS = ["benchmark", "fps test", "performance test"]
FRAMES_PER_SECOND = 1
MAX_STORAGE_GB = 90  # 90GB sur disque E
MAX_DOWNLOAD_THREADS = 3  # Plus de threads pour download
MAX_PROCESS_THREADS = 2  # Plus de threads pour traitement parallele
MAX_VIDEOS_PER_GAME = 5  # Plus de videos par jeu
MAX_VIDEO_DURATION = 600

OUTPUT_DIR = Path("E:/benchs/output")
OUTPUT_DIR.mkdir(exist_ok=True, parents=True)
OUTPUT_JSON = OUTPUT_DIR / "bench_results.json"
OUTPUT_CSV = OUTPUT_DIR / "bench_results.csv"

# Dossier temp sur E: au lieu de C:
TEMP_DIR = Path("E:/benchs/temp")
TEMP_DIR.mkdir(exist_ok=True, parents=True)

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
OCR_LANGS = ['en']

print(f"[CONFIG] Dossier sortie: {OUTPUT_DIR}")
print(f"[CONFIG] Dossier temp: {TEMP_DIR}")
print(f"[CONFIG] Device: {DEVICE}")
print(f"[CONFIG] Stockage max: {MAX_STORAGE_GB}GB sur E:")
print(f"[CONFIG] Jeux: {len(GAMES)}")
print(f"[CONFIG] Max videos/jeu: {MAX_VIDEOS_PER_GAME}")
print(f"[CONFIG] Threads DL: {MAX_DOWNLOAD_THREADS} | Process: {MAX_PROCESS_THREADS}")
print(f"[CONFIG] Pipeline: Traitement immediat des videos telechargees\n")

# ------------------- UTILITAIRES -------------------
def get_dir_size_gb(path):
    """Calcule la taille d'un dossier en GB"""
    try:
        total = sum(f.stat().st_size for f in Path(path).rglob('*') if f.is_file())
        return total / (1024**3)
    except:
        return 0

def wait_for_storage_space():
    """Attend qu'il y ait de l'espace disponible"""
    while get_dir_size_gb(TEMP_DIR) >= MAX_STORAGE_GB:
        print(f"[WARN] Stockage plein ({get_dir_size_gb(TEMP_DIR):.2f}GB/{MAX_STORAGE_GB}GB). En attente...")
        sleep(5)

# ------------------- EXTRACTION DONNEES -------------------
def extract_all_data(text):
    """Extrait toutes les donnees possibles du texte OCR"""
    data = {
        "fps": None, "resolution": None, "gpu": None, "cpu": None,
        "ram": None, "settings": None, "api": None
    }
    
    if not text or len(text) < 2:
        return data
    
    # FPS
    for pattern in [r'(\d{1,3}(?:\.\d+)?)\s*fps', r'fps[:\s]*(\d{1,3}(?:\.\d+)?)', r'(\d{2,3})\s*FPS']:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            fps_val = float(match.group(1))
            if 10 <= fps_val <= 500:
                data["fps"] = fps_val
                break
    
    # Resolution
    for pattern in [r'(\d{3,4})[x×](\d{3,4})', r'(\d{3,4})p']:
        match = re.search(pattern, text)
        if match:
            if 'p' in pattern:
                height = match.group(1)
                if height == '1080': data["resolution"] = "1920x1080"
                elif height == '1440': data["resolution"] = "2560x1440"
                elif height in ['2160', '4k']: data["resolution"] = "3840x2160"
            else:
                data["resolution"] = f"{match.group(1)}x{match.group(2)}"
            break
    
    # GPU
    for pattern in [r'(RTX\s*\d{4}(?:\s*Ti)?(?:\s*SUPER)?)', r'(GTX\s*\d{4}(?:\s*Ti)?)', r'(RX\s*\d{4}\s*XT)']:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            data["gpu"] = match.group(1).strip()
            break
    
    # CPU
    for pattern in [r'(Intel\s*Core\s*i[3579]-?\d{4,5}[A-Z]*)', r'(AMD\s*Ryzen\s*[3579]\s*\d{4}[A-Z]*)']:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            data["cpu"] = match.group(1).strip()
            break
    
    # RAM
    ram_match = re.search(r'(\d{1,3})\s*GB(?:\s*RAM)?', text, re.IGNORECASE)
    if ram_match:
        ram_val = int(ram_match.group(1))
        if 4 <= ram_val <= 256:
            data["ram"] = f"{ram_val}GB"
    
    # Settings
    for keyword in ['ultra', 'high', 'medium', 'low', 'maximum', 'epic']:
        if keyword in text.lower():
            data["settings"] = keyword.capitalize()
            break
    
    # API
    for api in ['directx 12', 'dx12', 'directx 11', 'dx11', 'vulkan']:
        if api in text.lower():
            data["api"] = api.upper().replace(' ', '').replace('DIRECTX', 'DX')
            break
    
    return data

# ------------------- OCR -------------------
print("[INIT] Chargement EasyOCR...")
try:
    reader = easyocr.Reader(OCR_LANGS, gpu=torch.cuda.is_available(), verbose=False)
    print("[OK] EasyOCR charge\n")
except Exception as e:
    print(f"[ERREUR] EasyOCR: {e}")
    sys.exit(1)

def ocr_frame_full(frame):
    """OCR sur zones strategiques"""
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
        except:
            continue
    
    # Fusion
    merged = {"fps": None, "resolution": None, "gpu": None, "cpu": None, "ram": None, "settings": None, "api": None}
    for key in merged.keys():
        values = [d[key] for d in all_data if d[key] is not None]
        if values:
            if key == "fps":
                merged[key] = values[0]
            else:
                counter = Counter(values)
                if counter:
                    merged[key] = counter.most_common(1)[0][0]
    return merged

# ------------------- TRAITEMENT VIDEO -------------------
def process_video(video_path, game_name, video_url):
    """Traite une video et extrait les donnees"""
    try:
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            print(f"[ERREUR] Ouverture video: {video_path}")
            return None
        
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        video_fps = cap.get(cv2.CAP_PROP_FPS) or 30
        duration = frame_count / video_fps
        
        if duration > MAX_VIDEO_DURATION:
            print(f"[SKIP] Video trop longue ({duration:.0f}s)")
            cap.release()
            return None
        
        fps_values = []
        resolutions = []
        gpus = []
        cpus = []
        rams = []
        settings = []
        apis = []
        
        sample_interval = int(video_fps / FRAMES_PER_SECOND)
        frames_to_process = list(range(0, frame_count, sample_interval))
        
        if len(frames_to_process) > 300:
            frames_to_process = frames_to_process[::len(frames_to_process)//300]
        
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
            print(f"[WARN] Donnees insuffisantes ({len(fps_values)} FPS)")
            return None
        
        result = {
            "game": game_name,
            "video_url": video_url,
            "duration_seconds": round(duration, 2),
            "frames_analyzed": len(frames_to_process),
            "timestamp": datetime.now().isoformat(),
            "fps": {
                "avg": round(sum(fps_values)/len(fps_values), 2),
                "min": round(min(fps_values), 2),
                "max": round(max(fps_values), 2),
                "1_percent_low": round(sorted(fps_values)[max(0, len(fps_values)//100)], 2) if len(fps_values) > 10 else None,
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
    except Exception as e:
        print(f"[ERREUR] Traitement: {e}")
        return None

# ------------------- DOWNLOAD -------------------
def download_video(youtube_url, outdir):
    wait_for_storage_space()
    ydl_opts = {
        "outtmpl": str(outdir / "%(id)s.%(ext)s"),
        "format": "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/best",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "ignoreerrors": True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(youtube_url, download=True)
            if info:
                return Path(ydl.prepare_filename(info))
    except:
        return None

# ------------------- YOUTUBE SEARCH -------------------
def search_youtube(query, max_results=5):
    urls = []
    search_query = f"ytsearch{max_results}:{query}"
    ydl_opts = {"quiet": True, "no_warnings": True, "ignoreerrors": True}
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(search_query, download=False)
            if info and 'entries' in info:
                for entry in info['entries']:
                    if entry and 'id' in entry:
                        urls.append(f"https://www.youtube.com/watch?v={entry['id']}")
    except:
        pass
    return urls

# ------------------- PIPELINE -------------------
download_queue = queue.Queue()
process_queue = queue.Queue()
results = []
results_lock = threading.Lock()

def download_worker():
    """Thread de telechargement - envoie immediatement au traitement"""
    while True:
        try:
            item = download_queue.get(timeout=10)
        except queue.Empty:
            break
        game_name, url = item
        video_file = None
        try:
            print(f"[DL] {game_name[:30]} - {url[:50]}")
            video_file = download_video(url, TEMP_DIR)
            if video_file and video_file.exists():
                file_size_mb = video_file.stat().st_size / (1024**2)
                print(f"[OK-DL] {video_file.name} ({file_size_mb:.1f}MB)")
                # Envoi immediat au traitement (pas d'attente)
                process_queue.put((game_name, url, video_file))
            else:
                print(f"[SKIP] Download echoue: {url[:50]}")
        except Exception as e:
            print(f"[ERR-DL] {e}")
            if video_file and video_file.exists():
                try:
                    video_file.unlink()
                except:
                    pass
        finally:
            download_queue.task_done()

def process_worker():
    """Thread de traitement - traite des que video disponible"""
    while True:
        try:
            item = process_queue.get(timeout=20)
        except queue.Empty:
            break
        game_name, url, video_file = item
        try:
            file_size_mb = video_file.stat().st_size / (1024**2)
            print(f"[PROCESS] {video_file.name} ({file_size_mb:.1f}MB)")
            data = process_video(video_file, game_name, url)
            
            if data and data["fps"]["avg"]:
                with results_lock:
                    results.append(data)
                    # Sauvegarde incrementale
                    try:
                        with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
                            json.dump(results, f, indent=2, ensure_ascii=False)
                        print(f"[SAVE] {len(results)} resultats sauvegardes")
                    except Exception as e:
                        print(f"[WARN] Sauvegarde: {e}")
                
                print(f"[OK-PROC] {game_name[:25]} | FPS:{data['fps']['avg']:.1f} | Res:{data['resolution']} | GPU:{data['gpu'] or 'N/A'}")
            else:
                print(f"[SKIP] Donnees insuffisantes: {game_name[:30]}")
        except Exception as e:
            print(f"[ERR-PROC] {e}")
        finally:
            # Suppression immediate apres traitement
            try:
                if video_file and video_file.exists():
                    video_file.unlink()
                    print(f"[DEL] {video_file.name}")
            except Exception as e:
                print(f"[WARN] Suppression: {e}")
            process_queue.task_done()

# ------------------- MAIN -------------------
print(f"[SEARCH] Recherche videos pour {len(GAMES)} jeux...\n")
video_count = 0

for i, game in enumerate(GAMES, 1):
    print(f"[{i}/{len(GAMES)}] {game}")
    game_video_count = 0
    for keyword in KEYWORDS:
        if game_video_count >= MAX_VIDEOS_PER_GAME:
            break
        query = f"{game} {keyword}"
        urls = search_youtube(query, max_results=2)
        for url in urls:
            if game_video_count >= MAX_VIDEOS_PER_GAME:
                break
            download_queue.put((game, url))
            video_count += 1
            game_video_count += 1
        sleep(0.5)
    print(f"  -> {game_video_count} videos")

print(f"\n[INFO] Total: {video_count} videos\n")

# ------------------- THREADS -------------------
print(f"[START] Pipeline parallele: {MAX_DOWNLOAD_THREADS} DL + {MAX_PROCESS_THREADS} Process")
print(f"[INFO] Les videos sont traitees immediatement apres telechargement\n")

# Demarrage des threads de traitement EN PREMIER (prets a recevoir)
process_threads = []
for i in range(MAX_PROCESS_THREADS):
    t = threading.Thread(target=process_worker, name=f"Process-{i+1}", daemon=False)
    t.start()
    process_threads.append(t)

# Puis demarrage des threads de telechargement
download_threads = []
for i in range(MAX_DOWNLOAD_THREADS):
    t = threading.Thread(target=download_worker, name=f"DL-{i+1}", daemon=False)
    t.start()
    download_threads.append(t)

print("[RUN] Telechargement et traitement en cours...\n")

# Attendre que tous les telechargements soient finis
download_queue.join()
for t in download_threads:
    t.join()

print("\n[INFO] Telechargements termines, finalisation du traitement...\n")

# Attendre que tous les traitements soient finis
process_queue.join()
for t in process_threads:
    t.join()

# ------------------- EXPORT -------------------
print("\n" + "="*70)
print("[EXPORT] Sauvegarde finale...")

try:
    # Sauvegarde JSON
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    # Sauvegarde CSV
    if results:
        df = pd.DataFrame(results)
        df.to_csv(OUTPUT_CSV, index=False, encoding='utf-8-sig')
    
    # Statistiques
    if results:
        avg_fps = sum(r['fps']['avg'] for r in results if r['fps']['avg'])/len([r for r in results if r['fps']['avg']])
        total_samples = sum(r['fps']['samples'] for r in results)
        unique_games = len(set(r['game'] for r in results))
        
        # Stats par resolution
        res_stats = {}
        for r in results:
            if r['resolution']:
                if r['resolution'] not in res_stats:
                    res_stats[r['resolution']] = []
                res_stats[r['resolution']].append(r['fps']['avg'])
        
        print(f"""
[OK] ANALYSE TERMINEE !

Fichiers generes:
  JSON: {OUTPUT_JSON}
  CSV:  {OUTPUT_CSV}

Statistiques globales:
  Jeux analyses: {unique_games}
  Videos traitees: {len(results)}
  FPS moyen global: {avg_fps:.1f}
  Echantillons FPS: {total_samples}

Stats par resolution:""")
        
        for res, fps_list in sorted(res_stats.items()):
            avg = sum(fps_list) / len(fps_list)
            print(f"  {res}: {avg:.1f} FPS moyen ({len(fps_list)} videos)")
        
        print(f"""
Prochaine etape:
  1. Copiez {OUTPUT_JSON.name} dans le dossier de la page HTML
  2. Ouvrez la page web dans votre navigateur
""")
    else:
        print("\n[WARN] Aucun resultat collecte")
        
except Exception as e:
    print(f"[ERREUR] Export: {e}")
    import traceback
    traceback.print_exc()

# ------------------- CLEANUP -------------------
try:
    # Nettoyer le dossier temp
    if TEMP_DIR.exists():
        for file in TEMP_DIR.glob("*"):
            try:
                file.unlink()
            except:
                pass
        print(f"[CLEAN] Dossier temp nettoye: {TEMP_DIR}")
except Exception as e:
    print(f"[WARN] Nettoyage: {e}")

print("="*70)
print("[TERMINE] Script termine avec succes!")
print("="*70)