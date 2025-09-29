# MDK Parser

该项目通过 Keil MDK 工程的 .dep 文件生成 compile_commands.json，使 clangd 可以工作。

## 配置方法

将 /config/config_template.yaml 重命名为 config.yaml 并配置 Keil Path 即可。

## 使用方法

--project-path 指定项目路径。

--project-name 指定项目名称。

--target-name 指定 Target 名称。

生成的 compile_commands.json 位于 project_dir/build

可能需要新建 project_dir/.clangd 以指示 clangd 行为。参考内容如下：

    ```yaml
    CompileFlags:
        CompilationDatabase: ./build/
        Compiler: path/to/armclang/bin/armclang.exe
    ```
