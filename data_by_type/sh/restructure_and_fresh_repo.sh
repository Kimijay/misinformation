#!/usr/bin/env bash
set -euo pipefail

# Script: restructure_and_fresh_repo.sh
# Purpose: Reorganize files by extension, split files >50MB into chunks
#          (for JSONL, split on line boundaries), create a fresh repo with only
#          the current files and force-push to origin to remove history.
# WARNING: This will overwrite remote history when pushing. Use with care.

REPO_ROOT="$(pwd)"
TS=$(date +%Y%m%d_%H%M%S)
BACKUP_TAR="/tmp/misinformation_backup_${TS}.tar.gz"
NEWDIR="/tmp/misinformation_reorg_${TS}"
MAX_BYTES=$((50 * 1024 * 1024))

echo "Repository root: $REPO_ROOT"
echo "Backup archive: $BACKUP_TAR"
echo "Working new tree: $NEWDIR"

# 1) backup current repo (tar the working tree including .git to backup)
echo "Creating backup archive..."
rm -f "$BACKUP_TAR"
tar -czf "$BACKUP_TAR" -C "$(dirname "$REPO_ROOT")" "$(basename "$REPO_ROOT")"

# 2) prepare new working tree
rm -rf "$NEWDIR"
mkdir -p "$NEWDIR"

# Copy non-git files to newdir preserving structure for later processing
# We'll copy everything except .git directory (and optionally large temp files)
echo "Copying files to working tree (excluding .git) ..."
rsync -a --exclude='.git' "$REPO_ROOT/" "$NEWDIR/"

cd "$NEWDIR"

# 3) Create target base dir for reorganized files
TARGET_BASE="data_by_type"
rm -rf "$TARGET_BASE"
mkdir -p "$TARGET_BASE"

# Helper: get file size (macOS stat)
files_to_process=()
while IFS= read -r -d $'\0' file; do
  files_to_process+=("$file")
done < <(find . -type f -not -path './.git/*' -print0)

echo "Found ${#files_to_process[@]} files to process."

for f in "${files_to_process[@]}"; do
  # skip files under the new target base if any
  [[ "$f" == ./${TARGET_BASE}/* ]] && continue
  # normalize
  rel=${f#./}
  # skip .gitignore? we'll keep it at root
  if [[ "$rel" == ".gitignore" || "$rel" == "README.md" ]]; then
    echo "Keeping $rel at repo root"
    continue
  fi

  # determine extension
  filename=$(basename "$rel")
  dirname=$(dirname "$rel")
  if [[ "$filename" == *.* ]]; then
    base=${filename%.*}
    ext=${filename##*.}
  else
    base="$filename"
    ext="noext"
  fi
  ext_lc=$(echo "$ext" | tr '[:upper:]' '[:lower:]')
  target_dir="$TARGET_BASE/$ext_lc"
  mkdir -p "$target_dir"

  size=$(stat -f%z "$rel")
  if (( size > MAX_BYTES )); then
    echo "Splitting large file: $rel (size=$size bytes) -> $target_dir"
    # For newline-delimited text (jsonl, txt) use split -C to keep lines intact
    if [[ "$ext_lc" == "jsonl" || "$ext_lc" == "txt" || "$ext_lc" == "log" ]]; then
      prefix="$target_dir/${base}.part."
      # macOS split may not support -C; use perl to split by byte size while keeping line boundaries
      echo "  (text) splitting $rel into parts of up to $MAX_BYTES bytes"
      # Write a small perl script to do line-preserving byte-accurate splitting
      perl_script="/tmp/split_jsonl_${TS}_$$.pl"
      cat > "$perl_script" <<'PERL'
use strict; use warnings;
my ($in, $prefix, $ext, $max) = @ARGV;
open my $fh, "<:raw", $in or die "open $in: $!";
my $part = 0;
my $outfh;
my $size = 0;
while (my $line = <$fh>) {
  my $len = length($line);
  if (!defined $outfh || $size + $len > $max) {
    close $outfh if defined $outfh;
    my $out = sprintf("%s%04d.%s", $prefix, $part, $ext);
    open $outfh, ">:raw", $out or die "open $out: $!";
    $part++;
    $size = 0;
  }
  print $outfh $line;
  $size += $len;
}
close $outfh if defined $outfh;
PERL

      perl "$perl_script" "$rel" "$prefix" "$ext_lc" "$MAX_BYTES"
      rm -f "$perl_script"
      # perl already writes extension in filenames
    else
      # binary files: use byte-split
      prefix="$target_dir/${base}.part."
      split -d -a 4 -b ${MAX_BYTES} "$rel" "$prefix"
      for part in "${prefix}"*; do
        if [[ -f "$part" ]]; then
          mv "$part" "${part}.${ext_lc}"
        fi
      done
    fi
    # remove original large file
    rm -f "$rel"
  else
    # move file into target dir (preserve directory structure under type?)
    mv "$rel" "$target_dir/$(basename "$rel")"
  fi
done

# Move kept root files (.gitignore, README.md) back to root of newdir
# They already exist in newdir root; ensure they are retained

# 4) Create a fresh git repository in newdir
echo "Preparing fresh git repository in $NEWDIR"
# Remove any existing .git inside newdir (we copied it earlier excluded but double-check)
rm -rf .git

git init -b main
# ensure no LFS attributes
rm -f .gitattributes || true

# Add everything and commit
git add --all
GIT_COMMITTER_NAME="migration-bot" GIT_COMMITTER_EMAIL="no-reply@example.com" git commit -m "Reorganized files by type and split large files; fresh history" || true

# configure remote origin from original repo
ORIGIN_URL=$(git --git-dir="$REPO_ROOT/.git" config --get remote.origin.url || true)
if [[ -z "$ORIGIN_URL" ]]; then
  echo "No origin URL found in original repo. Please add remote manually. New repo is prepared at: $NEWDIR"
  exit 0
fi

git remote add origin "$ORIGIN_URL"

# 5) Final push -- force (this will overwrite remote history)
echo "About to force-push the new repository to $ORIGIN_URL"

echo "Pushing main branch..."
git push --force origin main

# also push tags and all refs if needed (none expected)
# git push --force origin --tags || true

# 6) cleanup: remove old LFS local storage in this new repo if any
rm -rf .git/lfs || true

# Report summary
echo "Reorganization complete. New tree: $NEWDIR"
echo "Backup archive saved to: $BACKUP_TAR"

exit 0
