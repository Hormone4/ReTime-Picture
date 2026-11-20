# ReTime-Picture

CLI to modify the date of pictures (EXIF metadata + NTFS timestamps).

Especially designed to get back lost date metadata from pictures taken with Android / iOS phones.

## Description

This software allows to:

- Automatically detect the picture's date from the filename (manual mode is also an option).
- Update all relevant EXIF date fields.
- Set the Windows creation and modification timestamps (NTFS).
- Skip images once both metadata and file timestamps match.

## How to use

### Auto Mode (if you have many pictures in a folder)

If your filename formats are among the following (Android / iOS standard):

```
IMG_YYYYMMDD_hhmmss.jpg
YYYY-MM-DD hh.mm.ss.jpeg
```

For example:

```
IMG_20250717_220715.jpg
2025-07-21 11.14.55.jpeg
```

Run it directly from the folder:

```bash
python retime.py
```

Or specify another folder:

```bash
python retime.py "C:\path\to\pictures"
```

`retime.py` will detect the filenames, extract the correct dates and update your pictures.



### Custom mode (to modify pictures individually)

If you just wish to change the date of a picture, run `retime.py` with individual picture date updates.

Examples:

```bash
python retime.py --file "photo.jpg" --date "2025-07-21 11.14.55"
python retime.py -f "photo.jpg" -d "2025-07-21"
```

You can update several pictures with the same date:

```bash
python retime.py -f "photo1.jpg" -f "photo2.jpg" -d "2025-07-21 11.14.55"
```

Both EXIF metadata and Windows file timestamps are updated.



