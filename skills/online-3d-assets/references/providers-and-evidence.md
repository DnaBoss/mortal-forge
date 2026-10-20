# 來源、作品與 AI 工具查核

查核日：2026-10-19。以下分開列官方規格、已讀程式碼、看過的畫面與作者自述。未登入、未生成模型、未執行供應商外掛。動態價格、模型名及套件版本在使用前重新查。

## 官方入口

| 服務 | Skill | MCP：讓 AI 呼叫工具的接口 | Plugin：宿主或編輯器外掛 | 本輪確認程度 |
| --- | --- | --- | --- | --- |
| Tripo | `tripo-cli` 內附 `skill/SKILL.md` 與工作範例 | 新 CLI 的 `tripo mcp`；另有 VAST-AI-Research/tripo-mcp | 官方 Codex Tripo 3D；UE、Blender 等外掛 | 官方文件＋npm 0.7.0 內的 Skill、命令與 MCP 程式碼；舊 MCP 來源也已讀 |
| Meshy | `meshy-dev/meshy-3d-agent` | `@meshy-ai/meshy-mcp-server` | 官方 Codex；Skill repo 有 Claude/Cursor plugin manifest；UE、Blender 等外掛 | 官方交叉連結＋GitHub Skill／manifest＋CLI 0.4.4、MCP 0.6.4 套件來源 |

官方來源：

- [Tripo CLI](https://developers.tripo3d.ai/en/docs/cli)、[Codex 外掛](https://developers.tripo3d.ai/en/docs/codex-plugin)、[編輯器外掛](https://developers.tripo3d.ai/en/docs/plugins)。
- [Tripo 舊 MCP 原始碼](https://github.com/VAST-AI-Research/tripo-mcp)、[Tripo CLI 原始碼](https://github.com/vast-enterprise/Tripo-API-CLI)。
- [Meshy AI 整合](https://docs.meshy.ai/en/api/ai)、[官方 Skill](https://github.com/meshy-dev/meshy-3d-agent)、[MCP](https://github.com/meshy-dev/meshy-mcp-server)、[CLI](https://github.com/meshy-dev/meshy-cli)。
- [Meshy Codex 外掛](https://docs.meshy.ai/en/webapp/plugins/codex/introduction)、[UE 外掛](https://docs.meshy.ai/en/webapp/plugins/unreal/introduction)。

「官方」依供應商文件連到該套件／repo 判定，不是只看 GitHub 名稱。CLI 是可讓 AI 執行的命令工具；Skill 是操作知識；MCP 是工具接口；Plugin 是打包入口，四者不能混稱。

## 我們採用的方式

自己的技能管預算、選樣、保存與 UE 驗收，供應商工具負責生成／查任務／下載。一次選 CLI 或 MCP，避免同一任務兩邊各送一次。現階段優先可輸出 JSON、可分開提交與等待、能回傳 task ID 的官方 CLI；沒有必要再做自己的生成 API 包裝。

本機是 Linux、UE 5.8.3：Tripo 插件表列 UE 5.6.0，Meshy 文件列 UE 5.4–5.7 和 source package。這些都不能證明 Linux／5.8.3 相容。先以檔案匯出及既有 UE 匯入能力規劃，外掛另做隔離編譯與真匯入測試；不裝進正在用的遊戲專案來碰運氣。

外掛頁面存在不代表本帳戶插件目錄可用，更不代表此 session 已載入。Meshy Skill 的不同文件仍有 CLI 0.4.0／0.4.3 等版本文字，而本輪 registry 是 0.4.4；應鎖定驗過的套件並讀該版本命令，不把範例當不會過期的接口。

## 實作抽查發現

以下是讀取已發布套件的實際程式分支，未執行遠端生成，也不是完整安全稽核。

| 套件與位置 | 查到的實作 | 對我們的決策 |
| --- | --- | --- |
| Tripo 0.7.0 `dist/commands/make.js` | dry-run 在正式 client 執行前分支返回；非互動 confirmPlan 直接 true | 離線預演有入口，但程式內確認不可當預算授權 |
| Tripo 0.7.0 `dist/commands/batch.js` | retries 預設 1；依 job key 的 success 略過；runJob 後才寫 batch 結果，catch 後可再次嘗試 | 逐件保存 task ID；不直接啟用無人看管的預設重試批次 |
| Tripo 0.7.0 `dist/core/task-service.js` | 取得 task ID 後記 history／context；dry-run 的本機檔案使用 placeholder | 發生超時先查 history，不新建任務 |
| Meshy 0.4.4 `dist/cmd/make.js` | max-credits 在執行前比對 plan.estimatedCredits；dry-run 直接輸出；支援分段停止 | 估價上限只覆蓋此計畫；專案累計費用另記 |
| Meshy 0.4.4 `dist/internal/download.js` | 下載流程有串流大小界線、暫存發布、SHA-256、材質連結處理 | 重用官方下載能力，再獨立核對成果與備份，不重寫下載器 |
| Meshy MCP 0.6.4 `dist/tools/` | 有生成、查任務、列任務與下載的 registerTool 呼叫 | 確認工具有實作；未證明已能在本機呼叫 |
| Tripo 舊 MCP `src/server.py` | 有文字／圖片生成、Blender 匯入、場景操作及執行 Blender 程式碼 | 功能較廣，若只需生成不必同時接入整套 Blender 控制 |

本輪抓取 GitHub：Meshy Skill `92ffd747638284f6ccdf419d764e6f14753ec298`；Tripo 舊 MCP `7e8ec9eeb751e38f7bd1955f9df961c2676c5e38`。npm 壓縮包雜湊及抽查檔案雜湊見研究專案的 evidence JSON；來源快照留在本機研究資料夾，不安裝也不執行套件。

## 費率與保存容易誤讀的地方

- [Tripo 點數說明](https://www.tripo3d.ai/help/credit/how-do-credits-work)明確區分 Web App 與 API 點數；[API billing](https://developers.tripo3d.ai/en/docs/billing)列凍結、成功扣除、失敗／取消釋放，以及逐 task 的 usage。API 網路超時不代表服務端失敗。
- [Meshy API pricing](https://docs.meshy.ai/en/api/pricing)與[網頁 pricing](https://docs.meshy.ai/en/webapp/pricing)的操作費率不同。網頁文件部分段落與表格也不一致，不自行挑較便宜的說法。CLI／MCP 要用對應 API 費率，帳戶額度是否共享仍以該登入方式和實際計費頁核對。
- [Meshy asset retention](https://docs.meshy.ai/en/api/asset-retention)寫一般 API 模型最多三天，Enterprise 例外；簽章網址按 expires_at 到期，重新 GET 不延期。原始模型與材質應在成功後立即取回。
- Meshy API 文件另公告舊 `model_type: lowpoly` 於 2026-10-30 退役。不要把它寫成長期預設；固定並記錄實際支援模型，執行前再核對。

## 看過的作品與可採用心得

### 1. Tripo：官方騎士製作案例

[原文與完整步驟](https://www.tripo3d.ai/blog/game-industry-character-workflow)；[UE 結果圖](https://cdn-blog.holymolly.ai/media/production/game-industry-character-workflow-49-an-unreal-engine-viewport-showing-the-imported-armored-character-on-a-gridded-floor-with-the-content.webp)；[頭部網格圖](https://cdn-blog.holymolly.ai/media/production/game-industry-character-workflow-41-a-wireframe-character-head-view-illustrating-manual-positioning-scaling-and-repair-of-components-dur.webp)。

本輪已打開兩張原圖：可見 UE 編輯器中的藍色盔甲騎士，以及頭髮與臉部網格。這只能支持畫面中確有整理後角色，不證明原始生成一次成功、動畫合格或我們能達到同品質。作者使用拆件、重新組裝、修洞、重做貼圖座標及材質轉貼；官方也未把該骨架流程宣稱為免人工的正式角色方案。採用重點：先保存原始貼圖座標，後製用副本；不把漂亮結果圖當零修整成本。

### 2. Meshy：開發者 Abhilasha Singh 的製作紀錄

[作者原文](https://www.singhabhilasha.com/case-studies/ai-native-pipeline.html)；[Meshy 礦車](https://www.singhabhilasha.com/assets/case-studies/ai-pipeline/03-meshy-minecart.png)；[Unity 內礦車](https://www.singhabhilasha.com/assets/case-studies/ai-pipeline/03-riley-lava-cart.png)；[Blender 角色整理](https://www.singhabhilasha.com/assets/case-studies/ai-pipeline/03-blender-rig.png)。

已檢視三圖：Meshy 介面顯示礦車 2,987 faces；另一張為 Unity 遊戲視窗中的礦車；Blender 圖顯示鵝角色及骨架。可觀察配色與輪廓，但沒有下載模型，不能確認網格可編輯、權重正確、效能或發布狀態。作者說有重做輪子、修整、骨架與動畫；這支持「AI 底模＋局部整理」的路線。頁首稱三款已發布，但 Riley 區段又說等 beta，因此不採其發布數或製作時間作保證。

### 3. 社群心得：有用的失敗模式，不當客觀排名

- [三個月使用心得](https://www.reddit.com/r/meshyai/comments/1sjig1n/using_ai_generated_3d_assets_in_my_game_3_months/)：作者表示道具較順、主角多次重生成仍不合而另請人；留言指出黏連、貼圖座標及面數需要整理。採用「固定次數後改修整／換路」；其 80% 成功率、節省月份與 50 次主角嘗試均為自述，未驗證，附圖未成功取得。
- [宣稱 200 次比較的貼文](https://www.reddit.com/r/aigamedev/comments/1ucirid/meshy_vs_tripo_vs_rodin_vs_hunyuan_for_game/)：標題 200 次、內文 100 個資產，未附可重現明細，留言也質疑樣本並有相反推薦。其百分比不納入排名或預算。只採「按素材類型比較、把修整時間計入」作待測假說。
- [較早的開發者討論](https://www.reddit.com/r/gamedev/comments/1isoq3k/meshy_or_any_other_3d_generative_ai_impressions/)：有人覺得遠景可用、有人指出動畫與網格問題。舊版本心得不直接推論現版；用來設計近景／動作檢查，而不是判死某服務。

沒有以廣告式比較站、社群票數或自評數字宣稱誰品質最好。現階段能選的是我們的流程；供應商勝負留給同圖、同條件、UE 內實測。
