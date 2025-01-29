#!/usr/bin/env python3.11

SKIP_EXTENSIONS: str = ",".join(
    [
        # Misc
        ".gitignore",
        # Images
        "png",
        "jpg",
        "jpeg",
        "gif",
        "bmp",
        "ico",
        "tiff",
        "webp",
        "psd",
        "raw",
        "svg",
        # Fonts
        "ttf",
        "woff",
        "woff2",
        "eot",
        "otf",
        # Audio/Video
        "mp3",
        "mp4",
        "wav",
        "ogg",
        "m4a",
        "flac",
        "avi",
        "mov",
        "wmv",
        "webm",
        # Documents
        "pdf",
        "doc",
        "docx",
        "xls",
        "xlsx",
        "ppt",
        "pptx",
        # Archives
        "zip",
        "tar",
        "gz",
        "7z",
        "rar",
        "bz2",
        "xz",
        # Binaries
        "bin",
        "exe",
        "dll",
        "so",
        "dylib",
        "class",
        "pyc",
        "pyo",
        # Configuration/Lock files
        "lock",
        "json",
        "json-lock",
        "yaml-lock",
        # IDE/Editor specific
        "iml",
        "workspace",
        "project",
        "sln",
        "suo",
        "sublime-project",
        "sublime-workspace",
        # Build outputs
        "min.js",
        "min.css",
        "map",
        # Database files
        "db",
        "sqlite",
        "sqlite3",
        # Godot stuff
        "tres",
        "tscn",
        "import",
        "godot",
        # Unity stuff
        "unity",
        "meta",
        "prefab",
        "asset",
        # Unreal stuff
        "uasset",
        "umap",
        "upk",
        # Blender stuff
        "blend",
        "blend1",
        # Maya stuff
        "ma",
        "mb",
        # 3D model formats
        "fbx",
        "obj",
        "3ds",
        "dae",
        "stl",
    ]
)
