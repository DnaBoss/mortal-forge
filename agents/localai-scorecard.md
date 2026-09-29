# 本機模型成績單

## 2026-09-22 Windows installer

- code / qwen3-coder:30b：首次設定表單草稿，3/4，edited；16.26 秒，193/768 實測 token；修正 label 關聯、錯誤型別與成功後防重送，修復約 1 分鐘，未單獨計秒。
- code / qwen3-coder:30b：terminal_setup 保存審查，2/4，edited；2.73 秒，1276/100 實測 token；部分寫入殘留為真問題（已改完整寫入再發布），「驗證在建立檔案後」為誤報；主管核對與修復約 1 分鐘。後續限於可重現的小範圍審查。

- code / qwen3-coder:30b：Windows LOOP 審查，2/4，11.5 秒，2537/241 實測 token；將細化誤稱矛盾，採用乾淨 Windows／補印提示，忽略已存在的備援路徑；修正低於約 1 分鐘，無独立計秒。

- code / qwen3-coder:30b：workflow 唯讀審查回「無」，2/4，僅作輔助；6.88 秒，1212/2 實測 token，修復 0 秒。actionlint 過，Windows 尚未執行，完整度有限，不視為無 BUG 證明。

## S25（2026-09-21）

| 日期 | 角色 | 模型 | 任務 | 結果 | 分數 | 備註 |
| --- | --- | --- | --- | --- | --- | --- |
| 2026-09-21 | code | qwen3-coder:30b | S25 舊事件零件盤點 | edited；同時聲稱讀未來與不讀未來，只採經工具複核的日盤限制 | 2 | 12.56秒；實測4635/160輸入/輸出token；主管修復時間未單獨量測 |
| 2026-09-21 | code | qwen3-coder:30b | S25 回放程式唯讀審查 | rejected；未給可重現案例，把另扣滑價誤稱未處理方向 | 1 | 3.05秒；實測2310/74輸入/輸出token；不作放行依據，轉獨立高能力審查 |
| 2026-09-24 | code | qwen3-coder:30b | 判斷分鐘K線完整性稽核是否值得成為共用工具 | edited；正確建議重用 Helios 稽核、區分無tick證據與確定遺失；未照要求提供行號，且任務後來釐清為零量K線計數，不能直接採用該工具作本題掃描 | 2 | 24.52秒；實測12461/277輸入/輸出token；主管重查腳本後修正查詢範圍 |

## 2026-09-21 Windows POS S09

- qwen3-coder:30b，契約摘要，2/4，edited：34.12 秒，16834/403 輸入／輸出 token；漏來源符號及 state/outcome 區別，主管需核對；修復時間未單獨量測。
- qwen3-coder:30b，device-bridge 介面草稿，3/4，edited：43.71 秒，14735/1286 輸入／輸出 token；印表機 driver/transport 分離方向可用，刷卡錯誤解析草稿不採，由主管依 bk result.ts 重寫。
- qwen3-coder:30b，printer target parser 測試清單，4/4，used：13.21 秒，4609/191 輸入／輸出 token；列出的 TCP/serial/USB/LPT/錯誤輸入案例與 bk 契約一致，實作由主管完成。
- qwen3-coder:30b，POS card adapter 小範圍 review，4/4，used：11.71 秒，2031/246 輸入／輸出 token；確認 UNKNOWN/NotSentFailed 未轉 approved、Training/Live 對應正確，建議補「不會開票」測試，主管採納並驗證。
- qwen3-coder:30b，device-bridge card sale terminal mapper review，4/4，used：5.55 秒，3692/162 輸入／輸出 token；未發現四態分類錯誤，建議補 `0003` 逾時 named test，主管採納並驗證。
- qwen3-coder:30b，device-bridge card conversation review，3/4，edited：9.01 秒，5671/244 輸入／輸出 token；未發現規則搬錯，但漏看既有 ACK timeout 測試；其「補強 request frame 只寫一次」建議可用，主管採納並驗證。
- qwen3-coder:30b，device-bridge NCCC card codec review，4/4，used：7.97 秒，7245/65 實測輸入／輸出 token；正確指出 response amount 空白缺測，主管採納並修成 ResultUnknown 後重跑 device-agent 與 POS 回歸。
- qwen3-coder:30b，device-bridge NCCC sale transport review，4/4，used：9.62 秒，7836/139 實測輸入／輸出 token；正確指出 concrete transport 缺 ACK timeout 後成功 response 的測試，主管採納並驗證。
- qwen3-coder:30b，device-bridge Windows serial boundary review，4/4，used：9.67 秒，8956/71 實測輸入／輸出 token；確認 Windows-only dependency 與 unknown 分類方向，指出 serial 層缺 ACK timeout 不重送測試，主管採納並驗證。
- qwen3-coder:30b，POS card startup config review，3/4，edited：31.34 秒，20823/217 實測輸入／輸出 token；確認不偷 fallback 與每筆 context provider，Linux/Windows 編譯結論文字寫反，主管依測試與 cfg 程式碼修正判讀。
- qwen3-coder:30b，Windows target smoke review，2/4，edited：24.95 秒，18002/149 實測輸入／輸出 token；正確確認 Display/Error 與 MSVC toolchain 限制，但誤判 smoke crate 不能證明 trait-object 包裝，主管以 cargo check 結果修正。
- gpt-oss:20b，兩檔反方審查，rejected：空回應，無可評內容品質，可靠性失敗；本輪停止重試。證據：POS loops/evidence/pos-checkout/s09-bk-contract.md。

每次派工給本機模型就記一筆。分數判準是**主管要花多少力氣收拾**：

| 分數 | 意思 |
| --- | --- |
| 4 | 可直接用。結論正確、指得出位置，雲端不必重做 |
| 3 | 要改一點。方向對，細節要修 |
| 2 | 只能當線索。要自己重查，但省了找的時間 |
| 1 | 有害。編造、答非所問、漏掉明顯的東西 |

同一角色連續兩次 1 分就換模型，並在下方記下換的理由。
換新模型時拿同一個舊任務再跑一次比較，不憑感覺。

## review（目前：huihui_ai/Qwen3.8-abliterated:latest；尚未通過同任務驗證）

| 日期 | 任務 | 結果 | 分數 | 備註 |
| --- | --- | --- | --- | --- |
| 2026-09-21 | 讀一支故意寫錯的金額計算，找錯 | 抓出兩個真錯誤（折扣沒乘金額、稅金漏乘數量），附正確算式 | 4 | 由使用者的另一個工作階段實測 |
| 2026-09-21 | 讀整張桌面截圖，說出畫面內容 | 正確讀出視窗、分支名稱、檔案清單、終端機內容 | 4 | 看圖能力可用 |
| 2026-09-21 | 給錯檔案，問商品介面有哪些欄位 | 明說「這兩個檔案裡沒有這個端點」，並列出實際有哪些函式，要求補檔案 | 4 | **沒有編造**。給錯資料時說找不到，正是要的行為 |
| 2026-09-21 | 讀 ai-mall 商品 controller 與 service barrel，問圖片欄位 | 正確追出實作在 `product-query.service.ts`，並說明 barrel 只是轉出；沒有硬答 | 4 | 追鏈正確，仍然不編造 |
| 2026-09-21 | 讀 ai-mall `product-query.service.ts` 確認商品圖片欄位 | 呼叫跑 683 秒後輸出 0 字元，沒有可審查結論 | 1 | 工具此前誤記為 ok；已改成空回應失敗並記錄。先視為穩定性／呼叫問題，未據此判定語意能力 |
| 2026-09-21 | 審查 S08b 單檔圖片下載流程 | 180 秒無回應且沒有新增紀錄，沒有可審查結論 | 1 | 同角色連續不可用，依規則切換至 `huihui_ai/Qwen3.8-abliterated:latest`；同任務比較尚待跑 |
| 2026-09-21 | 切換後重跑 S08b 單檔精準 review | 120 秒仍無回應，沒有可審查結論 | 1 | 候選 reviewer 尚未可用；主管以測試、資料庫與人工反方檢查完成本輪判斷 |
| 2026-09-21 | 明確設定容量 32768 後，重跑 39,542 字元的同一題 | 453 秒仍回空白；同一題交給 `code` 角色 19 秒就答出來 | 1 | **證明不是輸入太大，是這個模型不行**。大檔閱讀改派 `code` 角色 |

## code（目前：qwen3-coder:30b）

| 日期 | 任務 | 結果 | 分數 | 備註 |
| --- | --- | --- | --- | --- |
| 2026-09-21 | S24 候選點 schema 草稿建議 | 呼叫超過本輪需要仍無輸出，主管中止；未採用其結果 | 1 | 測試與程式由主管完成；若 code 角色再 1 分一次就換模型 |
| 2026-09-21 | 讀 39,528 字元的 ai-mall 查詢檔，找商品圖片欄位 | 19 秒答出欄位名 `images` 正確；但行號說 389，實際在 424／639／785，型別也說錯 | 2 | 大檔輸入穩定、快；細節不可信，位置一定要用 grep 複核 |

## second（目前：gpt-oss:20b）

| 日期 | 任務 | 結果 | 分數 | 備註 |
| --- | --- | --- | --- | --- |
| 2026-09-21 | 審查 S08a 圖片網址與 migration 差異 | Ollama 回 HTTP 500，沒有審查結論 | 1 | 工具已記錄錯誤；未把失敗當成程式通過或不通過 |

## 換模型紀錄
| 2026-09-22 | code | qwen3-coder:30b | mallqa票號compose/Caddy部署審查 | rejected，把internal network和未發布port誤判外露，自相矛盾；主管不採，改以Docker實態與HTTP驗證 | 1 | 11.36秒；868/182實測token；無程式修復，約1分鐘複核 |

| 2026-09-22 | code | qwen3-coder:30b | DBB 測試票號 Caddy/compose/systemd/secret 審查 | used，公開路徑及 localhost 邊界正確；主管再以 Caddy validate 與實際部署驗證 | 4 | 2.31秒；1032/93實測token；無修復，HTTP實測待完成 |


| 日期 | 角色 | 從 | 換成 | 理由 | 比較用的任務 |
| --- | --- | --- | --- | --- | --- |
| 2026-09-21 | review | qwen3.8:27b | huihui_ai/Qwen3.8-abliterated:latest | 同角色連續兩次無可用輸出 | 審查 S08b 圖片下載流程 |

## 主管自己的檢討（2026-09-21）

陰性對照做了兩次假的：腳本印出「已改壞」但實際沒動到檔案，導致我一度誤判
「沒有測試守著離線圖片」。重做並先確認改動落地後，測試確實變紅。

**規矩補上：改壞之後，先用 `git diff --stat` 確認改動存在，再跑測試。**
沒確認就看到綠燈，等於在測自己的腳本，不是在測程式。

## 依證據調整的派工（2026-09-21）

**讀大檔找答案改派 `code` 角色。** 同一個 39,542 字元的檔案、同一個問題：

| 角色 | 模型 | 結果 |
| --- | --- | --- |
| review | qwen3.8 系列 | 453 秒，空白，兩次都是 |
| code | qwen3-coder:30b | 19 秒，答出欄位名，行號錯 |

qwen3.8 系列是會先想很久的那種模型，看來把輸出額度都花在內部推理上，最後什麼都沒吐出來。
`review` 角色暫時只留給小輸入與看截圖。

**工具也修了**：以前沒有指定模型能拿多少內容，Ollama 預設很小又不會報錯，
會安靜地把內容剪掉。現在每次都明講容量、送之前先算會不會超過、回來後比對模型
實際讀了多少，對不上就當失敗。**但這一題證明容量不是唯一原因**，換角色才真的有效。

## POS S10（2026-09-21）

| 日期 | 角色 | 模型 | 任務 | 結果 | 分數 | 備註 |
| --- | --- | --- | --- | --- | --- | --- |
| 2026-09-21 | code | qwen3-coder:30b | review device-bridge printer target transport diff | 前兩題確認方向正確，但第三題自相矛盾；三個 bug 多是已知設計取捨，未指出可重現錯誤 | 2 | 8.19 秒；3424/320 實測 token；主管依測試與程式碼覆核 |
| 2026-09-21 | code | qwen3-coder:30b | review POS print_certificate command diff | 正確確認成功/拒印/錯誤分流、handoff 未誤稱紙張印出、失敗寫 FAILED；列出的 bug 多數被編譯測試排除 | 3 | 15.19 秒；5321/255 實測 token；主管採結論、不採誤判 bug |
| 2026-09-21 | code | qwen3-coder:30b | review S12 frontend auto-print diff | 正確確認自動列印條件與防重複；抓到 UI 把 failed/refused data 顯示成綠色成功的真問題，已採納修正 | 3 | 5.24 秒；1411/262 實測 token；另兩項為防呆或不成立 |
| 2026-09-21 | code | qwen3-coder:30b | review dependency boundary gate diff | 三個方向回答正確，但誤稱只是增加 gate 調用、沒有改變檢查邏輯；實際新增了一整支腳本 | 2 | 1.66 秒；410/85 實測 token；主管用實跑 gate 驗收 |
| 2026-09-21 | code | qwen3-coder:30b | review clean release gate 行為 | 正確指出 build 與 all/pre-push 的 target 行為差異可能造成誤會；主管採納補註解，不採納讓 build 也走暫存 target | 3 | 10.56 秒；1257/199 實測 token；`./scripts/check.sh all` 已實跑通過 |
| 2026-09-21 | code | qwen3-coder:30b | S12 auto-print 防重複規則設計與 diff review | 第一次只重述既有函式，第二次指出可能重複/漏印但沒有具體可成立路徑；主管自行抽純函式並用測試驗收 | 2 | 約 11.2 秒；第一次 4534/218 實測 token；第二次作為線索未採 bug |
| 2026-09-21 | code | qwen3-coder:30b | S12 training approved 可列印發票核心測試 | 測試方向正確，確認不混淆 training/live/simulator，也沒有宣稱真硬體；但建議中編出不存在 helper，review 誤稱用了 SimulatedCardReader | 3 | 設計建議 4.63 秒；diff review 3.81 秒；主管採納意圖、不採用程式碼 |
| 2026-09-21 | code | qwen3-coder:30b | S12 checkout command training printable result diff review | 正確確認 refactor 不改 production checkout，新測試覆蓋 training approved 到 invoiceNumber/shouldPrintInvoice/TRAINING source，未發現來源混淆 | 4 | 8.36 秒；6571/153 實測 token；主管以實跑測試與 gate 驗收 |
| 2026-09-21 | code | qwen3-coder:30b | S12 checkout command card failure diff review | 正確確認五種非 approved outcome 都覆蓋不建訂單、不耗發票號碼，未漏 CardAuthOutcome，未發現測試誤綠 | 4 | 9.19 秒；6904/170 實測 token；主管以 command/core/frontend/gate 驗收 |
| 2026-09-21 | code | qwen3-coder:30b | S12 frontend card error text diff review | 正確確認大部分刷卡狀態與票號中心映射，但誤稱 Unknown 沒明確提示；實際程式與測試都有「不要直接重刷」 | 2 | 2.17 秒；778/97 實測 token；主管用 rg 與測試覆核，不採誤判 |
| 2026-09-21 | code | qwen3-coder:30b | S13 desktop preflight script review | 正確確認腳本只檢查不啟動，simulated/training 判斷符合目前設定；指出 `POS_PRINTER_PORT` 未驗證，已採納修正 | 3 | 3.87 秒；1523/175 實測 token；主管加負向測試驗收 |
| 2026-09-21 | review | huihui_ai/Qwen3.8-abliterated:latest | S13 simulated desktop screenshot review | 正確辨識 POS 視窗、商品圖片不是全同一張、購物車空、票號與票號中心狀態可見 | 4 | 55.67 秒；2166/517 實測 token；主管用截圖與 process cleanup 驗收 |
| 2026-09-21 | code | qwen3-coder:30b | S13 training checkout + print failure smoke review | 正確確認 smoke 串起 training checkout、同一張 invoice、print failure 與可補印；也指出尚未直接測 `print_certificate` Tauri command | 3 | 16.2 秒；7336/206 實測 token；主管列為下一輪缺口 |
| 2026-09-21 | code | qwen3-coder:30b | S13 print_certificate command core path review | 乾淨重跑後正確確認 helper 覆蓋 command 核心路徑，測試打到 certificate rendering、printer target error 與 print_log | 4 | 9.82 秒；7878/140 實測 token；另一次 prompt 反引號污染的 review 丟棄不用 |
| 2026-09-21 | code | qwen3-coder:30b | S14 Windows package metadata / training preflight review | 乾淨 bundle review 正確確認 MSVC/Rust target/COM/printer/font/env 檢查與防 iPad 命名 gate；提醒真 COM/driver 仍需 Windows 硬體驗收 | 4 | 5.23 秒；2518/206 實測 token；另一次漏 untracked 檔的 review 丟棄不用 |
| 2026-09-21 | code | qwen3-coder:30b | S14 Windows preflight PowerShell 5 相容性 review | 正確確認 `Test-IsWindows` 修掉 Windows PowerShell 5 缺少 `$IsWindows` 的誤判，未指出明顯風險，建議採用 | 4 | 8.99 秒；1396/88 實測 token；主管以 static gate 與 `check.sh gate` 驗收 |
| 2026-09-21 | code | qwen3-coder:30b | S14 Windows hardware acceptance runbook review | 確認 runbook 覆蓋訓練刷卡成功後開票列印，並提醒 preflight 可能被誤當成硬體完成；主管採納補強 preflight 邊界與紙本號碼比對 | 4 | 3.92 秒；1520/181 實測 token；主管以文件 diff 與 gate 驗收 |
| 2026-09-21 | code | qwen3-coder:30b | S14 POS handoff evidence gate review | 確認可防缺少 S09-S14 關鍵 evidence 誤交付，指出 log 只看存在不看內容與字串過硬風險；主管採納補 log 內容 rc/test/build 檢查，保留 handoff 邊界字串檢查 | 4 | 4.59 秒；2457/163 實測 token；主管修正循環誤紅後以 gate/all 驗收 |
| 2026-09-21 | code | qwen3-coder:30b | S14 Windows preflight static gate review | 確認可防 preflight 腳本改壞仍過 Linux gate；指出硬編碼字串可能誤紅；主管採納把 platform gate 改成正則、保留關鍵能力字串 | 4 | 5.49 秒；3334/167 實測 token；主管以 gate/all 驗收 |
| 2026-09-21 | code | qwen3-coder:30b | S14 POS delivery scope gate review | 確認可防兩個 repo 混入 S09-S14 範圍外檔案；誤稱 device-agent 缺 Cargo 檔；主管採納補刪除檔案一律紅，保留必要 allowlist | 3 | 4.94 秒；2497/183 實測 token；主管以 direct gate/check.sh all 驗收 |
| 2026-09-21 | code | qwen3-coder:30b | S14 POS branch policy gate review | 確認可防 main/dev/develop 上開發並要求 feature branch 基於 dev；誤稱沒檢查 device-agent；主管保留邏輯，以 direct gate/check.sh all 驗收 | 3 | 5.15 秒；3056/170 實測 token；另已在 device-agent 建本地 dev 指向 develop |
| 2026-09-21 | code | qwen3-coder:30b | S14 Windows acceptance collector review | 確認收集器只保存證據、不自動宣稱硬體成功；未發現危險操作；主管採納補憑證字型 SHA256 | 4 | 5.06 秒；3437/140 實測 token；主管以 direct gate 驗收 |
| 2026-09-21 | code | qwen3-coder:30b | S14 PR handoff package review | 確認 handoff 沒誤稱 Windows/硬體完成，缺口足以阻止誤解；建議真 PR 前補 Windows acceptance run gate | 4 | 8.77 秒；1312/150 實測 token；主管先以 handoff evidence gate 防誤交接 |
| 2026-09-21 | code | qwen3-coder:30b | S14 handoff diff-map gate review | 第一次抓到原版只看 marker、沒保證每個 dirty path 已分類；主管採納補未分類路徑紅燈；第二次確認 lockfile/manifests 已揭露且未誤稱硬體完成 | 4 | 11.24 秒；3424/105 + 3956/225 實測 token；主管以 direct gate 驗收 |
| 2026-09-21 | code | qwen3-coder:30b | S14 final status audit review | 確認 final audit 沒把未完成 Windows/硬體驗收說成完成，已證明/未證明分類清楚，下一步應跑 collector preflight | 4 | 3.33 秒；1216/157 實測 token；主管以 direct gate 驗收 |

| 2026-09-22 | code | qwen3-coder:30b | SC2 科技實驗室門檻最小改動 | used，指定差異正確；25 tests 與原版陰性對照通過，實戰待驗 | 4 | 12.98 秒；525/351 實測 token；主管僅補空行，修復成本低於 1 分鐘 |

| 2026-09-22 | SC2 coach | qwen3.8:27b | 兩場敗局提出兩條候選規則 | rejected，手冊完全未改且誤判補給 | 1 | 32.74秒；4357/396實測token；縮小為明確兩個欄位，若再次1分換方法 |

| 2026-09-22 | SC2 coach | qwen3.8:27b | 兩條坦克前置規則 | rejected，瓦斯前置死鎖且兩條互相矛盾 | 1 | 11.45秒；326/144實測token；連續2次1分，停止此角色，候選生成改qwen3-coder:30b |

| 2026-09-22 | code | qwen3-coder:30b | 坦克前置策略兩規則 | edited，優先方向可用但缺少只補缺項條件；主管修正後保留2條範圍 | 2 | 9.14秒；274/101實測token；修正约1分鐘，尚待實戰 |

| 2026-09-22 | code | qwen3-coder:30b | POS Windows device-agent host/launcher 最小設計 | edited，方向正確：POS repo 管 host、installer 帶 device-agent 模組包；但誤稱 host-launcher.exe 可由 Tauri 組建且沒有處理 Node runtime/serialport native/Node 22.13 細節 | 2 | 約 30 秒內；實測 token 未從工具輸出取得；主管用 README/manifest/Tauri docs 複核 |
| 2026-09-22 | review | qwen3.8:27b | POS Windows packaging diff review | edited，正確判斷 Tauri resource/staging 只完成打包層，不能宣稱 Windows 安裝後可刷卡列印；指出缺 POS 啟動 agent、health check、API 切換 | 3 | 約 197 秒；輸入 diff 約 25KB；有一個小誤判稱 staging script 未在 diff 中出現，主管不採 |
| 2026-09-22 | code | qwen3-coder:30b | ai-mall Store API 是否已有 POS 建單端點 | edited，正確判斷沒有現成 POS 建單端點，但誤把 consumer `POST /orders` 說成 `POST /store-api/orders`；只能當線索 | 2 | 約 13 秒；輸入約 33K 字元，輸出約 90 字；主管用路由與文件行號複核 |
| 2026-09-22 | code | qwen3-coder:30b | POS→ai-mall S03 service 測試清單 | edited，列出成功、duplicate、庫存不足、金額錯誤四類測試；但誤稱庫存不足時 transaction 不執行，主管改成 transaction 內丟錯並回滾 | 2 | 約 10 秒；輸入約 12K 字元，輸出約 330 字；主管採測試類別、不採錯誤交易判斷 |
| 2026-09-22 | code | qwen3-coder:30b | POS→ai-mall S04 command 最小接線 | accepted，正確指出一次只送一筆、accepted/duplicate 才標 synced、其他失敗不標 synced | 4 | 約 5 秒；輸入約 11K 字元，輸出約 180 字；主管照此實作並以 Rust 測試/clippy 驗收 |
| 2026-09-22 | code | qwen3-coder:30b | POS→ai-mall final diff blocker review | rejected，沒有正確讀到實際 Rust/TypeScript diff，輸出不存在的 Go 範例與不成立 blocker | 1 | 約 10-16 秒；主管完全不採，改用 pre-push、單元測試與真 DB 驗收判斷 |
| 2026-09-22 | review | qwen3.8:27b | POS Windows 設備設定 diff review | rejected，超過 2 分鐘無輸出，被主管中止；沒有形成可用審查 | 1 | 輸入 diff 約 10KB；localai 未寫完成 log；同類 diff review 暫不續用此角色 |

| 2026-09-22 | SC2 replay analyst | qwen3.8:27b | 三族精簡高手教材 | edited，引用有效但驗收只寫無錯誤；主管要求真實型態與能力 | 2 | 25.81秒；1796/420實測token；原大輸入逾時未回應，未評模型內容 |
| 2026-09-22 | SC2 replay teacher | qwen3.8:27b | TvZ高手手冊初稿 | rejected，未證實勝因、搬運與定位超出能力、缺worker_target；具體審查後修訂 | 1 | 54.83秒；6702/524實測token；本角色採高手資料而非先前自由猜規則 |

| 2026-09-22 | SC2 replay teacher | qwen3.8:27b | TvZ候選具體審查後修訂 | edited，移除錯誤因果與未支援操作；主管補合法名稱、軟目標及可見worker容量 | 2 | 25.66秒；797/426實測token；68d146eef3進單場發展驗證，非已晉升 |
| 2026-09-22 | code | qwen3-coder:30b | memory_summary.md Phase 2 schema review | accepted，回覆 NO_FINDINGS；主管以 v1/header、task metadata、reference existence 與 git diff --check 交叉驗證 | 4 | 9.94秒；4280/4 實測 token；全 handbook review 因 96k-token 輸入超過 32k context 在推論前拒絕 |
| 2026-09-22 | review | huihui_ai/Qwen3.8-abliterated:latest（請求 ID，實際解析版本未回傳） | Fluke 麻將舊畫面負向檢查 | edited：抓到無四方桌體、無白色牌身；刪除字形上下錯位及未等距的過度推論 | 3 | 47.55 秒，1054/466 實測 token；主管修訂文字約 1 分鐘；本輪程式修改 0 |

| 2026-09-22 | code | qwen3-coder:30b | POS mall client narrow test matrix | edited | 2 | Listed useful mismatch/count cases but invented payload fields; cloud verified contracts and authored tests. 11.57s, input 120/output 361 measured tokens. |

| 2026-09-22 | code | qwen3-coder:30b | SC2成本探查草稿 | rejected | 1 | 錯誤Player呼叫與不存在game_version欄位；主管改用已安裝API，25.67秒、11415/422 tokens |
| 2026-09-22 | strategy | qwen3.8:27b | 8工兵教材候選 | rejected | 1 | 不可見距離與近期損失；未解第二瓦斯，縮成單項再評估；53.13秒、5039/470 tokens |
| 2026-09-22 | code | qwen3-coder:30b | 建築間距幾何草稿 | edited | 3 | 修正等於2格邊界、移除markdown fence；真機通道與6項幾何檢查通過；11.78秒、198/286 tokens |

| 2026-09-22 | code | qwen3-coder:30b | SC2 Protoss/Zerg macro draft | rejected | 1 | Invented GAS, wrong buffs and commands, incomplete macro; supervisor implements against installed API |

| 2026-09-23 | code | qwen3-coder:30b | Fluke ws_echo窄測試遷移 | rejected | 1 | 違反不改production要求，恢復未知桌建桌並編造JoinTable型別；草稿全棄用，改派gpt-6-sol。16.89秒，2161/577實測token，修復時間0（未採用） |
| 2026-09-23 | review | qwen3.8系列 | Fluke lobby/table/client狀態來源盤點 | rejected | 1 | 第一次因134079 tokens超過32768 context被拒，第二次摘要輸入仍45秒逾時無輸出；主管改用rg與窄測完成。localai log本輪2次、45.05秒、chars_out=0 |

| 2026-09-23 | code | qwen3-coder:30b | POS串列片段比較 | rejected | 1 | 說BK每筆開关与程式相反，root原始碼複核；本輪不再派同類判斷 |

| 2026-09-23 | code | gpt-oss:20b | POS連線錯誤格式化函式 | rejected | 1 | 120.1秒逾時無輸出；不重試，升級一般雲端窄實作；未回傳token數 |
| 2026-09-23 | review | huihui_ai/Qwen3.8-abliterated:latest | POS首次啟動商城欄位移除審查 | rejected | 1 | 45秒逾時無輸出；主管改用diff、Rust單測與前端型別檢查驗收 |
| 2026-09-23 | code | qwen3-coder:30b | Fluke 星燈茶會桌邊角色動態試跑建議 | edited | 2 | 7.53秒、156/158實測token；提醒呼吸／眨眼與接縫風險可用，但把待機誤讀成左右走動並要求30張序列，未採納；主管改成單角色分層待機計畫 |
| 2026-09-23 | code/review | qwen3-coder:30b / huihui_ai Qwen3.8 | S25多時間尺度K線特徵 | edited | 3 | code窄建議方向可用但欄位太粗；review 60秒逾時；code窄審查未見P1/P2。主管重寫成串流已完成K線狀態並補測試。合計3次、74.01秒、5806/175實測token |
| 2026-09-23 | code | qwen3-coder:30b | S25 runner特徵契約審查 | edited | 2 | 提醒feature_names可能影響續跑，但定性成P1過重；主管用s25_runtime與續跑測試複核，保留為線索。9.67秒、2496/98實測token |
| 2026-09-23 | code | qwen3-coder:30b | POS Windows quick-build diff review | used | 3 | 正確確認 --quick 略過 NSIS 且保留 full path；主管另以 node/YAML 檢查及 Windows runner 驗收 artifact。3.91s，2358/126 實測 token |
| 2026-09-23 | code | qwen3-coder:30b | POS Rust/Node 通訊計畫審查 | rejected | 1 | 將已列的退出、版本及交易保護誤報遺漏，範例依賴全域 Node；未採用。12.25s，2339/255 實測 tokens；主管以 cmp 及介面核對 |
