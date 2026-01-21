#!/usr/bin/env python3
"""
Pond5 自動アップローダー
========================
Playwrightを使用してPond5に楽曲を自動アップロードするスクリプト

使い方:
1. config.json に認証情報とパスを設定
2. playwright install chromium を実行（初回のみ）
3. python pond5_auto_uploader.py を実行

依存関係:
pip install playwright
playwright install chromium
"""

import os
import sys
import json
import csv
import logging
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Optional

try:
    from playwright.async_api import async_playwright, Page, Browser, BrowserContext
    from playwright.async_api import TimeoutError as PlaywrightTimeoutError
except ImportError:
    print("必要なパッケージをインストールしてください:")
    print("pip install playwright")
    print("playwright install chromium")
    sys.exit(1)

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('pond5_upload.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class Pond5Uploader:
    """Pond5自動アップローダークラス"""

    POND5_LOGIN_URL = "https://www.pond5.com/login"
    POND5_UPLOAD_URL = "https://www.pond5.com/uploads"
    POND5_CSV_URL = "https://www.pond5.com/uploads/apply-csv"

    def __init__(self, config_path: str = "config.json"):
        """
        初期化

        Args:
            config_path: 設定ファイルのパス
        """
        self.config = self._load_config(config_path)
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.uploaded_files: list[str] = []
        self.failed_files: list[str] = []

    def _load_config(self, config_path: str) -> dict:
        """設定ファイルを読み込む"""
        if not os.path.exists(config_path):
            # デフォルト設定を作成
            default_config = {
                "email": "YOUR_POND5_EMAIL",
                "password": "YOUR_POND5_PASSWORD",
                "music_folder": "/path/to/your/music/files",
                "csv_file": "pond5_upload_diff_316songs.csv",
                "headless": False,
                "upload_batch_size": 20,
                "wait_between_uploads": 2,
                "timeout": 60
            }
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(default_config, f, indent=2, ensure_ascii=False)
            logger.warning(f"設定ファイルを作成しました: {config_path}")
            logger.warning("認証情報とパスを設定してから再実行してください")
            sys.exit(0)

        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    async def _setup_browser(self, playwright) -> None:
        """Playwrightブラウザをセットアップ"""
        self.browser = await playwright.chromium.launch(
            headless=self.config.get("headless", False),
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
            ]
        )

        # コンテキスト作成（User-Agent設定、Bot検知回避）
        self.context = await self.browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

        self.page = await self.context.new_page()

        # Bot検知回避のためのスクリプト
        await self.page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        """)

    async def login(self) -> bool:
        """Pond5にログイン"""
        logger.info("Pond5にログイン中...")
        timeout = self.config["timeout"] * 1000  # Playwrightはミリ秒

        try:
            await self.page.goto(self.POND5_LOGIN_URL, wait_until="networkidle")

            # メールアドレス入力（自動待機）
            await self.page.fill("#email", self.config["email"], timeout=timeout)

            # パスワード入力
            await self.page.fill("#password", self.config["password"])

            # ログインボタンクリック
            await self.page.click("button[type='submit']")

            # ログイン成功を確認（アップロードページに遷移できるか）
            await self.page.wait_for_timeout(3000)
            await self.page.goto(self.POND5_UPLOAD_URL, wait_until="networkidle")

            # アップロード要素が表示されることを確認
            await self.page.wait_for_selector(
                "[data-testid='upload-button'], .upload-button, input[type='file']",
                timeout=timeout
            )

            logger.info("ログイン成功")
            return True

        except PlaywrightTimeoutError:
            logger.error("ログインタイムアウト")
            return False
        except Exception as e:
            logger.error(f"ログインエラー: {e}")
            return False

    async def upload_files(self, file_list: list[str]) -> tuple[list[str], list[str]]:
        """
        ファイルをアップロード

        Args:
            file_list: アップロードするファイルパスのリスト

        Returns:
            (成功リスト, 失敗リスト)
        """
        logger.info(f"{len(file_list)}ファイルのアップロードを開始")
        timeout = self.config["timeout"] * 1000

        uploaded = []
        failed = []

        try:
            await self.page.goto(self.POND5_UPLOAD_URL, wait_until="networkidle")

            # ファイル入力要素を探す
            file_input = self.page.locator("input[type='file']").first
            await file_input.wait_for(timeout=timeout)

            # バッチ処理
            batch_size = self.config.get("upload_batch_size", 20)
            wait_time = self.config.get("wait_between_uploads", 2) * 1000

            for i in range(0, len(file_list), batch_size):
                batch = file_list[i:i + batch_size]
                logger.info(f"バッチ {i//batch_size + 1}: {len(batch)}ファイル")

                for file_path in batch:
                    if not os.path.exists(file_path):
                        logger.warning(f"ファイルが見つかりません: {file_path}")
                        failed.append(file_path)
                        continue

                    try:
                        # ファイルをアップロード（Playwrightのset_input_files）
                        await file_input.set_input_files(os.path.abspath(file_path))
                        logger.info(f"  アップロード中: {os.path.basename(file_path)}")
                        uploaded.append(file_path)

                        await self.page.wait_for_timeout(wait_time)

                    except Exception as e:
                        logger.error(f"  アップロード失敗: {os.path.basename(file_path)} - {e}")
                        failed.append(file_path)

                # バッチ間の待機
                if i + batch_size < len(file_list):
                    logger.info("次のバッチまで30秒待機...")
                    await self.page.wait_for_timeout(30000)
                    # ページをリロード
                    await self.page.goto(self.POND5_UPLOAD_URL, wait_until="networkidle")
                    file_input = self.page.locator("input[type='file']").first
                    await file_input.wait_for(timeout=timeout)

        except Exception as e:
            logger.error(f"アップロードプロセスエラー: {e}")

        self.uploaded_files = uploaded
        self.failed_files = failed

        return uploaded, failed

    async def apply_csv_metadata(self, csv_path: str) -> bool:
        """
        CSVファイルでメタデータを一括適用

        Args:
            csv_path: Pond5形式のCSVファイルパス
        """
        logger.info(f"CSVメタデータを適用中: {csv_path}")
        timeout = self.config["timeout"] * 1000

        try:
            await self.page.goto(self.POND5_CSV_URL, wait_until="networkidle")

            # CSVアップロード用のinput要素を探す
            csv_input = self.page.locator("input[type='file'][accept='.csv']")
            await csv_input.wait_for(timeout=timeout)

            await csv_input.set_input_files(os.path.abspath(csv_path))
            await self.page.wait_for_timeout(2000)

            # 適用ボタンをクリック
            apply_button = self.page.locator("button[type='submit'], .apply-csv-button").first
            await apply_button.click()

            # 処理完了を待機
            await self.page.wait_for_timeout(10000)

            logger.info("CSVメタデータ適用完了")
            return True

        except Exception as e:
            logger.error(f"CSVメタデータ適用エラー: {e}")
            return False

    def get_files_from_csv(self, csv_path: str, music_folder: str) -> list[str]:
        """
        CSVからアップロード対象ファイルリストを取得

        Args:
            csv_path: 差分CSVファイルパス
            music_folder: 音楽ファイルが格納されているフォルダ

        Returns:
            ファイルパスのリスト
        """
        files = []

        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                filename = row.get('OriginalFilename', '').strip()
                if filename:
                    file_path = os.path.join(music_folder, filename)
                    if os.path.exists(file_path):
                        files.append(file_path)
                    else:
                        logger.warning(f"ファイルが見つかりません: {filename}")

        return files

    def generate_pond5_csv(self, input_csv: str, output_csv: str) -> str:
        """
        Pond5アップロード用のCSVを生成（メタデータ適用用）

        Args:
            input_csv: 差分CSVファイルパス
            output_csv: 出力CSVファイルパス
        """
        logger.info("Pond5用CSVを生成中...")

        with open(input_csv, 'r', encoding='utf-8-sig') as f_in, \
             open(output_csv, 'w', encoding='utf-8', newline='') as f_out:

            reader = csv.DictReader(f_in)

            # Pond5が要求するカラム
            fieldnames = [
                'OriginalFilename', 'name', 'Price', 'Keywords',
                'Description', 'Copyright', 'SoundType'
            ]

            writer = csv.DictWriter(f_out, fieldnames=fieldnames)
            writer.writeheader()

            count = 0
            for row in reader:
                writer.writerow({
                    'OriginalFilename': row.get('OriginalFilename', ''),
                    'name': row.get('name', ''),
                    'Price': row.get('Price', '49'),
                    'Keywords': row.get('Keywords', ''),
                    'Description': row.get('Description', ''),
                    'Copyright': row.get('Copyright', 'Toshiyuki Kimura'),
                    'SoundType': 'music'
                })
                count += 1

        logger.info(f"{count}曲のCSVを生成: {output_csv}")
        return output_csv

    async def run(self):
        """メイン実行"""
        logger.info("=" * 60)
        logger.info("Pond5 自動アップローダー 開始 (Playwright版)")
        logger.info("=" * 60)

        async with async_playwright() as playwright:
            try:
                # ブラウザセットアップ
                await self._setup_browser(playwright)

                # ログイン
                if not await self.login():
                    logger.error("ログインに失敗しました。終了します。")
                    return

                # CSVからファイルリストを取得
                csv_file = self.config.get("csv_file", "pond5_upload_diff_316songs.csv")
                music_folder = self.config.get("music_folder", "")

                files = self.get_files_from_csv(csv_file, music_folder)
                logger.info(f"アップロード対象: {len(files)}ファイル")

                if not files:
                    logger.warning("アップロードするファイルがありません")
                    return

                # ユーザー確認
                print(f"\n{len(files)}ファイルをアップロードします。続行しますか？ (y/n): ", end="")
                if input().lower() != 'y':
                    logger.info("キャンセルされました")
                    return

                # ファイルアップロード
                uploaded, failed = await self.upload_files(files)

                logger.info("=" * 60)
                logger.info("アップロード結果:")
                logger.info(f"   成功: {len(uploaded)}ファイル")
                logger.info(f"   失敗: {len(failed)}ファイル")
                logger.info("=" * 60)

                # 結果をファイルに保存
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                result_file = f"upload_result_{timestamp}.json"
                with open(result_file, 'w', encoding='utf-8') as f:
                    json.dump({
                        "timestamp": timestamp,
                        "uploaded": [os.path.basename(fp) for fp in uploaded],
                        "failed": [os.path.basename(fp) for fp in failed]
                    }, f, indent=2, ensure_ascii=False)

                logger.info(f"結果を保存: {result_file}")

                # メタデータCSVの適用案内
                if uploaded:
                    logger.info("\n" + "=" * 60)
                    logger.info("次のステップ:")
                    logger.info("1. Pond5でファイルの処理完了を待つ（数時間）")
                    logger.info("2. 'Apply CSV' ページでメタデータを適用")
                    logger.info(f"   CSV: {csv_file}")
                    logger.info("3. ファイルをSubmitしてキュレーター審査へ")
                    logger.info("=" * 60)

            except KeyboardInterrupt:
                logger.info("\nユーザーによる中断")
            except Exception as e:
                logger.error(f"エラー: {e}")
                import traceback
                traceback.print_exc()
            finally:
                if self.browser:
                    await self.browser.close()
                    logger.info("ブラウザを終了しました")


class Pond5MetadataUpdater:
    """既存楽曲のメタデータを一括更新するクラス"""

    def __init__(self, config_path: str = "config.json"):
        self.config = self._load_config(config_path)
        self.browser = None

    def _load_config(self, config_path: str) -> dict:
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    async def update_via_csv(self, csv_path: str):
        """CSVでメタデータを一括更新"""
        logger.info(f"CSVによるメタデータ更新: {csv_path}")

        # Pond5のApply CSVページを使用
        # 実装は Pond5Uploader.apply_csv_metadata() と同様


def main():
    """メイン関数"""
    import argparse

    parser = argparse.ArgumentParser(description="Pond5 自動アップローダー (Playwright版)")
    parser.add_argument("--config", default="config.json", help="設定ファイルパス")
    parser.add_argument("--generate-csv", action="store_true", help="Pond5用CSVを生成のみ")
    parser.add_argument("--input-csv", help="入力CSVファイル")
    parser.add_argument("--output-csv", help="出力CSVファイル")

    args = parser.parse_args()

    if args.generate_csv:
        if not args.input_csv or not args.output_csv:
            print("--input-csv と --output-csv を指定してください")
            sys.exit(1)
        uploader = Pond5Uploader(args.config)
        uploader.generate_pond5_csv(args.input_csv, args.output_csv)
    else:
        uploader = Pond5Uploader(args.config)
        asyncio.run(uploader.run())


if __name__ == "__main__":
    main()
