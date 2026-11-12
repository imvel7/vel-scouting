# SoccerTrack v2 validation tool

This tool validates the structure and metadata of a locally available SoccerTrack v2 dataset. It does not download data, bypass access controls, upload files, or modify the dataset.

## Access first

The dataset is gated on Hugging Face. Request access from the dataset owner and wait for approval before downloading. Follow the dataset's CC BY 4.0 attribution terms, but do not treat the license as a bypass for the Hugging Face access gate.

Official dataset: https://huggingface.co/datasets/atomscott/soccertrack-v2  
Upstream download instructions: https://github.com/AtomScott/SoccerTrack-v2/blob/main/scripts/download.sh

## Install

From the repository root:

    python -m pip install -r requirements-vision.txt

The GSR parser uses ijson because a single half file may be several gigabytes. Keep the data on a local disk with enough free space.

## Run

    python vision/soccertrack_v2/validate_dataset.py \
      --dataset-root /path/to/soccertrack-v2 \
      --match-id 117093 \
      --video-first-half /path/to/117093_first_half.mp4 \
      --video-second-half /path/to/117093_second_half.mp4 \
      --output /path/to/117093_validation.json

Video arguments are optional. If supplied, the tool uses ffprobe to inspect stream metadata only; it does not decode or alter the video.

## Tests

    python -m unittest discover -s vision/soccertrack_v2 -p 'test_*.py'

The test suite uses small synthetic BAS fixtures. It does not claim validation against the gated full dataset. GSR streaming tests should be run after ijson is installed and an authorized sample is available.

## Important limitations

- The tool validates annotations; it does not train or run a tracking/action-recognition model.
- It does not create a scouting report, player rating, identity match, or real-person profile.
- Exact half-two event-to-frame alignment remains deliberately unresolved until the release's per-period timing metadata is checked.
- Compare actual video geometry with GSR metadata. Upstream documentation flags dimension inconsistencies in most matches.
- Do not load multi-gigabyte GSR files with json.load().
