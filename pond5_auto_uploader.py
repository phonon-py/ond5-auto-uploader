#!/usr/bin/env python3
"""
Pond5 自動アップローダー
========================
Seleniumを使用してPond5に楽曲を自動アップロードするスクリプト

使い方:
1. config.json に認証情報とパスを設定
2. python pond5_auto_uploader.py を実行

依存関係:
pip install selenium webdriver-manager
"""

import os
import sys
import json
import time
import csv
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional

try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    from selenium.common.exceptions import TimeoutException, NoSuchElementException
    from webdriver_manager.chrome import ChromeDriverManager
except ImportError:
    print("必要なパッケージをインストールしてください:")
    print("pip install selenium webdriver-manager")
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
        self.driver: Optional[webdriver.Chrome] = None
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
    
    def _setup_driver(self) -> webdriver.Chrome:
        """Chromeドライバーをセットアップ"""
        options = Options()
        
        if self.config.get("headless", False):
            options.add_argument("--headless=new")
        
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        
        # User-Agent設定
        options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        return driver
    
    def login(self) -> bool:
        """Pond5にログイン"""
        logger.info("Pond5にログイン中...")
        
        try:
            self.driver.get(self.POND5_LOGIN_URL)
            time.sleep(3)
            
            # メールアドレス入力
            email_field = WebDriverWait(self.driver, self.config["timeout"]).until(
                EC.presence_of_element_located((By.ID, "email"))
            )
            email_field.clear()
            email_field.send_keys(self.config["email"])
            
            # パスワード入力
            password_field = self.driver.find_element(By.ID, "password")
            password_field.clear()
            password_field.send_keys(self.config["password"])
            
            # ログインボタンクリック
            login_button = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
            login_button.click()
            
            # ログイン成功を確認（アップロードページに遷移できるか）
            time.sleep(5)
            self.driver.get(self.POND5_UPLOAD_URL)
            
            WebDriverWait(self.driver, self.config["timeout"]).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='upload-button'], .upload-button, input[type='file']"))
            )
            
            logger.info("✅ ログイン成功")
            return True
            
        except TimeoutException:
            logger.error("❌ ログインタイムアウト")
            return False
        except Exception as e:
            logger.error(f"❌ ログインエラー: {e}")
            return False
    
    def upload_files(self, file_list: list[str]) -> tuple[list[str], list[str]]:
        """
        ファイルをアップロード
        
        Args:
            file_list: アップロードするファイルパスのリスト
            
        Returns:
            (成功リスト, 失敗リスト)
        """
        logger.info(f"📤 {len(file_list)}ファイルのアップロードを開始")
        
        uploaded = []
        failed = []
        
        try:
            self.driver.get(self.POND5_UPLOAD_URL)
            time.sleep(3)
            
            # ファイル入力要素を探す（非表示の場合もある）
            file_input = WebDriverWait(self.driver, self.config["timeout"]).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='file']"))
            )
            
            # バッチ処理
            batch_size = self.config.get("upload_batch_size", 20)
            
            for i in range(0, len(file_list), batch_size):
                batch = file_list[i:i + batch_size]
                logger.info(f"📦 バッチ {i//batch_size + 1}: {len(batch)}ファイル")
                
                for file_path in batch:
                    if not os.path.exists(file_path):
                        logger.warning(f"⚠️ ファイルが見つかりません: {file_path}")
                        failed.append(file_path)
                        continue
                    
                    try:
                        # ファイルパスを送信
                        file_input.send_keys(os.path.abspath(file_path))
                        logger.info(f"  ✅ アップロード中: {os.path.basename(file_path)}")
                        uploaded.append(file_path)
                        
                        time.sleep(self.config.get("wait_between_uploads", 2))
                        
                    except Exception as e:
                        logger.error(f"  ❌ アップロード失敗: {os.path.basename(file_path)} - {e}")
                        failed.append(file_path)
                
                # バッチ間の待機
                if i + batch_size < len(file_list):
                    logger.info("⏳ 次のバッチまで30秒待機...")
                    time.sleep(30)
                    # ページをリロード
                    self.driver.get(self.POND5_UPLOAD_URL)
                    time.sleep(3)
                    file_input = WebDriverWait(self.driver, self.config["timeout"]).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='file']"))
                    )
            
        except Exception as e:
            logger.error(f"❌ アップロードプロセスエラー: {e}")
        
        self.uploaded_files = uploaded
        self.failed_files = failed
        
        return uploaded, failed
    
    def apply_csv_metadata(self, csv_path: str) -> bool:
        """
        CSVファイルでメタデータを一括適用
        
        Args:
            csv_path: Pond5形式のCSVファイルパス
        """
        logger.info(f"📋 CSVメタデータを適用中: {csv_path}")
        
        try:
            self.driver.get(self.POND5_CSV_URL)
            time.sleep(3)
            
            # CSVアップロード用のinput要素を探す
            csv_input = WebDriverWait(self.driver, self.config["timeout"]).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='file'][accept='.csv']"))
            )
            
            csv_input.send_keys(os.path.abspath(csv_path))
            time.sleep(2)
            
            # 適用ボタンをクリック
            apply_button = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit'], .apply-csv-button")
            apply_button.click()
            
            # 処理完了を待機
            time.sleep(10)
            
            logger.info("✅ CSVメタデータ適用完了")
            return True
            
        except Exception as e:
            logger.error(f"❌ CSVメタデータ適用エラー: {e}")
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
                        logger.warning(f"⚠️ ファイルが見つかりません: {filename}")
        
        return files
    
    def generate_pond5_csv(self, input_csv: str, output_csv: str) -> str:
        """
        Pond5アップロード用のCSVを生成（メタデータ適用用）
        
        Args:
            input_csv: 差分CSVファイルパス
            output_csv: 出力CSVファイルパス
        """
        logger.info(f"📝 Pond5用CSVを生成中...")
        
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
        
        logger.info(f"✅ {count}曲のCSVを生成: {output_csv}")
        return output_csv
    
    def run(self):
        """メイン実行"""
        logger.info("=" * 60)
        logger.info("🎵 Pond5 自動アップローダー 開始")
        logger.info("=" * 60)
        
        try:
            # ドライバーセットアップ
            self.driver = self._setup_driver()
            
            # ログイン
            if not self.login():
                logger.error("ログインに失敗しました。終了します。")
                return
            
            # CSVからファイルリストを取得
            csv_file = self.config.get("csv_file", "pond5_upload_diff_316songs.csv")
            music_folder = self.config.get("music_folder", "")
            
            files = self.get_files_from_csv(csv_file, music_folder)
            logger.info(f"📂 アップロード対象: {len(files)}ファイル")
            
            if not files:
                logger.warning("アップロードするファイルがありません")
                return
            
            # ユーザー確認
            print(f"\n{len(files)}ファイルをアップロードします。続行しますか？ (y/n): ", end="")
            if input().lower() != 'y':
                logger.info("キャンセルされました")
                return
            
            # ファイルアップロード
            uploaded, failed = self.upload_files(files)
            
            logger.info("=" * 60)
            logger.info(f"📊 アップロード結果:")
            logger.info(f"   成功: {len(uploaded)}ファイル")
            logger.info(f"   失敗: {len(failed)}ファイル")
            logger.info("=" * 60)
            
            # 結果をファイルに保存
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            result_file = f"upload_result_{timestamp}.json"
            with open(result_file, 'w', encoding='utf-8') as f:
                json.dump({
                    "timestamp": timestamp,
                    "uploaded": [os.path.basename(f) for f in uploaded],
                    "failed": [os.path.basename(f) for f in failed]
                }, f, indent=2, ensure_ascii=False)
            
            logger.info(f"📝 結果を保存: {result_file}")
            
            # メタデータCSVの適用案内
            if uploaded:
                logger.info("\n" + "=" * 60)
                logger.info("📋 次のステップ:")
                logger.info("1. Pond5でファイルの処理完了を待つ（数時間）")
                logger.info("2. 'Apply CSV' ページでメタデータを適用")
                logger.info(f"   CSV: {csv_file}")
                logger.info("3. ファイルをSubmitしてキュレーター審査へ")
                logger.info("=" * 60)
            
        except KeyboardInterrupt:
            logger.info("\n⚠️ ユーザーによる中断")
        except Exception as e:
            logger.error(f"❌ エラー: {e}")
            import traceback
            traceback.print_exc()
        finally:
            if self.driver:
                self.driver.quit()
                logger.info("🔒 ブラウザを終了しました")


class Pond5MetadataUpdater:
    """既存楽曲のメタデータを一括更新するクラス"""
    
    def __init__(self, config_path: str = "config.json"):
        self.config = self._load_config(config_path)
        self.driver = None
    
    def _load_config(self, config_path: str) -> dict:
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def update_via_csv(self, csv_path: str):
        """CSVでメタデータを一括更新"""
        logger.info(f"📋 CSVによるメタデータ更新: {csv_path}")
        
        # Pond5のApply CSVページを使用
        # 実装は Pond5Uploader.apply_csv_metadata() と同様


def main():
    """メイン関数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Pond5 自動アップローダー")
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
        uploader.run()


if __name__ == "__main__":
    main()
