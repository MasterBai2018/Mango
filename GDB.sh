#!/bin/bash

set -e

# ================= 配置与参数解析 =================
BATCH_MODE=false
USE_DOCKER=true
OUTPUT_DIR=""
POSITIONAL_ARGS=()

# 循环解析命令行参数
while [[ $# -gt 0 ]]; do
    case $1 in
        -b|--batch)
            BATCH_MODE=true
            shift # 移出参数列表
            ;;
        -n|--no-docker)
            USE_DOCKER=false
            shift # 移出参数列表
            ;;
        -o|--output)
            OUTPUT_DIR="$2"
            shift 2 # 移出参数和值
            ;;
        -h|--help)
            echo "用法: $0 [选项] <可执行文件/python> <core-dump文件>"
            echo "选项:"
            echo "  -b, --batch      批处理模式 (自动打印堆栈并退出)"
            echo "  -n, --no-docker 不使用 Docker，直接在本机执行 GDB"
            echo "  -o, --output     指定输出目录 (将 GDB 输出保存到该目录)"
            echo "  -h, --help       显示帮助"
            echo ""
            echo "示例 (交互模式 - 默认):"
            echo "  $0 /usr/bin/myapp ./core.dump"
            echo "  $0 python3 ./core.dump"
            echo ""
            echo "示例 (批处理模式 - 用于自动化):"
            echo "  $0 -b /usr/bin/myapp ./core.dump"
            echo "  $0 -b -n python3 ./core.dump  # 不使用 Docker"
            echo "  $0 -b -n -o ./reports python3 ./core.dump  # 输出到指定目录"
            exit 0
            ;;
        *)
            POSITIONAL_ARGS+=("$1") # 保存位置参数
            shift
            ;;
    esac
done

# 恢复位置参数并检查数量
set -- "${POSITIONAL_ARGS[@]}"
if [ $# -ne 2 ]; then
    echo "错误: 参数数量不正确。"
    echo "请运行: $0 --help 查看用法"
    exit 1
fi

# ================= 变量准备 =================

# 1. 确定 Docker 和 GDB 的运行参数
if [ "$BATCH_MODE" = true ]; then
    # 批处理模式: 无交互终端，GDB 自动运行 bt 并退出
    DOCKER_IT_FLAG=""
    GDB_FLAGS="-q --batch -ex bt"
    echo ">>> 当前模式: 批处理 (自动输出堆栈)"
else
    # 交互模式 (默认): 分配 TTY，GDB 等待用户输入
    DOCKER_IT_FLAG="-it"
    GDB_FLAGS="-q" # 仅安静启动，不自动退出
    echo ">>> 当前模式: 交互式 (进入 GDB Shell)"
fi

# 2. 解析输入路径
INPUT_EXEC="$1"
CORE_FILE_RAW="$2"

# 将core-dump文件的相对路径转换为绝对路径
CORE_FILE=$(realpath "$CORE_FILE_RAW")
CORE_DIR=$(dirname "$CORE_FILE")
CORE_NAME=$(basename "$CORE_FILE")

if [ ! -f "$CORE_FILE" ]; then
    echo "错误: core-dump文件不存在: $CORE_FILE"
    exit 1
fi

# 3. 处理输出目录
if [ -n "$OUTPUT_DIR" ]; then
    # 创建输出目录（如果不存在）
    mkdir -p "$OUTPUT_DIR"
    # 将输出目录转换为绝对路径（如果 realpath 支持 -m 则使用，否则先创建再转换）
    if realpath -m "$OUTPUT_DIR" >/dev/null 2>&1; then
        OUTPUT_DIR=$(realpath -m "$OUTPUT_DIR")
    else
        OUTPUT_DIR=$(cd "$OUTPUT_DIR" && pwd)
    fi
    # 生成输出文件名（基于 core 文件名）
    OUTPUT_FILE="$OUTPUT_DIR/gdb_${CORE_NAME}.txt"
    echo ">>> 输出将保存到: $OUTPUT_FILE"
fi

# ================= 执行逻辑 =================

# 检查是否使用容器内的 python/python3
if [ "$INPUT_EXEC" = "python" ] || [ "$INPUT_EXEC" = "python3" ]; then
    # --- Python 分支 ---
    EXEC_NAME="$INPUT_EXEC"
    
    if [ "$USE_DOCKER" = true ]; then
        echo "分析core-dump: $CORE_FILE"
        echo "使用容器内程序: $EXEC_NAME"
        echo "启动docker环境..."

        # 注意：这里移除了 --args，因为加载 core 文件不需要它
        if [ -n "$OUTPUT_DIR" ]; then
            # 挂载输出目录到容器，并将输出重定向到文件
            docker run --rm $DOCKER_IT_FLAG \
                -v "$CORE_DIR:/tmp/core-dump" \
                -v "$OUTPUT_DIR:/tmp/output" \
                mango:v3.6.0 \
                /bin/bash -c "cd /tmp/core-dump && gdb $GDB_FLAGS $EXEC_NAME $CORE_NAME > /tmp/output/gdb_${CORE_NAME}.txt 2>&1"
        else
            docker run --rm $DOCKER_IT_FLAG \
                -v "$CORE_DIR:/tmp/core-dump" \
                mango:v3.6.0 \
                /bin/bash -c "cd /tmp/core-dump && gdb $GDB_FLAGS $EXEC_NAME $CORE_NAME"
        fi
    else
        # 非 Docker 模式：查找本机的 Python 可执行文件
        if command -v "$EXEC_NAME" >/dev/null 2>&1; then
            EXEC_PATH=$(command -v "$EXEC_NAME")
            echo "分析core-dump: $CORE_FILE"
            echo "使用本机程序: $EXEC_PATH"
            echo "直接执行 GDB (不使用 Docker)..."
            if [ -n "$OUTPUT_FILE" ]; then
                cd "$CORE_DIR" && gdb $GDB_FLAGS "$EXEC_PATH" "$CORE_NAME" > "$OUTPUT_FILE" 2>&1
                echo ">>> GDB 输出已保存到: $OUTPUT_FILE"
            else
                cd "$CORE_DIR" && gdb $GDB_FLAGS "$EXEC_PATH" "$CORE_NAME"
            fi
        else
            echo "错误: 找不到本机的 $EXEC_NAME 可执行文件"
            exit 1
        fi
    fi

else
    # --- C++ 可执行程序分支 ---
    # 将可执行文件的相对路径转换为绝对路径
    EXEC_FILE=$(realpath "$INPUT_EXEC")
    EXEC_DIR=$(dirname "$EXEC_FILE")
    EXEC_NAME=$(basename "$EXEC_FILE")

    if [ ! -f "$EXEC_FILE" ]; then
        echo "错误: 可执行文件不存在: $EXEC_FILE"
        exit 1
    fi

    if [ "$USE_DOCKER" = true ]; then
        echo "分析core-dump: $CORE_FILE"
        echo "挂载宿主机文件: $EXEC_FILE"
        echo "启动docker环境..."

        if [ -n "$OUTPUT_DIR" ]; then
            # 挂载输出目录到容器，并将输出重定向到文件
            docker run --rm $DOCKER_IT_FLAG \
                -v "$CORE_DIR:/tmp/core-dump" \
                -v "$EXEC_DIR:/tmp/executable" \
                -v "$OUTPUT_DIR:/tmp/output" \
                mango:v3.6.0 \
                /bin/bash -c "cd /tmp/core-dump && gdb $GDB_FLAGS /tmp/executable/$EXEC_NAME $CORE_NAME > /tmp/output/gdb_${CORE_NAME}.txt 2>&1"
        else
            docker run --rm $DOCKER_IT_FLAG \
                -v "$CORE_DIR:/tmp/core-dump" \
                -v "$EXEC_DIR:/tmp/executable" \
                mango:v3.6.0 \
                /bin/bash -c "cd /tmp/core-dump && gdb $GDB_FLAGS /tmp/executable/$EXEC_NAME $CORE_NAME"
        fi
    else
        # 非 Docker 模式：直接在本机执行
        echo "分析core-dump: $CORE_FILE"
        echo "使用本机可执行文件: $EXEC_FILE"
        echo "直接执行 GDB (不使用 Docker)..."
        if [ -n "$OUTPUT_FILE" ]; then
            cd "$CORE_DIR" && gdb $GDB_FLAGS "$EXEC_FILE" "$CORE_NAME" > "$OUTPUT_FILE" 2>&1
            echo ">>> GDB 输出已保存到: $OUTPUT_FILE"
        else
            cd "$CORE_DIR" && gdb $GDB_FLAGS "$EXEC_FILE" "$CORE_NAME"
        fi
    fi
fi
