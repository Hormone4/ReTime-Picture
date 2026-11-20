# ReTime-Picture

CLI to modify the date of pictures (EXIF metadata + NTFS timestamps).<br/>
Accepted formats:

* jpeg
* jpg
* png

## Description

This software allows to:

- Automatically detect your picture's dates from their filename (manual mode is also an option).
- Update all relevant EXIF date fields.
- Set the Windows creation and modification timestamps (NTFS).
- Skip images once both metadata and file timestamps match.

## How to use

### Auto Mode (if you have many pictures in a folder)

If your filename formats are among the following (Android / iOS standard):

* IMG_YYYYMMDD_hhmmss.jpg
* YYYY-MM-DD hh.mm.ss.jpeg

For example:

* IMG_20250717_220715.jpg
* 2025-07-21 11.14.55.jpeg


Run `retime.py` directly in your folder:

```bash
python retime.py
```

Or specify another folder:

```bash
python retime.py "C:\path\to\pictures"
```

The script will automatically detect the filenames, extract the correct dates and update your pictures.
<br/><br/>


### Custom mode (to modify pictures individually)

Run `retime.py` with individual picture date updates.

Examples:

```bash
python retime.py --file "photo.jpg" --date "2025-07-21 11.14.55"
python retime.py -f "photo.jpg" -d "2025-07-21"
```

You can update several pictures with the same date:

```bash
python retime.py -f "photo1.jpg" -f "photo2.jpg" -d "2025-07-21 11.14.55"
```
