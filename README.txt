FCPXML Role SRT Exporter
========================

概要
----
Final Cut Pro の FCPXML(.fcpxml) または FCPXML Package(.fcpxmld) から、
title要素をRoleごとに分類してSubRip(SRT)字幕を書き出すPython 3用CLIツールです。

対応環境
--------
- macOS
- Python 3.9以上
- Apple Silicon / Intel Mac
- 外部ライブラリ不要

使い方
------
Terminal:

python3 exporter.py "/path/to/file.fcpxml"

または

python3 exporter.py "/path/to/file.fcpxmld"

.fcpxmld の場合は、パッケージ内の Info.fcpxml を自動で読み込みます。

出力
----
入力ファイルまたはパッケージと同じフォルダに、Role名.srt をUTF-8(BOMなし)、LF改行で保存します。

例:

r8.srt
video.video-1.srt

Role判定
--------
X-Title Extractor互換のため、title要素のrole属性を優先します。
role属性が無いtitleはref属性をRoleとして扱います。

例:

<title ref="r8">
Role = r8

<title role="video.video-1">
Role = video.video-1

エラー
------
以下の場合は日本語でエラーを表示し、終了コード1で終了します。

- XMLではない
- .fcpxmld内にInfo.fcpxmlが無い
- Roleが無い
- SRTを書き込めない

AppleScriptから使う場合
-----------------------
同梱の export_from_script_editor.applescript をScript Editorに貼り付けて使用してください。
スクリプト内の exporter.py のパスは、実際に配置した場所に合わせて変更してください。
