# Risen Modding Tools / Risen 遊戲模組工具指南

A collection of specialized Python tools for unpacking, packing, and extracting text/resources from the *Risen* game series (Risen 1, Risen 2: Dark Waters, and Risen 3: Titan Lords).

一套專門用於《異世界》（Risen）系列遊戲（Risen 1、Risen 2、Risen 3）進行資源解包、打包以及文本提取與回填的 Python 工具。

---

## English

### Environment Requirements
- **Python Version:** `Python 3.11`

### 1. risen_pak (Resource Unpacking & Packing)
Used to extract and rebuild game resource archives (`.pak` files).

* **Supported Games:** `Risen 1` and `Risen 2: Dark Waters`.
* **Important Note for Risen 3:** Do **not** use this tool for *Risen 3*. Please use `r3resman.exe` instead to handle packing/unpacking for the third game.

### 2. risen_text (Localization & Text Tools)
Used to extract (unpack) and inject (pack) localization text strings for editing or translation.

* **Supported Games:** `Risen 1`, `Risen 2`, and `Risen 3`.
* **Crucial Guide for Risen 3:**
    * The localized text stored in Risen 3's `.bin` files contains only **hash values** rather than plaintext IDs.
    * To successfully decode and restore the actual in-game IDs, it is highly recommended to use the mapping file `lianzifu-unpack.risen3.csv` provided by Nicodex's repository:
      [Nicodex Lianzifu GitHub Repository](https://github.com/nicodex/lianzifu/tree/master)


### 3. Risen 2 XGFN Font Builder
Used to generate game-compatible font files after unpacking the font archives.

* **Process:** Unpacking `font.pak` generates `XGFN` font files.
* **Usage:** Use `xgfn_rebuild.py` to rebuild and build the font.
* **GUI Support:** Run with the `--gui` argument to open the Graphical User Interface.
* **Format & Resolution:** Supports generating game-specific fonts from standard `TTF` / `OTF` files. 
* **Note:** Please be aware that some files may not support a resolution of `2048`.

---

## 中文

### 環境需求
- **Python 版本:** `Python 3.11`

### 1. risen_pak (資源解包與打包)
用於提取與重建遊戲資源封包（`.pak` 檔案）。

* **支援遊戲:** 《Risen 1》與《Risen 2: Dark Waters》。
* **Risen 3:** 請使用 `r3resman` 此工具處理《Risen 3》的打包與解包。

### 2. risen_text (文本解包與打包)
用於提取（解包）與回填（打包）遊戲的在地化語系文字，以便進行翻譯或文本修改。

* **支援遊戲:** 《Risen 1》、《Risen 2》與《Risen 3》。
* **Risen 3 核心使用指南:**
    * 由於《Risen 3》存在於 `.bin` 檔案中的在地化文本**只有哈希值（Hash）而沒有明文 ID**。
    * 強烈建議搭配使用由 Nicodex 提供的 `lianzifu-unpack.risen3.csv` 對遊戲實際 ID 進行解碼與還原。
    * 對應工具與對照表下載：[Nicodex GitHub 專案庫](https://github.com/nicodex/lianzifu/tree/master)

### 3. Risen 2 XGFN 字體建構工具
用於在解包字體封包後，製作遊戲專用的字體檔案。

* **運作流程:** 對 `font.pak` 進行解包後會產生 `XGFN` 檔案。
* **使用方式:** 使用 `xgfn_rebuild.py` 腳本進行製作。
* **圖形介面:** 附加 `--gui` 參數（例如 `python xgfn_rebuild.py --gui`）可開啟 GUI 圖形介面操作。
* **格式與解析度:** 支援匯入常規的 `ttf` 或 `otf` 字體來轉換為遊戲專用字體。
* **注意事項:** 注意解析度設定，部分字體檔案可能不支援 `2048` 解析度。