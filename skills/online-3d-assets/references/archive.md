# 保存與恢復

## 一件素材的可恢復資料

```text
assets/generated/<asset-id>/<revision>/
  input/                 Original reference images and request specification
  raw/                   Unmodified downloaded geometry and all textures
  work/                  Editable Blender/DCC files and changed textures
  export/                Engine import files for this revision
  evidence/              Fixed views, measurements and UE validation
  asset.json             Provider, lineage, cost, files and acceptance
```

新候選、新貼圖、新網格各有新修訂，不覆蓋舊版。`asset.json` 用 [範例](../assets/asset-record.example.json)；未知值用 null／not_run，不以 0 或 true 填空。範例不是已合格資產。

每個付費步驟記 provider、model version、操作、task ID、parent task、輸入 SHA-256、請求參數、種子、時間、預估與實扣、狀態、輸出位置。索引可用單一 JSON／CSV，不必先建資料庫。

範例的 `files` 每筆填 `path`、`role`、`bytes`、`sha256`；`inputs` 同樣記來源檔與現算雜湊。路徑以素材修訂根目錄為基準。靜態道具的動畫檢查可明確填 `not_applicable` 並記理由，不要把沒跑的檢查寫成通過。

## 去重與斷線

請求識別值由「供應商＋模型版本＋操作＋輸入檔雜湊＋標準化參數＋種子＋父版本」計算；同一字串 prompt 或檔名不夠。打算要新候選時明確換 seed／candidate ID，不能誤當重送。

狀態分開：`planned`、`submitted`、`submission_unknown`、`running`、`succeeded_remote`、`archived`、`ue_accepted`、`rejected`、`failed`。遠端成功不等於保存成功；檔案下載失敗只重下載舊 task，不重新生成。

送出前寫本地 request ID，收到 task ID 後立刻保存。斷線沒有 task ID 時查遠端歷史、usage、凍結點數與時間範圍；只靠餘額變動不能唯一確認哪一件。若無法對應，保留未知狀態與預留額度，不猜測未扣款。人工確認或廠商回覆後才續行。

Tripo 0.7.0 batch 只依 job 名稱與成功狀態略過，並非請求內容去重；同名改參數可能跳過，新名可能重做。`--retries 0` 可關閉批次再次嘗試，但不是解決中斷恢復或避免重複扣款的完整保證。本案先逐件記 task ID，不直接使用無人看管重試批次。

## 下載與原始檔

- 成功即下載，保存模型、全部貼圖、預覽及去除敏感欄位的任務資料；對每個檔案現算大小和 SHA-256，再讀回核對。雜湊不可手填，也不能只核對檔名。
- OBJ 要連同 MTL 與貼圖；FBX 要檢查材質及外部圖片；GLB 要檢查是否包含完整資源。保留一份可編輯來源及 UE 匯入檔，不能只保存截圖。
- 不重排原始貼圖座標。若要重展 UV（模型表面對應圖片的位置），先複製原檔，再把原材質轉貼到新版；原始檔作來源保留。
- 臨時網址、登入 token、帶簽章查詢參數不進 Git。私有原始回應保存在受限本地位置；共享紀錄只保留供應商、task ID、非秘密參數與本地檔案位置。
- Meshy 非 Enterprise API 的官方上限為三天，下載連結依 `expires_at` 失效，查詢不會延期。Tripo 本輪未核實統一保留期限，不能假定永久；一律立即下載。

## 備份與版本管理

小型需求、參數、授權來源、成本紀錄與驗收圖進 Git。大模型、貼圖與 `.blend` 優先沿用專案已有的大檔儲存；沒有才提出 Git LFS 或物件儲存方案，先估費、權限與還原方式，不自行購買或改寫歷史。

至少保有工作副本與獨立備份。相同磁碟另一個資料夾只算副本，不能宣稱防硬碟損壞；遠端備份涉及外部寫入須有授權。LFS 指標本身不是模型，驗收時必須實際取回內容。

備份記位置、時間、檔案數、總大小及雜湊清單。從第二份取回一個完整資產到新暫存資料夾，核對雜湊並用 Blender／UE 重新開啟，才標 `restore_verified`。未有第二份就標缺備份，不刪唯一副本。

## 授權與來源

保存輸入圖來源與使用權、生成時方案、官方授權頁 URL／查核日期、是否須標示出處、公開／私有設定及付款紀錄索引。不把廠商提供的商用權推論為輸入圖片一定合法，也不把後來升級付費推定能追溯改變舊產物權利。條款改動時重新核對；有疑義的素材先不進發布包。

## 交接最小清單

列合格／待修／拒絕的 asset ID、實扣與未知費用、剩餘額度、正在跑的 task ID、已保存／尚未下載的檔案、備份與讀回狀態、下一個不重複付費的動作。不要用供應商儀表板或聊天記憶代替自己的紀錄。
