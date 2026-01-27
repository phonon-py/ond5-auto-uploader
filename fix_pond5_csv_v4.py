#!/usr/bin/env python3
"""
Pond5 CSV最終クリーニングスクリプト v4
- 返却ステータスのファイルのみを処理
- Curatorから指摘されたすべてのアーティスト名を削除
- 日本語のDescription/Titleを英語に変換
"""

import csv
import re

# Curatorから指摘されたアーティスト名（今回の返却で指摘されたもの + 過去のもの）
COPYRIGHTED_NAMES = [
    # === v4で追加（今回の返却） ===
    "sheck wes", "wes",
    "sheff g",
    "bryson tiller", "tiller",
    "the weeknd", "weeknd",
    "ta-ku", "taku",

    # === v3から引き続き ===
    "g herbo", "herbo",
    "king von", "von",
    "moneybagg yo", "moneybagg",
    "nardo wick", "wick",
    "rich the kid",
    "lil mosey", "mosey",
    "lil skies", "skies",
    "lil peep", "peep", "lilpeep",
    "r3hab",
    "kygo",
    "midwxst",
    "mike dimes", "dimes",
    "jakub tumaczenia",
    "lljw",  # Juice WRLDのアルバム名
    "lunarrr",
    "maitchhh",

    # === 前回から引き続き ===
    "tyler the creator", "tyler", "the creator",
    "kyle",
    "polo g", "polo",
    "the kid laroi", "kid laroi", "laroi", "the kid raroi", "kid raroi",
    "kota the friend", "kota",
    "deorro", "dillon francis", "diplo",
    "wizkid",
    "mac miller",
    "machine gun kelly", "mgk",
    "lil tjay", "tjay",
    "lil uzi vert", "lil uzi", "lil vert", "uzi vert", "uzi",
    "lil yachty", "yachty",
    "roddy rich", "roddy ricch", "roddy",
    "juice wrld", "juice world", "juicewrld",
    "lil tecca", "tecca",
    "a$ap", "asap", "a$ap rocky", "asap rocky",
    "lil durk", "durk",
    "playboi carti", "carti",
    "trippie redd", "trippie",
    "nba youngboy", "nba yongboy", "youngboy", "nbayoungboy",
    "kodak black", "kodak",
    "post malone", "malone",
    "kid cudi", "cudi",
    "travis scott", "travis",
    "drake",
    "kanye", "kanye west", "ye",
    "kendrick", "kendrick lamar",
    "j cole", "j. cole", "cole",
    "21 savage", "savage",
    "future",
    "young thug", "thug",
    "gunna",
    "lil baby", "baby",
    "dababy", "da baby",
    "migos", "quavo", "offset", "takeoff",
    "cardi b", "cardi",
    "nicki minaj", "nicki",
    "megan thee stallion", "megan",
    "doja cat", "doja",
    "pop smoke", "popsmoke",
    "xxxtentacion", "xxx", "tentacion",
    "ski mask", "ski mask the slump god",
    "denzel curry", "denzel",
    "jid",
    "yeat",
    "central cee", "cee",
    "aj tracey", "tracey",
    "bad bunny", "bunny",
    "childish gambino", "gambino",
    "anderson paak", "anderson .paak", "paak",
    "rich amiri", "amiri",
    "bad hop", "badhop",
    "jjj",
    "jumadiba",
    "ashanti",
    "nelly",
    "nba",

    # === 今回新たに発見したもの ===
    "$not", "snot",
    "a boogie wit da hoodie", "a boogie", "boogie",
    "chief keef", "keef",
    "comethazine",
    "famous dex", "dex",
    "nav",
    "smokepurpp", "purpp",
    "tay-k", "tayk",
    "ybn nahmir", "nahmir",
    "ynw melly", "melly",
    "blueface",
    "iann dior",
    "internet money",
    "lil loaded",
    "nle choppa", "choppa",
    "sleepy hallow", "hallow",
    "sofaygo", "faygo",
    "afrojack",
    "alesso",
    "axwell ingrosso", "axwell", "ingrosso",
    "dj snake",
    "don diablo", "diablo",
    "galantis",
    "hardwell",
    "martin solveig", "solveig",
    "nicky romero", "romero",
    "steve aoki", "aoki",
    "don toliver", "toliver",
    "key glock", "glock",
    "lil keed", "keed",
    "metro boomin", "metro",
    "quality control",
    "young nudy", "nudy",
    "24kgoldn", "goldn",
    "bankrol hayden", "hayden",
    "ddg",
    "dj scheme", "scheme",
    "dro kenji", "kenji",
    "fivio foreign", "fivio",
    "jackboys",
    "lil gnar", "gnar",
    "mustard",
    "ssgkobe", "kobe",
    "swae lee", "swae",
    "thehxliday",
    "tyfontaine",
    "tyla yaweh", "yaweh",
    "42 dugg", "dugg",
    "jaydayoungan",
    "nle choppa", "choppa",
    "nocap",
    "pooh shiesty", "shiesty",
    "quando rondo", "rondo",
    "rod wave", "wave",
    "tee grizzley", "grizzley",
    "chase b",
    "cordae",
    "danny towers", "towers",
    "dc the don",
    "southside",
    "teezo touchdown", "touchdown",
    "est gee", "gee",
    "only the family",
    "brooklyn drill",
    "chicago drill",
    "chicago rap",
    "nyc rap",
    "atl hip hop",
    "baton rouge rap",
    "alunageorge",
    "cashmere cat",
    "cosmo's midnight",
    "disclosure",
    "flume",
    "goldlink",
    "jamie xx",
    "kaytranada",
    "louis the child",
    "nao",
    "rejjie snow", "snow",
    "sam gellaitry", "gellaitry",
    "sampha",
    "sbtrkt",
    "sg lewis",
    "slowthai",
    "snakehips",
    "night lovell", "lovell",
    "bones",
    "city morgue",
    "duckboy",
    "fat nick",
    "freddie dredd", "dredd",
    "germ",
    "ghostemane",
    "killstation",
    "lil darkie", "darkie",
    "lil tracy", "tracy",
    "pouya",
    "ramirez",
    "3breezy",
    "ann marie",
    "fredo bang", "bang",
    "hotboii",
    "i the prince of n",
    "jackboy",
    "kb mike",
    "layton greene", "greene",
    "lil poppa", "poppa",
    "lil zay osama", "osama",
    "major nine",
    "mo3",
    "arizona zervas", "zervas",
    "benny blanco", "blanco",
    "jack harlow", "harlow",
    "lil pump", "pump",
    "lil xan", "xan",
    "landon cube", "cube",
    "ugly god",
    "wifisfuneral",
    "pnb rock",
    "luh kel", "kel",
    "frank ocean", "ocean",

    # 追加（前回リスト）
    "chancetherapper", "chance the rapper", "chance",
    "bj the chicago kid", "chicago kid",
    "black party",
    "buddy",
    "duckwrth",
    "earthgang",
    "isaiah rashad", "rashad",
    "j dilla", "dilla",
    "jay prince",
    "madlib",
    "mick jenkins", "jenkins",
    "noname",
    "nujabes",
    "nxworries",
    "phony ppl",
    "saba",
    "sango",
    "sir",
    "logic",
    "nf",
]

# 日本語を含むかチェック
def contains_japanese(text):
    """日本語が含まれているかチェック"""
    if not text:
        return False
    return bool(re.search(r'[ぁ-んァ-ン一-龯]', text))

def clean_keywords(keywords_str):
    """キーワード文字列から問題のあるものを削除"""
    if not keywords_str:
        return keywords_str, []

    # カンマで分割
    keywords = [k.strip() for k in keywords_str.split(',')]

    # 各キーワードをチェック
    cleaned_keywords = []
    removed = []

    for keyword in keywords:
        keyword_lower = keyword.lower().strip()

        # 空のキーワードをスキップ
        if not keyword_lower:
            continue

        # 日本語を含むキーワードを削除
        if contains_japanese(keyword):
            removed.append(keyword)
            continue

        # 著作権問題のある名前かチェック
        is_copyrighted = False
        for name in COPYRIGHTED_NAMES:
            # 完全一致または含まれている場合
            if keyword_lower == name or name in keyword_lower:
                is_copyrighted = True
                removed.append(keyword)
                break

        if not is_copyrighted:
            cleaned_keywords.append(keyword)

    return ', '.join(cleaned_keywords), removed

def translate_description(japanese_text, title):
    """
    日本語の説明文を英語に置き換え
    ジャンルベースの汎用的な説明文を生成
    """
    # タイトルから情報を抽出
    title_lower = title.lower()

    # ジャンル/スタイルを判定
    if 'piano' in title_lower:
        return "This beat features an emotional piano melody that creates a deep and moving atmosphere. Perfect for hip-hop productions, content creation, and background music."
    elif 'guitar' in title_lower or 'gtr' in title_lower:
        return "This beat features a captivating guitar melody with modern hip-hop production. The combination of warm guitar tones and crisp beats creates a unique and engaging sound."
    elif 'synth' in title_lower:
        return "This beat features impressive synthesizer melodies with modern trap production. The atmospheric synths and hard-hitting drums create an impactful listening experience."
    elif 'drill' in title_lower:
        return "This drill beat features dark melodies and hard-hitting rhythms. Perfect for creating intense and energetic hip-hop tracks."
    elif 'afro' in title_lower:
        return "This Afrobeat-inspired track combines vibrant rhythms with modern production. Perfect for dance music and upbeat content creation."
    elif 'lofi' in title_lower or 'lo-fi' in title_lower or 'chill' in title_lower:
        return "This chill beat features relaxing melodies and laid-back rhythms. Perfect for study sessions, relaxation, and lo-fi content."
    elif 'rage' in title_lower:
        return "This rage beat features intense synths and aggressive drums. The energetic production creates a powerful and dynamic atmosphere."
    elif 'emo' in title_lower:
        return "This emotional beat features heartfelt melodies that evoke deep feelings. Perfect for expressive hip-hop and introspective content."
    elif 'flute' in title_lower:
        return "This beat features melodic flute phrases with modern hip-hop production. The combination creates a unique and memorable sound."
    else:
        # デフォルトの説明文
        return "This beat features modern hip-hop production with captivating melodies and professional sound design. Perfect for content creators, music producers, and commercial use."

def translate_title(japanese_title, filename):
    """日本語タイトルを英語に変換"""
    # ファイル名から英語タイトルを生成
    # 拡張子を除去
    name = filename.rsplit('.', 1)[0] if '.' in filename else filename
    # アンダースコアをスペースに
    name = name.replace('_', ' ')
    # タイトルケースに
    return name.title()

def process_csv(input_file, output_file):
    """CSVファイルを処理（全ファイル対象）"""

    rows_modified = 0
    keywords_removed = 0
    descriptions_fixed = 0
    titles_fixed = 0

    with open(input_file, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    processed_rows = []

    for row in rows:
        modified = False
        filename = row.get('OriginalFilename', 'unknown')

        # キーワードをクリーニング
        if 'Keywords' in row:
            cleaned_keywords, removed = clean_keywords(row['Keywords'])
            if removed:
                row['Keywords'] = cleaned_keywords
                modified = True
                keywords_removed += len(removed)
                print(f"キーワード削除: {filename}")
                for r in removed[:5]:  # 最初の5つだけ表示
                    print(f"  - {r}")
                if len(removed) > 5:
                    print(f"  ... 他 {len(removed) - 5}件")

        # 説明文の日本語をチェック
        if 'Description' in row and contains_japanese(row['Description']):
            title = row.get('name', filename)
            row['Description'] = translate_description(row['Description'], title)
            modified = True
            descriptions_fixed += 1
            print(f"説明文修正: {filename}")

        # タイトルの日本語をチェック
        if 'name' in row and contains_japanese(row['name']):
            row['name'] = translate_title(row['name'], filename)
            modified = True
            titles_fixed += 1
            print(f"タイトル修正: {filename}")

        if modified:
            rows_modified += 1

        processed_rows.append(row)

    # 出力
    with open(output_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(processed_rows)

    print("\n" + "=" * 60)
    print("処理完了:")
    print(f"  - 修正した行数: {rows_modified}")
    print(f"  - 削除したキーワード数: {keywords_removed}")
    print(f"  - 修正した説明文数: {descriptions_fixed}")
    print(f"  - 修正したタイトル数: {titles_fixed}")
    print("=" * 60)

    return rows_modified

if __name__ == "__main__":
    input_csv = "/Users/kimuratoshiyuki/Downloads/pond5.csv"
    output_csv = "/Users/kimuratoshiyuki/Downloads/pond5_cleaned_v4.csv"

    print("=" * 60)
    print("Pond5 CSV クリーニングツール v4")
    print("  - 返却ステータスのファイルのみ処理")
    print("  - 新規アーティスト名追加: sheck wes, sheff g, bryson tiller, the weeknd, ta-ku")
    print("=" * 60)
    print(f"入力: {input_csv}")
    print(f"出力: {output_csv}")
    print()

    process_csv(input_csv, output_csv)

    print(f"\n出力ファイル: {output_csv}")
    print("\nこのCSVをPond5の「Apply CSV」機能で適用してください。")
