" 自动识别 Mango NANO DSL 文件类型
" 使用独立 augroup，避免清空系统/插件的 filetypedetect 规则
augroup mango_nano_mgo_ftdetect
  autocmd!
  " 强制将 .mgo 识别为 nano_mgo，避免被其他插件规则覆盖
  autocmd BufNewFile,BufRead *.mgo set filetype=nano_mgo
augroup END
