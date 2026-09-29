---
id: local-model-management
version: 3
updated: 2026-09-24
host: Essence
status: applied-short-probes-verified
scope: Linux / Ollama / localai / future RAG
---

# 本機模型管理策略

## 目的與適用範圍

讓 Orca、終端與未來的文件檢索問答共用本機模型，同時保留桌面操作空間。模型由獨立的 `ollama.service` 管理；Orca session 只是呼叫端，不能各自啟停共用服務。

本機現況：Ollama 0.34.0、109 GiB 可見 RAM、AMD Strix Halo 整合 GPU。GPU 與主機記憶體的用量必須一起觀察，不能把兩個顯示容量直接相加成兩份獨立資源。不能把工作組計數當成所有 GPU 配置的完整計數。

## 執行中的設定

設定來源：`/home/cash/.config/ollama-management/resource-policy.conf`。
實際套用：`/etc/systemd/system/ollama.service.d/60-resource-management.conf`。

| 項目 | 設定 | 真正涵義 |
| --- | --- | --- |
| 服務入口 | `127.0.0.1:11434` | 本機共用；不開放區域網路 |
| 不同模型 | `OLLAMA_MAX_LOADED_MODELS=2` | 最多兩個載入名額；容量不足時不保證兩個都能留住 |
| 單模型並行 | `OLLAMA_NUM_PARALLEL=1` | 每模型一次一個生成請求；兩個模型可能同時各跑一個 |
| 排程等候 | `OLLAMA_MAX_QUEUE=8` | 限制部分載入排程通道；不是全部 HTTP 等候請求的總上限 |
| 閒置保留 | `OLLAMA_KEEP_ALIVE=10m` | 預設閒置十分鐘；請求可以覆蓋此值，容量不足也可能提早替換 |
| 對話暫存長度 | `OLLAMA_CONTEXT_LENGTH=32768` | 預設最多保留的文字單位數；請求與模型設定可覆蓋，不是入口硬上限 |
| 載入停滯 | `OLLAMA_LOAD_TIMEOUT=2m` | 載入無進展的偵測；不是整個推論請求兩分鐘超時 |
| GPU 載入餘裕 | `LLAMA_ARG_FIT_TARGET=12288` | llama-server 載入時以剩餘 12 GiB 為安排目標；不是執行期間硬上限，不能阻止其他程序取用 |
| CPU 端記憶體回收門檻 | `MemoryHigh=12G` | 對工作組可計入的 RAM 生效；超過會強制回收並拖慢，須查壓力 |
| CPU 端記憶體硬上限 | `MemoryMax=16G` | 超額無法回收可終止程序；較大型模型退回 CPU 執行可能被終止 |
| 交換空間上限 | `MemorySwapMax=2G` | 避免此服務大量使用交換空間；不能保證完全不交換 |
| CPU | `CPUQuota=1200%` | 最多相當於十二個核心的 CPU 時間；不固定核心，不限制 GPU |
| 資源優先權 | CPU／IO 權重 50、Nice 5 | 相對降低優先權；IO 權重不是磁碟讀寫速度硬上限 |
| 故障恢復 | 失敗後 15 秒再啟動；十分鐘內最多三次啟動 | 避免快速重啟；到上限後停止，人工查原因 |
| 記憶體不足 | `OOMPolicy=stop` | 服務內程序遭記憶體不足終止時停止服務；隨後依有限重啟規則處理 |

12／16 GiB 是兩個 GPU 模型短測後的 CPU 端預算，必須對照實測紀錄。不是「模型全部只用 16 GiB」，也不是全機所有工作加起來的總上限。

初版曾用 48／56 GiB；實測兩模型約 36.6 GiB，而工作組僅約 3 GiB，因此調低 CPU 端額度，避免 GPU 之外再額外使用 56 GiB。主機 dmem 計數也只列小量 vram，沒有涵蓋模型使用的大量 GTT 共享記憶體，故不設定假稱完整的 dmem 硬限。

GPU 預留採用本機 `/usr/local/lib/ollama/llama-server --help` 可識別的 FIT_TARGET；未採用僅在排程日誌看到的 `OLLAMA_GPU_OVERHEAD`。這個版本相依設定必須在升級 Ollama 後重驗啟動日誌，不可以只確認環境變數存在。

## 呼叫與釋放規則

1. 所有本機呼叫共用現有 Ollama，不另開一份服務。相同模型與相容設定盡量重用；變更對話暫存長度等參數可能需要重載。
2. 各 session 可以指定不同模型。現有 `localai` 的 code、review、second 仍使用各自模型；不為限制資源擅自替換模型品質。
3. 固定輸入與輸出預算。`localai` 現有輸入估算僅是近似防護，不能當精確文字切分或語意完整性保證。
4. 工作完成先釋放該請求的工作資源，模型依閒置策略保留；不要每次回答後強制重啟 Ollama。
5. 個別 session 不得自行 `ollama stop`、`systemctl restart ollama` 或送共享模型卸載請求。這是操作規則，尚非帳號權限強制隔離。
6. 管理者切換／卸載前，先確認共用者没有正在執行的工作。確認閒置後才用正常卸載；`ollama ps` 只表示載入狀態，不證明沒有在途請求。
7. 忙碌、503、超時或記憶體不足後先回報，不盲目重送。呼叫端超時不直接視為服務端已停止，先查狀態。
8. 常用模型短時間保留；同模型需求可以集中，但不讓另一模型無限等候。原生設定尚未提供全機公平排程保證。

## 桌面保護與觀察

- 同時記錄模型清單、主機可用 RAM、主機與 Ollama 記憶體阻塞、工作組用量／尖峰／超限事件、GPU 可見用量與載入耗時。
- 本次驗證停止門檻：可用 RAM 低於 20 GiB，或最近十秒的主機記憶體全面阻塞比例高於 10%，就中止本次合成測試請求；不殺其他工作。
- 前述 20 GiB／阻塞門檻屬驗證工具。另已部署常駐 12／8 GiB 主機可用記憶體保護，以及兩實體核心 CPU 排除；完整規則、檔案與還原見 [OS 資源保護](os-resource-protection.md)。
- 觸及回收門檻應減少並行、縮小請求或正常卸載閒置模型；不能只反覆加大門檻。
- 不為釋放模型執行 `swapoff`、清空系統快取或刪除模型檔。卸載模型與停用交換空間是不同操作。
- 不把 109 GiB 全部分配給模型。資料庫、瀏覽器、Orca、檔案快取、GPU 配置及載入尖峰都要有餘裕。

## 未來 RAG：檢索文件後再交給模型回答

目前只保留策略，未建置文件索引、向量資料庫或 RAG 服務。

| 工作 | 未來管理方式 |
| --- | --- |
| 文件解析與分段 | 有界批次；先限制單批檔案／位元組與並行數；留存檔案來源及版本 |
| 文字轉向量 | 也算一個模型載入名額；和生成模型共同分配兩個名額 |
| 大批索引 | 低優先權、可續跑；不要與互動問答無限制競爭 GPU／記憶體 |
| 檢索與重排 | 限定候選數、送入模型的總文字量及輸出長度；更換向量模型須記索引版本與相容性 |
| 向量資料庫 | 獨立資源預算；不在 Ollama 工作組內的程序不受此服務 CPU 端 16 GiB 上限保護 |
| 全機排程 | 若需要「跨模型合計一次一請求」或全服務嚴格等候上限，再加共用接單入口；所有呼叫端一起切換，避免繞過 |
| 文件安全 | 保留來源引用、存取權限及更新／刪除追蹤；檢索文件當資料，不當系統指令 |

新增 RAG 前的驗收：互動與索引共跑、取消工作、服務重啟、文件更新／刪除、來源可追溯，以及桌面仍可操作。不得把本次小提示測試當成這些驗收已通過。

## 檢查、設定更新與還原

唯讀狀態：`python3 /home/cash/tools/ollama_management/status.py`。
小型單次驗證：見 `/home/cash/tools/ollama_management/README.md`；每次只送一個合成請求，不自動重試。
原始證據與還原前設定：`/home/cash/.local/state/ollama-management/20260924-151809/`。

更新設定時：先核對原始檔與實際 drop-in，修改來源、複製到 drop-in、執行 `systemd-analyze verify`，確認沒有進行中的工作後再重啟 Ollama。僅 `daemon-reload` 不會讓 Ollama 讀到新的環境設定。

第一輪模型設定只新增一個 drop-in。要單獨還原第一輪，先確認沒有進行中的工作，再刪除 `/etc/systemd/system/ollama.service.d/60-resource-management.conf`，執行 `sudo systemctl daemon-reload`、`sudo systemctl restart ollama`。不使用 `systemctl revert`，避免刪除其他人新增的設定。還原後回到原本沒有本次資源限制的狀態。

## 來源與紀錄

本次最終驗證：兩個不同模型短答 2/2 成功，皆使用 32768 對話暫存設定，合計模型配置約 36.6 GiB；主機最低仍有 35.40 GiB 可用 RAM。Linux 可計入的工作組尖峰約 2.55 GiB，沒有 high/max/oom 事件。實際啟動日誌有 `35247 >= 12288 MiB`、`15481 >= 12312 MiB`，確認 GPU 載入目標餘裕被採用。

正常卸載寫程式模型後，另一個審查模型仍保留，主機可用 RAM 回到約 57.86 GiB。低記憶體與高阻塞等防護檢查 4/4 通過、0 略過；不存在模型的請求被拒絕並記為失敗。未做長提示／大量請求／故意耗盡記憶體壓測、未等滿十分鐘驗閒置到期、未重開機、未驗 RAG。

以上雙模型數據屬第一輪實測。後續 CPU／OS 記憶體保護已增加常駐監測，驗證過程曾在無載入模型時停止並恢復 Ollama；新證據見 [OS 資源保護](os-resource-protection.md)。未修改遠端正式服務。

- [Ollama 設定與模型保留](https://docs.ollama.com/faq)
- [Ollama 0.34.0 排程實作](https://github.com/ollama/ollama/blob/v0.34.0/server/sched.go)：已載入模型可繞過載入排程通道。
- [Ollama 0.34.0 llama-server 啟動路徑](https://github.com/ollama/ollama/blob/v0.34.0/llm/llama_server.go)：FIT_TARGET 環境繼承與多媒體額外餘裕。
- [Linux 工作組記憶體控制](https://docs.kernel.org/admin-guide/cgroup-v2.html)：memory.high、memory.max 與壓力計數。
- 本機 `man systemd.resource-control`、`man systemd.service`。
- 驗證結果與變更歷史見相鄰 `local-model-management.changelog.md`，事實以時間戳與實測輸出為準。
