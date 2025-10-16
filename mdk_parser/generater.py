import argparse
import re
import json


def get_source_files(dep_file: str) -> set[str]:
    with open(dep_file) as f:
        dep = f.read()
        source_files = re.findall(r"F \((.*?\.c)\)", dep)
    if source_files.count == 0:
        exit("Number of source file is 0.")
    return set(source_files)


def get_compile_arg(dep_file: str) -> str:
    with open(dep_file) as f:
        dep = f.read()
        m = re.search(r"\((-[\S\s\n]+?)\)", dep)
    if m is None:
        exit("Compile arg not found.")
    compile_arg = m.group(1)
    return re.sub(r"[\r\n]", " ", compile_arg)


def generate_compiler_commands(
    mdk_path: str,
    project_dir: str,
    source_files: set[str],
    compile_arg: str,
):
    compiler = mdk_path + "/ARM/ARMCLANG/bin/armclang.exe"
    compiler_include_dir = mdk_path + "/ARM/ARMCLANG/include"

    compile_arg = compile_arg + " -I" + compiler_include_dir

    compile_commands: list[dict[str, str]] = list()
    for source_file in source_files:
        command: dict[str, str] = {
            "directory": project_dir,
            "file": source_file,
            "command": compiler + " " + compile_arg + " " + source_file,
        }
        compile_commands.append(command)

    with open(project_dir + "/compile_commands.json", "w") as f:
        f.write(json.dumps(compile_commands))


argParser = argparse.ArgumentParser(
    description="Generate compile_commands.json form MDK project"
)

argParser.add_argument(
    "-p", "--project-path", help="MDK project path", type=str, required=True
)
argParser.add_argument(
    "-n", "--project-name", help="MDK project name", type=str, required=True
)
argParser.add_argument(
    "-t", "--target-name", help="target name", type=str, required=True
)
argParser.add_argument("-m", "--mdk-path", help="mdk path", type=str, required=True)

args = argParser.parse_args()

project_path: str = args.project_path
project_name: str = args.project_name
target_name: str = args.target_name
mdk_path: str = args.mdk_path

dep_file: str = project_path + "/Objects/" + project_name + "_" + target_name + ".dep"

compile_arg: str = get_compile_arg(dep_file)

source_files: set[str] = get_source_files(dep_file)

generate_compiler_commands(mdk_path, project_path, source_files, compile_arg)
