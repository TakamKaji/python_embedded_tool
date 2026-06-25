# MENU_TITLE: NotebookLMへファイル同期
import asyncio
import os
from dotenv import load_dotenv
from pathlib import Path
from notebooklm import NotebookLMClient

async def replace_md_sources(notebook_id: str, folder_path: str, file_extension: str):
    # 1. フォルダの絶対パスを取得・解決
    target_dir = Path(folder_path).resolve()
    
    if not target_dir.is_dir():
        print(f"エラー: 指定されたフォルダが存在しません - {target_dir}")
        return

    # フォルダ内の指定拡張子のファイルをすべて取得
    md_files = list(target_dir.glob(f"*{file_extension}"))
    if not md_files:
        print(f"警告: {target_dir} 内に {file_extension} ファイルが見つかりませんでした。")
        return

    # 【変更点】同名チェック用に、ローカルのファイル名のセットを作成 (例: "example.md")
    local_file_names = {f.name for f in md_files}

    print(f"対象フォルダ: {target_dir}")
    print(f"見つかったファイル数: {len(md_files)} 件")
    print(f"同期対象: {', '.join(local_file_names)}")

    # クライアントの初期化（認証情報は自動的に読み込まれます）
    async with NotebookLMClient.from_storage() as client:
        
        # 2. 既存のソースを取得し、ローカルと同名のものだけを削除
        print("\n=== 既存のソースを確認・削除中 ===")
        existing_sources = await client.sources.list(notebook_id)
        if not existing_sources:
            print("既存のソースはありません。")
        
        deleted_count = 0
        for source in existing_sources:
            # 【変更点】NotebookLM上のソース名とローカルのファイル名が一致するかチェック
            if source.title in local_file_names:
                # 同名ソースのみを削除（最新API仕様では削除成功時にNoneを返します）[1, 2]
                await client.sources.delete(notebook_id, source.id)
                print(f"削除完了 (同名ソースを更新): {source.title}")
                deleted_count += 1
            else:
                # 同名でないソース（PDFや他のテキストなど）はスキップして残す
                pass
                
        if deleted_count == 0 and existing_sources:
            print("ローカルと同名のソースは見つかりませんでした（既存ソースの削除をスキップします）。")

        # 3. 新しいファイルをアップロード
        print("\n=== 新しいファイルをアップロード中 ===")
        added_source_ids = []
        for file_path in md_files:
            print(f"アップロード中: {file_path.name} ...")
            # wait=False を指定し、処理完了を待たずに次のファイルをアップロード [2]
            source = await client.sources.add_file(
                notebook_id, 
                str(file_path),
                wait=False
            )
            added_source_ids.append(source.id)
            print(f"  -> 送信完了: {source.title} (ID: {source.id})")

        # 4. バックグラウンドでの処理完了を一括で待機
        if added_source_ids:
            print("\n=== NotebookLM 側での処理完了を待機中 ===")
            # 全ファイルのインデックス化が終わるまで一括待機 [2]
            await client.sources.wait_for_sources(notebook_id, added_source_ids)
            print("すべてのソースが準備完了になりました！")

if __name__ == "__main__":
    # .env ファイルから環境変数を読み込む
    load_dotenv()

    # --- 環境変数から設定を取得 ---
    NOTEBOOK_ID = os.environ.get("NOTEBOOK_ID")
    FOLDER_PATH = os.environ.get("FOLDER_PATH")
    FILE_EXTENSION = os.environ.get("FILE_EXTENSION", ".txt")

    if not NOTEBOOK_ID or not FOLDER_PATH:
        print("エラー: .env ファイルに NOTEBOOK_ID と FOLDER_PATH を設定してください。")
        print(".env.sample をコピーして .env を作成できます。")
    else:
        asyncio.run(replace_md_sources(NOTEBOOK_ID, FOLDER_PATH, FILE_EXTENSION))