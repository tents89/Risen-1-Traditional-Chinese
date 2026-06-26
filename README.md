# Risen Series Traditional Chinese Mod (《異世界》系列繁體中文修正檔)
>《異世界》為早期台灣代理商對此款遊戲的譯名。 

本專案為遊戲 **《異世界》（Risen）系列作** 提供繁體中文化模組。由於現存的舊版繁中補丁一代於 2023 年的更新導致失效。為了讓繁中玩家能舒服的體驗劇情，特此整合並製作本系列繁體中文修正檔。

---

## 模組功能

### 共通修正
* **詞彙調整**：修正繁簡轉換錯別字。
* **新版適配**：支援 **Steam 最新現行版本**（GOG 版本未測試）。

### 各代版本說明
| 遊戲版本 | 文本基礎來源 | 相容性與備註 |
| :--- | :--- | :--- |
| **Risen 1** | 3DM v2.0 繁體版 | 針對 Steam 2023 年大更新進行相容性修復與 DLL 修正。 |
| **Risen 2** | 蒹葭 v2.0 文本 | 完整轉換繁體。 |
| **Risen 2** | 3DM v6.0 文本 | 完整轉換繁體。 |
---

## 安裝說明

1. **下載檔案**：下載本專案釋出的繁體中文語系包。
2. **放置路徑**：解壓縮檔案後，依據您要遊玩的代數，解壓縮到對應的遊戲**根目錄**中：
   * **Risen 1**：`Steam\steamapps\common\Risen\`
   * **Risen 2**：`Steam\steamapps\common\Risen 2\`
   * **Risen 3**：`Steam\steamapps\common\Risen 3\`

3. **啟動遊戲**：開啟遊戲即可享受繁體中文內容。

---

## Credits
 
* **腳本參考**：
> * [GitHub - hhergeth/RisenEditor](https://github.com/hhergeth/RisenEditor)
> * [GitHub - Baltram/rmtools](https://github.com/Baltram/rmtools)
> * [worldofplayers社群](https://forum.worldofplayers.de/forum/forums/417-World-of-Risen)
> * [Risen2jptools](https://u10.getuploader.com/gothic3/index/date/desc/2)

* **文本基礎**：感謝3DM與蒹葭漢化組的辛勞。

### Risen 1 相關
* **DLL 修正**：取自 [适用于更新后崛起1的Steam最新版汉化补丁](https://steamcommunity.com/sharedfiles/filedetails/?id=3732711224) 。

[!NOTE]因為不確定GOG是否可用，因此若DLL放入後無法開啟，請用十六進制編輯器(如:HxD)去編輯原始dll
> 記憶體位置 `00527940` (可能不同但下面這部分應該是差不多的)
> 原始 02 00 00 00 EB 03 48 8B D9 BA 00 01 00 00 48 8B
> 修正 02 00 00 00 EB 03 48 8B D9 BA 00 08 00 00 48 8B

---

## 免責聲明

* 本模組僅供愛好者交流與學習使用，所有遊戲文本版權皆歸原遊戲開發商與發行商所有。
* 使用AI輔助製作。

---

## 其它
請看[Wiki](https://github.com/tents89/Risen-1-Traditional-Chinese/wiki)
