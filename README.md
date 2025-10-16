# MDK Parser

该项目通过 Keil MDK 工程的 .dep 文件生成 compile_commands.json，使 clangd 可以工作。

## 使用方法

可能需要新建 project_dir/.clangd 以指示 clangd 行为。参考内容如下：

    ```yaml
    CompileFlags:
        CompilationDatabase: ./build/
        Compiler: path/to/armclang/bin/armclang.exe
    ```
