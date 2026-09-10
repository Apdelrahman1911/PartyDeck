#!/usr/bin/env python3
"""Pinned Godot install, isolated renderer validation, PCK export, and previews."""

import argparse
import configparser
from datetime import datetime, timezone
from hashlib import sha256, sha512
import io
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
import zipfile

from partydeck_pck import read_pack


TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parents[1]
PROJECT = ROOT / "godot/renderer"
BUILD = ROOT / "godot/qualification/build"
OUTPUT = BUILD / "renderer/partydeck-last-light.pck"
PINS_FILE = TOOLS / "godot-pins.json"
PINS = json.loads(PINS_FILE.read_text(encoding="utf-8"))
SCENES = ("main.tscn", "presentations/two_d/table.tscn", "presentations/three_d/table.tscn")
REQUIRED_NOTICES = (
    "assets/licenses/fraunces_ofl.txt",
    "assets/licenses/manrope_ofl.txt",
    "assets/licenses/font_notices.txt",
    "licenses/GODOT_LICENSE.txt",
    "licenses/GODOT_COPYRIGHT.txt",
)
EXCLUDED_DIRS = {".git", ".godot", ".gradle", ".idea", "__pycache__", "build", "tests", "checks", "fixtures"}
EXCLUDED_PREFIXES = ("assets/proofs/", "assets/sources/")
EXCLUDED_NAMES = {".gitignore", ".DS_Store", "README.md", "export_credentials.cfg", ".env"}
PRIVATE_SUFFIXES = {".jks", ".keystore", ".p12", ".pfx", ".key", ".pem", ".mobileprovision"}
ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
ENGINE_ERROR = re.compile(r"(?m)^\s*(?:SCRIPT ERROR|SHADER ERROR|USER ERROR|ERROR):")


class ToolError(ValueError):
    pass


def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def excluded(relative: Path) -> bool:
    name = relative.as_posix()
    return (
        bool(set(relative.parts) & EXCLUDED_DIRS)
        or name.startswith(EXCLUDED_PREFIXES)
        or relative.name in EXCLUDED_NAMES
        or relative.name.startswith(".env.")
        or relative.suffix.lower() in PRIVATE_SUFFIXES
        or (relative.suffix.lower() == ".md" and "licenses" not in relative.parts)
    )


def source_snapshot(project: Path) -> dict:
    if not (project / "project.godot").is_file():
        raise ToolError("Renderer project.godot is missing: " + str(project))
    files = []
    omitted = []
    for directory, directories, names in os.walk(project, followlinks=False):
        directory_path = Path(directory)
        for name in list(directories):
            path = directory_path / name
            relative = path.relative_to(project)
            if excluded(relative) or (path / ".gdignore").exists():
                directories.remove(name)
                omitted.append(relative.as_posix() + "/")
            elif path.is_symlink():
                raise ToolError("Renderer input directory is a symlink: " + relative.as_posix())
        for name in names:
            path = directory_path / name
            relative = path.relative_to(project)
            if excluded(relative):
                omitted.append(relative.as_posix())
                continue
            if path.is_symlink() or not path.is_file():
                raise ToolError("Renderer input is not a regular file: " + relative.as_posix())
            files.append({"path": relative.as_posix(), "bytes": path.stat().st_size, "sha256": digest(path)})
    files.sort(key=lambda item: item["path"])
    required = {"project.godot", "export_presets.cfg", "assets/manifest.json", *SCENES, *REQUIRED_NOTICES}
    missing = required - {entry["path"] for entry in files}
    if missing:
        raise ToolError("Required renderer inputs are missing: " + ", ".join(sorted(missing)))
    tool_files = ["renderer.py", "partydeck_pck.py", "scene_check.gd", "godot-pins.json"]
    tools = [{"path": name, "sha256": digest(TOOLS / name)} for name in tool_files]
    fingerprint = sha256(json.dumps({"files": files, "tools": tools}, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return {"fingerprint": fingerprint, "files": files, "tools": tools, "excluded": sorted(omitted)}


def engine_info(argument: Path | None) -> dict:
    candidates = [argument] if argument else [BUILD / "toolchain/godot", Path("/opt/partydeck-godot/godot")]
    executable = next((path.resolve() for path in candidates if path and path.is_file()), None)
    if executable is None:
        raise ToolError("Godot is missing; run renderer.py install or provide --godot")
    command = [str(executable), "--version"]
    result = subprocess.run(command, capture_output=True, text=True, timeout=20, check=False)
    version = result.stdout.strip()
    if result.returncode or version != PINS["version_output"]:
        raise ToolError("Godot must be the pinned official " + PINS["version_output"])
    binary_hash = digest(executable)
    if platform.system() == "Linux" and platform.machine().lower() in ("x86_64", "amd64"):
        if binary_hash != PINS["linux_x86_64"]["executable_sha256"]:
            raise ToolError("Godot binary differs from the verified official Linux executable")
    return {"executable": str(executable), "version": version, "sha256": binary_hash, "version_command": command}


class Commands:
    def __init__(self, directory: Path):
        self.directory = directory
        self.records: list[dict] = []

    def run(self, label: str, command: list[str], cwd: Path, timeout: int = 180) -> str:
        self.directory.mkdir(parents=True, exist_ok=True)
        log = self.directory / (label + ".log")
        started = datetime.now(timezone.utc).isoformat()
        before = time.monotonic()
        try:
            result = subprocess.run(command, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    text=True, errors="replace", timeout=timeout or None, check=False)
            output = result.stdout
            returncode = result.returncode
        except subprocess.TimeoutExpired as error:
            output = error.stdout or b""
            if isinstance(output, bytes):
                output = output.decode("utf-8", errors="replace")
            output += "\nPartyDeck tooling: command timed out.\n"
            returncode = 124
        log.write_text(output, encoding="utf-8")
        diagnostics = bool(ENGINE_ERROR.search(ANSI.sub("", output)))
        self.records.append({"label": label, "argv": command, "cwd": str(cwd), "started_utc": started,
                             "elapsed_seconds": round(time.monotonic() - before, 3), "exit_code": returncode,
                             "engine_error_diagnostic": diagnostics, "log": str(log), "log_sha256": digest(log)})
        write_json(self.directory / "commands.json", {"commands": self.records})
        if returncode or diagnostics:
            print(output[-12000:], file=sys.stderr)
            raise ToolError(f"{label} failed (exit {returncode}, engine errors {diagnostics}); log: {log}")
        print(f"{label}: passed; log: {log}")
        return output


def copy_project(project: Path, snapshot: dict, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    for entry in snapshot["files"]:
        source = project / entry["path"]
        data = source.read_bytes()
        if sha256(data).hexdigest() != entry["sha256"]:
            raise ToolError("Renderer input changed during staging; retry after writes finish")
        target = destination / entry["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)


def explicit_export_preset(source: bytes, snapshot: dict, preset_name: str) -> tuple[bytes, dict]:
    config = configparser.ConfigParser(interpolation=None)
    config.optionxform = str
    try:
        config.read_string(source.decode("utf-8"))
        sections = [section for section in config.sections() if re.fullmatch(r"preset\.\d+", section)
                    and json.loads(config[section].get("name", '""')) == preset_name]
    except (configparser.Error, ValueError) as error:
        raise ToolError("Cannot read renderer export presets: " + str(error)) from error
    if len(sections) != 1:
        raise ToolError("Expected exactly one renderer export preset named " + preset_name)
    metadata = {"project.godot", "export_presets.cfg", ".gdignore"}
    omitted = sorted(entry["path"] for entry in snapshot["files"]
                     if entry["path"] in metadata or Path(entry["path"]).suffix.lower() in {".import", ".uid"})
    files = sorted("res://" + entry["path"] for entry in snapshot["files"] if entry["path"] not in omitted)
    preset = config[sections[0]]
    # Godot preserves explicit insertion order. Wildcard scans use unsorted
    # readdir; their insertions/removals can change both payload and cache order.
    preset["export_filter"] = '"resources"'
    preset["export_files"] = "PackedStringArray(" + ", ".join(json.dumps(path, ensure_ascii=False) for path in files) + ")"
    preset["include_filter"] = '""'
    preset["exclude_filter"] = '""'
    stream = io.StringIO()
    config.write(stream, space_around_delimiters=False)
    prepared = stream.getvalue().encode("utf-8")
    plan = {"strategy": "sorted-explicit-resources", "preset": preset_name,
            "source_preset_sha256": sha256(source).hexdigest(),
            "staged_preset_sha256": sha256(prepared).hexdigest(),
            "files": files, "omitted_metadata": omitted}
    return prepared, plan


def scene_check(engine: dict, project: Path, commands: Commands, pack: Path | None = None) -> dict:
    argv = [engine["executable"], "--headless", "--path", str(project)]
    if pack:
        argv += ["--main-pack", str(pack)]
    argv += ["--script", str(TOOLS / "scene_check.gd")]
    label = "packed-scene-check" if pack else "source-scene-check"
    output = commands.run(label, argv, project)
    prefix = "PARTYDECK_SCENE_CHECK="
    records = [json.loads(line[len(prefix):]) for line in output.splitlines() if line.startswith(prefix)]
    if len(records) != 1 or records[0] != {"ok": True, "scenes": ["res://" + path for path in SCENES]}:
        raise ToolError("Godot did not confirm all three real scene loads/instantiations")
    return records[0]


def import_and_check(engine: dict, project: Path, commands: Commands) -> dict:
    commands.run("import", [engine["executable"], "--headless", "--path", str(project), "--editor", "--import"], project)
    return scene_check(engine, project, commands)


def verify_contents(pack: dict, snapshot: dict) -> None:
    entries = {entry["path"]: entry for entry in pack["entries"]}
    for path in entries:
        # Export-generated .godot resources are required; source caches never enter staging.
        parts = Path(path).parts
        if any(part in ("tests", "checks", "fixtures", "build", ".git") for part in parts):
            raise ToolError("Development content entered PCK: " + path)
        if path.startswith(EXCLUDED_PREFIXES) or Path(path).suffix.lower() in PRIVATE_SUFFIXES:
            raise ToolError("Excluded source/credential content entered PCK: " + path)
        if Path(path).name in {"export_credentials.cfg", ".env"} or Path(path).name.startswith(".env."):
            raise ToolError("Credential content entered PCK: " + path)
    for scene in SCENES:
        if scene not in entries and scene + ".remap" not in entries:
            raise ToolError("PCK is missing required presentation scene: " + scene)
    if "project.binary" not in entries:
        raise ToolError("PCK is missing exported project settings")
    for source in snapshot["files"]:
        path = source["path"]
        if "licenses" in Path(path).parts or path == "assets/manifest.json":
            if path not in entries or entries[path]["sha256"] != source["sha256"]:
                raise ToolError("PCK omits or changes a license/provenance file: " + path)


def install(args: argparse.Namespace) -> None:
    if platform.system() != "Linux" or platform.machine().lower() not in ("x86_64", "amd64"):
        raise ToolError("Automatic installation supports Linux x86_64; other hosts must provide an official 4.7.2 --godot executable")
    destination = args.destination.resolve()
    destination.mkdir(parents=True, exist_ok=True)
    pin = PINS["linux_x86_64"]
    archive = args.archive.resolve() if args.archive else destination / pin["archive"]
    if not archive.exists():
        if args.archive:
            raise ToolError("Provided archive is missing")
        partial = archive.with_suffix(archive.suffix + ".part")
        try:
            request = urllib.request.Request(pin["url"], headers={"User-Agent": "PartyDeck-Godot-tooling"})
            with urllib.request.urlopen(request, timeout=60) as response, partial.open("wb") as output:
                shutil.copyfileobj(response, output, length=1024 * 1024)
            partial.replace(archive)
        finally:
            partial.unlink(missing_ok=True)
    data = archive.read_bytes()
    if len(data) != pin["bytes"] or sha256(data).hexdigest() != pin["sha256"] or sha512(data).hexdigest() != pin["sha512"]:
        raise ToolError("Godot archive differs from the pinned official checksums")
    with zipfile.ZipFile(archive) as source:
        if source.namelist() != [pin["executable_member"]]:
            raise ToolError("Official Godot archive has unexpected contents")
        binary = source.read(pin["executable_member"])
    if sha256(binary).hexdigest() != pin["executable_sha256"]:
        raise ToolError("Extracted Godot executable differs from the pinned binary")
    executable = destination / "godot"
    temporary = destination / "godot.tmp"
    temporary.write_bytes(binary)
    temporary.chmod(0o755)
    temporary.replace(executable)
    engine = engine_info(executable)
    write_json(destination / "install.receipt.json", {"schema_version": 1, "engine": engine,
               "source": pin["url"], "archive_sha256": pin["sha256"], "archive_sha512": pin["sha512"],
               "pins_sha256": digest(PINS_FILE), "export_templates_downloaded": False})
    print(executable)


def validate_or_pack(args: argparse.Namespace) -> None:
    project = args.project.resolve()
    engine = engine_info(args.godot)
    snapshot = source_snapshot(project)
    output = args.output.resolve() if args.command == "pack" else BUILD / "renderer/validation.json"
    if args.command == "pack" and output.suffix != ".pck":
        raise ToolError("Pack output must have a .pck extension")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="renderer-stage-", dir=output.parent) as temporary:
        stage = Path(temporary) / "project"
        copy_project(project, snapshot, stage)
        source_preset = (stage / "export_presets.cfg").read_bytes()
        commands = Commands(output.parent / ("pack-logs" if args.command == "pack" else "validation-logs"))
        structural = import_and_check(engine, stage, commands)
        receipt = {"schema_version": 1, "engine": engine, "inputs": snapshot, "scene_check": structural,
                   "scope": "Structural import/resource validation; no authority or gameplay acceptance is inferred."}
        if args.command == "pack":
            preset_path = stage / "export_presets.cfg"
            prepared, receipt["export_inputs"] = explicit_export_preset(source_preset, snapshot, args.preset)
            preset_path.write_bytes(prepared)
            (commands.directory / "export_presets.cfg").write_bytes(prepared)
            pending = Path(temporary) / output.name
            commands.run("export-pack", [engine["executable"], "--headless", "--path", str(stage),
                         "--export-pack", args.preset, str(pending)], stage, timeout=300)
            pack = read_pack(pending)
            verify_contents(pack, snapshot)
            isolated = Path(temporary) / "pack-only"
            isolated.mkdir()
            receipt["packed_scene_check"] = scene_check(engine, isolated, commands, pending)
            if source_snapshot(project)["fingerprint"] != snapshot["fingerprint"]:
                raise ToolError("Renderer sources changed during export; output was not promoted")
            pending.replace(output)
            receipt["pack"] = pack
            receipt["export_preset"] = args.preset
            receipt["export_templates_required"] = False
            receipt["commands"] = commands.records
            write_json(output.with_suffix(".receipt.json"), receipt)
            print(f"PCK: {output}\nSHA-256: {pack['sha256']}\nEntries: {len(pack['entries'])}; bytes: {pack['bytes']}")
        else:
            if source_snapshot(project)["fingerprint"] != snapshot["fingerprint"]:
                raise ToolError("Renderer sources changed during validation; retry")
            receipt["commands"] = commands.records
            write_json(output, receipt)
            print("Validation receipt: " + str(output))


def check_pack(args: argparse.Namespace) -> dict:
    path = args.pack.resolve()
    receipt_path = path.with_suffix(".receipt.json")
    if not path.is_file() or not receipt_path.is_file():
        raise ToolError("PCK or receipt is missing; run renderer.py pack")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    snapshot = source_snapshot(args.project.resolve())
    if receipt.get("schema_version") != 1 or receipt.get("inputs", {}).get("fingerprint") != snapshot["fingerprint"]:
        raise ToolError("PCK is stale for the renderer/tool sources; run renderer.py pack")
    pack = read_pack(path)
    if pack != receipt.get("pack"):
        raise ToolError("PCK differs from its recorded export; rebuild it")
    expected_scene_check = {"ok": True, "scenes": ["res://" + item for item in SCENES]}
    if receipt.get("scene_check") != expected_scene_check or receipt.get("packed_scene_check") != expected_scene_check:
        raise ToolError("PCK has no successful source and packed scene checks")
    preset = receipt.get("export_preset")
    if not isinstance(preset, str):
        raise ToolError("PCK receipt has no export preset name")
    _, expected_plan = explicit_export_preset((args.project.resolve() / "export_presets.cfg").read_bytes(), snapshot, preset)
    if receipt.get("export_inputs") != expected_plan:
        raise ToolError("PCK has no matching explicit-resource export plan; rebuild it")
    verify_contents(pack, snapshot)
    print(f"PCK checks passed: {len(pack['entries'])} entries; SHA-256 {pack['sha256']}")
    return receipt


def preview(args: argparse.Namespace) -> None:
    launch = args.launch_file.resolve()
    raw = launch.read_bytes()
    if len(raw) > 65_536:
        raise ToolError("Launch file exceeds the bridge payload limit")
    document = json.loads(raw)
    if not isinstance(document, dict) or document.get("type") != "launch" or document.get("gameId") != "last-light":
        raise ToolError("Preview requires a real Last Light launch document")
    if document.get("presentationMode") != args.presentation:
        raise ToolError("--presentation must match launch.presentationMode; no document is rewritten")
    engine = engine_info(args.godot)
    commands = Commands(BUILD / "renderer" / ("preview-" + args.presentation))
    receipt_path = commands.directory / "preview.receipt.json"
    # A failed run must not leave a previous success beside overwritten logs.
    receipt_path.unlink(missing_ok=True)
    argv = [engine["executable"]]
    if args.headless:
        argv.append("--headless")
    if args.audio_driver:
        argv += ["--audio-driver", args.audio_driver]
    if args.quit_after:
        argv += ["--quit-after", str(args.quit_after)]
    temporary_root = BUILD / "renderer"
    temporary_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="preview-", dir=temporary_root) as temporary:
        project = Path(temporary)
        if args.pack:
            packed = check_pack(args)
            source_fingerprint = packed["inputs"]["fingerprint"]
            pack_sha256 = packed["pack"]["sha256"]
            argv += ["--path", str(project), "--main-pack", str(args.pack.resolve())]
        else:
            snapshot = source_snapshot(args.project.resolve())
            source_fingerprint = snapshot["fingerprint"]
            pack_sha256 = None
            copy_project(args.project.resolve(), snapshot, project)
            import_and_check(engine, project, commands)
            argv += ["--path", str(project)]
        argv += ["--", "--presentation=" + args.presentation, "--launch-file=" + str(launch)]
        output = commands.run("preview", argv, project, timeout=args.timeout)
        if "PartyDeck renderer event: ready" not in output or "PartyDeck renderer event: failed" in output:
            raise ToolError("Renderer preview did not report a successful Ready event; inspect preview.log")
    write_json(receipt_path, {"engine": engine, "presentation": args.presentation,
               "launch_file": str(launch), "launch_sha256": sha256(raw).hexdigest(), "commands": commands.records,
               "source_fingerprint": source_fingerprint, "pack_sha256": pack_sha256,
               "headless": args.headless, "audio_driver": args.audio_driver,
               "renderer_ready_observed": True,
               "scope": "Fixture presentation preview only. Accepted actions/outcomes require the Kotlin comparison authority."})


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    setup = sub.add_parser("install", help="Install the checksum-pinned official Linux x86_64 editor; no templates")
    setup.add_argument("--destination", type=Path, default=BUILD / "toolchain")
    setup.add_argument("--archive", type=Path, help="Reuse a local official ZIP after verifying both pinned checksums")
    for name in ("validate", "pack", "check-pack", "preview"):
        command = sub.add_parser(name)
        command.add_argument("--project", type=Path, default=PROJECT)
        if name != "check-pack":
            command.add_argument("--godot", type=Path)
        if name == "pack":
            command.add_argument("--output", type=Path, default=OUTPUT)
            command.add_argument("--preset", default="Renderer pack")
        if name in ("check-pack", "preview"):
            command.add_argument("--pack", type=Path, default=OUTPUT if name == "check-pack" else None)
        if name == "preview":
            command.add_argument("--presentation", choices=("2d", "3d"), required=True)
            command.add_argument("--launch-file", type=Path, required=True)
            command.add_argument("--headless", action="store_true")
            command.add_argument("--audio-driver", help="Godot audio driver; use Dummy for display checks without an audio device")
            command.add_argument("--quit-after", type=int)
            command.add_argument("--timeout", type=int, default=0, help="Seconds; zero waits until the preview closes")
    args = parser.parse_args()
    try:
        if args.command == "install":
            install(args)
        elif args.command in ("validate", "pack"):
            validate_or_pack(args)
        elif args.command == "check-pack":
            check_pack(args)
        else:
            if args.quit_after is not None and args.quit_after <= 0 or args.timeout < 0:
                raise ToolError("Preview frame/timeout limits must be positive (timeout zero means unlimited)")
            preview(args)
        return 0
    except (OSError, ValueError, subprocess.SubprocessError, zipfile.BadZipFile) as error:
        print("Godot tooling: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
