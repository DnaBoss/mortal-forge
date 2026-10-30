---
name: mall-standard-intake
description: 核商城 API 經共用收集器保存標準資料，或核歷史原頁、續跑位置與Web送件意圖時使用；只跑自有隔離驗收或有界唯讀來源，不替代畫面或正式站安裝驗收。
---

# 商城標準資料隔離驗收

先查 `mortal_catalog` 的 `mall-standard-intake`。這批只補技能與清單，MCP 執行介面尚未實作；範例的 `not_implemented` 不可當可呼叫工具，也不要重啟共用服務補掛載。

程式來源唯一是商城 repo 的 `apps/api/test/standard-intake-isolated.py`，不要複製到工具 repo。現在已存在的版本位於 `/home/cash/work_space/newretail/crossec-standard-observability`；合併或搬工作樹後重新核路徑、版本及清單，不猜主工作目錄已經有此程式。

用已有 Python protobuf 環境，不以 `-O` 關掉斷言。先核已安裝商城依賴、Aletheia 已編譯的官方描述檔、既有 runtime 目錄的 `receipt.json` 與固定映像快取；不自動安裝、拉映像、新增Rust編譯或複製收件執行檔；腳本會在商城工作樹建立API bundle，並只在自有DB建立schema。

```sh
python3 <mall-root>/apps/api/test/standard-intake-isolated.py   --mall-root <商城工作樹>   --aletheia-root <Aletheia工作樹>   --runtime-dir <既有且版本已核對的執行目錄>   --evidence-root <已存在的自有證據父目錄>
```

路徑是操作者明確選定的自有來源，不能當正式站設定；從腳本核當前支援的參數，不把清單文字當 shell 執行。工具用不可跟隨連結、不可重入的本機鎖，拒絕同時再開一輪；主要執行上限240秒，之後仍清理自有容器、網路及子程序。

正常輪讀完整 `receipt.json`、來源原文與保存批次，核原文／時間／嚴重程度／身分及追蹤、HTTP分布、錯環境403及資料不變、停止後保存內容、所有正常退出及精確資源清理。收據非 `pass`、必要清理非零或差異存在，都不能列通過。只讀摘要與少量身分，不把整份原文或以原文作鍵的差異表印到工具輸出。

期限對照只加 `--negative execution-budget`：預期在隔離業務GET後退出1並留失敗收據，另核精確資源已清；這不是出口故障或正式斷線驗證。逾時先查同一程序句柄與已留證據；確認原程序已終止後才決定下一個不同驗證，不盲重送。

既有固定樣本曾核187筆日誌、7段追蹤及指標保存；數字只指該輪，不是新版本重跑保證。預設只核保存；原首頁與兩站安裝仍未驗，不授權真付款、通知或故障注入；部署沿用使用者的持續授權，仍須完成必要測試與驗收。

API隔離命令可加 `--receiver-binary <既有成品>`：唯讀掛載，不編譯或複製大檔，分段核執行前後摘要；僅證該成品，不證來源建置對應。再加 `--query-readback`，初始未就緒503保留；明確補索引最多一次16批／1MiB／1000項／3秒。日誌、指標與追蹤各最多10頁、每頁100項、合計1000項；獨立核資料庫身分，逐筆對官方完整內容、收件及原位置、精確整數型別與來源時間。指標逐資料點拆開核，不把指標名稱數當資料點數。API十六進位追蹤編號須轉成官方描述檔的bytes表示才比對，不新增來源屬性。

查詢對照加 `--negative query-body`、`query-time` 或 `query-position-type`，各預期退出1，核實際失敗位置與精確資源清理。這些是讀回比較的陰性，並非產品程式變異分數。查詢來源完整性保留未知；統計、跨服務請求關聯、原首頁與正式安裝仍須另外驗。

再加 `--analysis-readback` 可核同一隔離API服務的統計與日誌／追蹤連線。先讀一次全部統計候選，每筆對保存的官方單點；兩個商品請求各用原起訖讀一次統計，核原候選、來源、名稱、代表內容、秒數定義、計數與總和／最大／最小、完整分布與百分位區間。單筆分布只證區間，不說精確百分位；其他系列缺起點基準維持未知，不補零、不把兩個不同區間相加。指標重送／重置與多份分布合併須另驗。

同一請求關聯只發一次，先按保存的請求編號獨立篩完整事件、時間及位置，再核各日誌連到正確追蹤、原觀測索引與外部父缺失。這仍只有一個API服務，不是兩服務串聯、原首頁或正式安裝驗收。加 `--negative statistics-count`、`statistics-distribution` 或 `correlation-link` 各預期退出1；只證讀回比較器，不能稱產品變異100%。原回覆仍存私有檔，錯誤對照只改記憶體副本。


## 歷史頁面保存分支

需要核原文與位置一起保存時，先讀商城`docs/observability/selfhost-collector-installation.md`的保存核心範圍。程式來源是商城`apps/api/scripts/cloudwatch_history_store.py`；這是標準庫模組，有界AWS入口見下節；完整晚到重掃、確認送件及MCP介面尚未實作，不能當正式來源切換。

```sh
python3 -B <mall-root>/apps/api/scripts/cloudwatch_history_store_test.py
python3 -B <mall-root>/apps/api/test/fixtures/cloudwatch_history_mutation.py --source <mall-root>/apps/api/scripts/cloudwatch_history_store.py --evidence-root <已存在的私人證據目錄>
python3 -B <mall-root>/apps/api/test/fixtures/cloudwatch_history_crash.py --source <mall-root>/apps/api/scripts/cloudwatch_history_store.py --evidence-root <已存在的自有證據目錄>
```

只用自有暫存資料庫，沒有Docker、AWS、安裝或正式憑證依賴。變異工具只改新證據目錄內的副本，每次8秒／整次120秒、最多256個；固定來源與測試bytes，來源改動不算當前通過。自有證據目錄建立後，基準失敗或逾時也留失敗收據與部分結果；前置路徑拒絕只回錯誤。存活變異使工具退出1，等價判斷另經反方與實際路徑核對，保留原分數，不由清單或工具自動放行。範圍是比較、布林、raise及整數變異，沒有SQL字串。

中斷對照只建立兩個自有Python子程序，每個標記最多4秒、停止後等待最多3秒，精確PID停止並回收；正向核交易中斷後原文／位置不變，反例先提交位置必須被拒。這不是硬體斷電；資料庫容量也不涵蓋交易日誌總額。必要收據、固定檔案摘要或精確清理不符即停止，不把27／28等歷史案例數當新版保證。

續跑準備另核位置與查詢開始時間：開始時間須在來源要求前取得，與原頁同交易保存。同一位置再出現採最早時間，現在時間不得早於最新要求；年齡加等待預算達24小時就停，預算限1至18000毫秒。舊資料缺時間不補猜，保留原文並停止續跑。保存核心與AWS入口分開核；本機時間守門不保證AWS接受位置。中斷正向也須核已保存時間不變。


## 有界AWS讀取與續跑

需要讀已授權的商城歷史時，使用同一商城工作樹的`apps/api/scripts/cloudwatch_history_reader.py`。此入口只允許既有mall身分與ap-east-2台北區域，固定官方TLS端點，先用STS核實際帳號，再讀頁。先從權威容器配置核group／stream與站點，不靠內文env猜；只有舊配置時明列未刷新，不把來源group接受當主機安裝證據。

固定查詢檔須為自有0600一般檔案，最多16KiB，內容是保存核心的九欄：profile、account、region、environment、logGroupName、logStreamNames、startTime、endTime、unmask。帳號須先核實，單一stream，日期窗包含兩端、unmask=false。保存目錄須0700；新資料庫或續跑資料庫使用同一查詢檔，位置只取來源回覆，不手填或轉成CLI的starting-token。

```sh
python3 -B <mall-root>/apps/api/scripts/cloudwatch_history_reader.py --query <私人固定查詢檔> --db <私人保存目錄>/history.sqlite --max-pages 2 --max-events 40 --page-size 20 --seconds 60
python3 -B <mall-root>/apps/api/scripts/cloudwatch_history_reader_test.py
python3 -B <mall-root>/apps/api/test/fixtures/cloudwatch_history_mutation.py --source <mall-root>/apps/api/scripts/cloudwatch_history_reader.py --evidence-root <已存在的私人證據目錄>
```

單輪最多10頁、1000筆、每頁100筆；要求總預算最多120秒，單命令最多18秒，stdout上限1MiB／stderr64KiB，最多額外讀一個byte判斷超限。清理等待與SQLite交易不算整體硬期限。關閉CLI自動翻頁、嘗試次數1、不重送；頁滿、時間到而hasNext仍真，只是部分完成。每頁原始bytes與取得時間一起保存，不輸出token或內文。DB上限不涵蓋交易日誌／其他證據總額。

退出1先讀失敗結果與保存狀態；身分錯、來源失敗、時間未知、過期或容量滿時不前進。要續跑先核來源與原位置，不能因失敗就自動重掃或重送。此分支用已有AWS CLI；不裝套件、重啟共用服務或新增費用，不含標準送件、完整來源時間線、原首頁、正式安裝或MCP掛載。

變異工具會固定相依保存模組；基準逾時保留失敗、不開始變異。單個改壞版本超過8秒時，精確停止其自有測試程序群，記真退出代碼及timedOut，再按120秒總預算處理下一個；逾時拒絕與斷言拒絕分開核。不把原分數或等價審查自動改成工具成功。


來源命令已擷取的失敗會另存私人DB，最多16筆；滿額不刪舊資料，stdout最多1MiB／stderr64KiB。逾時與超限僅存已讀有界部分；容量滿可能diagnosticSaved=false，仍保留原來源錯誤及頁面位置。清理再失敗不覆蓋原錯誤，cleanupConfirmed=false及安全摘要明列，必要時列自有PID；不要因摘要無原文就宣稱沒有來源錯誤。

讀取核心變異宜加--start 0 --count 32分批，後續起點依完整收據接續。核各批sourceSHA256、testSHA256、dependencySHA256相同，起點及executed覆蓋全體、無重疊；保留存活及逾時原結果，不能只加總pass批次。


實際站點對照沿用已核權限：每批最多6個唯讀GET、並行最多2、沒有重試。保存每次開始／結束、標記與回應requestId，再從固定日期來源窗逐筆核access的method／route／status及時間；原文與五欄對照，無後頁只代表當次來源分頁結束，不保證晚到全完整。health只有status/timestamp時不當依賴就緒；根readyz與api/v1路徑分開核，404不直接判健康故障。本機來源或舊盤點不當線上同版／安裝證據。


## Web原頁分支

Web先用既有reader選已核Web group／selfhost；QA0事件不當沒有日誌，仍有後頁算部分。cloudwatch_web_otlp.py只產標準JSON，原文／CW時間／接收時間／事件身分保留，等級未知，不猜版本／追蹤／堆疊；1MiB原頁、100事件、512KiB輸出，超限整頁拒絕，沒有發送或清理原頁。

```sh
python3 -B <mall-root>/apps/api/scripts/cloudwatch_web_otlp_test.py
python3 -B <mall-root>/apps/api/test/fixtures/cloudwatch_history_mutation.py --source <mall-root>/apps/api/scripts/cloudwatch_web_otlp.py --evidence-root <私人證據目錄>
python3 -B <mall-root>/apps/api/test/cloudwatch_web_isolated.py --mall-root <商城工作樹> --aletheia-root <Aletheia工作樹> --runtime-dir <既有且摘要已核執行目錄> --evidence-root <自有私人證據父目錄> --source-root <reader的query及sqlite目錄> --site prod
```

source-root須有prod-query.json／prod.sqlite（或qa兩檔），至少一筆、最多10頁／1000筆，空來源不能當格式通過。只用既有固定快取映像與runtime，不讀AWS／下載／編譯；三自有容器與隔離網路，240秒預算後仍精確清理。正向核原五欄／位置／全部標準內容、錯環境403表不變、正常停後全批／表與原DB。只消除完全空optional scope有無表示差異，保留有值內容。

陰性加--negative comparator-body，應退出1且source-body比較失敗，仍核精確清理；不改原頁，不是正式故障。當輪13案例／36變異與40真樣本保存只限同摘要，不代表自動sender確認、完整歷史、最新接收端、原首頁或安裝，不新增純文字無秘密的保證。


## Web送件紀錄分支

需要核已存Web原頁的送件意圖時，使用商城cloudwatch_delivery.py；已接單次HTTP／HTTPS候選；來源自動送件、下游保存確認與MCP介面尚未接上。沿固定查詢產生內容，先提交unknown再交出payload；原頁／位置保留，入口200完整接受只能記ingress_accepted。未知、接受與重複意圖均先查原紀錄，保持不自動重送。

```sh
python3 -B <mall-root>/apps/api/scripts/cloudwatch_delivery_test.py
python3 -B <mall-root>/apps/api/test/fixtures/cloudwatch_history_mutation.py --source <mall-root>/apps/api/scripts/cloudwatch_delivery.py --evidence-root <既有私人證據目錄>
python3 -B <mall-root>/apps/api/test/fixtures/cloudwatch_delivery_crash.py --source <mall-root>/apps/api/scripts/cloudwatch_delivery.py --evidence-root <既有私人證據目錄>
```

中止工具只建兩個自有合成資料子程序，標記4秒／回收3秒；核UPDATE後提交前及提交後狀態、原五表及完整性。加--negative-unsafe-reset應退出1，保留失敗收據；再以收據精確PID核沒有剩餘。16意圖、每份內容512KiB及回應64KiB；容量沿HistoryStore，交易日誌合計上限仍未知。變異固定mapper與保存核心，不碰產品來源；核基準、摘要、所有結果與零跳過，不把入口接受當成下游確認，也不當正式站故障、安裝或畫面。


核送件候選時，先讀商城安裝文件的「單次Web送件候選」，再跑以下自有合成對照；這些命令不讀AWS、不送正式入口。

```sh
python3 -B <mall-root>/apps/api/scripts/cloudwatch_delivery_sender_test.py
python3 -B <mall-root>/apps/api/scripts/cloudwatch_delivery_sender_process_test.py
python3 -B <mall-root>/apps/api/scripts/cloudwatch_delivery_sender_guard_process_test.py
python3 -B <mall-root>/apps/api/test/fixtures/cloudwatch_history_mutation.py --source <mall-root>/apps/api/scripts/cloudwatch_delivery_sender.py --evidence-root <既有私人證據目錄>
python3 -B <mall-root>/apps/api/test/fixtures/cloudwatch_delivery_sender_crash.py --source <mall-root>/apps/api/scripts/cloudwatch_delivery_sender.py --evidence-root <既有私人證據目錄>
```

同版快測、真程序期限、真連線、所有改壞結果與來源摘要均需通過；中止反例加--negative-unsafe-reset應退出1。任一失敗先讀收據與原紀錄，不自動再送。中止只涵蓋提交未知後HTTP前，以及HTTP完成後保存結果前；私人合成暫存會留在證據目錄，不含真憑證。仍須另驗下游確認、最新接收端、原首頁與兩站安裝。


Web隔離命令加--delivery-sender可跑真單次候選到原共用Collector；唯讀掛已核本機curl及系統庫，守8.4與檔案摘要，不裝套件。來源副本最多8MiB／10頁，原庫不改。加--receiver-binary <既有成品>及--query-readback可核指定成品的有限分頁查詢；僅成品摘要，不代表來源建置對應。初始未就緒503保留；明確index-begin及最多一次16批次／1MiB／1000項／3秒index-step後查最多100項，失敗即停止並查原狀態。

核保存原文、完整標準內容與出現次數，再核API全文、奈秒及從SQLite官方解碼獨立列舉的座標，來源完整性保持未知。三個陰性分別加--negative comparator-query-body／comparator-query-position／comparator-query-position-type，均須退出1；401／403／400及精確清理另核。前階段收據只驗一頁及一個下游批次，現行多批對照見下段；下游確認狀態、任意頁形狀、原首頁與正式兩站安裝另驗。


加--query-page-size 7核小頁續行，1–100項／最多10頁及1000項；空續頁、重複cursor或超上限直接失敗，不自動重試。按全文及出現次數核全部批次，所有receipt／座標及db/run／保存上界／保留代數從自有SQLite獨立核，不只互比回應。

--split-delivery-batches在自有送件間等2.5秒核自然拆批，原Collector配置不改。--restart-receiver以自有client保留隔離網路，正常停／重啟接收端後重新查完整分頁、全部事件／快照與所有表；不重送來源。新增兩個陰性--negative comparator-query-snapshot（所有頁同錯身分）與comparator-restart-body（重啟後壞原文）應退出1，連同原三種對照、同版摘要與精確清理核。

固定40筆／2批／前後各6頁，只涵蓋一次正常重啟；完整歷史、長期／斷電恢復、來源建置對應、下游確認、原首頁與兩站安裝另驗。
