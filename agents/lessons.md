# 錯誤知識庫（開工先讀；同樣的錯不得再犯）

每條：錯誤 → 原因 → 防止方式 → 日期與來源。新錯誤追加在最下面。

同一個錯第二次出現，讀文件已證明擋不住：必須加進 `~/.agents/guards/` 的機械檢查（PreToolUse／Stop hook），並在該條加 `guard:` 標記寫明哪支腳本、哪條規則擋它。已升級的：`pkill -f`／`pgrep -f` → write_guard.py pkill-full；手寫或直接改 `*.checkpoints.jsonl`（含時間戳用猜） → write_guard.py checkpoint-write；對未提交檔 `git checkout --`／`git restore` → write_guard.py discard-uncommitted。

1. **只查一個程序就斷定「只有我在改這個工作樹」**
   - 原因：另一個 Codex 程序已經在同一個工作樹跑了 35 小時，我只看到其中一個。
   - 防止：宣稱擁有權前，列出所有工作目錄在該工作樹的 codex、claude、godot 程序；列不出就寫「未查證」。
   - 2026-09-28 Fluke。

2. **短時間實跑綠燈就說 BOT 流程正常**
   - 原因：5 分鐘實跑沒有任何淘汰，淘汰後補位從未被驗證。實際跑 30 分鐘後，10 張桌全部停住。
   - 防止：常駐牌桌要跑到至少出現淘汰和補位，每 5 分鐘記錄有幾張桌在開局；「沒發生」不等於「驗過」。
   - 2026-09-28 Fluke。

3. **沒先比較分支差異就開始合併**
   - 原因：develop 和本機分支從 3 月就分開，各自做了半年的後端。一合併就出現 58 個檔案衝突。
   - 防止：合併前先看兩邊的共同起點日期、各自改了多少，以及兩邊都改到的檔案；兩邊都有大量改動時，先請使用者決定以哪一邊為主。
   - 2026-09-28 Fluke。

4. **Godot 網頁版中文變方框，圖片也讀不到**
   - 原因：瀏覽器版讀不到系統字型。程式用 `Image.load` 讀原始 png，但打包後只剩匯入後的格式。
   - 防止：打包網頁版要附上中文字型。讀 `res://` 圖片一律用 `load()`，不要讀原始檔。
   - 2026-09-28 Fluke。

5. **本機推理模型逾時，沒有任何輸出**
   - 原因：模型先在內部推理了 3,500 多個字詞才要回答，已經超過 240 秒的時限。
   - 防止：`localai` 預設關閉隱藏推理並限制輸出長度；逾時先看 `journalctl -u ollama` 的產生字數，不要直接重送。
   - 2026-09-28。

6. **為了 Godot 模板，差點下載整個 1GB 的壓縮檔**
   - 防止：大型遠端壓縮檔只取需要的檔案，用 `~/tools/remote_zip_extract.py`，只下載目錄和選中的那幾個檔。
   - 2026-09-28。

7. **重啟隔離 Gateway 時被拒絕啟動，錯誤是 funded-seat recovery**
   - 原因：舊測試資料庫裡還有桌上籌碼。
   - 防止：隔離測試要換新的測試資料庫，只刪自己建立的庫，不動 25432 和 8080 的服務。
   - 2026-09-28 Fluke。

8. **本地 code 模型只拿到片段時會漏行、改錯語意**
   - 原因：兩次派 qwen3-coder 修小段 Rust。一次在回傳真假值的函式裡用 `?`，會編譯失敗；一次把原本的程式行刪掉，也沒修到錯誤。
   - 防止：派工要給完整函式和確切的編譯錯誤原文。回來的修改一定要經過編譯、測試和差異檢查才採用。機械性修正先用 `cargo clippy --fix` 這類工具，不要先派模型。
   - 2026-09-28 Fluke。

9. **把 Claude 內建的 `rg` 當成系統已經安裝**
   - 原因：Claude 的 shell 裡 `rg` 是它自己提供的函式，系統本身沒有裝 ripgrep。檢查腳本在自己的環境執行時找不到 `rg`，所有檢查項目都被判定失敗。
   - 防止：宣稱工具已經安裝前，先用 `bash -lc 'command -v <工具>'` 在乾淨的 shell 裡確認。
   - 2026-09-28 已用 apt 安裝到 /usr/bin/rg。

10. **寫檔前沒確認檔案是否已經存在**
   - 原因：新增 Fluke 的 `.githooks/pre-push` 時直接覆寫，沒發現 develop 本來就有一份，而且因為 `core.hooksPath` 從沒設定，那份檔案一直沒有執行過。
   - 防止：寫入任何路徑前，先用 `git ls-files <路徑>` 或 `ls` 確認；如果已經存在，先讀內容再決定要合併還是取代，並在回報時說明。
   - 2026-09-29 Fluke。

11. **本機寫程式模型拆 200 行以上的函式會亂編型別**
   - 原因：qwen3-coder 拆 238 行的麻將函式時，編了不存在的型別，型別也對不上。拆 135 行的函式則修 3 處就能用。
   - 防止：100 到 150 行的函式先派本機模型；更長的，或本機模型失敗一次的，改派能讀整個 repo、能自己編譯的代理，監督者負責驗收。
   - 2026-09-29 Fluke。

12. **測試遇到準備步驟失敗就提早 `return`，結果變成永遠通過**
   - 原因：新增的 BOT 棄牌測試，用 `let ... else { return }` 解析牌名。解析失敗時測試直接結束，故意把答案改錯也照樣通過。
   - 防止：測試裡的準備步驟失敗一律要讓測試失敗，不可以提早結束。每個新測試都要做陰性對照：故意改錯答案，確認它會失敗。
   - 2026-09-30 Fluke。

## 2026-09-30 測試失敗卻照樣提交（JobResearch）
- 錯：`uv run pytest -q | tail -1 && git commit`，管線結束碼是 tail 的，測試失敗仍提交。
- 防：提交前的檢查鏈先 `set -o pipefail`，或不要把測試接管線；以測試自身結束碼決定是否提交。

## 2026-09-30 陰性對照後測試讀到舊編譯檔（JobResearch）
- 錯：用 sed 在同一秒內把斷言數字改壞又改回，檔案大小相同，pytest 斷言改寫快取以為沒變，出現假失敗。
- 防：陰性對照改回後先刪 `__pycache__`，或用 `-p no:cacheprovider` 並確認檔案內容再判斷。

## 2026-09-30 測試環境放在 /tmp，事後照文件跑全失敗（Helios 券商串接）
- 錯：券商測試的隔離環境建在 `/tmp/helios-broker-contract-20260924`，被清掉後，文件記的指令用系統 Python 只跑 59 項、45 項失敗；LOOP 仍寫 136/136。
- 防：通過數要連同「用哪個環境、裝了哪些套件和版本」一起記；環境放在不會被清的位置，或記一行可重建的安裝指令。

## 2026-09-30 本機寫程式模型編造不存在的方法（Helios 券商串接）
- 錯：localai 寫的價格檢查用 `float.is_finite()`，Python 浮點數沒有這個方法；只有非法價格的測試會短路通過，合法價格反而會當掉。
- 防：本機模型產出的程式，監督者要逐行找「呼叫的方法是否真的存在於該型別」，並一定跑到合法輸入的路徑；另一次同日草稿則整段刪除既有檢查，套用前一律比對差異。

## 2026-09-30 SDK 與手冊也放在 /tmp，全部遺失（Helios 券商串接）
- 錯：元大 SDK、群益手冊、凱基 wheel、dotnet 探測環境都下載到 /tmp，重開機後消失；只剩文件裡的 SHA256。
- 防：券商 SDK、手冊這類要重複引用的證據檔，放在不會被清的位置（例如 ~/.cache 下固定目錄）並在文件記路徑與 SHA256；/tmp 只放可丟棄的中間檔。

## 2026-09-30 排程腳本被編輯後失去執行權限，月排程會靜默不跑（account_linker）
- 錯：dbb 上 `monthly_fav_rebuild.sh` 9/1 手動修改後權限變成 644；crontab 用 `flock ... 腳本路徑` 直接執行，10/1 03:00 會因權限不足失敗，狀態檔仍是上月成功，看門狗也判定正常，無任何告警。
- 防：接手任何排程前，對 crontab 內每個被直接執行的腳本跑 `test -x`；修改排程腳本後重新 `chmod 755` 並讀回權限。

## 2026-10-01 部署腳本失敗時把遊戲停著沒重開（Fluke essence）
- 錯：換版腳本先停服務再退籌碼，退籌碼失敗就直接結束；遊戲停了約 10 分鐘。原本也沒在真實資料上試過麻將點數桌。
- 防：會「先停服務」的腳本，每個失敗分支都要把服務重新啟動。第一次自動部署前，先把正式資料複製到用完即丟的資料庫，在上面完整跑一次換版步驟。

## 2026-10-01 Claude shell 的 find 不是 GNU find，時間條件靜默失效（家目錄 /tmp 清理）
- 錯：用 `find DIR -newermt '-24 hours'` 判斷「24 小時內有沒有修改」；Claude shell 的 `find` 是 bfs，不認得這種寫法，報錯後輸出空白，結果每個資料夾都被當成舊的而刪除（共 15 個、0.3MB）。
- 防：時間或條件篩選一律用 `/usr/bin/find`，或寫成 Python；刪除前先把「要刪的清單」印出並抽查一筆最新的，確認篩選真的有作用。

## 2026-10-01 用 pkill -f 停服務，連自己的 shell 一起殺掉（ai-mall #2778）
- 錯：在同一行 bash 指令裡用 `pkill -f "crossec-hotfix-2778/...tsx.*src/index.ts"`；這行 bash 的命令列本身也含這段字串，pkill 殺掉自己，指令停在中途（exit 144），陰性對照改壞的檔案沒被還原。
- 防：停服務改成「先列出 PID、排除自己，再 kill PID」，寫成獨立腳本執行；任何「先改壞、後還原」的流程，還原步驟放在 trap 或另一個指令，執行後立刻 `git status` 確認。
- guard: write_guard.py pkill-full

## 2026-10-01 `pkill -f` 殺掉了自己所在的 shell（Fluke）
- 錯：用 `pkill -f 'GATEWAY_PORT=18197'` 關測試程式，但這個字串也出現在同一個 shell 指令裡，結果 shell 被殺，後面的紀錄和提交都沒做。
- 防：關程式用 `pgrep <程式名>`（不要加 -f），再比對 `/proc/<pid>/exe` 的完整路徑。`pgrep -f` 和比對 cwd 都會選到自己的 shell（同日重犯一次）。
- guard: write_guard.py pkill-full

## 2026-10-01 JobResearch 陰性對照意外讀到原工作樹
- 錯：隔離副本放在 repo 的 data 下，pytest 向上讀原 pyproject 的 pythonpath，改壞副本仍測到原版而通過。
- 防：陰性對照明確指定獨立 --rootdir、-c /dev/null、PYTHONPATH；先確認匯入模組的 __file__ 指向隔離副本，並保存失敗輸出。

## 2026-10-01 找 QA 測試帳號只搜文字檔，沒搜試算表（ai-mall #2778）
- 錯：QA 帳密表在本機的 `新零售QA.xlsx`，我只搜了 .md／.env／筆記，就回報「本機找不到」，來回問了使用者四輪。
- 防：找帳號、環境表這類資料時，第一輪就用 `/usr/bin/find ~ -iname '*.xlsx'` 連試算表一起搜；確定搜過試算表才可以說找不到。

## 2026-10-01 瀏覽器工具會把腳本內容原樣印出，測試密碼因此外露（ai-mall #2778）
- 錯：把測試帳號密碼寫進 Playwright 腳本檔再執行，工具回傳時把整段腳本（含密碼）印進對話。
- 防：登入改用畫面表單由工具逐欄填，或先用 API 取得登入狀態再帶進瀏覽器；不要把密碼放進會被回印的腳本。印出後要告知使用者並換掉密碼。

## 2026-10-01 `sudo -g 群組` 沒有變成 root，收集程式其實以一般帳號執行（Aletheia 本機監控）
- 錯：想讓 root 寫出的檔案給自己的群組讀，用 `sudo -n -g cash python3 ...`；只給 `-g` 時 sudo 仍用原帳號執行，結果「誰在呼叫模型」全部變成未取得。
- 防：需要 root 就不要只加 `-g`；執行後先讀輸出裡的身分欄位或檔案擁有者確認。要給別的帳號讀，用 systemd 的 `Group=` 或輸出後再改群組。

## 2026-10-01 把「看不到」的值加總成 0（Aletheia 本機監控）
- 錯：依應用加總 GPU 記憶體時，把讀不到的程式當 0 加進去，頁面顯示「放在 GPU 的有 0 MB」，實際是 40 GB。單元測試全過，實跑才發現。
- 防：加總前先看有沒有未知值；只要有一筆未知，合計就是未知。每個合計欄位都要有一條「含未知成員」的測試。

## 2026-10-01 JobResearch 只按收據檔名搜尋而漏掉 interface 收據
- 錯：只搜含receipt的檔名，誤將Appier/Tomofun原收據標為未定位；實際在interface JSON。
- 防：對帳優先按來源URL與body SHA搜尋所有已存JSON/JSONL，再核來源、HTTP狀態、總筆數、時間；檔名不能當收據是否存在的證據。

## 2026-10-01 JobResearch 匯入計分順序與已存快照不同，且未查DB先猜同步錯誤
- 錯：匯入以dict加入順序計分，DB保存按job_id排序，真網頁重算陣列順序不同；未讀實際DB就猜對帳沒同步，判斷錯誤。
- 防：新結果一律從已保存快照payload讀回後計分；失敗先比較实际DB欄位及逐鍵差異，不依工具行號或預想猜原因。

## 2026-10-01 JobResearch 外部依序請求未逐次判斷錯誤
- 錯：五URL同exec依序呼叫但等全部回來才檢視；Indeed首頁Cache miss後仍讀另一頁。
- 防：有來源停止相依性時，每次回應先檢視；外部錯誤立即停止該來源範圍，不把多URL當独立批次。

## 2026-10-01 JobResearch 搜尋收據用單一命令列參數保存超限
- 錯：五份搜尋完整JSON直接傳exec argv，觸發E2BIG；查詢已完成但保存失敗。
- 防：大payload先store，再分段stdin寫入；不要放單一argv。失敗先從本session已返回literal恢复，不重搜。此次恢復五份/166001bytes，0重複請求。

## 2026-10-01 JobResearch 對select option等待visible造成假逾時
- 錯：option已存在但Playwright默认visible等待逾時。
- 防：option資料載入用state=attached，再select_option；不要把option不可見當頁面未載入。此次原因確認後重驗83→84通過。

## 2026-10-01 JobResearch 本機模型修函式未附原函式
- 錯：提示寫提供完整sourceSalary但漏附檔，模型自行猜salary_raw為number，改壞原結構。
- 防：送出前檢查附件或prompt包含完整函式；草稿先核既有資料型別。此次拒絕首稿，補完整函式再審，監督修early-return遺漏。

## 2026-10-02 JobResearch 忽略網址查詢代號造成假職缺關聯
- 錯：對帳刪掉整段query，把不同Indeed jk及yes123 job_id連到既有職缺，三筆被錯誤略過。
- 防：來源關聯保留所有未知query、重複/空值及fragment，僅移除明確追蹤字；用真實不同職缺URL做測試與隔離故障對照。URL相同也不是內容去重證據。

## 2026-10-02 JobResearch 匯入已提交後run建立失敗
- 錯：未核events函式參數，匯入提交後呼叫events(conn)缺project_id，run未建立。
- 防：先查既有函式簽名；部分失敗先查batch、snapshot與run，確認既有請求內容後只補缺步驟，不重送匯入。本次空projects不需讀history，補run92，舊run91不變。

## 2026-10-02 JobResearch 瀏覽器驗證腳本誤判抽樣數
- 錯：wait_for_function字串用arguments無函式包覆而ReferenceError；又假設3query各2slot就一定6unique，實際backend跨query重複只有5。
- 防：Playwright參數用箭頭函式與arg=；分開核對query_slots及獨立URL數。失敗若POST已保存先查實際紀錄，再幂等重用，不以測試錯誤判產品失敗。

## 2026-10-02 JobResearch 依摘要猜DB結構與瀏覽器一括號錯失結果
- 錯：誤用decision_snapshots表、dict jobs與摘要SHA，真表snapshots/payload list/SHA尾343866；英文頁完成載入後evaluate_all多括號導致只保存error。
- 防：先PRAGMA及run.snapshot_id取真值，檢查payload型別；逐段先保存已成功body/status再計算links，JS先核括號。錯誤不能推論頁面不存在或封鎖。

## 2026-10-02 JobResearch 延後讀瀏覽器response造成原文body消失
- 錯：把response物件留到頁面載入後才read body，Network.getResponseBody不可用；重複JS括號錯也造成首輪未保存。
- 防：到達時即時保存有限payload，逐項先落盤；短小DOM讀取用locator/Python避免eval拼字，多步不得一個大dict全成全敗。原始body成功不等結構payload成功。

## 2026-10-02 JobResearch API列表對帳誤含當前檔
- 錯：glob binance*25-v1.json同時讀新offset125檔，將當前25筆判成先前重複。
- 防：明確排除當前response，核所有先前API list原文與DB snapshot兩份獨立集合；不因本機對帳錯誤重抓外部來源。

## 2026-10-02 JobResearch 市場設定與來源停止核對
- 錯：未先核params地區/職階空，回報分類有效量易被解讀台灣資深；另查官方Github文件漏已存github403停止。
- 防：每次市場量附實際region/level與scope；新情境另保存舊結果。任何外部讀取（含工具瀏覽）先核host與來源停止，技術文件也適用；不得切工具重送停止來源。

## 2026-10-02 JobResearch 官方API收據解析草稿捏造shape
- 錯：只給口頭欄位規格，模型仍把dict收據寫成attributes、list原文寫成content/count包裝；測試又編固定hash/bytes。
- 防：附實際最小JSON fixture與完整原函式；實際body計算hash/bytes，先跑成功路徑及真5筆，再測錯source/time/內容。不同歷史formatter只允許空白正規化，比全文不容許字詞異動。

## 2026-10-02 JobResearch cached全來源錯當LinkedIn與部分成功復原
- 錯：先保存五typed來源，再全cached讀回；既有fallback把Greenhouse JSON當LinkedIn HTML而失敗，receipt檔/run未建立。
- 防：先查來源種類與指定≤25job_ids，明確dispatch，不用else猜LinkedIn。部分失敗先核DB批次/snapshot/observations，只補讀回與run，不重匯；全測綠不替代真DB全部來源驗收。

## 2026-10-02 JobResearch 原測試假收據與cache action承襲
- 錯：新增row id/hash校驗後，舊Cake fixture沒payload jobid且用fixture-sha，造成full測試失敗；原setdefault action可能承襲舊保留標籤。
- 防：測試fixture帶完整身份、用真raw計hash，不弱化production校驗；重解析action直接指定，不讓舊payload標籤當本次行為。實際來源522hash全相符，陰性unknown fallback3fail。

## 2026-10-02 JobResearch 採用草稿混淆代號與筆數／交易鍵
- 錯：模型將1至25筆誤寫為整數ID範圍、list當dict，還自訂ValueError；保存稿用base_id取代batch_id且漏BEGIN IMMEDIATE。均未採入正式版本。
- 防：固定實際型別與成功fixture，核builtin例外、來源列表轉map、唯一批次鍵及交易開頭；測相同批次重用、不同请求拒绝與中途寫失敗整體rollback。來源：source-adoption-supervisor-review-v1.json。

## 2026-10-02 JobResearch 分類範圍變數與查詢名額變數撞名
- 錯：sampling新增selected分類list，但內層既有selected查詢去重set覆寫它，輸出set導致JSON保存失敗；full首輪4fail。
- 防：跨層值使用具體category_scope與query selected不同名稱，實際保存成功路徑先驗；測試最小runs fixture新增正式parameters欄，不放寬production schema。修後49target/645fullpass，舊frame相容。

## 2026-10-02 JobResearch 來源盤點重複長URL輸出造成60秒逾時
- 錯：25筆來源盤點要求回印完整URL，模型在60秒已產生1274tokens仍未完成，CLI空輸出。
- 原因：Ollama紀錄約25.43tokens/sec、上下文4002未截斷、OOM0，屬輸出長度超過期限，不是記憶體不足；取消後allslotsidle。
- 防：明列穩定索引，由模型只回索引與短代碼，程式回接原URL；先核取消與資源再換輸出規格，不原樣重送。本輪400token版本25索引全核，來源限制不由模型解除。證據：balanced-nine196-triage-timeout-diagnosis-v1.json。

## 2026-10-02 JobResearch資格details未展開誤判內容缺失
- 錯：inner_text在details收合時不含內文，結果143已建立但assert失敗。
- 防：先保存POST收據，再展開內外details讀可見文字；失敗只讀既有run驗證，不重POST。

## 2026-10-02 JobResearch 市場巢狀結果輸出過大
- 錯：直接將完整result/quality列印及交模型，包含原文群組造成大量輸出與CLI輸入限制；縮減一次仍保留categories內原文。
- 防：先選明確scalar欄位與category計數/理由，不輸出groups或分類內職缺全文；先核bytes與結構後派工。原文完整版本只落盤，模型改送精簡固定欄位。

## 2026-10-02 JobResearch 語意核對誤用localai code角色
- 錯：用code處理職缺判讀；目前code是qwen3-coder，連續輸出未要求的程式而非結論。
- 防：先查localai roles；職缺語意審查使用review角色，保留原文監督；不能把仲介當client或根據金額猜年薪。review仍須修科系與引句錯誤，不能宣稱模型已普遍可靠。

## 2026-10-02 JobResearch廣列程序暴露無關服務連線參數
- 錯：ps -C python args列出其他服務含憑證連線。
- 防：先在本機按精確module匹配，僅輸出屬於任務的PID/cwd/command；不打印無關程序參數。已告知使用者輪替，未再次引用憑證。

## 2026-10-02 JobResearch官方原文formatter不一致
- 錯：新批regex去HTML保留entities，與既有BeautifulSoup官方收據校驗式不同，5筆bad desc。
- 防：官方同來源复用既有canonical解析方式；匯入前先驗原文綁定。不得改guard容納差異，從保存原API修新版本且保留舊快照。

## 2026-10-02 ai-mall #2771 Edit 的唯一比對字串落在錯的函式
- 錯：要改 usePosCheckout 的 onError，用「onError 那行＋結尾＋下一個 export」當比對字串；檔內多個 hook 有同一行，唯一命中的是前一個函式，改錯地方。tsc 報 qc 未定義才發現。
- 防：比對字串要含目標函式自己的名稱或函式內獨有的前一行；改完先讀回該函式再跑檢查。

## 2026-10-02 ai-mall #2771 用 pgrep -f 比對字串殺行程時殺到自己的 shell
- 錯：迴圈用 pgrep -f 'tsx watch src/index.ts' 再比工作目錄；執行中的 shell 命令列本身含這段字串且工作目錄相同，被自己 kill，後半段命令沒跑。
- 防：停行程用程序名（pgrep -x node）加 /proc/PID/cwd 完全相等，並在別的目錄下執行；不要用會比對到自己命令列的 -f 字串。
- guard: write_guard.py pkill-full

## 2026-10-02 ai-mall dev-up.sh 把被別的 worktree 佔用的 3000 埠當成空的
- 錯：腳本用 lsof 查埠，查不到別的 next-server 佔的 *:3000，網頁啟動失敗（EADDRINUSE），後面的檢查卻打到別人的網頁。
- 防：跑完先用 ss -ltnp 查監聽行程的工作目錄是不是本 worktree；不是就自己挑埠手動起。共用的本機資料庫 crossec 結構太舊時，另建專用資料庫再 migrate＋seed，不改共用庫。

## 2026-10-02 進度紀錄的時間用猜的，寫成了未來時間（Aletheia 本機監控）
- 錯：寫 checkpoint 時沒有看時鐘，憑印象填 `05:10Z`，實際才 `01:05Z`，三筆紀錄的時間都在未來。
- 防：每次寫紀錄前先跑 `date -u +%Y-%m-%dT%H:%M:%SZ`，直接用輸出；不要用對話裡的印象推算。
- guard: write_guard.py checkpoint-write（只准經 cash-rule-checkpoint 寫入，時間由工具蓋）

## 2026-10-02 CI 用浮動的 stable Rust，上游升版後檢查突然失敗（Fluke）
- 錯：GitHub Actions 用 `dtolnay/rust-toolchain@stable`，本機是 1.98.0；stable 升版後新的 clippy 規則在 async-trait 展開碼報錯，擋下已核准的部署，本機卻全綠。
- 防：每個 repo 放 `rust-toolchain.toml` 釘死版本（含 rustfmt、clippy），本機與 CI 同一版；升版要刻意改檔並跑全套檢查。

## 2026-10-02 Helios 進度紀錄的時間戳用猜的
- 錯：寫第一筆 checkpoint 時沒查時鐘，自己填了一個時刻，與實際差四小時，事後才改。
- 防：寫任何時間戳前先跑 `date -u +%FT%TZ`，用輸出值，不憑印象填。
- guard: write_guard.py checkpoint-write（只准經 cash-rule-checkpoint 寫入，時間由工具蓋）

## 2026-10-02 Helios 含程式的提交被 repo 提交規則擋下
- 錯：工作區有使用者原有的未追蹤檔，直接 `git commit` 被拒（Untracked files would contaminate the gate）；暫時分支取名 `tmp/...` 又被拒一次。我還一度誤以為後續指令已把錯的提交編號寫進紀錄，實際上 `&&` 已中止、檔案沒被改——沒查檔案就下判斷。
- 防：Helios 含 `.rs` 的提交在乾淨的暫時工作區做（匯出暫存差異 → `git worktree add` → 套用提交 → 回原處 `git reset --soft`），暫時分支名用 `feature/<slug>`，不用 `--no-verify`。提交後比對 HEAD 前後 SHA 才記錄；懷疑檔案被寫錯時先 `git status`／讀檔確認。

## 2026-10-02 Fluke 又用 pkill -f 關暫時網頁服務，殺到自己的 shell
- 錯：用 `pkill -f "http.server 18321 ..."` 關背景服務；執行中的 shell 命令列含同一字串，被一起殺掉（結束碼 144），後半段指令沒跑。這與 ai-mall #2771 那條是同一個錯。
- 防：背景服務啟動時就記 PID（或用工具回傳的背景工作代號停止）；要查就用 `ss -ltnp` 取得監聽埠的 PID 再 `kill <PID>`。任何 `pkill -f`／`pgrep -f` 都先當成會打到自己。
- guard: write_guard.py pkill-full

## 2026-10-02 Fluke 分支名與提交被 repo 規則擋下（與 Helios 同一套規則）
- 錯：照 Fluke 的 CLAUDE.md 開 `feat/<name>` 分支，提交被拒（只收 `feature/`、`bug/`、`release/`、`hotfix/`）；改名後又因工作區有使用者的未追蹤檔 `AGENTS.md` 被拒，推送也被同一條擋。
- 防：Fluke 開分支一律 `feature/<slug>` 或 `bug/<slug>`。提交與推送前先 `git status --short` 看有無未追蹤檔；有就在乾淨的暫時工作區提交（匯出暫存差異 → `git worktree add` → 套用提交 → 回原處 `git reset --soft`），推送也從乾淨工作區做。不用 `--no-verify`，不動使用者的未追蹤檔。

## 2026-10-02 Fluke 差點把原始錄音檔加入提交，且檢查到卻沒停
- 錯：用 `git add -A` 後雖然 grep 出三個 `.raw` 錄音檔，但指令用分號串接，照樣往下做提交；`.gitignore` 只擋 wav/mp3，沒擋 raw。另有三個程式輸出檔結尾多空行，被 repo 規則的 `git diff --cached --check` 擋下，訊息只有「git diff failed」。
- 防：暫存後先單獨跑兩個檢查並看結果再提交：媒體檔數量必須是 0（`git diff --cached --name-only | grep -cE '\.(png|mp4|mp3|wav|raw|ogg)$'`，素材資料夾另算），`git diff --cached --check` 必須無輸出。檢查與提交之間用 `&&`，不用分號。證據夾只放 README 與報告，不放程式原始輸出。

## 2026-10-02 Helios 憑印象寫第三方函式庫的常數（DMI 歸零門檻）
- 錯：照 TA-Lib 實作 DMI 時，把「小到當成零」的門檻憑印象寫成 1e-8，實際是 1e-14。小樣本逐位相同，全資料比對才在漲跌停鎖死的 34 根抓到。
- 防：要「與某函式庫相同」的實作，邊界常數與特殊分支先用該函式庫實跑一段邊界資料（全平、全零、極端值）確認，再寫進程式；單元測試要含那段邊界資料。

## 2026-10-02 Orca crashpad 診斷：刪檔動作和驗證步驟串在同一條命令被整條拒絕
- 錯：驗證新啟動腳本的命令裡夾了 `rm -f`／`rm -rf`（刪戳記、清暫存），整條被權限層拒絕，前面的解壓與驗證一步都沒跑。
- 防：含刪除的動作單獨下；陰性對照用 `touch -d '2000-01-01'` 把戳記弄舊，不靠刪檔。

## 2026-10-02 Fluke 把「人類的音效」解讀成背景人聲，整步作廢
- 錯：使用者說星燈茶會要「動態、加上人類的音效」，我解讀成背景交談環境音，找素材、寫程式、寫測試、推送都做完，使用者才更正：要的是畫面中兩位女角色自己發出聲音。整步撤除。
- 原因：需求有兩種讀法時，我選了成本低的那種，並把另一種只寫成「什麼會推翻決定」，沒有先用最小樣本確認就做完整步。
- 防：創作類需求（聲音、美術、風格）有兩種以上讀法時，仍自己決定，但第一個交付必須是最小樣本（一段音檔、一張圖、十秒短片），請使用者看過聽過再做完整實作；樣本沒被看過之前，不寫程式、不寫測試、不推送。畫面裡有角色時，「人聲」先假設是角色的聲音。

## 2026-10-02 陰性對照後用 git checkout 還原，把整份改好的檔案退回原版（Aletheia 改名）
- 錯：為了驗證編譯檢查，往 `src/probe.rs` 尾端加了一行中文函數，事後用 `git checkout -- src/probe.rs` 還原；但這個檔案在工作目錄裡已經改名過、還沒提交，checkout 把它退回提交前的中文版本。
- 防：在「有未提交修改」的檔案上做陰性對照，先把檔案複製到暫存區，結束後從那份複製還原並 `cmp` 比對；不要用 `git checkout` 還原未提交的檔案。
- guard: write_guard.py discard-uncommitted

## 2026-10-02 照專案既有寫法而違反使用者的全域規則（Aletheia）
- 錯：專案原本的測試函數多用中文命名，我跟著用中文寫了 23 個測試名稱與 82 行註解，違反「識別字與註解用英文 ASCII」。
- 防：使用者全域規則優先於「配合周圍程式碼」。動手前若發現專案慣例與全域規則衝突，照全域規則寫，並在回報中指出衝突。

## 2026-10-02 ai-mall #2829 流程檔沒先跑語法檢查就提交，多一個修正提交
- 錯：本機沒裝 actionlint，提交前的自動檢查只印「跳過」。我只用 YAML 解析確認格式就提交，之後才用容器版 actionlint 抓到單引號內的 `${...}` 被擋（SC2016）。
- 防：改 `.github/workflows/` 的檔案，提交前先跑 `docker run --rm -v "$PWD":/repo -w /repo rhysd/actionlint:latest <檔>`；在 `node -e '...'` 裡不寫 `${}`，用字串相加。自動檢查印「跳過」等於沒檢查。

## 2026-10-03 檢查點證據種類用了不存在的artifact
- 錯：cash-rule-checkpoint的evidence種類傳artifact，格式驗證拒絕並還原，沒有留下錯誤歷史。
- 防：檔案證據傳file；新增種類前先讀schema允許清單，不從其他工具的名稱猜。

## 2026-10-03 進度說明反覆混入簡體字
- 錯：本輪第158筆的時效誤用簡體；歷史保持原樣，不改寫。
- 防：寫入前只查進度工具的說明欄位，檔名與證據路徑不攔；已登記字形遇到就拒絕。不是完整語意或所有中文檢查。
- guard: write_guard.py checkpoint-prose；14項新舊測試及真實hook輸入拒絕通過。Claude既有hook已登記；目前Codex會話是否自動載入未證明，寫入前另明確呼叫檢查。

## 2026-10-03 SDK前置檢查失敗仍啟動編譯
- 錯：在SDK子目錄把cwd當Git根，檢查拒絕後，同一shell下一行仍執行cargo。
- 防：根目錄由git rev-parse取得；先確認前置檢查成功，再另行編譯或用&&綁定成功條件。
- guard: write_guard.py cargo-unchecked-preflight；僅涵蓋Python heredoc後直接cargo的已知型態，18項新舊測試與真hook拒絕通過。

## 2026-10-03 SDK測試CA缺用途欄位
- 錯：自建CA少了keyUsage，Python嚴格憑證檢查拒絕，尚未進入SDK驗簽。
- 防：CA明訂critical CA:TRUE與keyCertSign/cRLSign；另造CA:FALSE伺服器憑證，啟動前先以openssl verify -x509_strict核對完整鏈。不得關TLS驗證。
