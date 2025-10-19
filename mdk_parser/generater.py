import argparse
import os
import re
import json
import shlex
from pathlib import Path
import time
import shutil
import sys
from datetime import timedelta


def get_raw_file_blocks(dep_file: Path) -> list[str]:
    with open(dep_file) as f:
        raw_file_blocks = re.findall(
            r"^F.*(?:\n(?!F).*)*", f.read(), flags=re.MULTILINE
        )
    if len(raw_file_blocks) == 0:
        raise ValueError(f"No file blocks found in {dep_file}")
    return raw_file_blocks


def get_source_file(raw_file_block: str) -> Path:
    m = re.search(r"F \(([\s\S]+?)\)", raw_file_block)
    if m is None:
        raise ValueError("No match source file string.")
    return Path(m.group(1))


def get_compile_args(raw_file_block: str) -> list[str]:
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


def generate_compiler_commands(
    project_root: Path,
    compiler_exe: Path,
    compiler_include_dir: Path,
    sources: list[Path],
    compile_args: dict[Path, list[str]],
    output_path: Path,
):
    compile_commands: list[dict[str, str]] = list()
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


def run_once(
    dep_file: Path,
    project_root: Path,
    compiler_exe: Path,
    compiler_include_dir: Path,
    compile_commands_out_path: Path,
):
    raw_file_blocks = get_raw_file_blocks(dep_file)
    sources: list[Path] = list()
    compile_args: dict[Path, list[str]] = dict()
    for raw_file_block in raw_file_blocks:
        source = get_source_file(raw_file_block)
        sources.append(source)
        compile_args[source] = get_compile_args(raw_file_block)
    generate_compiler_commands(
        project_root,
        compiler_exe,
        compiler_include_dir,
        sources,
        compile_args,
        compile_commands_out_path,
    )


def main():
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

    last_dep_file_modify_time = dep_file.stat().st_mtime
    last_generate_compile_commands_time = time.time()
    run_once(
        dep_file,
        project_root,
        compiler_exe,
        compiler_include_dir,
        compile_commands_out_path,
    )

    if monitor_mode is True:
        try:
            while True:
                latest_dep_file_modify_time = dep_file.stat().st_mtime
                if latest_dep_file_modify_time != last_dep_file_modify_time:
                    last_dep_file_modify_time = latest_dep_file_modify_time
                    last_generate_compile_commands_time = time.time()
                    run_once(
                        dep_file,
                        project_root,
                        compiler_exe,
                        compiler_include_dir,
                        compile_commands_out_path,
                    )

                width = shutil.get_terminal_size().columns
                sys.stdout.write("\r" + " " * width + "\r")
                now = time.time()
                time.strftime("%H:%M:%S", time.localtime(now))
                sys.stdout.write(
                    f"Current time: {time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now))} | Last generation was { str(timedelta(seconds = int(now - last_generate_compile_commands_time))) } seconds ago."
                )
                sys.stdout.flush()

                time.sleep(1)

        except KeyboardInterrupt:
            print("Stopped monitoring.")
            sys.exit(0)


if __name__ == "__main__":
    main()
