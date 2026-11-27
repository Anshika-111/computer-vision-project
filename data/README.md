# Dataset files

Git holds the metadata only: `manifest.csv`, `annotations/pairs.json`, `image_checksums.csv`,
and `license_review.csv`. The images themselves live on the team Google Drive (CLAUDE.md
Section 4) and are ignored by git.

## Getting the images

1. On the team Drive, download the folder **`data/images`** (the processed, repo-ready set).
   Do **not** use the raw originals folder: 27 raw images are larger than 1024 px and 12 are
   JPEGs, so the annotation polygons and evaluation numbers would not line up with them.
2. Put it at `data/images/` in your clone, so you have e.g.
   `data/images/maps/maps_0022.png`.
3. Check it:

   ```bash
   python -m scripts.check_images
   ```

   It should print `data/images/ matches the dataset exactly.` Anything else lists the
   files to fix.

## Layout

`data/images/<category>/<image_id>.png`, with categories `charts`, `maps`, `traffic`, `food`,
`coded_items`, `natural`, and `image_id = <category>_<4-digit number>`.

## Regenerating (Aliza)

The processed set is built from the raw originals by `scripts/prepare_dataset.py`. If it is
ever rebuilt, run `python -m scripts.check_images --write`, commit the new
`image_checksums.csv`, and re-upload `data/images/` to the Drive.
