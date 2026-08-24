import os
import uuid

from flask import current_app
from werkzeug.utils import secure_filename


class InvalidFileError(Exception):
    pass


def _validate(file_storage, allowed_extensions, max_bytes):
    if not file_storage or file_storage.filename == "":
        raise InvalidFileError("No file provided.")

    filename = secure_filename(file_storage.filename)
    if "." not in filename:
        raise InvalidFileError("File has no extension.")

    ext = filename.rsplit(".", 1)[1].lower()
    if ext not in allowed_extensions:
        raise InvalidFileError(f"File type .{ext} is not allowed.")

    # Check real size by seeking to end
    file_storage.stream.seek(0, os.SEEK_END)
    size = file_storage.stream.tell()
    file_storage.stream.seek(0)
    if size > max_bytes:
        raise InvalidFileError("File is too large.")

    return filename, ext


def save_upload(file_storage, subfolder, allowed_extensions=None, max_bytes=None):
    """
    Validates and saves an uploaded file under UPLOAD_FOLDER/subfolder.
    Returns the relative path (from static/uploads) to store in the DB.
    """
    allowed_extensions = allowed_extensions or current_app.config["ALLOWED_DOC_EXTENSIONS"]
    max_bytes = max_bytes or current_app.config["MAX_CONTENT_LENGTH"]

    filename, ext = _validate(file_storage, allowed_extensions, max_bytes)
    unique_name = f"{uuid.uuid4().hex}.{ext}"

    target_dir = os.path.join(current_app.config["UPLOAD_FOLDER"], subfolder)
    os.makedirs(target_dir, exist_ok=True)
    full_path = os.path.join(target_dir, unique_name)
    file_storage.save(full_path)

    return f"{subfolder}/{unique_name}"
