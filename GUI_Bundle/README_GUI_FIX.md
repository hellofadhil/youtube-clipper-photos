# GUI Metadata Fix — youtube-clipper-photos

## Masalah yang diperbaiki

GUI berhasil membuat `assets/final/final_short.mp4`, tetapi alur GUI tidak
selalu membuat `assets/final/final_short_metadata.txt`. Notebook lama kemudian
langsung membaca file metadata tersebut dan melempar `FileNotFoundError`.

Notebook lama juga memiliki dua blok yang memproses output. Blok pertama
memindahkan file dari `assets/final`, lalu blok berikutnya mencoba memproses
file yang sama lagi.

## Isi bundle

- `youtube_shorts_pipeline_GUI_FIXED.ipynb`
- `gui_metadata_bridge.py`
- `install_gui_fix.py`

## Memasang fix permanen ke repository

Dari root repository:

```bash
cp gui_metadata_bridge.py /path/to/youtube-clipper-photos/
cp install_gui_fix.py /path/to/youtube-clipper-photos/
cd /path/to/youtube-clipper-photos
python install_gui_fix.py
git add web_app.py main.py gui_metadata_bridge.py install_gui_fix.py
git commit -m "fix: persist GUI metadata and stabilize Colab workflow"
git push origin main
```

Installer membuat backup:

- `web_app.py.gui-fix.bak`
- `main.py.gui-fix.bak`

## Perubahan penting di notebook baru

1. Gradio berjalan sebagai background process.
2. URL `gradio.live` dibaca otomatis dari log.
3. `ContentBrain.generate_script()` dibungkus agar script dan metadata ditulis
   secara atomic.
4. Notebook menunggu sampai MP4 valid dan stabil.
5. Output disalin ke project folder, bukan dipindah.
6. Upload Kora tidak mengulang parsing/pemindahan output.
7. Encoder dipilih lewat probe nyata: NVENC bila benar-benar tersedia,
   `libx264` bila tidak.
8. Worker default diturunkan menjadi 3 agar Colab tidak menjalankan terlalu
   banyak proses FFmpeg bersarang.
