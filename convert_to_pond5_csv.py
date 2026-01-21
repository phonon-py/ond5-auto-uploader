#!/usr/bin/env python3
"""
Pond5 Apply CSV フォーマット変換ツール
======================================
差分CSVをPond5のApply CSVフォーマットに変換

使い方:
python convert_to_pond5_csv.py pond5_upload_diff_316songs.csv pond5_apply_ready.csv
"""

import csv
import sys
import os
from datetime import datetime


def enhance_keywords(original_keywords: str, title: str, genre: str = "", mood: str = "") -> str:
    """
    キーワードを40-50個に拡張（Pond5推奨）
    
    Args:
        original_keywords: 元のキーワード
        title: 楽曲タイトル
        genre: ジャンル（オプション）
        mood: ムード（オプション）
    
    Returns:
        拡張されたキーワード文字列
    """
    # 基本キーワード
    base_keywords = set()
    
    # 元のキーワードを追加
    if original_keywords:
        for kw in original_keywords.replace(', ', ',').split(','):
            kw = kw.strip().lower()
            if kw and len(kw) > 1:
                base_keywords.add(kw)
    
    # 2026年必須キーワード
    essential_2026 = [
        'authentic', 'human made', 'ai free', 'handcrafted', 'organic sound',
        'royalty free', 'background music', 'commercial use', 'content creator',
        'tiktok', 'instagram reels', 'youtube shorts', 'viral ready',
        'professional', 'high quality', '2026'
    ]
    
    # ジャンル関連キーワード
    genre_keywords = {
        'hip hop': ['hip hop', 'hiphop', 'rap', 'urban', 'beats', 'trap'],
        'r&b': ['rnb', 'r&b', 'soul', 'smooth', 'soulful', 'groove'],
        'trap': ['trap', 'modern trap', '808', 'hard hitting', 'bass heavy'],
        'lofi': ['lofi', 'lo-fi', 'chill', 'relaxing', 'study music', 'calm'],
        'electronic': ['electronic', 'synth', 'synthesizer', 'edm', 'modern'],
        'ambient': ['ambient', 'atmospheric', 'dreamy', 'ethereal', 'spacious'],
        'latin': ['latin', 'afrobeat', 'tropical', 'reggaeton'],
    }
    
    # ムード関連キーワード
    mood_keywords = {
        'sad': ['sad', 'melancholic', 'emotional', 'heartfelt', 'moody', 'dark'],
        'chill': ['chill', 'relaxing', 'calm', 'peaceful', 'mellow', 'easy'],
        'energetic': ['energetic', 'upbeat', 'dynamic', 'powerful', 'exciting'],
        'romantic': ['romantic', 'love', 'sensual', 'intimate', 'warm'],
        'dark': ['dark', 'mysterious', 'intense', 'dramatic', 'cinematic'],
    }
    
    # 必須キーワードを追加
    for kw in essential_2026:
        base_keywords.add(kw)
    
    # ジャンルキーワードを追加
    genre_lower = genre.lower() if genre else ""
    title_lower = title.lower() if title else ""
    
    for key, keywords in genre_keywords.items():
        if key in genre_lower or key in title_lower:
            for kw in keywords:
                base_keywords.add(kw)
    
    # ムードキーワードを追加
    mood_lower = mood.lower() if mood else ""
    
    for key, keywords in mood_keywords.items():
        if key in mood_lower or key in title_lower:
            for kw in keywords:
                base_keywords.add(kw)
    
    # タイトルから追加キーワードを抽出
    title_words = title_lower.replace('-', ' ').replace('_', ' ').split()
    for word in title_words:
        if len(word) > 2 and word.isalpha():
            base_keywords.add(word)
    
    # 一般的な楽器キーワード
    instruments = ['piano', 'guitar', 'synth', 'drums', 'bass', '808', 
                   'strings', 'keys', 'pad', 'vocal', 'percussion']
    for inst in instruments:
        if inst in title_lower or inst in original_keywords.lower():
            base_keywords.add(inst)
    
    # 重複を除去してソート
    final_keywords = sorted(list(base_keywords))
    
    # 50個に制限
    if len(final_keywords) > 50:
        final_keywords = final_keywords[:50]
    
    return ', '.join(final_keywords)


def convert_to_pond5_format(input_csv: str, output_csv: str) -> int:
    """
    差分CSVをPond5 Apply CSVフォーマットに変換
    
    Args:
        input_csv: 入力CSVファイルパス
        output_csv: 出力CSVファイルパス
    
    Returns:
        変換した楽曲数
    """
    count = 0
    
    with open(input_csv, 'r', encoding='utf-8-sig') as f_in:
        reader = csv.DictReader(f_in)
        
        # Pond5 Apply CSV の必須カラム
        fieldnames = [
            'OriginalFilename',  # ファイル名で照合
            'name',              # タイトル
            'Price',             # 価格
            'Keywords',          # キーワード（カンマ区切り）
            'Description',       # 説明文
            'Copyright',         # 著作権者
            'SoundType',         # 'music'
        ]
        
        with open(output_csv, 'w', encoding='utf-8', newline='') as f_out:
            writer = csv.DictWriter(f_out, fieldnames=fieldnames)
            writer.writeheader()
            
            for row in reader:
                # キーワードを拡張
                enhanced_kw = enhance_keywords(
                    row.get('Keywords', row.get('ME_Keywords', '')),
                    row.get('name', row.get('ME_Title', '')),
                    row.get('ME_Genre', ''),
                    row.get('ME_Mood', '')
                )
                
                writer.writerow({
                    'OriginalFilename': row.get('OriginalFilename', ''),
                    'name': row.get('name', ''),
                    'Price': '49',  # Pond5推奨価格
                    'Keywords': enhanced_kw,
                    'Description': row.get('Description', ''),
                    'Copyright': 'Toshiyuki Kimura',
                    'SoundType': 'music'
                })
                count += 1
    
    return count


def main():
    if len(sys.argv) < 3:
        print("使い方: python convert_to_pond5_csv.py <入力CSV> <出力CSV>")
        print("例: python convert_to_pond5_csv.py pond5_upload_diff_316songs.csv pond5_apply_ready.csv")
        sys.exit(1)
    
    input_csv = sys.argv[1]
    output_csv = sys.argv[2]
    
    if not os.path.exists(input_csv):
        print(f"エラー: 入力ファイルが見つかりません: {input_csv}")
        sys.exit(1)
    
    print(f"📋 変換中: {input_csv} → {output_csv}")
    
    count = convert_to_pond5_format(input_csv, output_csv)
    
    print(f"✅ 完了: {count}曲を変換しました")
    print(f"   出力ファイル: {output_csv}")
    print()
    print("📌 次のステップ:")
    print("1. WAVファイルをPond5にアップロード")
    print("2. ファイル処理完了を待つ（数時間）")
    print(f"3. Apply CSV ページで {output_csv} をアップロード")
    print("4. Submitでキュレーター審査へ送信")


if __name__ == "__main__":
    main()
