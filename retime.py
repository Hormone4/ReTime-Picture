import argparse
import ctypes
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path
import sys

from PIL import Image


DATE_FORMAT = "%Y:%m:%d %H:%M:%S"
EXIF_DATE_TAGS = (36867, 36868, 306)  # DateTimeOriginal, DateTimeDigitized, DateTime
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}

FILENAME_PATTERNS = (
    re.compile(r"^IMG_(\d{8})_(\d{6})$"),
    re.compile(r"^(\d{4}-\d{2}-\d{2}) ([0-2]\d)\.([0-5]\d)\.([0-5]\d)$"),
)


def extract_datetime(filename: str) -> datetime | None:
    stem = Path(filename).stem

    match = FILENAME_PATTERNS[0].fullmatch(stem)
    if match:
        date_text, time_text = match.groups()
        try:
            return datetime.strptime(date_text + time_text, "%Y%m%d%H%M%S")
        except ValueError:
            return None

    match = FILENAME_PATTERNS[1].fullmatch(stem)
    if match:
        date_text, hour, minute, second = match.groups()
        try:
            return datetime.strptime(
                f"{date_text} {hour}:{minute}:{second}",
                "%Y-%m-%d %H:%M:%S",
            )
        except ValueError:
            return None

    return None


def exif_value(exif, tag: int) -> str | None:
    value = exif.get(tag)
    if isinstance(value, bytes):
        value = value.decode("ascii", errors="replace")
    return value.strip() if isinstance(value, str) else None


def picture_datetime_matches(exif, target: datetime) -> bool:
    values = [exif_value(exif, tag) for tag in EXIF_DATE_TAGS]

    for value in values:
        if value is not None:
            try:
                existing = datetime.strptime(value, DATE_FORMAT)
            except ValueError:
                continue
            if existing != target:
                return False

    # Missing all date fields should be treated as metadata that needs updating.
    if not any(values):
        return False
    return True


def set_windows_file_times(path: Path, target: datetime) -> None:
    if sys.platform != "win32":
        timestamp = target.timestamp()
        os.utime(path, (timestamp, timestamp))
        return

    timestamp = target.timestamp()
    file_time = int((timestamp + 11644473600) * 10_000_000)

    filetime_class = ctypes.c_ulonglong(file_time)
    creation = filetime_class
    access = ctypes.c_ulonglong(file_time)
    modification = ctypes.c_ulonglong(file_time)

    handle = ctypes.windll.kernel32.CreateFileW(
        str(path),
        0x40000000,  # GENERIC_WRITE
        0x00000001 | 0x00000002 | 0x00000004,
        None,
        3,  # OPEN_EXISTING
        0x02000000,  # FILE_ATTRIBUTE_NORMAL
        None,
    )
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError()

    try:
        result = ctypes.windll.kernel32.SetFileTime(
            handle,
            ctypes.byref(creation),
            ctypes.byref(access),
            ctypes.byref(modification),
        )
        if not result:
            raise ctypes.WinError()
    finally:
        ctypes.windll.kernel32.CloseHandle(handle)


def file_times_match(path: Path, target: datetime) -> bool:
    stat = path.stat()
    creation = datetime.fromtimestamp(stat.st_ctime)
    modification = datetime.fromtimestamp(stat.st_mtime)
    return (
        abs((creation - target).total_seconds()) < 1
        and abs((modification - target).total_seconds()) < 1
    )


def parse_datetime(value: str) -> datetime:
    formats = (
        "%Y-%m-%d %H.%M.%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y%m%d_%H%M%S",
        "%Y:%m:%d %H:%M:%S",
        "%Y-%m-%d",
        "%Y%m%d",
    )
    for date_format in formats:
        try:
            return datetime.strptime(value, date_format)
        except ValueError:
            continue
    raise argparse.ArgumentTypeError(
        f"invalid date {value!r}; use YYYY-MM-DD HH.MM.SS"
    )


def update_exif(path: Path, target: datetime) -> None:
    target_text = target.strftime(DATE_FORMAT)
    extension = path.suffix.lower()

    with Image.open(path) as image:
        exif = image.getexif()
        for tag in EXIF_DATE_TAGS:
            exif[tag] = target_text

        icc_profile = image.info.get("icc_profile")
        saved_image = image

        file_descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{path.stem}.",
            suffix=extension,
            dir=path.parent,
        )
        os.close(file_descriptor)
        temporary_path = Path(temporary_name)

        try:
            if extension in {".jpg", ".jpeg"}:
                if image.mode == "RGBA":
                    background = Image.new("RGB", image.size, "white")
                    background.paste(image, mask=image.getchannel("A"))
                    saved_image = background
                elif image.mode not in {"RGB", "CMYK", "L"}:
                    saved_image = image.convert("RGB")

                save_options = {
                    "format": "JPEG",
                    "exif": exif,
                }
                if image.format == "JPEG":
                    save_options.update({
                        "quality": "keep",
                        "subsampling": "keep",
                        "qtables": "keep",
                    })
                if icc_profile:
                    save_options["icc_profile"] = icc_profile
            else:
                save_options = {
                    "format": "PNG",
                    "exif": exif,
                }
                if icc_profile:
                    save_options["icc_profile"] = icc_profile

            saved_image.save(temporary_path, **save_options)
            os.replace(temporary_path, path)
        except Exception:
            temporary_path.unlink(missing_ok=True)
            raise

    set_windows_file_times(path, target)


def process_folder(folder: Path) -> None:
    if not folder.is_dir():
        raise NotADirectoryError(folder)

    for path in sorted(folder.iterdir()):
        if not path.is_file() or path.suffix.lower() not in IMAGE_EXTENSIONS:
            continue

        target = extract_datetime(path.name)
        if target is None:
            print(f"SKIP (filename): {path.name}")
            continue

        try:
            with Image.open(path) as image:
                exif = image.getexif()
        except Exception as exc:
            print(f"SKIP (invalid image): {path.name} ({exc})")
            continue

        if (
            picture_datetime_matches(exif, target)
            and file_times_match(path, target)
        ):
            print(f"PASS: {path.name}")
            continue

        try:
            update_exif(path, target)
            print(f"UPDATED: {path.name} -> {target.strftime(DATE_FORMAT)}")
        except Exception as exc:
            print(f"ERROR: {path.name} ({exc})")


def process_file(path: Path, target: datetime) -> None:
    path = path.resolve()

    if not path.is_file():
        print(f"ERROR (missing file): {path}")
        return
    if path.suffix.lower() not in IMAGE_EXTENSIONS:
        print(f"ERROR (not a JPEG or PNG): {path}")
        return

    try:
        with Image.open(path) as image:
            exif = image.getexif()
    except Exception as exc:
        print(f"ERROR (invalid image): {path} ({exc})")
        return

    if (
        picture_datetime_matches(exif, target)
        and file_times_match(path, target)
    ):
        print(f"PASS: {path.name}")
        return

    try:
        update_exif(path, target)
        print(f"UPDATED: {path.name} -> {target.strftime(DATE_FORMAT)}")
    except Exception as exc:
        print(f"ERROR: {path.name} ({exc})")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Update JPEG/PNG EXIF and file dates from filenames or explicit CLI values.",
        epilog=(
            "Examples:\n"
            "  retime.py\n"
            "  retime.py --file photo.jpg --date \"2025-07-21 11.14.55\"\n"
            "  retime.py --file photo.jpg --date 2025-07-21"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "folder",
        nargs="?",
        type=Path,
        default=Path(__file__).resolve().parent,
        help="Folder to process (default: folder containing this script)",
    )
    parser.add_argument(
        "-f",
        "--file",
        action="append",
        type=Path,
        dest="files",
        help="Picture to update explicitly; may be repeated",
    )
    parser.add_argument(
        "-d",
        "--date",
        type=parse_datetime,
        dest="explicit_date",
        help="Date to set (YYYY-MM-DD HH.MM.SS; date-only sets midnight)",
    )
    args = parser.parse_args()

    if args.files and args.explicit_date is None:
        parser.error("--date is required when --file is used")
    if args.explicit_date is not None and not args.files:
        parser.error("--file is required when --date is used")

    if args.files:
        for path in args.files:
            process_file(path, args.explicit_date)
        return

    process_folder(args.folder)


if __name__ == "__main__":
    main()