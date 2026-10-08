# memory-ledger

[Claude Code](https://code.claude.com) 外掛：把 auto-memory 裡的專案筆記變成可追蹤的帳本。

- **Dashboard**：`memory-ledger generate` 從 `project_*.md` 的 `status`、`observe_until`、`checkpoints`、`chores` frontmatter 產生 `dashboard.md`，列出哪些逾期、哪些今天到期、哪些在觀察中、進行中或待辦。
- **驗證器**：`memory-ledger validate` 抓出平常沒人發現的問題：無效的 `status`（專案會靜默從 dashboard 消失）、無法解析的查核點日期或沒有縮排的清單項目（永遠不會到期）、失效的 `[[wikilink]]`，以及兩份索引都走不到的 memory 檔。
- **Hook**：PostToolUse hook 會在寫入每個 `project_*.md` 的當下進行驗證。
- **Skills**：`memory-ledger:conventions`（規約，供 Claude 遵守）與 `memory-ledger:due`（每日回查流程，產出 PASS/FAIL/BLOCKED 表）。

純 Python 標準函式庫，沒有任何相依套件。

## 安裝

```text
/plugin marketplace add NeoWYM/memory-ledger
/plugin install memory-ledger@memory-ledger
```

依 Claude Code 外掛文件，外掛啟用期間 `bin/` 目錄會加入 Bash 工具的 PATH，Claude 可直接以 `memory-ledger` 執行。若找不到，或要在自己的 shell 使用，請執行外掛安裝目錄中的腳本。已安裝的外掛會複製到 `~/.claude/plugins/cache/<marketplace>/<plugin>/<version>/`（見 [plugin loading](https://code.claude.com/docs/en/plugins/loading)）；若設定了 `CLAUDE_CODE_PLUGIN_CACHE_DIR`，它會取代 `~/.claude/plugins` 這個根目錄（見[環境變數文件](https://code.claude.com/docs/en/env-vars)）。下列片段會挑選已安裝的最高版本，找不到時印出訊息並以 `exit 1` 結束；在互動式 shell 中請存成腳本或用 `bash -c` 執行，不要直接貼上，以免關閉 terminal：

```bash
root="${CLAUDE_CODE_PLUGIN_CACHE_DIR:-$HOME/.claude/plugins}"
dir=$(for d in "$root"/cache/*/memory-ledger/*/; do
  [ -f "${d}scripts/memory_ledger.py" ] && printf '%s %s\n' "$(basename "$d")" "$d"
done | sort -V -k1,1 | tail -1 | cut -d' ' -f2-)
[ -n "$dir" ] || { echo "memory-ledger plugin not found under $root/cache" >&2; exit 1; }
python3 "${dir}scripts/memory_ledger.py" validate --memory-dir <dir>
```

或把 `bin/memory-ledger` 連結到 PATH 內。

## Frontmatter

欄位放在 project memory 檔的 `metadata:` 底下（與 Claude Code 寫入 memory 檔的方式一致）。清單項目必須縮排。

```yaml
---
name: example-project
description: 顯示在 dashboard 上的一句話
metadata:
  type: project
  status: observing
  observe_until: 2026-12-01
  checkpoints:
    - 2026-11-20 | verify the first scheduled run produced output
  chores:
    - remove the temporary branch
---
```

| 欄位 | 意義 |
| --- | --- |
| `type: project` | 必填，檔案才會被追蹤。 |
| `status` | `todo`、`active`、`observing`、`done` 或 `superseded`。`done` 與 `superseded` 是終態，會離開 dashboard；其他值一律視為驗證錯誤。 |
| `observe_until` | `YYYY-MM-DD`。該專案自己的觀察期，一個專案最多一個；過期後標為逾期。 |
| `checkpoints` | `YYYY-MM-DD \| 要查什麼` 的清單。有日期的子項目，獨立成一個區段，逾期或今日到期會標示。 |
| `chores` | 無日期的收尾事項清單。即使專案已是終態也照樣顯示。 |

完整規則與背後的理由見 [`skills/conventions/SKILL.md`](skills/conventions/SKILL.md)（英文）。

## 命令列

```text
memory-ledger generate --memory-dir DIR [--output PATH] [--locale en|zh-TW] [--today YYYY-MM-DD]
memory-ledger validate --memory-dir DIR [FILES...]
memory-ledger hook          # 從 stdin 讀取 PostToolUse JSON
```

- 記憶目錄不會從工作目錄推導。請傳入 `--memory-dir` 或設定 `MEMORY_LEDGER_DIR`；兩者皆無時，`generate` 與 `validate` 會拒絕執行（exit 2）。
- `generate` 預設寫入 `<memory-dir>/dashboard.md`，可用 `--output` 改路徑，發現的問題以警告印出。成功 exit 0，用法或寫入錯誤 exit 2。
- `validate`：乾淨 exit 0，有任何發現 exit 1，用法錯誤（沒有記憶目錄、檔名參數不存在）或內部錯誤 exit 2。帶檔名參數時只檢查那些檔案，並略過索引檢查。
- `hook` exit 0（沒有要回報的，或任何內部錯誤）或 exit 2（發現的問題寫到 stderr）。
- `--today` 可覆寫日期（測試與可重現輸出用）。

## 語系

dashboard 的文字由 `--locale` 或 `MEMORY_LEDGER_LOCALE` 決定，可用值為 `en`（預設）與 `zh-TW`（台灣繁體中文）。多數驗證器訊息兩種語系皆為英文，有三處會本地化：零縮排清單項目的訊息、「查核點格式錯誤」訊息中的佔位文字，以及 hook 提示。若有工具依標題文字讀取 dashboard，請固定語系；各區段標題前的 emoji 在所有語系都相同。

## Hook 行為

`hooks/hooks.json` 為 `Write|Edit|MultiEdit` 註冊 PostToolUse hook。外掛的 hook 會在每個專案觸發，因此刻意保守：

- 只有當 `tool_input.file_path` 符合 `*/memory/project_*.md`，且該檔 frontmatter 為 `type: project` 才動作，記憶目錄就是該檔的上層目錄；其他檔案（例如無關的 `memory/` 資料夾裡的筆記）一律忽略。
- 只驗證被改的那一個檔（status、checkpoints、清單縮排、wikilink），不會因為別的檔有舊問題而打斷不相關的編輯。
- 有發現時以 exit 2 將內容寫到 stderr（Claude 看得到）；否則 exit 0 且無任何輸出，輸入格式錯誤或缺欄位時也一樣。

## 套用到既有的記憶目錄

1. 執行 `memory-ledger validate --memory-dir <dir>` 並閱讀結果。舊檔通常需要補 `status`（已完成的用 `done`），以及在 `MEMORY.md` 或 `archive_index.md` 補上連結。
2. 在要追蹤的 project 檔補上 `status`（視情況補 `observe_until`、`checkpoints`、`chores`）。
3. 執行 `memory-ledger generate --memory-dir <dir>`。
4. 把已結案專案的連結從 `MEMORY.md` 搬到 `archive_index.md`，讓常載入的索引維持精簡。驗證器把兩個檔案合起來視為「索引」。

## 開發

```text
python3 -m unittest discover -s tests
claude plugin validate .
```

測試使用 `tests/fixtures` 下的合成記憶目錄，以及 `tests/golden` 下的 golden dashboard。

## 限制

- 依賴 Claude Code auto-memory 的檔案格式：以 `---` 開頭的 frontmatter 區塊，且欄位巢狀在 `metadata:` 底下。若該格式改變，解析器可能需要更新。
- frontmatter 解析器刻意做得很小，不是完整的 YAML 解析器。它只讀扁平的 `key: value` 行與兩個清單欄位；沒有縮排的清單項目會被忽略，因此驗證器會把它回報為問題。
- 索引連結偵測只認 `(name.md)` 形式，名稱限英數字、底線、連字號與斜線。
- Hook 只看得到 Write、Edit、MultiEdit 工具的編輯，看不到透過 shell 指令做的修改。
- 缺少 `type: project` frontmatter 的 `project_*.md` 檔，dashboard 與所有逐檔檢查都看不到它。不帶檔名的 `validate` 與重新產生時的警告會列出這類檔案；hook 則直接忽略。
- `checkpoints` 與 `chores` 必須是清單。純量值（如 `checkpoints: 2026-10-15 | text`）會被回報為問題，因為解析器會忽略它；沒有項目請寫 `[]`。

## 授權

MIT，見 [LICENSE](LICENSE)。

[English README](README.md)
