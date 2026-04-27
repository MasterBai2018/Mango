# Mango NANO MGO VSCode Extension

## 1. 目标

这个扩展为 Mango NANO `.mgo` DSL 提供 VSCode 支持，能力分为三层：

1. 文件识别与 TextMate 语法高亮
2. 语言配置：注释、括号、folding markers
3. 语言能力：补全、悬浮提示、基础诊断、文档符号

## 2. 目录结构

```text
plugins/vscode-mgo-extension/
├── package.json
├── extension.js
├── language-configuration.json
├── metadata/
│   └── nano-dsl-schema.json
├── scripts/
│   └── generate_metadata.py
└── syntaxes/
    └── nano-mgo.tmLanguage.json
```

## 3. 元数据来源

扩展不手写多套 DSL 词表，而是优先复用项目源码：

- `src/testsuite/NANO/config.py`
- `conf/assert_key_value.yaml`
- `src/core/Status/AIBSSessionStatus.py`
- `src/testsuite/NANO/client/SpeechEngineClient.py`
- `src/testsuite/NANO/client/TSSClient.py`
- `src/testsuite/NANO/doc/COMMAND.md`
- `src/testsuite/NANO/doc/NANO_DSL_CLIENT_COMMAND_REFERENCE.md`

使用下面的脚本重新生成：

```bash
python3 plugins/vscode-mgo-extension/scripts/generate_metadata.py
```

## 4. 当前能力

### 4.1 语法高亮

支持高亮：

- `>>>` / `<<<`
- `SETUP` / `TEARDOWN` / `SUITE_TEARDOWN` / `PARAMETER`
- `[TSA]`、`[SET]`、`[EXP]` 等客户端标签
- 客户端命令
- 断言类型
- `${...}` / `{...}` / `{EVAL:...}`
- `<timeout=...>`
- `SETVRCONFIG` / `GET_VR_CONFIG` 后的 VR 配置项
- `SET_PARAM` 后的参数枚举（`TSA/NIS/HWK/TSS`）
- 行首和行尾注释

### 4.2 自动补全

支持基础补全：

- `>>> ` 后补全块关键字
- `[` 后补全客户端
- `[CLIENT]` 后补全命令
- `[EXP]` 后补全断言类型
- `SETVRCONFIG ` / `GET_VR_CONFIG ` 后补全 VR 配置项
- `SET_PARAM ` 后按客户端补全参数枚举
- `{` 后补全环境变量
- `<timeout=` 后补全常见 timeout 值

### 4.3 Hover

支持对以下对象给出基础说明：

- 块关键字
- 客户端
- 命令
- 断言类型
- 环境变量
- VR 配置项
- `SET_PARAM` 参数枚举

其中：

- 客户端 Hover 会列出该客户端支持的所有命令及其作用摘要
- 命令 Hover 会显示语法、参数说明、示例，以及适用客户端
- 同名命令会优先按当前客户端匹配说明，例如 `[TSA]CREATE` 与其它客户端的 `CREATE` 可展示不同用法
- `EXP` 下的 `LOG`、`SUM`、文件断言等会优先展示断言专属说明

### 4.4 诊断

当前实现的是第一版静态诊断，主要检查：

- 非法块头
- 未知客户端
- 客户端不支持的命令
- 未知断言类型
- 未知环境变量
- `SETVRCONFIG` / `GET_VR_CONFIG` 后未知配置项
- `SET_PARAM` 后未知参数枚举
- 明显非法的 timeout

## 5. 开发与调试

### 5.1 在 VSCode 中调试扩展

推荐步骤：

1. 用一个支持 Node.js 的环境打开 `plugins/vscode-mgo-extension`
2. 安装 `yo code` 或手动创建 `.vscode/launch.json`
3. 使用 VSCode 的 `Run Extension` 启动一个 Extension Development Host
4. 在新窗口中打开 `.mgo` 文件验证效果

### 5.2 本机限制说明

当前这台服务器上的 `node` 运行时存在系统库版本不兼容问题，因此：

- 扩展源码已经可以直接维护
- 但 `npm install`、`vsce package`、本机调试可能需要在 Node 兼容的环境中执行

如果你后续准备真正打包 `.vsix`，建议：

- 在开发机或容器里使用兼容版本的 Node.js
- 或先升级当前机器上的 Node 运行环境

## 6. 打包发布

当你拥有可用的 Node.js / npm / vsce 环境后，可以在扩展目录下执行：

```bash
cd plugins/vscode-mgo-extension
npm install -g @vscode/vsce
vsce package
```

生成的 `.vsix` 可以通过以下方式安装：

```bash
code --install-extension mango-nano-mgo-0.0.1.vsix
```

## 7. 后续可扩展方向

- 更强的块级语义诊断
- snippets
- 跳转到命令文档
- 独立 Language Server
