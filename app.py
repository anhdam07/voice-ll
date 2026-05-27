# @title Văn bản tiêu đề mặc định
from IPython.display import display, HTML, clear_output, Audio
import ipywidgets as widgets
import requests
import os
import re
import base64
from pydub import AudioSegment
from google.colab import files
import zipfile

# ========================== #
# 📊 Lấy thông tin credits
# ========================== #
def get_credits(api_key):
    try:
        res = requests.get("https://api.elevenlabs.io/v1/user", headers={"xi-api-key": api_key})
        if res.status_code == 200:
            data = res.json().get("subscription", {})
            return data.get("character_limit", 0) - data.get("character_count", 0)
    except: pass
    return None

# ========================== #
# 📜 Format thời gian kiểu SRT
# ========================== #
def format_srt_time(seconds):
    ms = int((seconds % 1) * 1000)
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"

# ========================== #
# 📝 Tách đoạn văn bản
# ========================== #
def parse_text_blocks(raw_text):
    parts = re.split(r'\n(?=\d+\.\s*\n)', raw_text)
    blocks = []
    for part in parts:
        lines = part.strip().splitlines()
        if len(lines) >= 2:
            blocks.append("\n".join(lines[1:]).strip())
    return blocks

# ========================== #
# 🚀 Xử lý chính
# ========================== #
def run_tool(api_bytes, voice_bytes, text_bytes):
    api_keys = [line.strip() for line in api_bytes.decode().splitlines() if line.strip()]
    voice_id = voice_bytes.decode().strip()
    text_raw = text_bytes.decode()
    print("\U0001f510 Tín dụng còn lại:")
    credit_list = []
    for key in api_keys:
        r = get_credits(key)
        print(f"- {key[:6]}...: {r if r is not None else 'lỗi'}")
        credit_list.append((key, r))

    texts = parse_text_blocks(text_raw)
    print(f"\n\U0001f4c4 Phát hiện {len(texts)} đoạn văn cần xử lý.\n")
    os.makedirs("voices", exist_ok=True)

    merged_audio = AudioSegment.empty()
    subtitles = []
    time_offset = 0.0
    idx_counter = 1
    generated_files = []

    for i, text in enumerate(texts):
        used = False
        print(f"\u23f3 Đang xử lý đoạn {i+1}...")
        for key, r in credit_list:
            if r is None or r <= 0:
                continue
            try:
                url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/with-timestamps"
                headers = {
                    "xi-api-key": key,
                    "Content-Type": "application/json"
                }
                payload = {
                    "text": text,
                    "model_id": "eleven_multilingual_v2",
                    "output_format": "mp3_44100_128"
                }
                response = requests.post(url, headers=headers, json=payload)
                if response.status_code != 200:
                    continue
                data = response.json()
                audio_bytes = base64.b64decode(data["audio_base64"])
                fname = f"voices/voice_{i+1}.mp3"
                with open(fname, "wb") as f:
                    f.write(audio_bytes)

                audio = AudioSegment.from_mp3(fname)
                merged_audio += audio
                generated_files.append(fname)

                chars = data["alignment"]["characters"]
                times = data["alignment"]["character_start_times_seconds"]
                full_text = "".join(chars)
                sentence_matches = re.finditer(r"(.+?[.!?])(\s|$)", full_text)
                for match in sentence_matches:
                    sent_text = match.group(1)
                    start_idx = match.start(1)
                    end_idx = match.end(1) - 1
                    start_time = times[start_idx] if start_idx < len(times) else times[-1]
                    end_time = times[end_idx] if end_idx < len(times) else times[-1]
                    start_time += time_offset
                    end_time += time_offset
                    subtitles.append((idx_counter, start_time, end_time, sent_text.strip()))
                    idx_counter += 1

                time_offset += audio.duration_seconds
                print(f"\u2705 Đoạn {i+1} tạo thành công bằng {key[:6]}...")
                display(Audio(fname))
                used = True
                break
            except Exception as e:
                continue
        if not used:
            print(f"\u274c Đoạn {i+1} lỗi: không có API hoạt động hoặc tạo thất bại.")

    # Save merged audio and subtitles
    merged_audio.export("merged.mp3", format="mp3")
    with open("merged.srt", "w", encoding="utf-8") as f:
        for idx, start, end, content in subtitles:
            f.write(f"{idx}\n")
            f.write(f"{format_srt_time(start)} --> {format_srt_time(end)}\n")
            f.write(f"{content}\n\n")

    print("\n\U0001f389 Hoàn tất!\n")
    display(Audio("merged.mp3"))

    return generated_files

# ========================== #
# 🎮 Giao diện tương tác
# ========================== #
api_file = widgets.FileUpload(accept='.txt', multiple=False)
voice_file = widgets.FileUpload(accept='.txt', multiple=False)
text_file = widgets.FileUpload(accept='.txt', multiple=False)
run_btn = widgets.Button(description="🎧 Tạo audio + phụ đề")
reload_btn = widgets.Button(description="🔄 Tải lại tất cả")
output = widgets.Output()

# ========================== #
# 🏷️ Label hiển thị tên file
# ========================== #
api_file_label  = widgets.HTML(value='<span style="color:#888; font-style:italic;">Chưa chọn file</span>')
voice_file_label = widgets.HTML(value='<span style="color:#888; font-style:italic;">Chưa chọn file</span>')
text_file_label  = widgets.HTML(value='<span style="color:#888; font-style:italic;">Chưa chọn file</span>')

def make_filename_observer(label_widget):
    def _observer(change):
        new_val = change['new']
        if new_val:
            name = list(new_val.keys())[0]
            label_widget.value = f'<span style="color:#2e7d32; font-weight:bold;">✅ {name}</span>'
        else:
            label_widget.value = '<span style="color:#888; font-style:italic;">Chưa chọn file</span>'
    return _observer

api_file.observe(make_filename_observer(api_file_label),   names='value')
voice_file.observe(make_filename_observer(voice_file_label), names='value')
text_file.observe(make_filename_observer(text_file_label),  names='value')

# Button to download all files after processing
download_btn = widgets.Button(description="⬇️ Tải về tất cả kết quả")

def on_run_click(b):
    with output:
        clear_output()
        try:
            # Run tool to generate the audio and subtitle files
            generated_files = run_tool(
                list(api_file.value.values())[0]['content'],
                list(voice_file.value.values())[0]['content'],
                list(text_file.value.values())[0]['content']
            )

            # Show the "Download All" button
            download_btn.layout.display = 'block'

        except Exception as e:
            print("\u274c Lỗi xảy ra:", e)

def on_reload_click(b):
    api_file.value = {}
    voice_file.value = {}
    text_file.value = {}
    api_file_label.value  = '<span style="color:#888; font-style:italic;">Chưa chọn file</span>'
    voice_file_label.value = '<span style="color:#888; font-style:italic;">Chưa chọn file</span>'
    text_file_label.value  = '<span style="color:#888; font-style:italic;">Chưa chọn file</span>'
    output.clear_output()
    download_btn.layout.display = 'none'
    print("Giao diện đã được tải lại. Vui lòng tải lại các tệp tin.")

def on_download_all_click(b):
    try:
        # Tạo file zip chứa tất cả các file MP3 trong thư mục voices
        zip_name = "all_voices.zip"
        with zipfile.ZipFile(zip_name, "w") as zipf:
            if os.path.isdir("voices"):
                for file in os.listdir("voices"):
                    if file.endswith(".mp3"):
                        zipf.write(os.path.join("voices", file), arcname=file)

        # Tải về file zip
        if os.path.exists(zip_name):
            files.download(zip_name)

        # Tải về merged.mp3 và merged.srt
        if os.path.exists("merged.mp3"):
            files.download("merged.mp3")
        if os.path.exists("merged.srt"):
            files.download("merged.srt")

        with output:
            print("✅ Đã đóng gói và tải về tất cả file thành công!")

    except Exception as e:
        with output:
            print("❌ Lỗi khi đóng gói/tải file:", e)

# Display the UI
display(widgets.VBox([
    widgets.HTML("<h3>🎤 <b>ElevenLabs - Tạo giọng nói + phụ đề từ nhiều API key</b></h3><p>Upload 3 file: <code>api_keys.txt</code>, <code>voice_id.txt</code>, <code>texts.txt</code></p>"),
    widgets.HTML("<b>📄 File API Keys:</b>"),
    widgets.HBox([api_file, api_file_label]),
    widgets.HTML("<b>🎙️ File Voice ID:</b>"),
    widgets.HBox([voice_file, voice_file_label]),
    widgets.HTML("<b>📝 File Văn bản:</b>"),
    widgets.HBox([text_file, text_file_label]),
    run_btn, reload_btn, output,
    download_btn  # Hidden initially, shown after processing
]))

run_btn.on_click(on_run_click)
reload_btn.on_click(on_reload_click)
download_btn.on_click(on_download_all_click)

# Initially hide the "Download All" button
download_btn.layout.display = 'none'
