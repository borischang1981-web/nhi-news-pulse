# 全民健保新聞輿情監控站（NHI News Pulse）— 個人網頁版

> 瀏覽器使用、不需在公務電腦安裝應用程式。正式啟用公開網站前，請先確認機關對外部服務及資料管理的規範。

## 立即使用：免安裝、無帳號

1. 使用 `健保輿情監控站_個人免安裝版.html`，或開啟此部署包中的 `index.html`。
2. 以 Chrome 或 Edge 直接開啟；若只開啟單一 HTML，沒有自動 RSS 新聞，先用「新增新聞」「匯入 CSV / JSON」或「加入虛構示範資料」操作。
3. 新聞明細可編輯查證、事件、風險、健保連動、新聞稿及 QA 草稿。
4. 每次工作後，使用「備份資料」下載 JSON，避免瀏覽器政策清空資料。
5. 不要將未公開業務資料、個案病歷、個資、內部簽辦資料輸入外部網站。

## 變成有固定網址、可排程更新公開新聞的網頁

不需要在公務電腦安裝任何程式，也不需要把 OpenAI API 金鑰放在網站。

1. 準備你自己的 GitHub 帳號，建立新的 repository（例如 `nhi-news-pulse`）。此方案採用 GitHub Pages，**發布的網頁與 RSS 新聞會是公開內容**。
2. 將本部署包內的所有檔案及資料夾（包含 `.github/workflows`）上傳到 repository 的 `main` 分支根目錄。
3. 在 repository 的 **Settings → Pages → Build and deployment → Source** 選擇 **GitHub Actions**。
4. 到 **Actions → Update public news and publish website → Run workflow**，手動執行第一次新聞收集與上線。
5. 後續排程每四小時嘗試執行一次（GitHub Actions 排程並不保證準點）。開啟網站並重新整理，即可讀取最新公開 RSS 快照。
6. 網址通常為 `https://<github帳號>.github.io/<repository名>/`。此處只是網址格式，不是本工具已完成發布的網址。

### 雲端與隱私邊界（很重要）

- 雲端只取得媒體或政府公開 RSS 的**標題、有限簡介、日期、來源及新聞連結**，不下載全文，不使用機關內部資料，也不呼叫付費 AI API。
- 新聞分類／連動線索只是 **Python 規則初判**；沒有自動查核報導真偽，也不等於 AI 已審閱法律或提出機關立場。
- 手動新增的新聞、私人註記、風險改判、查核結果與草稿**預設只存在你目前瀏覽器的 localStorage**，不透過網頁寫入 GitHub。
- 不同瀏覽器／電腦、無痕模式、清除站台資料或更改網址，都可能無法讀取先前註記。請使用 JSON 備份及還原。
- GitHub Pages 本身不是僅個人可見的內網。不要把任何非公開文件、內部資料、個資、密件或 API key 上傳到 GitHub repository，也不要放入 `config/feeds.json`。
- 若機關網路禁止 GitHub Pages、GitHub 登入或外部雲端網站，仍可用單一 HTML 的**手動匯入版**；自動更新則需經核准的網站託管或伺服器環境。

## 系統功能與實際限制

| 功能 | 現況 |
| --- | --- |
| 新聞儲存、篩選、標籤、事件追蹤 | 已實作，瀏覽器直接可用 |
| 新增個人備註、新聞稿、QA | 已實作，預設僅存本機 |
| CSV 匯入／匯出、JSON 備份／還原 | 已實作 |
| RSS 自動收集、去重與初步分類 | 需將本包部署至 GitHub Actions 並成功執行 |
| 最新新聞日期與來源 | 保留 RSS 原始時間戳；部分 RSS 未提供日期者不會納入晨報 |
| AI 查證、AI 新聞稿自動撰寫 | **未提供背景 API**；提供「複製 ChatGPT 分析指令」供人工核對 |
| 官方完整新聞／正文擷取 | **未提供**；請點擊原始來源，遵守著作權及 RSS 使用條款 |
| 國定假日精確判斷 | **未提供**；晨報起迄期間可手動調整 |
| 監測涵蓋率 | RSS 自帶限制、Google 索引落差及網頁改版可能造成遺漏；絕非全網監控 |
| 推播通知、多人共編、權限控管 | **未提供**；需後續經核准環境建置 |

## 來源與著作權

本專案已設定：衛福部焦點新聞及澄清 RSS、疾管署新聞及澄清 RSS、中央社政治／生活／產經／地方／社會 RSS，以及透過 Google 新聞 RSS 的健保署、立法院、勞動部、移民署、廣義健保政策索引。網站來源設定位於 `config/feeds.json`。

中央社 RSS 使用條款要求標示來源且不得轉載全文；本工具只保留公開 RSS 標題與摘要（限制 320 字）、連結，並連回原站。請自行確認使用方式符合最新的條款。

- https://www.cna.com.tw/about/rss.aspx
- https://www.mohw.gov.tw/cp-2661-6125-1.html
- https://www.cdc.gov.tw/RSS
- https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages

## 如果更新失敗

1. 打開 GitHub repository → Actions → Update public news and publish website，查看當次執行紀錄。
2. 來源 RSS 若改版、阻擋機器人或不再提供有效日期，程式會記錄來源錯誤，保留60日內既有項目。
3. 可在 `config/feeds.json` 停用或替換 RSS／索引來源；`scripts/collect.py` 使用 Python 標準函式庫，不需額外安裝套件。
4. 若網頁顯示「公開來源 0 筆」，代表尚未完成更新或所有來源均未回傳符合規則的新訊息，**不代表沒有新聞**。

## 資料使用聲明

本工具是供個人監測與備詢準備的原型，不代表衛福部、健保署或其他政府機關的官方立場。涉及法規適用、醫療案件及媒體爭議的內容需經人工核實，不應將自動分類或初步風險標籤直接用於對外正式發布。
