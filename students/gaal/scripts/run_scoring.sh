#!/bin/bash
#
# run_scoring.sh - Download, filter, and run Community Notes scoring
#
# Usage:
#   ./run_scoring.sh [--skip-download] [--skip-filter]
#
# Options:
#   --skip-download  Skip downloading data (use existing local-data/)
#   --skip-filter    Skip filtering (use existing filtered data)
#

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DATA_DIR="$PROJECT_ROOT/../../data"
LOCAL_DATA="$PROJECT_ROOT/local-data"
FILTERED_DATA="$DATA_DIR/filtered/2023-10"
OUTPUT_DIR="$PROJECT_ROOT/output"
CN_DIR="$PROJECT_ROOT/communitynotes"

SKIP_DOWNLOAD=false
SKIP_FILTER=false

# Parse arguments
for arg in "$@"; do
    case $arg in
        --skip-download)
            SKIP_DOWNLOAD=true
            shift
            ;;
        --skip-filter)
            SKIP_FILTER=true
            shift
            ;;
    esac
done

echo "=== Community Notes Scoring Pipeline ==="
echo ""

# Step 1: Download data
if [ "$SKIP_DOWNLOAD" = false ]; then
    echo "Step 1: Downloading Community Notes data..."
    echo "  (Not implemented - please download manually from https://twitter.com/i/communitynotes/download-data)"
    echo "  Place files in: $LOCAL_DATA"
    echo ""
else
    echo "Step 1: Skipping download (--skip-download)"
    echo ""
fi

# Step 2: Filter data
if [ "$SKIP_FILTER" = false ]; then
    echo "Step 2: Filtering data to October 2023..."
    python "$SCRIPT_DIR/filter_notes_2023_10.py"
    echo ""
else
    echo "Step 2: Skipping filter (--skip-filter)"
    echo ""
fi

# Step 3: Strip extra columns
echo "Step 3: Stripping extra columns from filtered data..."
cd "$PROJECT_ROOT"
python scripts/strip_extra_columns.py
echo ""

# Step 4: Create output directory
echo "Step 4: Creating output directory..."
mkdir -p "$OUTPUT_DIR"
echo "  Output will be written to: $OUTPUT_DIR"
echo ""

# Step 5: Check dependencies (assumes venv already activated with deps installed)
echo "Step 5: Checking Python dependencies..."
echo "  (Assuming dependencies already installed in active venv)"
echo ""

# Step 6: Merge ratings files (old scoring code doesn't support directories)
echo "Step 6: Merging ratings files..."
MERGED_RATINGS="$OUTPUT_DIR/merged_ratings.tsv"
head -1 "$FILTERED_DATA/ratings/ratings-00000.tsv" > "$MERGED_RATINGS"
for f in "$FILTERED_DATA/ratings/"*.tsv; do
    tail -n +2 "$f" >> "$MERGED_RATINGS"
done
echo "  Merged $(ls "$FILTERED_DATA/ratings/"*.tsv | wc -l) ratings files"

# Step 7: Run scoring
echo "Step 7: Running scoring algorithm..."
cd "$CN_DIR/sourcecode"

# Use end of October 2023 as the epoch time (same as filter cutoff)
EPOCH_MILLIS=1698796799000

python main.py \
    --notes "$FILTERED_DATA/notes/notes-00000.tsv" \
    --ratings "$MERGED_RATINGS" \
    --status "$FILTERED_DATA/notes-status-history/noteStatusHistory-00000.tsv" \
    --enrollment "$FILTERED_DATA/user-enrollment/userEnrollment-00000.tsv" \
    --epoch-millis "$EPOCH_MILLIS" \
    --nostrict-columns \
    --nopseudoraters \
    --outdir "$OUTPUT_DIR"

echo ""
echo "=== Scoring complete! ==="
echo "Results written to: $OUTPUT_DIR"
echo ""
echo "Output files:"
ls -la "$OUTPUT_DIR"
