# -*- coding: utf-8 -*-
# ==============================================================================
# === 필수 라이브러리 임포트 ===
# ==============================================================================
from moviepy import (
    ImageClip, VideoFileClip, CompositeVideoClip, ColorClip, TextClip,
    AudioFileClip, CompositeAudioClip, concatenate_audioclips
)
import moviepy.video.fx as vfx
import moviepy.audio.fx as afx
import os
import json
import math
import difflib
from typing import List, Dict, Any, Optional, Union
import imageio.v3 as iio
import traceback

# --- Fuzzywuzzy Import ---
# 이 모듈은 자막 처리 과정에서 사용됩니다.
try:
    from fuzzywuzzy import fuzz
    print("라이브러리 로드 성공: fuzzywuzzy")
except ImportError:
    print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
    print("오류: 'fuzzywuzzy' 라이브러리를 찾을 수 없습니다.")
    print("고급 자막 처리를 사용하려면 fuzzywuzzy 및 python-Levenshtein을 설치해야 합니다.")
    print("  pip install fuzzywuzzy python-Levenshtein")
    print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
    # fuzzywuzzy가 없으면 고급 자막 처리를 건너<0xEB><0x9C><0x91>도록 설정하거나, 오류를 발생시킬 수 있습니다.
    # 여기서는 일단 진행하되, 자막 처리 부분에서 오류가 발생할 수 있습니다.
    fuzz = None # fuzz 객체를 None으로 설정하여 이후 코드에서 확인 가능하게 함

# ==============================================================================
# === 전역 설정 및 경로 ===
# ==============================================================================
template_config = {
    'resolution': (1080, 1920), 'fps': 30,
    'background_color': (30, 30, 30),
    'use_base_video_as_visual_background': True,
    'image_frame_scale': (0.9, 0.65),
    'image_frame_position': ('center', 1050),
    'image_padding_within_frame': 0.98,
    'font_path': 'C:/Users/gaterbelt/Downloads/fonts/NanumGothic.ttf', # 자막/기본 폰트
    'font_size': 70, 'font_color': 'white',                           # 자막/기본 스타일
    'text_position': ('center', 1550),                               # 자막 위치
    'text_highlight_color': (0, 0, 0, 172),                          # 자막 배경색 (RGBA)
    'subtitle_target_chars': 35,       # 고급 자막 처리 시 목표 글자 수
    'subtitle_debug': False,           # 고급 자막 처리 디버그 출력 여부
    'title_text': "당근이 주황색이 된 이유",                              # 제목
    'title_font_path': 'C:/Users/gaterbelt/Downloads/fonts/NanumGothic.ttf', # 제목 폰트
    'title_font_size': 85, 'title_font_color': 'black',                 # 제목 스타일
    'title_position': ('center', 285),                                 # 제목 위치
    'bgm_volume_factor': 0.20,                                         # BGM 볼륨 (오디오 생성 시 0.5 하드코딩됨)
}

# --- 파일 경로 ---
JSON_PATH = 'processed_video_data.json'
BASE_VIDEO_PATH = 'C:/Users/gaterbelt/Downloads/쿰쿰파민.mp4'
BGM_PATH = 'C:/Users/gaterbelt/Downloads/base_music.mp3'
OUTPUT_PATH = 'final_video_output_with_processed_subs.mp4' # 출력 파일명 변경

# ==============================================================================
# === 헬퍼 함수 및 모듈 함수 정의 ===
# ==============================================================================

# --- Helper 1: JSON 로드 ---
def load_json_data(json_path: str) -> Optional[Dict[str, Any]]:
    try:
        with open(json_path, 'r', encoding='utf-8') as f: return json.load(f)
    except FileNotFoundError: print(f"오류: JSON 파일 없음 - {json_path}"); return None
    except json.JSONDecodeError: print(f"오류: JSON 디코딩 실패 - {json_path}"); return None

# --- Helper 2: GIF -> MP4 변환 ---
def convert_gif_to_mp4(gif_path: str) -> Optional[str]:
    # (이전 최종 버전 코드와 동일)
    mp4_path = os.path.splitext(gif_path)[0] + ".mp4"
    if os.path.exists(mp4_path): return mp4_path
    print(f"변환 시작: GIF -> MP4 ({os.path.basename(gif_path)})")
    frames = iio.imread(gif_path, index=None, plugin='pillow')
    fps = 10
    try:
        meta = iio.immeta(gif_path, plugin='pillow')
        duration = meta.get('duration')
        if duration and isinstance(duration, (int, float)) and duration > 0: fps = 1000 / duration
        elif meta.get('fps'): fps = meta.get('fps', 10)
        if not isinstance(fps, (int, float)) or fps <= 0: fps = 10
    except Exception: fps = 10
    iio.imwrite(mp4_path, frames, fps=fps, codec='libx264', output_params=['-pix_fmt', 'yuv420p'])
    return mp4_path


# --- Subtitle Processing Helper: finalize_chunk ---
def finalize_chunk(segments):
    # (사용자 제공 스크립트의 함수)
    if not segments: return None
    text_segments = [s for s in segments if s.get('text')]
    if not text_segments: return None
    full_text = "".join(s['text'] for s in text_segments).strip()
    start_time = segments[0]['start']; end_time = segments[-1]['end']
    if end_time < start_time:
        latest_end = max(s['end'] for s in segments)
        end_time = max(start_time, latest_end)
        if end_time <= start_time: end_time = start_time + 0.01
    return {"text": full_text, "start": start_time, "end": end_time, "char_count": len(full_text)}

# --- Subtitle Processing Core 1: match_words_to_text_context ---
def match_words_to_text_context(words_list, text_to_match, threshold=75, high_threshold=90, lookahead=5, debug=False):
    # (사용자 제공 스크립트의 함수 - fuzz 사용)
    if not fuzz: print("경고: fuzzywuzzy 라이브러리 로드 실패. 단어 매칭 건너<0xEB><0x9C><0x91>니다."); return [] # Fuzz 없으면 실행 불가
    chunk_words = text_to_match.split(); stt_words = words_list
    if not chunk_words or not stt_words: return []
    c_idx = 0; w_idx = 0; results = []
    while w_idx < len(stt_words) and c_idx < len(chunk_words):
        stt_word_info = stt_words[w_idx]; stt_word = stt_word_info['word']; chunk_word = chunk_words[c_idx]
        score_1_1 = fuzz.ratio(stt_word, chunk_word)
        if score_1_1 >= high_threshold:
            results.append({"text": chunk_word, "start": stt_word_info['start'], "end": stt_word_info['end'], "match_type": "1:1 Anchor", "score": score_1_1})
            w_idx += 1; c_idx += 1; continue
        found_next_anchor = False; best_anchor = None
        for k in range(1, lookahead + 1):
            if w_idx + k >= len(stt_words): break
            for l in range(1, lookahead + 1):
                if c_idx + l >= len(chunk_words): break
                next_stt_word = stt_words[w_idx + k]['word']; next_chunk_word = chunk_words[c_idx + l]
                next_score = fuzz.ratio(next_stt_word, next_chunk_word)
                if next_score >= high_threshold:
                    if not found_next_anchor: best_anchor = (k, l, next_score); found_next_anchor = True
        if found_next_anchor:
            k, l, _ = best_anchor; gap_stt_words = stt_words[w_idx : w_idx + k]; gap_chunk_words = chunk_words[c_idx : c_idx + l]
            matched_text = " ".join(gap_chunk_words); start_time = gap_stt_words[0]['start']; end_time = gap_stt_words[-1]['end']
            results.append({"text": matched_text, "start": start_time, "end": end_time, "match_type": f"Context Gap ({len(gap_stt_words)}:{len(gap_chunk_words)})", "score": None})
            w_idx += k; c_idx += l
        else:
            results.append({"text": chunk_word, "start": stt_word_info['start'], "end": stt_word_info['end'], "match_type": "1:1 Fallback", "score": score_1_1})
            w_idx += 1; c_idx += 1
    return results

# --- Subtitle Processing Core 2: map_segments_to_sentence ---
def map_segments_to_sentence(sentence, timed_segments, debug=False):
    # (사용자 제공 스크립트의 함수 - difflib 사용)
    if not timed_segments: return []
    aligned_chunk_text = "".join(seg['text'] for seg in timed_segments)
    if not aligned_chunk_text: return []
    char_timestamps = []; [char_timestamps.extend([(s['start'], s['end'])] * len(s['text'])) for s in timed_segments]
    if len(aligned_chunk_text) != len(char_timestamps):
        print("Warning: MapSegments - Length mismatch"); return [{"text": s['text'], "start": s['start'], "end": s['end'], "source_tag": "original"} for s in timed_segments]
    matcher = difflib.SequenceMatcher(None, aligned_chunk_text, sentence, autojunk=False); opcodes = matcher.get_opcodes()
    final_sentence_segments = []; last_end_time = timed_segments[0]['start'] if timed_segments else 0.0
    for tag, i1, i2, j1, j2 in opcodes:
        sentence_part = sentence[j1:j2]; start_time, end_time = last_end_time, last_end_time
        if tag == 'equal' or tag == 'replace':
            if i2 > i1 and (i2 - 1) < len(char_timestamps): start_time = char_timestamps[i1][0]; end_time = char_timestamps[i2-1][1]; end_time = max(start_time, end_time); last_end_time = end_time
            else: start_time = end_time = last_end_time
            final_sentence_segments.append({"text": sentence_part, "start": start_time, "end": end_time, "source_tag": tag})
        elif tag == 'insert': start_time = end_time = last_end_time; final_sentence_segments.append({"text": sentence_part, "start": start_time, "end": end_time, "source_tag": tag})
    merged_results = [];
    if not final_sentence_segments: return []
    current_segment = final_sentence_segments[0].copy()
    for next_segment in final_sentence_segments[1:]:
        if current_segment['start'] == next_segment['start'] and current_segment['end'] == next_segment['end']:
            current_segment['text'] += next_segment['text']; current_segment['source_tag'] += "+" + next_segment['source_tag']
        else: merged_results.append(current_segment); current_segment = next_segment.copy()
    merged_results.append(current_segment)
    return merged_results

# --- Subtitle Processing Core 3: chunk_segments_by_char_count ---
def chunk_segments_by_char_count(segments, n, max_factor=1.8, debug=False):
    # (사용자 제공 스크립트의 함수)
    if not segments: return []
    output_chunks = []; current_chunk_segments = []; current_chunk_char_count = 0; upper_bound = n * max_factor
    for i, segment in enumerate(segments):
        segment_char_count = len(segment['text'])
        if segment_char_count == 0:
            if current_chunk_segments: current_chunk_segments.append(segment)
            continue
        if not current_chunk_segments:
            current_chunk_segments = [segment]; current_chunk_char_count = segment_char_count; continue
        potential_count = current_chunk_char_count + segment_char_count
        if potential_count > upper_bound and current_chunk_char_count > 0:
            finalized = finalize_chunk(current_chunk_segments);
            if finalized: output_chunks.append(finalized)
            current_chunk_segments = [segment]; current_chunk_char_count = segment_char_count
        else:
            cost_current = abs(current_chunk_char_count - n); cost_potential = abs(potential_count - n)
            if cost_potential <= cost_current:
                current_chunk_segments.append(segment); current_chunk_char_count = potential_count
            else:
                finalized = finalize_chunk(current_chunk_segments);
                if finalized: output_chunks.append(finalized)
                current_chunk_segments = [segment]; current_chunk_char_count = segment_char_count
    if current_chunk_segments:
        finalized = finalize_chunk(current_chunk_segments);
        if finalized: output_chunks.append(finalized)
    return output_chunks

# --- Subtitle Processing Core 4: adjust_chunk_durations ---
def adjust_chunk_durations(subtitle_chunks, target_duration, debug=False):
    # (사용자 제공 스크립트의 함수)
    if not subtitle_chunks or target_duration <= 0: return subtitle_chunks
    first_start = subtitle_chunks[0]['start']; last_end = subtitle_chunks[-1]['end']
    current_duration = last_end - first_start
    if current_duration <= 1e-6: return subtitle_chunks
    scale = target_duration / current_duration
    if abs(scale - 1.0) < 1e-4: return subtitle_chunks
    adjusted_chunks = []
    for chunk in subtitle_chunks:
        adj_start = first_start + (chunk['start'] - first_start) * scale
        adj_end = first_start + (chunk['end'] - first_start) * scale
        adj_end = max(adj_start, adj_end) # Prevent negative duration
        new_chunk = chunk.copy(); new_chunk['start'] = adj_start; new_chunk['end'] = adj_end
        adjusted_chunks.append(new_chunk)
    return adjusted_chunks

# --- Subtitle Processing Orchestrator ---
def process_subtitle_data(input_data, target_char_count=30, debug=False):
    """Processes loaded video data to refine subtitle chunks."""
    if not fuzz: # Check if fuzzywuzzy was loaded
         print("오류: fuzzywuzzy 라이브러리 누락으로 자막 처리 불가.")
         # Return original structure or indicate failure
         return None # Indicate failure to process

    all_processed_sentences = []
    if not isinstance(input_data, dict) or 'sentences' not in input_data:
        print("오류: 입력 데이터 형식이 잘못되었습니다 (dict 및 'sentences' 키 필요).")
        return None

    print("고급 자막 처리 시작...")
    for i, sentence_info in enumerate(input_data.get('sentences', [])):
        original_sentence = sentence_info.get('sentence')
        sentence_duration = sentence_info.get('sentence_duration')
        chunks_data = sentence_info.get('chunks', [])
        if debug: print(f"\n--- Processing Sentence {i+1} ---")

        if not original_sentence or sentence_duration is None or not chunks_data:
             if debug: print("  Warning: Missing essential data. Skipping.")
             # Add original info so it's not lost, but mark as unprocessed?
             all_processed_sentences.append({
                 "sentence_index": i, "original_sentence": original_sentence,
                 "sentence_duration": sentence_duration, "final_subtitle_chunks": sentence_info.get('subtitle_chunks', []) # Use original subs if present
             })
             continue

        chunk_based_segments = []
        for j, chunk_info in enumerate(chunks_data):
            chunk_text = chunk_info.get('chunk_text'); words_list = chunk_info.get('words', [])
            if chunk_text and words_list:
                segments_for_chunk = match_words_to_text_context(words_list, chunk_text, debug=debug)
                chunk_based_segments.extend(segments_for_chunk)

        if not chunk_based_segments:
             if debug: print("  Warning: No segments after word-to-text alignment. Skipping sentence.")
             all_processed_sentences.append({
                 "sentence_index": i, "original_sentence": original_sentence,
                 "sentence_duration": sentence_duration, "final_subtitle_chunks": sentence_info.get('subtitle_chunks', [])
             })
             continue

        sentence_mapped_segments = map_segments_to_sentence(original_sentence, chunk_based_segments, debug=debug)
        if not sentence_mapped_segments:
             if debug: print("  Warning: No segments after mapping to sentence. Skipping sentence.")
             all_processed_sentences.append({
                 "sentence_index": i, "original_sentence": original_sentence,
                 "sentence_duration": sentence_duration, "final_subtitle_chunks": sentence_info.get('subtitle_chunks', [])
             })
             continue

        subtitle_chunks = chunk_segments_by_char_count(sentence_mapped_segments, target_char_count, debug=debug)
        if not subtitle_chunks:
             if debug: print("  Warning: No subtitle chunks generated. Skipping sentence.")
             all_processed_sentences.append({
                 "sentence_index": i, "original_sentence": original_sentence,
                 "sentence_duration": sentence_duration, "final_subtitle_chunks": sentence_info.get('subtitle_chunks', [])
             })
             continue

        adjusted_subtitle_chunks = adjust_chunk_durations(subtitle_chunks, sentence_duration, debug=debug)

        all_processed_sentences.append({
            "sentence_index": i, "original_sentence": original_sentence,
            "sentence_duration": sentence_duration, "final_subtitle_chunks": adjusted_subtitle_chunks
        })
        # if debug: print(f"--- Sentence {i+1} Processing Complete ---")

    print(f"고급 자막 처리 완료. 총 {len(all_processed_sentences)}개 문장 처리됨.")
    return all_processed_sentences


# --- Module 1: 배경 + 제목 생성 ---
def create_background_with_title(total_duration: float, config: dict, base_video_path: str,video_title_from_script: str) -> Optional[CompositeVideoClip]:
    # (이전 사용자 최종 버전 코드)
    target_resolution = config['resolution']
    try:
        base_clip_raw = VideoFileClip(base_video_path)
        resized_bg = base_clip_raw.resized(width=target_resolution[0], height=target_resolution[1])
        bg_clip = resized_bg.with_duration(total_duration).with_start(0)
        title_clip = TextClip(
            text=video_title_from_script, font_size=config['title_font_size'], color=config['title_font_color'],
            font=config['title_font_path'], size=(int(target_resolution[0] * 0.9), None),
            method='caption', text_align='center'
        )
        title_clip_positioned = title_clip.with_duration(total_duration).with_start(0).with_position(config['title_position'])
        return CompositeVideoClip([bg_clip, title_clip_positioned], size=target_resolution)
    except Exception as e: print(f"오류(BG+Title): {e}"); traceback.print_exc(); return None

# --- Module 2: 자막 클립 생성 ---
def create_subtitle_clips(video_data: Dict[str, Any], config: Dict[str, Any]) -> List[TextClip]:
    # (이전 사용자 최종 버전 코드 - 입력 subtitle_chunks는 사전 처리된 것 사용)
    subtitle_clips = []
    if not video_data or 'sentences' not in video_data: return subtitle_clips
    current_time = 0.0; target_resolution = config['resolution']
    font_path = config.get('font_path', 'Arial'); font_size = config.get('font_size', 60)
    font_color = config.get('font_color', 'black'); text_position = config.get('text_position', ('center', 0.8))
    width_ratio = 0.9; highlight_color = config.get('text_highlight_color')
    for sentence in video_data['sentences']:
        sentence_start_time = current_time # 중요: 절대 시간 계산 기준
        # 'subtitle_chunks'는 사전 처리된 데이터를 사용
        for chunk in sentence.get('subtitle_chunks', []):
            try:
                abs_start = chunk['start'] # 사전 처리된 데이터는 이미 절대 시간일 수 있음 -> 확인 필요! -> 아니었음, 상대시간임. 절대시간계산필요
                abs_end = chunk['end']     # 사전 처리된 데이터는 이미 절대 시간일 수 있음 -> 확인 필요! -> 아니었음, 상대시간임. 절대시간계산필요
                # === 수정: 사전 처리된 청크의 시간은 문장 내 상대 시간이므로 절대 시간으로 변환 ===
                abs_start = sentence_start_time + chunk['start']
                abs_end = sentence_start_time + chunk['end']
                duration = abs_end - abs_start
                # ========================================================================
                if duration <= 0: continue
                text_clip = TextClip(
                    text=chunk['text'], font_size=font_size, color=font_color, font=font_path,
                    size=(int(target_resolution[0] * width_ratio), None),
                    method='caption', text_align='center', bg_color=highlight_color
                )
                subtitle_clips.append(text_clip.with_start(abs_start).with_duration(duration).with_position(text_position))
            except Exception as e: print(f"경고: 자막 클립 생성 오류: {e}")
        current_time += float(sentence.get('sentence_duration', 0)) # 다음 문장 시작 시간 업데이트
    return subtitle_clips

# --- Module 3: 시각 자료 클립 생성 ---
def create_visual_clips(video_data: Dict[str, Any], config: Dict[str, Any]) -> List[Union[ImageClip, VideoFileClip]]:
    # (이전 최종 버전 코드 - Gapless)
    visual_clips = []
    if not video_data or 'sentences' not in video_data: return visual_clips
    target_resolution = config['resolution']; frame_scale = config.get('image_frame_scale', (0.9, 0.65))
    frame_pos_config = config.get('image_frame_position', ('center', 'center')); padding = config.get('image_padding_within_frame', 0.98)
    frame_width = target_resolution[0] * frame_scale[0]; frame_height = target_resolution[1] * frame_scale[1]
    image_target_width = frame_width * padding; image_target_height = frame_height * padding
    frame_center_x = target_resolution[0] / 2 if frame_pos_config[0] == 'center' else float(frame_pos_config[0])
    if frame_pos_config[1] == 'center': frame_center_y = target_resolution[1] / 2
    elif isinstance(frame_pos_config[1], (int, float)): frame_center_y = float(frame_pos_config[1])
    else: frame_center_y = target_resolution[1] / 2

    chunk_info_list = []; current_time = 0.0; last_sentence_end_time = 0.0
    for sentence in video_data['sentences']: # 정보 수집
        sentence_start_time = current_time; sentence_duration = float(sentence.get('sentence_duration', 0))
        last_sentence_end_time = sentence_start_time + sentence_duration
        if 'chunks' in sentence:
            for chunk in sentence['chunks']:
                visual_info = chunk.get('visual_info')
                if visual_info and 'selected_local_path' in visual_info:
                    visual_path = visual_info['selected_local_path']
                    if os.path.exists(visual_path):
                        start_offset = float(chunk.get('chunk_start_in_sentence', 0)); original_duration = float(chunk.get('chunk_duration', 0))
                        abs_start = sentence_start_time + start_offset
                        if original_duration > 0: chunk_info_list.append({"abs_start": abs_start, "original_duration": original_duration, "visual_path": visual_path})
        current_time += sentence_duration
    if not chunk_info_list: return []
    chunk_info_list.sort(key=lambda x: x['abs_start'])
    adjusted_chunk_info = []; total_duration_from_json = video_data.get('total_final_audio_duration_seconds', last_sentence_end_time)
    for i, chunk in enumerate(chunk_info_list): # 길이 조정
        abs_start = chunk['abs_start']; adjusted_duration = chunk['original_duration']
        if i < len(chunk_info_list) - 1: adjusted_duration = max(0.01, chunk_info_list[i+1]['abs_start'] - abs_start)
        else: adjusted_duration = max(0.01, min(abs_start + chunk['original_duration'], total_duration_from_json) - abs_start)
        adjusted_chunk_info.append({"abs_start": abs_start, "duration": adjusted_duration, "visual_path": chunk['visual_path']})

    for k, chunk_data in enumerate(adjusted_chunk_info): # 클립 생성
        abs_start = chunk_data['abs_start']; duration = chunk_data['duration']; visual_path = chunk_data['visual_path']
        clip_after_length_adjust = None; final_clip = None; initial_clip = None
        try:
            file_ext = os.path.splitext(visual_path)[1].lower(); clip_source_path = visual_path; is_video = False
            if file_ext == '.gif':
                mp4_path = convert_gif_to_mp4(visual_path);
                if mp4_path: clip_source_path = mp4_path; is_video = True
                else: continue
            elif file_ext in ['.mp4', '.mov', '.avi', '.webm']: is_video = True
            elif file_ext in ['.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp']: is_video = False
            else: continue
            if is_video:
                initial_clip = VideoFileClip(clip_source_path, target_resolution=(None, image_target_height))
                if initial_clip.duration < duration: clip_after_length_adjust = initial_clip.with_effects_on_subclip([vfx.Loop(duration=duration)])
                elif initial_clip.duration > duration: clip_after_length_adjust = initial_clip.subclipped(0, duration)
                else: clip_after_length_adjust = initial_clip
            else:
                initial_clip = ImageClip(clip_source_path); clip_after_length_adjust = initial_clip.with_duration(duration)
            final_resized_clip = clip_after_length_adjust.resized(height=image_target_height)
            if final_resized_clip.w > image_target_width: final_resized_clip = clip_after_length_adjust.resized(width=image_target_width)
            pos_x = frame_center_x - final_resized_clip.w / 2; pos_y = frame_center_y - final_resized_clip.h / 2
            final_clip = final_resized_clip.with_position((pos_x, pos_y)).with_start(abs_start).with_duration(duration)
            visual_clips.append(final_clip)
        except Exception as e: print(f"오류: 시각자료 처리 예외 (Idx {k}): {e}"); traceback.print_exc(); continue
        # finally: close() 없음
    return visual_clips

# --- Module 4: 최종 오디오 생성 ---
def create_final_audio(video_data: Dict[str, Any], config: Dict[str, Any], bgm_path: Optional[str]) -> Optional[CompositeAudioClip]:
    # (이전 사용자 최종 버전 코드)
    narration_track = None; final_bgm = None; adjusted_bgm = None
    try:
        if not video_data or 'sentences' not in video_data: return None
        total_duration = video_data.get('total_final_audio_duration_seconds')
        if total_duration is None or total_duration <= 0: return None
        narration_clips = []
        for sentence in video_data['sentences']:
            audio_path = sentence.get('audio_path')
            if audio_path and os.path.exists(audio_path):
                try: narration_clips.append(AudioFileClip(audio_path))
                except Exception as e: print(f"경고: 나레이션 로드 실패({audio_path}): {e}")
        if not narration_clips: return None
        narration_track = concatenate_audioclips(narration_clips)
        if bgm_path and os.path.exists(bgm_path):
            bgm_clip_loaded = AudioFileClip(bgm_path)
            adjusted_bgm = bgm_clip_loaded.with_effects([afx.MultiplyVolume(0.5)]) # 0.5 고정
            if adjusted_bgm.duration > total_duration: final_bgm = adjusted_bgm.subclipped(0, total_duration)
            else: final_bgm = adjusted_bgm # 루프 없음
        else: return narration_track.with_duration(total_duration) if narration_track else None
        if narration_track and final_bgm:
             final_audio = CompositeAudioClip([narration_track, final_bgm])
             return final_audio.with_duration(total_duration)
        elif narration_track: return narration_track.with_duration(total_duration)
        else: return None
    except Exception as e: print(f"오류: 오디오 처리 예외: {e}"); traceback.print_exc(); return None

# ==============================================================================
# === 메인 비디오 생성 함수 (통합 버전) ===
# ==============================================================================
def generate_complete_video_with_processed_subs(
    config: Dict[str, Any],
    json_data_path: str,
    base_video_path: str,
    bgm_path: Optional[str],
    output_path: str,
    video_title_from_script: str 
) -> bool:
    """
    고급 자막 처리 후, 모든 구성 요소를 결합하여 최종 비디오를 생성/저장합니다.
    """
    print("--- 최종 비디오 생성 프로세스 시작 (고급 자막 처리 포함) ---")
    print(f"Config: FPS={config.get('fps', 30)}, Resolution={config.get('resolution', 'N/A')}")
    print(f"Inputs: JSON={json_data_path}, BaseVid={base_video_path}, BGM={bgm_path}")
    print(f"Output: {output_path}")

    final_video = None

    try:
        # --- 1. 원본 JSON 데이터 로드 ---
        print("\n[단계 1/7] 원본 JSON 데이터 로드...")
        initial_video_data = load_json_data(json_data_path)
        if not initial_video_data: raise ValueError("원본 JSON 데이터 로드 실패")

        # --- 2. 자막 데이터 사전 처리 ---
        print("\n[단계 2/7] 자막 데이터 사전 처리...")
        # process_subtitle_data는 이제 input_data를 직접 받도록 수정 (파일 경로 대신)
        processed_sentences_list = process_subtitle_data(
            initial_video_data, # 로드된 데이터 직접 전달
            target_char_count=config.get('subtitle_target_chars', 15),
            debug=config.get('subtitle_debug', False)
        )

        if processed_sentences_list is None: # fuzzywuzzy 누락 등 처리 불가 상황
             raise ValueError("자막 사전 처리 중 치명적 오류 발생 (fuzzywuzzy 누락 가능성)")
        elif not processed_sentences_list:
            print("  - 경고: 자막 사전 처리 결과 없음. 원본 자막 데이터 사용 시도.")
            video_data = initial_video_data # 원본 데이터로 진행
        else:
            print("  - 자막 데이터 사전 처리 완료.")
            # 처리된 자막 정보를 원본 데이터 구조에 병합
            video_data = initial_video_data.copy() # 원본 복사
            processed_map = {item['sentence_index']: item['final_subtitle_chunks'] for item in processed_sentences_list}
            original_sentences = video_data.get('sentences', [])
            new_sentences = []
            for i, sentence_info in enumerate(original_sentences):
                 merged_sentence = sentence_info.copy() # 각 문장 정보 복사
                 if i in processed_map:
                      merged_sentence['subtitle_chunks'] = processed_map[i] # 처리된 자막으로 교체
                 else:
                      # 처리 안된 문장은 원본 subtitle_chunks 유지 (있다면)
                      print(f"  - 정보: 사전 처리된 자막 없음 (Sentence {i+1}). 원본 자막 유지.")
                 new_sentences.append(merged_sentence)
            video_data['sentences'] = new_sentences # 업데이트된 문장 리스트로 교체
            print("  - 사전 처리된 자막 데이터 병합 완료.")
            # 선택: 처리된 데이터 중간 저장 (디버깅용)
            # with open("processed_video_data_DEBUG.json", 'w', encoding='utf-8') as dbg_f:
            #     json.dump(video_data, dbg_f, indent=2, ensure_ascii=False)

        # --- 3. 기본 정보 추출 (이제 video_data는 처리된 자막 포함) ---
        print("\n[단계 3/7] 기본 정보 추출...")
        total_duration = video_data.get('total_final_audio_duration_seconds')
        if not total_duration or total_duration <= 0: raise ValueError("유효한 total_duration 없음")
        fps = config.get('fps', 30)
        print(f"  - 비디오 총 길이: {total_duration:.3f} 초, FPS: {fps}")

        # --- 4. 오디오 생성 ---
        print("\n[단계 4/7] 최종 오디오 생성...")
        # video_data (처리된 자막 포함된)를 전달하지만, 오디오 경로는 원본과 동일
        final_audio = create_final_audio(video_data, config, bgm_path)
        if not final_audio: print("  - 경고: 최종 오디오 생성 실패 (오디오 없이 진행)")
        else: print("  - 최종 오디오 생성 완료.")

        # --- 5. 비주얼 요소 생성 ---
        print("\n[단계 5/7] 비주얼 요소 생성...")
        print("  - 배경 + 제목 생성...")
        base_clip = create_background_with_title(total_duration, config, base_video_path, video_title_from_script)
        if not base_clip: raise ValueError("배경+제목 클립 생성 실패")
        print("  - 배경 + 제목 생성 완료.")
        print("  - 시각 자료 클립 생성...")
        # video_data (처리된 자막 포함된) 전달 - 시각 자료 타이밍은 영향 없음
        visual_clips = create_visual_clips(video_data, config)
        print(f"  - 시각 자료 클립 생성 완료 ({len(visual_clips)} 개).")
        print("  - 자막 클립 생성...")
        # video_data (처리된 자막 포함된) 전달 - create_subtitle_clips는 이 데이터를 사용함!
        subtitle_clips = create_subtitle_clips(video_data, config)
        print(f"  - 자막 클립 생성 완료 ({len(subtitle_clips)} 개).")

        # --- 6. 비주얼 합성 & 오디오 결합 ---
        print("\n[단계 6/7] 최종 합성 및 오디오 결합...")
        final_visual_assembly = [base_clip] + visual_clips + subtitle_clips
        print(f"  - 총 {len(final_visual_assembly)}개 비주얼 레이어 합성 시도...")
        final_video_no_audio = CompositeVideoClip(final_visual_assembly, size=config['resolution'])
        print("  - 비주얼 합성 완료.")
        if final_audio:
            final_video = final_video_no_audio.with_audio(final_audio) # .with_audio() 사용
            print("  - 오디오 결합 완료.")
        else:
            final_video = final_video_no_audio
            print("  - 오디오 없음.")
        final_video = final_video.with_duration(total_duration)

        # --- 7. 파일 저장 ---
        print("\n[단계 7/7] 최종 비디오 파일 저장...")
        print(f"  - 경로: {output_path}")
        final_video.write_videofile(
            output_path, fps=fps, codec='libx264', audio_codec='aac',
            threads=os.cpu_count(), preset='medium' # logger='bar'
        )
        print(f"***** 최종 비디오 저장 성공: {output_path} *****")
        return True

    except Exception as e:
        print(f"\n!!!!! 오류 발생 !!!!!\n오류 메시지: {e}"); traceback.print_exc(); return False
    finally:
        print("\n--- 비디오 생성 프로세스 완료 (Clean-up 생략됨) ---")


# ==============================================================================
# === 스크립트 실행 지점 ===
# ==============================================================================
if __name__ == "__main__":
    # 설정 및 경로 (스크립트 상단 전역 변수 사용)
    config_to_use = template_config
    json_input_path = JSON_PATH
    base_video_input_path = BASE_VIDEO_PATH
    bgm_input_path = BGM_PATH # None일 수 있음
    video_output_path = OUTPUT_PATH

    # 메인 생성 함수 호출
    success_status = generate_complete_video_with_processed_subs(
        config=config_to_use,
        json_data_path=json_input_path,
        base_video_path=base_video_input_path,
        bgm_path=bgm_input_path,
        output_path=video_output_path
    )

    # 결과 출력
    if success_status: print("\n최종 비디오 생성 작업 성공.")
    else: print("\n최종 비디오 생성 작업 실패.")