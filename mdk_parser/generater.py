import argparse
import re
import json
import shlex


def get_raw_file_blocks(dep_file: str) -> list[str]:
    with open(dep_file) as f:
        raw_file_blocks = re.findall(
            r"^F.*(?:\n(?!F).*)*", f.read(), flags=re.MULTILINE
        )
        assert len(raw_file_blocks) != 0, "File block not found."
        return raw_file_blocks


def get_source_file(raw_file_block: str) -> str:
    m = re.search(r"F \(([\s\S]+?)\)", raw_file_block)
    assert m is not None, "No match source file string."
    return m.group(1)


def get_compile_args(raw_file_block: str) -> list[str]:
    m = re.search(r"\((-[\S\s\n]+?)\)", raw_file_block)
    assert m is not None
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
    project_root: str,
    compiler_exe: str,
    sources: list[str],
    compile_args: dict[str, list[str]],
    output_path: str,
):
    compile_commands: list[dict[str, str]] = list()
    for source in sources:
        command: dict[str, str] = {
            "directory": project_root,
            "file": source,
            "command": f"{compiler_exe} {' '.join(compile_args[source])} {source}",
        }
        compile_commands.append(command)

    with open(output_path + "/compile_commands.json", "w") as f:
        f.write(json.dumps(compile_commands))


argParser = argparse.ArgumentParser(
    description="Generate compile_commands.json form MDK project"
)

argParser.add_argument("--root", help="Project root path", type=str, required=True)
argParser.add_argument("--dep-file", help="Keil MDK .dep file", type=str, required=True)
argParser.add_argument(
    "--compile-commands-out-path",
    help="compile_commands.json output path",
    type=str,
    required=True,
)
argParser.add_argument(
    "--compiler-exe", help="Compile exe file", type=str, required=True
)

args = argParser.parse_args()

project_root: str = args.root
dep_file: str = args.dep_file
compile_commands_out_path = args.compile_commands_out_path
compiler_exe = args.compiler_exe

raw_file_blocks = get_raw_file_blocks(dep_file)

sources: list[str] = list()
compile_args: dict[str, list[str]] = dict()
for raw_file_block in raw_file_blocks:
    source = get_source_file(raw_file_block)
    sources.append(source)
    compile_args[source] = get_compile_args(raw_file_block)
generate_compiler_commands(
    project_root, compiler_exe, sources, compile_args, compile_commands_out_path
)
