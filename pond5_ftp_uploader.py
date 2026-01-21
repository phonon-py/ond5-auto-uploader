#!/usr/bin/env python3
"""
Pond5 FTPアップローダー
========================
FTPを使用してPond5に楽曲を高速アップロードするスクリプト

使い方:
1. config.json に認証情報とパスを設定
2. python pond5_ftp_uploader.py を実行

メリット:
- ブラウザ不要で軽量・高速
- 安定した転送
- 進捗表示付き
"""

import os
import sys
import json
import time
import csv
import logging
import ftplib
from pathlib import Path
from datetime import datetime
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('pond5_ftp_upload.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class Pond5FTPUploader:
    """Pond5 FTPアップローダークラス"""

    DEFAULT_FTP_HOST = "ftp.pond5.com"
    FTP_PORT = 21

    def __init__(self, config_path: str = "config.json"):
        """
        初期化

        Args:
            config_path: 設定ファイルのパス
        """
        self.config = self._load_config(config_path)
        self.ftp: Optional[ftplib.FTP] = None
        self.uploaded_files: list[str] = []
        self.failed_files: list[str] = []

    def _load_config(self, config_path: str) -> dict:
        """設定ファイルを読み込む"""
        if not os.path.exists(config_path):
            logger.error(f"設定ファイルが見つかりません: {config_path}")
            sys.exit(1)

        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def connect(self) -> bool:
        """FTPサーバーに接続"""
        ftp_host = self.config.get("ftp_host", self.DEFAULT_FTP_HOST)
        ftp_username = self.config.get("ftp_username", self.config["email"])
        ftp_password = self.config.get("ftp_password", self.config["password"])

        logger.info(f"FTPサーバーに接続中: {ftp_host}")
        logger.info(f"   ユーザー名: {ftp_username}")

        try:
            self.ftp = ftplib.FTP()
            self.ftp.connect(ftp_host, self.FTP_PORT, timeout=30)
            self.ftp.login(ftp_username, ftp_password)
            self.ftp.set_pasv(True)  # パッシブモード

            logger.info(f"✅ FTP接続成功")
            logger.info(f"   サーバー応答: {self.ftp.getwelcome()}")

            return True

        except ftplib.error_perm as e:
            logger.error(f"❌ FTP認証エラー: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ FTP接続エラー: {e}")
            return False

    def disconnect(self):
        """FTP接続を切断"""
        if self.ftp:
            try:
                self.ftp.quit()
                logger.info("🔒 FTP接続を切断しました")
            except:
                pass

    def upload_file(self, local_path: str, progress_callback=None) -> bool:
        """
        ファイルをアップロード

        Args:
            local_path: ローカルファイルパス
            progress_callback: 進捗コールバック関数

        Returns:
            成功したらTrue
        """
        filename = os.path.basename(local_path)
        file_size = os.path.getsize(local_path)
        uploaded_size = 0

        def callback(data):
            nonlocal uploaded_size
            uploaded_size += len(data)
            if progress_callback:
                progress_callback(uploaded_size, file_size)

        try:
            with open(local_path, 'rb') as f:
                # バイナリモードでアップロード
                self.ftp.storbinary(f'STOR {filename}', f, 8192, callback)

            return True

        except ftplib.error_perm as e:
            logger.error(f"❌ アップロード権限エラー: {filename} - {e}")
            return False
        except Exception as e:
            logger.error(f"❌ アップロードエラー: {filename} - {e}")
            return False

    def upload_files(self, file_list: list[str]) -> tuple[list[str], list[str]]:
        """
        複数ファイルをアップロード

        Args:
            file_list: アップロードするファイルパスのリスト

        Returns:
            (成功リスト, 失敗リスト)
        """
        uploaded = []
        failed = []
        total = len(file_list)

        logger.info(f"📤 {total}ファイルのアップロードを開始")

        for i, file_path in enumerate(file_list, 1):
            filename = os.path.basename(file_path)
            file_size = os.path.getsize(file_path)
            file_size_mb = file_size / (1024 * 1024)

            logger.info(f"[{i}/{total}] アップロード中: {filename} ({file_size_mb:.1f}MB)")

            start_time = time.time()

            def progress(uploaded_size, total_size):
                percent = (uploaded_size / total_size) * 100
                # 進捗は10%刻みでログ出力（ログが多すぎないように）
                pass

            if self.upload_file(file_path, progress):
                elapsed = time.time() - start_time
                speed = file_size_mb / elapsed if elapsed > 0 else 0
                logger.info(f"   ✅ 完了 ({elapsed:.1f}秒, {speed:.1f}MB/s)")
                uploaded.append(file_path)
            else:
                logger.error(f"   ❌ 失敗")
                failed.append(file_path)

                # 接続が切れた場合は再接続
                try:
                    self.ftp.voidcmd("NOOP")
                except:
                    logger.warning("   ⚠️ 接続が切れました。再接続中...")
                    if not self.connect():
                        logger.error("   ❌ 再接続失敗。残りのファイルをスキップします。")
                        failed.extend(file_list[i:])
                        break

        self.uploaded_files = uploaded
        self.failed_files = failed

        return uploaded, failed

    def _build_file_index(self, music_folders: list[str]) -> dict[str, str]:
        """
        フォルダを走査してファイル名→パスのインデックスを構築（高速化）
        """
        file_index: dict[str, str] = {}
        total_files = 0

        excluded_dirs = {
            'node_modules', '.git', '.svn', '.hg', 'dist', 'build',
            '.next', '.cache', 'coverage', '__pycache__', '.DS_Store'
        }

        for folder_idx, folder in enumerate(music_folders, 1):
            if not os.path.exists(folder):
                logger.warning(f"⚠️ フォルダが存在しません: {folder}")
                continue

            logger.info(f"   📁 [{folder_idx}/{len(music_folders)}] インデックス構築中: {folder}")
            folder_file_count = 0

            try:
                for root, dirs, files in os.walk(folder):
                    dirs[:] = [d for d in dirs if d not in excluded_dirs]

                    for filename in files:
                        ext = os.path.splitext(filename)[1].lower()
                        if ext not in {'.mp3', '.wav', '.flac', '.aiff', '.aif', '.m4a', '.ogg'}:
                            continue

                        filename_lower = filename.lower()
                        full_path = os.path.join(root, filename)

                        if filename_lower not in file_index:
                            file_index[filename_lower] = full_path
                            folder_file_count += 1

            except OSError as e:
                logger.warning(f"⚠️ フォルダ探索エラー: {folder} - {e}")
                continue

            total_files += folder_file_count
            logger.info(f"      → {folder_file_count}ファイルを登録")

        logger.info(f"   📊 インデックス完成: 合計 {total_files}ファイル")
        return file_index

    def get_files_from_csv(self, csv_path: str, music_folders: list[str]) -> tuple[list[str], list[str]]:
        """
        CSVからアップロード対象ファイルリストを取得（高速版）
        """
        found_files = []
        missing_files = []
        skip_missing = self.config.get("skip_missing_files", True)

        logger.info(f"📂 探索対象フォルダ（優先順）:")
        for i, folder in enumerate(music_folders, 1):
            logger.info(f"   {i}. {folder}")

        logger.info(f"🔧 ファイルインデックスを構築中...")
        start_time = time.time()
        file_index = self._build_file_index(music_folders)
        index_time = time.time() - start_time
        logger.info(f"   ⏱️ インデックス構築時間: {index_time:.2f}秒")

        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        logger.info(f"🔍 {len(rows)}ファイルをマッチング中...")
        start_time = time.time()

        for row in rows:
            filename = row.get('OriginalFilename', '').strip()
            if not filename:
                continue

            filename_lower = filename.lower()

            if filename_lower in file_index:
                found_files.append(file_index[filename_lower])
            else:
                missing_files.append(filename)
                if skip_missing:
                    logger.warning(f"  ⏭️ スキップ（見つかりません）: {filename}")
                else:
                    logger.error(f"  ❌ 見つかりません: {filename}")

        match_time = time.time() - start_time
        logger.info(f"   ⏱️ マッチング時間: {match_time:.3f}秒")
        logger.info(f"📊 探索結果: 発見 {len(found_files)} / 未発見 {len(missing_files)}")

        return found_files, missing_files

    def run(self):
        """メイン実行"""
        logger.info("=" * 60)
        logger.info("🎵 Pond5 FTPアップローダー 開始")
        logger.info("=" * 60)

        try:
            # CSVからファイルリストを取得
            csv_file = self.config.get("csv_file", "pond5_upload_diff_316songs.csv")

            music_folders = self.config.get("music_folders", [])
            if not music_folders:
                old_folder = self.config.get("music_folder", "")
                if old_folder:
                    music_folders = [old_folder]

            if not music_folders:
                logger.error("❌ music_folders が設定されていません")
                return

            files, missing = self.get_files_from_csv(csv_file, music_folders)
            logger.info(f"📂 アップロード対象: {len(files)}ファイル")

            if missing:
                logger.warning(f"⚠️ 見つからなかったファイル: {len(missing)}件")
                missing_log = "missing_files.txt"
                with open(missing_log, 'w', encoding='utf-8') as f:
                    for name in missing:
                        f.write(f"{name}\n")
                logger.info(f"📝 見つからなかったファイル一覧を保存: {missing_log}")

            if not files:
                logger.warning("アップロードするファイルがありません")
                return

            # 合計サイズを計算
            total_size = sum(os.path.getsize(f) for f in files)
            total_size_gb = total_size / (1024 * 1024 * 1024)
            logger.info(f"📊 合計サイズ: {total_size_gb:.2f}GB")

            # ユーザー確認
            print(f"\n{len(files)}ファイル ({total_size_gb:.2f}GB) をFTPでアップロードします。")
            print("続行しますか？ (y/n): ", end="")
            if input().lower() != 'y':
                logger.info("キャンセルされました")
                return

            # FTP接続
            if not self.connect():
                logger.error("FTP接続に失敗しました。終了します。")
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
            result_file = f"ftp_upload_result_{timestamp}.json"
            with open(result_file, 'w', encoding='utf-8') as f:
                json.dump({
                    "timestamp": timestamp,
                    "uploaded": [os.path.basename(f) for f in uploaded],
                    "failed": [os.path.basename(f) for f in failed]
                }, f, indent=2, ensure_ascii=False)

            logger.info(f"📝 結果を保存: {result_file}")

            # 次のステップ案内
            if uploaded:
                logger.info("\n" + "=" * 60)
                logger.info("📋 次のステップ:")
                logger.info("1. Pond5でファイルの処理完了を待つ")
                logger.info("2. https://www.pond5.com/uploads/apply-csv でメタデータを適用")
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
            self.disconnect()


def main():
    """メイン関数"""
    import argparse

    parser = argparse.ArgumentParser(description="Pond5 FTPアップローダー")
    parser.add_argument("--config", default="config.json", help="設定ファイルパス")
    parser.add_argument("--test", action="store_true", help="接続テストのみ")

    args = parser.parse_args()

    if args.test:
        # 接続テスト
        uploader = Pond5FTPUploader(args.config)
        if uploader.connect():
            logger.info("✅ FTP接続テスト成功")
            # ディレクトリ一覧を表示
            try:
                logger.info("📁 リモートディレクトリ:")
                files = uploader.ftp.nlst()
                for f in files[:10]:
                    logger.info(f"   {f}")
                if len(files) > 10:
                    logger.info(f"   ... 他 {len(files) - 10} ファイル")
            except:
                pass
            uploader.disconnect()
        else:
            logger.error("❌ FTP接続テスト失敗")
    else:
        uploader = Pond5FTPUploader(args.config)
        uploader.run()


if __name__ == "__main__":
    main()
