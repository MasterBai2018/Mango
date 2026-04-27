#!/bin/sh
# 将 plugins/vim 下的高亮文件安装到当前用户 ~/.vim
# 用法：
#   sh plugins/vim/install_mgo_vim_systemwide.sh

set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
SRC_SYNTAX="$SCRIPT_DIR/syntax/nano_mgo.vim"
SRC_FTDETECT="$SCRIPT_DIR/ftdetect/nano_mgo.vim"
DST_BASE="${HOME}/.vim"
DST_SYNTAX_DIR="$DST_BASE/syntax"
DST_FTDETECT_DIR="$DST_BASE/ftdetect"

err() {
  printf '错误：%s\n' "$*" >&2
  exit 1
}

[ -n "${HOME:-}" ] || err "HOME 未设置，无法确定目标目录。"
[ -f "$SRC_SYNTAX" ] || err "找不到源文件：$SRC_SYNTAX。请在 plugins/vim 目录下运行该脚本。"
[ -f "$SRC_FTDETECT" ] || err "找不到源文件：$SRC_FTDETECT。请在 plugins/vim 目录下运行该脚本。"

mkdir -p "$DST_SYNTAX_DIR" || err "创建目录失败：$DST_SYNTAX_DIR"
mkdir -p "$DST_FTDETECT_DIR" || err "创建目录失败：$DST_FTDETECT_DIR"

cp -f "$SRC_SYNTAX" "$DST_SYNTAX_DIR/nano_mgo.vim" || err "复制失败：$SRC_SYNTAX -> $DST_SYNTAX_DIR/nano_mgo.vim"
cp -f "$SRC_FTDETECT" "$DST_FTDETECT_DIR/nano_mgo.vim" || err "复制失败：$SRC_FTDETECT -> $DST_FTDETECT_DIR/nano_mgo.vim"

printf '安装完成：\n'
printf '  %s\n' "$DST_SYNTAX_DIR/nano_mgo.vim"
printf '  %s\n' "$DST_FTDETECT_DIR/nano_mgo.vim"
printf '\n'
printf '请重新打开 .mgo 文件，或在 Vim 中执行：\n'
printf '  :syntax clear\n'
printf '  :e\n'
