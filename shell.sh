# depuis le repo monté dans /workspace/Hiveup
python app.py --mode cli --max-videos 1

docker build -t hiveup-bench .
docker run --rm -v "$(pwd)/output:/workspace/Hiveup/output" hiveup-bench

export WORKSPACE=/workspace/Hiveup
python app.py --mode cli
