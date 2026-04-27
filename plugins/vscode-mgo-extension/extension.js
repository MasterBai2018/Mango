const vscode = require("vscode");
const metadata = require("./metadata/nano-dsl-schema.json");

function buildLookup() {
  const commandToClients = new Map();
  for (const [client, commands] of Object.entries(metadata.commandsByClient)) {
    for (const command of commands) {
      const clients = commandToClients.get(command) || [];
      clients.push(client);
      commandToClients.set(command, clients);
    }
  }
  return { commandToClients };
}

const lookup = buildLookup();

function escapeRegExp(text) {
  return text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

const nonParameterBlockKeywords = metadata.blockKeywords.filter((k) => k !== "PARAMETER");
const fixtureAlt = nonParameterBlockKeywords.map(escapeRegExp).join("|");
const validBlockHeaderLineRe =
  fixtureAlt.length > 0
    ? new RegExp(`^\\s*>>>\\s+(${fixtureAlt})\\s*$`)
    : /(?!)/;
const blockSymbolLineRe =
  fixtureAlt.length > 0
    ? new RegExp(`^\\s*>>>\\s*((?:${fixtureAlt})|PARAMETER\\s+\\S+|\\d+)?\\s*$`)
    : /^\s*>>>\s*(PARAMETER\s+\S+|\d+)?\s*$/;

function getCommandDoc(client, command) {
  const byClient = (metadata.commandDocsByClient && metadata.commandDocsByClient[client]) || {};
  return byClient[command] || (metadata.commandDocsByName && metadata.commandDocsByName[command]) || null;
}

function getSetParamsForClient(client) {
  return (metadata.setParamsByClient && metadata.setParamsByClient[client]) || [];
}

function getCommandDocumentation(command, client) {
  const doc = getCommandDoc(client, command);
  if (doc && doc.summary) {
    let result = doc.summary;
    if (command === "SET_PARAM") {
      const params = getSetParamsForClient(client);
      result += `\n\n当前客户端 ${client} 可用参数数：${params.length}`;
    }
    return result;
  }
  return "DSL 命令。";
}

function getCurrentLineClientCommand(document, position) {
  const line = document.lineAt(position.line).text;
  const match = line.match(/^\s*\[([A-Z]+)\](\S+)/);
  if (!match) {
    return null;
  }
  return { client: match[1], command: match[2], line };
}

function buildCommandHoverMarkdown(client, command) {
  const doc = getCommandDoc(client, command);
  const md = new vscode.MarkdownString();
  md.isTrusted = false;
  md.appendMarkdown(`**${command}**\n\n`);
  md.appendMarkdown(`${getCommandDocumentation(command, client)}\n\n`);

  if (doc && doc.syntax) {
    md.appendMarkdown("语法：\n");
    md.appendCodeblock(doc.syntax, "text");
  }

  if (doc && doc.params && doc.params.length > 0) {
    md.appendMarkdown("\n参数说明：\n");
    for (const param of doc.params) {
      if (param.name) {
        md.appendMarkdown(`- \`${param.name}\`：${param.description}\n`);
      } else {
        md.appendMarkdown(`- ${param.description}\n`);
      }
    }
  }

  if (command === "SET_PARAM") {
    const params = getSetParamsForClient(client);
    if (params.length > 0) {
      md.appendMarkdown(`\n支持参数（${params.length}个）：\n`);
      md.appendMarkdown(params.map((item) => `\`${item}\``).join("、"));
      md.appendMarkdown("\n");
    }
  }

  if (doc && doc.example) {
    md.appendMarkdown("\n示例：\n");
    md.appendCodeblock(doc.example, "text");
  }

  return md;
}

function buildClientHoverMarkdown(client) {
  const commands = client === "EXP"
    ? (metadata.expCommands || metadata.assertions || [])
    : (metadata.commandsByClient[client] || []);
  const summaries = (metadata.clientCommandSummaries && metadata.clientCommandSummaries[client]) || {};
  const md = new vscode.MarkdownString();
  md.isTrusted = false;
  md.appendMarkdown(`**${client}**\n\n客户端标签。\n\n支持命令数：**${commands.length}**\n\n`);
  md.appendMarkdown("支持命令：\n");
  for (const command of commands) {
    const doc = getCommandDoc(client, command);
    const summary = summaries[command] || (doc && doc.summary) || "未补充说明";
    md.appendMarkdown(`- \`${command}\`：${summary}\n`);
  }
  return md;
}

function stripInlineComment(line) {
  let inSingle = false;
  let inDouble = false;
  for (let i = 0; i < line.length; i += 1) {
    const ch = line[i];
    const prev = i > 0 ? line[i - 1] : "";
    if (ch === "'" && prev !== "\\" && !inDouble) {
      inSingle = !inSingle;
    } else if (ch === "\"" && prev !== "\\" && !inSingle) {
      inDouble = !inDouble;
    } else if (ch === "#" && !inSingle && !inDouble) {
      if (i === 0 || /\s/.test(line[i - 1])) {
        return line.slice(0, i).trimEnd();
      }
    }
  }
  return line;
}

/** `>>>` / `<<<` 成对校验（与命令行校验独立扫描）。 */
function validateBlockDelimiters(document, addDiagnostic) {
  const stack = [];

  for (let lineNumber = 0; lineNumber < document.lineCount; lineNumber += 1) {
    const rawLine = document.lineAt(lineNumber).text;
    const line = stripInlineComment(rawLine);
    const trimmed = line.trim();
    if (!trimmed) {
      continue;
    }

    // 空块占位：同进同出，不占栈
    if (/^\s*>>>\s*<<<\s*$/.test(line)) {
      continue;
    }

    if (/^\s*<<<\s*$/.test(line)) {
      const closeIndex = rawLine.indexOf("<<<");
      if (stack.length === 0) {
        const start = closeIndex >= 0 ? closeIndex : 0;
        const end = closeIndex >= 0 ? closeIndex + 3 : rawLine.length;
        addDiagnostic(lineNumber, start, end, "多余的块结束标记 `<<<`：没有对应的 `>>>`");
      } else {
        stack.pop();
      }
      continue;
    }

    // 单行 `>>> SETUP<<<` 等同闭合，不占栈
    if (/^\s*>>>/.test(line) && /<<<\s*$/.test(trimmed) && !/^\s*>>>\s*<<<\s*$/.test(line)) {
      continue;
    }

    if (/^\s*>>>/.test(line)) {
      stack.push(lineNumber);
    }
  }

  for (let i = 0; i < stack.length; i += 1) {
    const lineNumber = stack[i];
    const rawLine = document.lineAt(lineNumber).text;
    const openIndex = rawLine.indexOf(">>>");
    const start = openIndex >= 0 ? openIndex : 0;
    const end = openIndex >= 0 ? openIndex + 3 : rawLine.length;
    addDiagnostic(lineNumber, start, end, "缺少块结束标记 `<<<`：该 `>>>` 未与结束行成对");
  }
}

function isNanoMgoDocument(document) {
  if (document.languageId === metadata.languageId) {
    return true;
  }
  const fsPath = document.uri.fsPath || "";
  if (fsPath && fsPath.toLowerCase().endsWith(".mgo")) {
    return true;
  }
  const path = document.uri.path || "";
  return path.toLowerCase().endsWith(".mgo");
}

function getWordAt(document, position) {
  const range = document.getWordRangeAtPosition(position, /[A-Za-z0-9_.-]+/);
  if (!range) {
    return null;
  }
  return { range, word: document.getText(range) };
}

function createCompletionItems(items, kind, detail) {
  return items.map((item) => {
    const completion = new vscode.CompletionItem(item, kind);
    completion.detail = detail;
    return completion;
  });
}

function provideCompletionItems(document, position) {
  const linePrefix = document.lineAt(position.line).text.slice(0, position.character);

  if (/^\s*>>>\s+[A-Z_]*$/.test(linePrefix)) {
    return createCompletionItems(metadata.blockKeywords, vscode.CompletionItemKind.Keyword, "MGO 块关键字");
  }

  if (/\$\{[A-Za-z0-9_]*$/.test(linePrefix)) {
    return createCompletionItems(metadata.parameterPlaceholders, vscode.CompletionItemKind.Variable, "参数化占位符");
  }

  if (/\{[A-Z_]*$/.test(linePrefix) && !/\$\{[A-Za-z0-9_]*$/.test(linePrefix)) {
    const envItems = createCompletionItems(metadata.environmentVariables, vscode.CompletionItemKind.Variable, "环境变量");
    const evalItem = new vscode.CompletionItem("EVAL:", vscode.CompletionItemKind.Function);
    evalItem.detail = "运行时动态表达式";
    return [...envItems, evalItem];
  }

  if (/^\s*\[[A-Z]*$/.test(linePrefix)) {
    return createCompletionItems(metadata.clients, vscode.CompletionItemKind.EnumMember, "客户端标签");
  }

  const clientCommandMatch = linePrefix.match(/^\s*\[([A-Z]+)\]\s*([A-Za-z0-9_-]*)$/);
  if (clientCommandMatch) {
    const client = clientCommandMatch[1];
    if (client === "EXP") {
      return createCompletionItems(metadata.assertions, vscode.CompletionItemKind.Event, "断言类型");
    }
    const commands = metadata.commandsByClient[client] || [];
    return createCompletionItems(commands, vscode.CompletionItemKind.Function, `${client} 命令`);
  }

  if (/\[(?:TSA|SET|TTS|VOI|OMS|NIS|NSE)\]SETVRCONFIG\s+[A-Z_]*$/.test(linePrefix)
    || /\[(?:TSA|SET|TTS|VOI|OMS|NIS|NSE)\]GET_VR_CONFIG\s+[A-Z_]*$/.test(linePrefix)) {
    return createCompletionItems(metadata.vrConfigs, vscode.CompletionItemKind.Constant, "VR 配置项");
  }

  const setParamMatch = linePrefix.match(/\[(TSA|NIS|HWK|TSS)\]SET_PARAM\s+([A-Z0-9_]*)$/);
  if (setParamMatch) {
    const client = setParamMatch[1];
    return createCompletionItems(getSetParamsForClient(client), vscode.CompletionItemKind.Constant, `${client} SET_PARAM 参数`);
  }

  if (/<timeout=[-0-9.]*$/.test(linePrefix)) {
    return createCompletionItems(["0", "1", "2", "5", "-1"], vscode.CompletionItemKind.Value, "timeout 值");
  }

  return undefined;
}

function provideHover(document, position) {
  const wordInfo = getWordAt(document, position);
  if (!wordInfo) {
    return undefined;
  }

  const { word, range } = wordInfo;

  if (metadata.blockKeywords.includes(word)) {
    return new vscode.Hover(new vscode.MarkdownString(`**${word}**\n\nMGO 块关键字。`), range);
  }

  if (metadata.clients.includes(word)) {
    return new vscode.Hover(buildClientHoverMarkdown(word), range);
  }

  if (metadata.environmentVariables.includes(word)) {
    return new vscode.Hover(new vscode.MarkdownString(`**${word}**\n\n内置环境变量，使用方式：\`{${word}}\``), range);
  }

  if (metadata.vrConfigs.includes(word)) {
    return new vscode.Hover(new vscode.MarkdownString(`**${word}**\n\nVR 配置项，可用于 \`SETVRCONFIG\` / \`GET_VR_CONFIG\`。`), range);
  }

  for (const [client, params] of Object.entries(metadata.setParamsByClient || {})) {
    if (params.includes(word)) {
      return new vscode.Hover(
        new vscode.MarkdownString(`**${word}**\n\n\`${client}\` 客户端的 \`SET_PARAM\` 参数枚举。`),
        range
      );
    }
  }

  if (metadata.assertions.includes(word)) {
    const expDoc = (metadata.expDocsByType && metadata.expDocsByType[word]) || getCommandDoc("EXP", word);
    const category = Object.entries(metadata.assertionCategories).find(([, values]) => values.includes(word));
    const md = new vscode.MarkdownString();
    md.appendMarkdown(`**${word}**\n\n`);
    if (expDoc && expDoc.summary) {
      md.appendMarkdown(`${expDoc.summary}\n\n`);
    } else {
      md.appendMarkdown("断言类型。\n\n");
    }
    if (category) {
      md.appendMarkdown(`分类：\`${category[0]}\`\n\n`);
    }
    if (expDoc && expDoc.syntax) {
      md.appendMarkdown("语法：\n");
      md.appendCodeblock(expDoc.syntax, "text");
    }
    if (expDoc && expDoc.params && expDoc.params.length > 0) {
      md.appendMarkdown("\n参数说明：\n");
      for (const param of expDoc.params) {
        if (param.name) {
          md.appendMarkdown(`- \`${param.name}\`：${param.description}\n`);
        } else {
          md.appendMarkdown(`- ${param.description}\n`);
        }
      }
    }
    if (expDoc && expDoc.example) {
      md.appendMarkdown("\n示例：\n");
      md.appendCodeblock(expDoc.example, "text");
    }
    return new vscode.Hover(md, range);
  }

  if (lookup.commandToClients.has(word)) {
    const clients = lookup.commandToClients.get(word);
    const current = getCurrentLineClientCommand(document, position);
    const client = current && current.command === word ? current.client : clients[0];
    const md = buildCommandHoverMarkdown(client, word);
    md.appendMarkdown(`\n适用客户端：\`${clients.join("`, `")}\``);
    return new vscode.Hover(md, range);
  }

  return undefined;
}

function validateDocument(document, diagnostics) {
  if (!isNanoMgoDocument(document)) {
    diagnostics.delete(document.uri);
    return;
  }

  const entries = [];

  const addDiagnostic = (lineNumber, start, end, message, severity = vscode.DiagnosticSeverity.Error) => {
    const range = new vscode.Range(lineNumber, start, lineNumber, end);
    entries.push(new vscode.Diagnostic(range, message, severity));
  };

  const envRegex = /\{([A-Z][A-Z0-9_]*)\}/g;

  for (let lineNumber = 0; lineNumber < document.lineCount; lineNumber += 1) {
    const rawLine = document.lineAt(lineNumber).text;
    const line = stripInlineComment(rawLine);
    const trimmed = line.trim();

    if (!trimmed) {
      continue;
    }

    // Allow standalone block-end markers and temporary auto-close placeholder while typing.
    if (/^\s*<<<\s*$/.test(line) || /^\s*>>>\s*<<<\s*$/.test(line)) {
      continue;
    }

    if (/^\s*>>>\s*/.test(line)) {
      if (/^\s*>>>\s*$/.test(line) || /^\s*>>>\s+\d+\s*$/.test(line)) {
        continue;
      }
      if (validBlockHeaderLineRe.test(line)) {
        continue;
      }
      if (/^\s*>>>\s+PARAMETER\s+\S+\s*$/.test(line)) {
        continue;
      }
      if (/^\s*>>>\s+PARAMETER\s*$/.test(line)) {
        addDiagnostic(lineNumber, rawLine.indexOf("PARAMETER"), rawLine.length, "PARAMETER 块缺少参数文件路径");
        continue;
      }
      addDiagnostic(lineNumber, 0, rawLine.length, "非法的块头写法");
      continue;
    }

    const commandMatch = line.match(/^\s*\[(\w+)\](\S+)\s*(.*?)(?:\s*<timeout=([-\d.]+)>)?\s*$/);
    if (commandMatch) {
      const [, client, command, paramsStr, timeoutStr] = commandMatch;
      const clientIndex = rawLine.indexOf(`[${client}]`);
      if (!metadata.clients.includes(client)) {
        addDiagnostic(lineNumber, clientIndex + 1, clientIndex + 1 + client.length, `未知客户端: ${client}`);
        continue;
      }

      const validCommands = client === "EXP" ? metadata.assertions : (metadata.commandsByClient[client] || []);
      const commandIndex = rawLine.indexOf(command, clientIndex + client.length + 2);
      if (!/\$\{[A-Za-z0-9_]+\}/.test(command) && !validCommands.includes(command)) {
        addDiagnostic(lineNumber, commandIndex, commandIndex + command.length, `客户端 ${client} 不支持命令或断言: ${command}`);
      }

      if (timeoutStr !== undefined && Number.isNaN(Number(timeoutStr))) {
        const timeoutStart = rawLine.lastIndexOf(timeoutStr);
        addDiagnostic(lineNumber, timeoutStart, timeoutStart + timeoutStr.length, `非法 timeout 值: ${timeoutStr}`);
      }

      if ((command === "SETVRCONFIG" || command === "GET_VR_CONFIG") && client !== "EXP") {
        const params = paramsStr.trim().split(/\s+/).filter(Boolean);
        if (params.length > 0) {
          const configName = params[0];
          if (!metadata.vrConfigs.includes(configName)) {
            const configIndex = rawLine.indexOf(configName, commandIndex + command.length);
            addDiagnostic(lineNumber, configIndex, configIndex + configName.length, `未知 VR 配置项: ${configName}`);
          }
        }
      }

      if (command === "SET_PARAM" && client !== "EXP") {
        const params = paramsStr.trim().split(/\s+/).filter(Boolean);
        const validSetParams = getSetParamsForClient(client);
        if (params.length > 0 && validSetParams.length > 0) {
          const paramName = params[0];
          if (!validSetParams.includes(paramName)) {
            const paramIndex = rawLine.indexOf(paramName, commandIndex + command.length);
            addDiagnostic(lineNumber, paramIndex, paramIndex + paramName.length, `客户端 ${client} 不支持 SET_PARAM 参数: ${paramName}`);
          }
        }
      }

      let envMatch;
      while ((envMatch = envRegex.exec(line)) !== null) {
        if (!metadata.environmentVariables.includes(envMatch[1])) {
          const envStart = rawLine.indexOf(envMatch[0]);
          addDiagnostic(lineNumber, envStart, envStart + envMatch[0].length, `未知环境变量: ${envMatch[1]}`, vscode.DiagnosticSeverity.Warning);
        }
      }

      continue;
    }

    addDiagnostic(lineNumber, 0, rawLine.length, "无法识别的 DSL 语句", vscode.DiagnosticSeverity.Warning);
  }

  validateBlockDelimiters(document, addDiagnostic);

  diagnostics.set(document.uri, entries);
}

function provideDocumentSymbols(document) {
  const symbols = [];
  const blockStack = [];

  for (let i = 0; i < document.lineCount; i += 1) {
    const line = document.lineAt(i).text;
    const startMatch = line.match(blockSymbolLineRe);
    if (startMatch) {
      const rawName = startMatch[1] || "TEST";
      const name = rawName.startsWith("PARAMETER") ? rawName : rawName;
      blockStack.push({ name, line: i });
      continue;
    }
    if (/^\s*<<<\s*$/.test(line) && blockStack.length > 0) {
      const block = blockStack.pop();
      const range = new vscode.Range(block.line, 0, i, document.lineAt(i).text.length);
      const selectionRange = new vscode.Range(block.line, 0, block.line, document.lineAt(block.line).text.length);
      symbols.push(new vscode.DocumentSymbol(block.name, "MGO Block", vscode.SymbolKind.Namespace, range, selectionRange));
    }
  }

  return symbols;
}

function activate(context) {
  const diagnostics = vscode.languages.createDiagnosticCollection("nano-mgo");
  context.subscriptions.push(diagnostics);

  if (vscode.window.activeTextEditor) {
    validateDocument(vscode.window.activeTextEditor.document, diagnostics);
  }

  context.subscriptions.push(
    vscode.workspace.onDidOpenTextDocument((doc) => validateDocument(doc, diagnostics)),
    vscode.workspace.onDidChangeTextDocument((event) => validateDocument(event.document, diagnostics)),
    vscode.workspace.onDidCloseTextDocument((doc) => diagnostics.delete(doc.uri))
  );

  context.subscriptions.push(
    vscode.languages.registerCompletionItemProvider(
      { language: metadata.languageId },
      { provideCompletionItems },
      "[",
      "{",
      "$",
      " ",
      "_"
    )
  );

  context.subscriptions.push(
    vscode.languages.registerHoverProvider(
      { language: metadata.languageId },
      { provideHover }
    )
  );

  context.subscriptions.push(
    vscode.languages.registerDocumentSymbolProvider(
      { language: metadata.languageId },
      { provideDocumentSymbols }
    )
  );
}

function deactivate() {}

module.exports = {
  activate,
  deactivate,
};
