cat > /workspace/Hiveup/requirements.txt <<'EOF'
tqdm
yt-dlp
opencv-python
torch
easyocr
pandas
numpy
requests
EOF

pip install -r /workspace/Hiveup/requirements.txt

python -m yt_dlp --version
