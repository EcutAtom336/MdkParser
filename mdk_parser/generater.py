import argparse
import os
import re
import json
import shlex
from pathlib import Path
import time
import shutil
from threading import Timer
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent
import sys
from datetime import timedelta


def _get_raw_file_blocks_from_dep_file(dep_file: Path) -> list[str]:
    with open(dep_file) as f:
        raw_file_blocks = re.findall(
            r"^F.*(?:\n(?!F).*)*", f.read(), flags=re.MULTILINE
        )
    if len(raw_file_blocks) == 0:
        raise ValueError(f"No file blocks found in {dep_file}")
    return raw_file_blocks


def _parse_source_file_from_raw_file_black(raw_file_block: str) -> Path:
    m = re.search(r"F \(([\s\S]+?)\)", raw_file_block)
    if m is None:
        raise ValueError("No match source file string.")
    return Path(m.group(1))


def _parse_compile_args_from_raw_file_black(raw_file_block: str) -> list[str]:
    m = re.search(r"\((-[\S\s\n]+?)\)", raw_file_block)
    if m is None:
        raise ValueError("No match compile arg string.")
    compile_args_str: str = m.group(1)
    tight_compile_args: list[str] = list()
    next_is_include_path: bool = False
    for compile_arg in shlex.split(compile_args_str):
        if next_is_include_path:
            next_is_include_path = False
            tight_compile_args.append("-I" + compile_arg)
            pass
        elif compile_arg == "-I":
            next_is_include_path = True
        else:
            tight_compile_args.append(compile_arg)

    return tight_compile_args


def _parse_raw_file_blocks(
    raw_file_blocks: list[str],
) -> tuple[list[Path], dict[Path, list[str]]]:

    sources: list[Path] = list()
    compile_args: dict[Path, list[str]] = dict()
    for raw_file_block in raw_file_blocks:
        source = _parse_source_file_from_raw_file_black(raw_file_block)
        sources.append(source)
        compile_args[source] = _parse_compile_args_from_raw_file_black(raw_file_block)
    return (sources, compile_args)


def _parse_dep_file(dep_file: Path) -> tuple[list[Path], dict[Path, list[str]]]:
    return _parse_raw_file_blocks(_get_raw_file_blocks_from_dep_file(dep_file))


def _generate_compiler_commands_from_dep_file(
    project_root: Path,
    compiler_exe: Path,
    compiler_include_dir: Path,
    dep_file: Path,
    output_path: Path,
):
    compile_commands: list[dict[str, str]] = list()
    sources, compile_args = _parse_dep_file(dep_file)
    for source in sources:
        command: dict[str, str] = {
            "directory": str(project_root),
            "file": str(source),
            "command": f"{compiler_exe} {' '.join(compile_args[source])} -I{compiler_include_dir} {source}",
        }
        compile_commands.append(command)

    with open(output_path / "compile_commands.json", "w") as f:
        f.write(json.dumps(compile_commands, indent=4, ensure_ascii=False))


argParser = argparse.ArgumentParser(
    description="Generate compile_commands.json form MDK project"
)


class DepFileMonitor(FileSystemEventHandler):
    _project_root: Path
    _compiler_exe: Path
    _compiler_include_dir: Path
    _dep_file: Path
    _output_path: Path

    _timer: Timer | None
    generate_compile_commands_count: int
    last_generate_compile_commands_time: float

    def __init__(
        self,
        project_root: Path,
        compiler_exe: Path,
        compiler_include_dir: Path,
        dep_file: Path,
        output_path: Path,
    ) -> None:
        super().__init__()

        self._project_root = project_root
        self._compiler_exe = compiler_exe
        self._compiler_include_dir = compiler_include_dir
        self._dep_file = dep_file
        self._output_path = output_path

        self._timer = None
        self._last_dep_file_sha256 = str()
        self.generate_compile_commands_count = 0
        self.last_generate_compile_commands_time = 0

        self._on_dep_file_changed()

    def on_modified(self, event: FileSystemEvent):
        if event.src_path != str(self._dep_file):
            return
        if self._timer and self._timer.is_alive():
            self._timer.cancel()
        self._timer = Timer(0.2, self._on_dep_file_changed)
        self._timer.start()

    def _on_dep_file_changed(self):
        self.generate_compile_commands_count += 1
        self.last_generate_compile_commands_time = time.time()
        _generate_compiler_commands_from_dep_file(
            self._project_root,
            self._compiler_exe,
            self._compiler_include_dir,
            self._dep_file,
            self._output_path,
        )


def _main():
    argParser.add_argument("--root", help="Project root path", type=Path)
    argParser.add_argument("--dep-file", help="Keil MDK .dep file", type=Path)
    argParser.add_argument(
        "--compile-commands-out-path",
        help="compile_commands.json output path",
        type=Path,
        required=True,
    )
    argParser.add_argument(
        "--compiler-exe", help="Compiler exe file", type=Path, required=True
    )
    argParser.add_argument(
        "--compiler-include-dir",
        help="Compiler include directory ",
        type=Path,
        required=True,
    )
    argParser.add_argument(
        "--monitor-mode",
        help="Monitor the .dep file, and regenerate compile_commands.json when it was changed.",
        action="store_true",
    )

    args = argParser.parse_args()

    project_root: Path | None = args.root
    dep_file: Path | None = args.dep_file
    compile_commands_out_path: Path = args.compile_commands_out_path
    compiler_exe: Path = args.compiler_exe
    compiler_include_dir = args.compiler_include_dir
    monitor_mode: bool = args.monitor_mode

    # Check param
    if project_root is None:
        project_root = Path(os.getcwd())
        print("Project root is not specified, and the cwd will be used.")

    if dep_file is None:
        print(f".dep file is not specified, will search .dep file in {project_root}.")
        dep_files: list[Path] = list(Path(project_root).rglob("*.dep"))
        if len(dep_files) == 0:
            raise FileNotFoundError(f"No .dep file was found in {project_root}.")
        if len(dep_files) > 1:
            print(
                f"Multiple .dep files found in {project_root}, you should use --dep-file to specifiy a .dep file."
            )
        dep_file = dep_files[0]
        print(f".dep file {dep_file} will be used.")
    elif not dep_file.is_absolute():
        dep_file = (project_root / dep_file).resolve()
        print(f".dep file path is relative, automatic completion as: {dep_file}.")

    if not compile_commands_out_path.is_absolute():
        compile_commands_out_path = (project_root / compile_commands_out_path).resolve()
        print(
            f"compile_commands.json output path is relative, automatic completion as: {compile_commands_out_path}."
        )

    if not project_root.exists():
        raise FileNotFoundError(f"Project root {project_root} no exist.")
    if not dep_file.exists():
        raise FileNotFoundError(f".dep file {dep_file} not found.")

    if monitor_mode is True:

        observer = Observer()
        monitor = DepFileMonitor(
            project_root,
            compiler_exe,
            compiler_include_dir,
            dep_file,
            compile_commands_out_path,
        )
        observer.schedule(monitor, path=str(dep_file.parent))
        observer.start()

        try:
            while True:
                width = shutil.get_terminal_size().columns
                sys.stdout.write("\r" + " " * width + "\r")
                now = time.time()
                time.strftime("%H:%M:%S", time.localtime(now))
                sys.stdout.write(
                    f"Current time: {time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now))} | "
                    f"Last generation was { str(timedelta(seconds = int(now - monitor.last_generate_compile_commands_time))) } seconds ago | "
                    f"Generate count: {monitor.generate_compile_commands_count}"
                )
                sys.stdout.flush()

                time.sleep(1)

        except KeyboardInterrupt:
            observer.stop()
        observer.join()

    else:
        _generate_compiler_commands_from_dep_file(
            project_root,
            compiler_exe,
            compiler_include_dir,
            dep_file,
            compile_commands_out_path,
        )


if __name__ == "__main__":
    _main()
