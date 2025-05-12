# PaMin/functions/audio_generation.py
import os
import platform
import json
import re
import gc
import traceback
import sys
from typing import List, Dict, Any, Optional, Tuple

import streamlit as st # Streamlit 캐시 기능을 위해 추가

try:
    # 1. ffmpeg.exe 파일이 있는 폴더 경로를 지정하세요.
    #    사용자님이 알려주신 경로를 사용합니다.
    ffmpeg_dir = r"C:\Users\gaterbelt\anaconda3\pkgs\ffmpeg-4.3.1-ha925a31_0\Library\bin" # <--- 사용자 지정 경로

    # 2. 해당 경로가 실제로 존재하는지 확인 (선택 사항이지만 권장)
    if not os.path.isdir(ffmpeg_dir):
        print(f"Warning: Specified ffmpeg directory does not exist: {ffmpeg_dir}", file=sys.stderr)
        # 경로가 존재하지 않으면 PATH에 추가하지 않음 (오류 방지)
    else:
        # 3. 현재 환경 변수 PATH 가져오기
        original_path = os.environ.get('PATH', '')

        # 4. PATH에 ffmpeg 폴더 경로 추가 (이미 추가되어 있지 않은 경우)
        if ffmpeg_dir not in original_path:
            print(f"Adding ffmpeg directory to PATH for this session: {ffmpeg_dir}")
            # os.pathsep은 운영체제에 맞는 경로 구분자 (Windows: ';', Linux/macOS: ':')
            os.environ['PATH'] = ffmpeg_dir + os.pathsep + original_path
            print(f"Updated PATH (partial): ...{os.pathsep}{ffmpeg_dir}{os.pathsep}...")
        # else:
            # print(f"ffmpeg directory already seems to be in PATH: {ffmpeg_dir}") # 필요시 주석 해제
except Exception as e:
    print(f"Error setting ffmpeg path: {e}", file=sys.stderr)
    traceback.print_exc()

# --- 필수 라이브러리 Import ---
try:
    import torch
    import torchaudio
    import whisper
    import librosa
    import librosa.effects
    import soundfile as sf
    from rapidfuzz import process, fuzz
    from zonos.model import Zonos
    from zonos.conditioning import make_cond_dict
    # phonemizer is needed by Zonos implicitly
    import phonemizer
    _libraries_available = True
except ImportError as e:
    print(f"Error: Required library not found - {e}", file=sys.stderr)
    print("Please ensure torch, torchaudio, openai-whisper, librosa, soundfile, rapidfuzz, zonos, phonemizer are installed.", file=sys.stderr)
    _libraries_available = False
    # Raise an error or handle it gracefully if used within the Streamlit app
    # For now, functions will check this flag.

# --- eSpeak NG 경로 설정 (Helper Function) ---
# This function should be called once when the module is potentially used.
# It's better than running at import time.
_espeak_checked = False


def _ensure_espeak_path():
    """Checks for and sets the eSpeak NG library path environment variable if on Windows."""
    global _espeak_checked
    if _espeak_checked or platform.system() != "Windows":
        return

    espeak_path = r"C:\Program Files\eSpeak NG\libespeak-ng.dll"
    espeak_path_x86 = r"C:\Program Files (x86)\eSpeak NG\libespeak-ng.dll"
    found_espeak = False
    if 'PHONEMIZER_ESPEAK_LIBRARY' not in os.environ: # Only set if not already set
        if os.path.exists(espeak_path):
            print(f"Found eSpeak NG library at: {espeak_path}")
            os.environ['PHONEMIZER_ESPEAK_LIBRARY'] = espeak_path
            found_espeak = True
        elif os.path.exists(espeak_path_x86):
            print(f"Found eSpeak NG library at: {espeak_path_x86}")
            os.environ['PHONEMIZER_ESPEAK_LIBRARY'] = espeak_path_x86
            found_espeak = True

        if not found_espeak:
            print(f"Warning: eSpeak NG library not found at expected Windows locations.", file=sys.stderr)
            print("Zonos/Phonemizer might fail. Ensure eSpeak NG is installed or set PHONEMIZER_ESPEAK_LIBRARY environment variable.", file=sys.stderr)
    else:
        print(f"Using existing PHONEMIZER_ESPEAK_LIBRARY: {os.environ['PHONEMIZER_ESPEAK_LIBRARY']}")
        found_espeak = True

    _espeak_checked = True # Mark as checked for this session
    return found_espeak


# --- 유틸리티 함수 ---

# 숫자 변환 함수 (digit2txt)
tenThousandPos = 4
hundredMillionPos = 9
txtDigit = ['', '십', '백', '천', '만', '억']
txtNumber = ['', '일', '이', '삼', '사', '오', '육', '칠', '팔', '구']
txtPoint = '쩜 '
def digit2txt(strNum):
    resultStr = ''
    digitCount = 0
    pointPos = -1
    commaCount = 0
    cleanNumStr = strNum.replace(',', '')
    for i, ch in enumerate(cleanNumStr):
        if ch == '.':
            pointPos = i
            break
        if ch.isdigit():
            digitCount += 1
    intPartStr = cleanNumStr
    floatPartStr = ''
    if pointPos != -1:
        intPartStr = cleanNumStr[:pointPos]
        floatPartStr = cleanNumStr[pointPos+1:]
    currentDigitCount = len(intPartStr) -1
    isZero = True # 0인지 확인용
    for i, ch in enumerate(intPartStr):
        try: # 숫자가 아닌 문자가 포함된 경우 처리 (예: '필트론')
            num = int(ch)
        except ValueError:
            continue # 숫자가 아니면 건너<0xEB><0x81>
        if num != 0: isZero = False
        notShowDigit = False
        is_man_or_eok_unit = (currentDigitCount == tenThousandPos -1) or (currentDigitCount == hundredMillionPos -1)
        is_block_unit = (currentDigitCount % 4 != 0) # 십, 백, 천 자리인가?
        if num == 1 and is_block_unit and not is_man_or_eok_unit:
            resultStr += '' # '일' 생략
        elif num == 0:
            resultStr += ''
            if not is_man_or_eok_unit: notShowDigit = True
        else:
            resultStr += txtNumber[num]
        if not notShowDigit:
            posInBlock = currentDigitCount % 4
            if currentDigitCount == hundredMillionPos -1: resultStr += txtDigit[5] # 억
            elif currentDigitCount == tenThousandPos -1: resultStr += txtDigit[4] # 만
            elif num != 0: resultStr += txtDigit[posInBlock]
        currentDigitCount -= 1
    if len(intPartStr) == 0 and pointPos != -1: # ".123" 같은 경우
        resultStr = '영'
    elif isZero and len(intPartStr) > 0 :
        if pointPos == -1: resultStr = '영'
        else: resultStr = '영'
    if pointPos != -1:
        if not resultStr and len(intPartStr) == 0: resultStr = '영' # ".123" 을 위에서 처리했지만 안전장치
        elif not resultStr and len(intPartStr) > 0 and isZero: pass # "0.123" -> "영" 상태 유지
        elif resultStr and not resultStr.endswith(txtPoint): resultStr += txtPoint
        elif not resultStr: resultStr = '영' + txtPoint # 만약을 대비
        for ch in floatPartStr:
            if ch.isdigit(): resultStr += txtNumber[int(ch)]
    if not resultStr and cleanNumStr == '0': return '영'
    if not resultStr and cleanNumStr: return cleanNumStr
    return resultStr


# 텍스트 전처리 함수 (괄호 제거, 숫자 변환)
def preprocess_text_simple(original_text):
    processed_text = original_text
    processed_text = re.sub(r'\([^)]*\)', '', processed_text)
    processed_text = processed_text.replace('(', '').replace(')', '')
    def replace_number(match):
        return digit2txt(match.group(0))
    processed_text = re.sub(r'\d[\d,.]*', replace_number, processed_text)
    processed_text = re.sub(r'\s+', ' ', processed_text).strip()
    if processed_text.startswith('/ '): processed_text = processed_text[2:]
    elif processed_text.startswith('/'): processed_text = processed_text[1:]
    processed_text = processed_text.replace(" '", "'").replace("' ", "'")
    return processed_text

# --- Streamlit 캐시를 사용한 모델 로딩 함수 ---
@st.cache_resource
def cached_load_zonos_model(model_name: str, device: torch.device) -> Zonos:
    """Caches and loads the Zonos TTS model."""
    print(f"Cache miss: Loading Zonos model: {model_name} to {device}...")
    _ensure_espeak_path() # eSpeak 경로 설정은 모델 로드 전에 필요
    model = Zonos.from_pretrained(model_name, device=device)
    print("Zonos model loaded and cached.")
    return model

@st.cache_resource
def cached_load_whisper_model(model_size: str, device: torch.device) -> whisper.Whisper:
    """Caches and loads the Whisper model."""
    print(f"Cache miss: Loading Whisper model: {model_size} to {device}...")
    model = whisper.load_model(model_size, device=device)
    print("Whisper model loaded and cached.")
    return model

# Zonos TTS 오디오 생성 함수
def generate_zonos_audio(
    text: str,
    output_path: str,
    zonos_model: Any, # Type hint for Zonos model object
    speaker_embed: Any, # Type hint for speaker embedding tensor
    config: Dict[str, Any] # TTS configuration dictionary
    ) -> Tuple[bool, Optional[str], Optional[int]]:
    """
    Generates TTS audio using the Zonos model and saves it.
    """
    if not _libraries_available:
        print("Error: Required libraries not available for Zonos TTS.", file=sys.stderr)
        return False, None, None
    try:
        cond_dict_params = {
            "text": text,
            "speaker": speaker_embed,
            "language": config.get("language", "ko")
        }
        if config.get("emotion"): cond_dict_params["emotion"] = config["emotion"]
        if config.get("speaking_rate"): cond_dict_params["speaking_rate"] = float(config["speaking_rate"])
        if config.get("pitch_std"): cond_dict_params["pitch_std"] = float(config["pitch_std"])
        cond_dict = make_cond_dict(**cond_dict_params)
        conditioning = zonos_model.prepare_conditioning(cond_dict)
        print(f"  Generating Zonos audio for: '{text[:50]}...'")
        codes = zonos_model.generate(
            conditioning,
            disable_torch_compile=config.get("disable_torch_compile", True)
        )
        wavs = zonos_model.autoencoder.decode(codes).cpu()
        output_sampling_rate = zonos_model.autoencoder.sampling_rate
        torchaudio.save(output_path, wavs[0], output_sampling_rate)
        print(f"  Zonos TTS audio generated: {output_path}")
        del codes, wavs, conditioning, cond_dict
        if torch.cuda.is_available():
             torch.cuda.empty_cache()
        gc.collect()
        return True, output_path, output_sampling_rate
    except Exception as e:
        print(f"Error generating Zonos TTS for {output_path}: {e}", file=sys.stderr)
        traceback.print_exc()
        if os.path.exists(output_path):
            try: os.remove(output_path)
            except OSError: pass
        return False, None, None


def speed_up_audio(input_path: str, output_path: str, speed_factor: float) -> bool:
    """Loads an audio file, changes its speed, and saves to a new file."""
    if not _libraries_available:
        print("Error: Librosa/Soundfile not available for audio speed up.", file=sys.stderr)
        return False
    if speed_factor <= 0:
        print(f"Error: Invalid speed_factor ({speed_factor}). Must be > 0.", file=sys.stderr)
        return False
    if abs(speed_factor - 1.0) < 1e-6: # 속도 변경 거의 없음 (부동소수점 비교)
         print(f"  Speed factor is ~1.0, copying original file: {os.path.basename(input_path)}")
         try:
            # 파일을 복사하거나 단순히 output_path를 input_path로 간주할 수 있음
            # 여기서는 input_path와 output_path가 다를 경우에만 복사
            if input_path != output_path:
                import shutil
                shutil.copy2(input_path, output_path)
            return True
         except Exception as e:
             print(f"  Error copying original file for speed factor 1.0: {e}", file=sys.stderr)
             return False
    print(f"  Speeding up audio: {os.path.basename(input_path)} by {speed_factor}x")
    try:
        y, sr = librosa.load(input_path, sr=None)
        y_fast = librosa.effects.time_stretch(y, rate=speed_factor)
        sf.write(output_path, y_fast, sr)
        print(f"  Sped-up audio saved: {os.path.basename(output_path)}")
        return True
    except Exception as e:
        print(f"Error during audio speed up for {input_path}: {e}", file=sys.stderr)
        traceback.print_exc()
        if os.path.exists(output_path):
            try: os.remove(output_path)
            except OSError: pass
        return False


# 오디오 길이 측정 함수
def get_audio_duration(file_path: str) -> float:
    """Gets the duration of an audio file using librosa."""
    if not _libraries_available: return 0.0
    try:
        duration = librosa.get_duration(path=file_path)
        return duration
    except Exception as e:
        print(f"Error getting duration for {file_path}: {e}", file=sys.stderr)
        return 0.0

# Whisper 타임스탬프 추출 함수
def extract_whisper_timestamps(
    audio_path: str,
    whisper_model: Any, # Type hint for Whisper model
    language: str
    ) -> List[Dict[str, Any]]:
    """
    Runs Whisper transcription to get word-level timestamps.
    """
    if not _libraries_available: return []
    word_timestamps = []
    if not os.path.exists(audio_path):
        print(f"  Whisper Error: Audio file not found at {audio_path}", file=sys.stderr)
        return []
    duration = get_audio_duration(audio_path)
    if duration <= 0.1:
        print(f"  Skipping Whisper for short/invalid audio: {audio_path} ({duration:.3f}s)")
        return []
    print(f"  Running Whisper on {os.path.basename(audio_path)}...")
    try:
        result = whisper_model.transcribe(audio_path, language=language, word_timestamps=True)
        # print("  Whisper Raw Output (Word Timestamps):") # Debug output - 주석 처리 (너무 길어질 수 있음)
        for i, seg in enumerate(result.get('segments', [])):
            # print(f"      Segment {i}:") # Debug - 주석 처리
            for word_info in seg.get('words', []):
                word_text = word_info.get('word', word_info.get('text', '')).strip()
                start_time = word_info.get('start')
                end_time = word_info.get('end')
                confidence = word_info.get('probability', word_info.get('confidence'))
                # print(f"        - '{word_text}' ({start_time:.3f}s - {end_time:.3f}s)") # Debug - 주석 처리
                if word_text and start_time is not None and end_time is not None:
                    word_timestamps.append({
                        "word": word_text,
                        "start": round(start_time, 3),
                        "end": round(end_time, 3),
                        "duration": round(end_time - start_time, 3),
                        "confidence": round(confidence, 3) if confidence is not None else 0.0
                    })
        print(f"  Whisper extracted {len(word_timestamps)} words total.")
        del result
        if torch.cuda.is_available():
             torch.cuda.empty_cache()
        gc.collect()
        return word_timestamps
    except Exception as e:
        print(f"  Whisper error processing {audio_path}: {e}", file=sys.stderr)
        traceback.print_exc()
        return []


# 순차 단어-청크 매칭 함수
def align_words_to_chunks_sequential(
    word_timestamps: List[Dict[str, Any]],
    matched_chunks_info: List[Dict[str, Any]],
    config: Dict[str, Any]
    ) -> List[List[Dict[str, Any]]]:
    """
    Assigns Whisper word timestamps to chunks using sequential fuzzy matching.
    """
    if not word_timestamps or not matched_chunks_info:
        return [[] for _ in matched_chunks_info]
    sequential_match_threshold = config.get('sequential_match_threshold', 90)
    slip_lookahead = config.get('slip_lookahead', 2)
    print(f"  Assigning {len(word_timestamps)} words to {len(matched_chunks_info)} matched chunks (Sequential Alignment)...")
    word_assignments = [[] for _ in matched_chunks_info]
    word_ptr = 0
    chunk_ptr = 0
    token_ptr = 0
    # print("    --- Word Assignment Log ---") # 로그가 너무 길어질 수 있어 주석 처리
    while word_ptr < len(word_timestamps) and chunk_ptr < len(matched_chunks_info):
        word_info = word_timestamps[word_ptr]
        whisper_word = word_info["word"].lower().strip()
        if not whisper_word:
            word_ptr += 1
            continue
        current_chunk_tokens = matched_chunks_info[chunk_ptr]["tokens"]
        if token_ptr >= len(current_chunk_tokens):
            # print(f"    Chunk {chunk_ptr} ended. Moving to next chunk.")
            chunk_ptr += 1
            token_ptr = 0
            continue
        chunk_token = current_chunk_tokens[token_ptr].lower().strip()
        if not chunk_token:
            token_ptr += 1
            continue
        similarity = fuzz.ratio(whisper_word, chunk_token)
        if similarity >= sequential_match_threshold:
            # print(f"    [Direct Match] Whisper:'{word_info['word']}' ({word_ptr}) -> Chunk {chunk_ptr}, Token:'{current_chunk_tokens[token_ptr]}' ({token_ptr}), Score:{similarity:.1f}")
            word_assignments[chunk_ptr].append(word_info)
            word_ptr += 1
            token_ptr += 1
            continue
        found_slip_match = False
        for lookahead in range(1, slip_lookahead + 1):
            lookahead_token_idx = token_ptr + lookahead
            if lookahead_token_idx < len(current_chunk_tokens):
                lookahead_chunk_token = current_chunk_tokens[lookahead_token_idx].lower().strip()
                if not lookahead_chunk_token: continue
                similarity = fuzz.ratio(whisper_word, lookahead_chunk_token)
                if similarity >= sequential_match_threshold:
                    # print(f"    [Slip Match] Whisper:'{word_info['word']}' ({word_ptr}) -> Chunk {chunk_ptr}, Token:'{current_chunk_tokens[lookahead_token_idx]}' ({lookahead_token_idx}). Skipped {lookahead} chunk token(s). Score:{similarity:.1f}")
                    word_assignments[chunk_ptr].append(word_info)
                    word_ptr += 1
                    token_ptr = lookahead_token_idx + 1
                    found_slip_match = True
                    break
        if found_slip_match: continue
        next_chunk_ptr = chunk_ptr + 1
        if next_chunk_ptr < len(matched_chunks_info):
            next_chunk_tokens = matched_chunks_info[next_chunk_ptr]["tokens"]
            if next_chunk_tokens:
                next_chunk_first_token = next_chunk_tokens[0].lower().strip()
                if next_chunk_first_token:
                    similarity = fuzz.ratio(whisper_word, next_chunk_first_token)
                    if similarity >= sequential_match_threshold:
                        # print(f"    [Next Chunk Match] Whisper:'{word_info['word']}' ({word_ptr}) matches start of Chunk {next_chunk_ptr} ('{next_chunk_tokens[0]}'). Score:{similarity:.1f}. Moving to next chunk.")
                        chunk_ptr = next_chunk_ptr
                        token_ptr = 0
                        continue
        # print(f"    [Fallback] Whisper:'{word_info['word']}' ({word_ptr}) failed to match Chunk {chunk_ptr}, Token:'{chunk_token}' ({token_ptr}) or lookahead/next chunk. Assigning to current chunk {chunk_ptr} and advancing Whisper word.")
        word_assignments[chunk_ptr].append(word_info)
        word_ptr += 1
    if word_ptr < len(word_timestamps):
        last_assigned_chunk_idx = min(chunk_ptr, len(matched_chunks_info) - 1)
        if last_assigned_chunk_idx < 0: last_assigned_chunk_idx = 0
        # print(f"    Assigning remaining {len(word_timestamps) - word_ptr} Whisper words to the last processed chunk index {last_assigned_chunk_idx}.")
        for i in range(word_ptr, len(word_timestamps)):
             if last_assigned_chunk_idx < len(word_assignments):
                 word_assignments[last_assigned_chunk_idx].append(word_timestamps[i])
             else:
                 print(f"      Error: Cannot assign remaining words, invalid chunk index {last_assigned_chunk_idx}", file=sys.stderr)
    # print("    --- Word Assignment Log End ---")
    return word_assignments

# --- 메인 처리 함수 ---
def generate_audio_and_timestamps(
    script_file_path: str, visual_plan_file_path: str, episode_audio_output_dir: str,
    final_output_json_path: str, channel_dir: str, tts_config: Dict[str, Any]
    ) -> bool:
    """
    Main function: generates TTS, optionally speeds it up, runs Whisper, maps timestamps.
    Uses cached models.
    """
    if not _libraries_available: print("Error: Required libraries not available.", file=sys.stderr); return False

    # --- Device 설정 ---
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}")

    # --- 모델 로드 (캐시된 함수 사용) ---
    zonos_model_name = tts_config.get("zonos_model_name", "Zyphra/Zonos-v0.1-transformer")
    whisper_model_size = tts_config.get("whisper_model_size", "large")
    zonos_model, whisper_model, speaker_embedding = None, None, None
    try:
        # 캐시된 함수를 통해 모델 로드
        zonos_model = cached_load_zonos_model(zonos_model_name, device)
        whisper_model = cached_load_whisper_model(whisper_model_size, device)

        # --- 스피커 임베딩 (캐시 대상 아님) ---
        zonos_ref_wav_filename = tts_config.get("zonos_ref_wav_path", "reference.wav")
        # zonos_ref_wav_path는 tts_config.json에 절대 경로로 제공되므로 channel_dir과 결합하지 않음
        zonos_ref_wav_full_path = zonos_ref_wav_filename
        print(f"Loading reference audio for speaker embedding: {zonos_ref_wav_full_path}")
        if not os.path.exists(zonos_ref_wav_full_path):
            raise FileNotFoundError(f"Reference audio not found: {zonos_ref_wav_full_path}")
        ref_wav, ref_sr = torchaudio.load(zonos_ref_wav_full_path)
        ref_wav = ref_wav.to(device) # GPU로 이동
        print("Generating speaker embedding...")
        # 스피커 임베딩 생성 시 Zonos 모델 사용
        speaker_embedding = zonos_model.make_speaker_embedding(ref_wav, ref_sr)
        print("Speaker embedding generated.")
        del ref_wav # 메모리 해제
        if device.type == 'cuda': torch.cuda.empty_cache()
        gc.collect()

    except Exception as e:
        print(f"Error during model/embedding loading: {e}", file=sys.stderr); traceback.print_exc()
        # 캐시된 모델은 del 할 필요 없음 (Streamlit이 관리)
        return False

    # --- 디렉토리 및 데이터 로딩 ---
    try:
        os.makedirs(episode_audio_output_dir, exist_ok=True); print(f"Output directory: {episode_audio_output_dir}")
        print("Loading script JSON...");
        with open(script_file_path, 'r', encoding='utf-8') as f: script_data = json.load(f)
        if not isinstance(script_data, dict) or "segments" not in script_data: raise ValueError("Invalid script data format")
        print("Loading visual plan JSON...");
        with open(visual_plan_file_path, 'r', encoding='utf-8') as f: visual_plan_data = json.load(f)
        if not isinstance(visual_plan_data, list): raise ValueError("Invalid visual plan data format")
    except Exception as e:
        print(f"Error loading input data or creating directory: {e}", file=sys.stderr)
        return False

    # --- 메인 처리 루프 ---
    final_output_data = []
    total_final_audio_duration = 0.0
    chunk_idx_in_visual_plan = 0
    processing_successful = True
    speed_factor = float(tts_config.get("audio_speed_factor", 1.0))
    print(f"Audio speed factor set to: {speed_factor}")
    print("\n--- Processing Start ---")
    sentence_global_index = 0

    with torch.no_grad(): # 추론 모드이므로 그래디언트 계산 비활성화
        for segment_idx, segment in enumerate(script_data.get('segments', [])):
            segment_type = segment.get('type', f'Unknown_{segment_idx}')
            for sentence_idx, sentence_original in enumerate(segment.get('sentences', [])):
                if not sentence_original or not isinstance(sentence_original, str): continue
                sentence_id = f"{segment_type}_S{sentence_idx}"
                print(f"\n[Sentence {sentence_global_index + 1} ({sentence_id})] Processing: '{sentence_original[:60]}...'")
                cleaned_sentence_original = sentence_original.strip()
                if cleaned_sentence_original.startswith('/'): cleaned_sentence_original = cleaned_sentence_original[1:].strip()
                processed_sentence = preprocess_text_simple(cleaned_sentence_original)
                if not processed_sentence: print(f"  Skipping empty sentence."); sentence_global_index += 1; continue
                print(f"  Preprocessed: '{processed_sentence[:60]}...'")
                raw_audio_filename = f"sentence_{segment_idx}_{sentence_idx}_raw.wav"
                raw_audio_path = os.path.join(episode_audio_output_dir, raw_audio_filename)
                tts_success, _, _ = generate_zonos_audio(processed_sentence, raw_audio_path, zonos_model, speaker_embedding, tts_config)
                if not tts_success: print(f"  TTS failed, skipping sentence.", file=sys.stderr); processing_successful = False; sentence_global_index += 1; continue
                final_audio_path = raw_audio_path
                if abs(speed_factor - 1.0) > 1e-6 and os.path.exists(raw_audio_path): # 속도 변경 필요시
                    sped_up_audio_filename = f"sentence_{segment_idx}_{sentence_idx}_fast.wav"
                    sped_up_audio_path = os.path.join(episode_audio_output_dir, sped_up_audio_filename)
                    speed_up_success = speed_up_audio(raw_audio_path, sped_up_audio_path, speed_factor)
                    if speed_up_success: final_audio_path = sped_up_audio_path
                    else: print(f"  Warning: Failed to speed up audio, using original.", file=sys.stderr)
                elif abs(speed_factor - 1.0) <= 1e-6 : print("  Skipping audio speed up (factor is ~1.0).")

                final_duration = get_audio_duration(final_audio_path)
                if final_duration <= 0: print(f"  Warning: Final audio has zero duration: {os.path.basename(final_audio_path)}", file=sys.stderr)
                total_final_audio_duration += final_duration
                print(f"  Final audio: {os.path.basename(final_audio_path)} ({final_duration:.3f}s)")
                word_timestamps = extract_whisper_timestamps(final_audio_path, whisper_model, tts_config.get("whisper_language", "ko"))
                if not word_timestamps and final_duration > 0.1: print(f"  Warning: Whisper failed for {os.path.basename(final_audio_path)}.")
                sentence_output = {"sentence": cleaned_sentence_original, "processed_sentence": processed_sentence, "audio_path": final_audio_path, "sentence_duration": round(final_duration, 3), "chunks": []}
                matched_chunks_info = []
                current_reconstruction_norm = ""
                processed_sentence_norm = re.sub(r'\s+', '', processed_sentence)
                temp_chunk_idx = chunk_idx_in_visual_plan
                while temp_chunk_idx < len(visual_plan_data):
                    chunk_info = visual_plan_data[temp_chunk_idx]; chunk_text = chunk_info.get("chunk_text", "")
                    processed_chunk = preprocess_text_simple(chunk_text); processed_chunk_norm = re.sub(r'\s+', '', processed_chunk)
                    if not processed_chunk_norm: temp_chunk_idx += 1; continue
                    next_reconstruction_norm = current_reconstruction_norm + processed_chunk_norm
                    if processed_sentence_norm.startswith(next_reconstruction_norm):
                        matched_chunks_info.append({"info": chunk_info, "tokens": processed_chunk.split()})
                        current_reconstruction_norm = next_reconstruction_norm; temp_chunk_idx += 1
                        if current_reconstruction_norm == processed_sentence_norm: break
                    else: break
                chunk_idx_in_visual_plan = temp_chunk_idx
                if not matched_chunks_info: print(f"  Warning: No visual plan chunks matched.")
                elif not word_timestamps: print(f"  Warning: No Whisper timestamps to assign.")
                else:
                    word_assignments = align_words_to_chunks_sequential(word_timestamps, matched_chunks_info, tts_config)
                    for chunk_idx, chunk_match_info in enumerate(matched_chunks_info):
                        assigned_words = word_assignments[chunk_idx] if chunk_idx < len(word_assignments) else []
                        chunk_start = assigned_words[0]['start'] if assigned_words else 0.0
                        chunk_end = assigned_words[-1]['end'] if assigned_words else 0.0
                        if chunk_end < chunk_start: chunk_end = chunk_start
                        chunk_duration = chunk_end - chunk_start
                        sentence_output["chunks"].append({"chunk_text": chunk_match_info["info"].get("chunk_text", ""), "visual_info": chunk_match_info["info"].get("visual"), "words": assigned_words, "chunk_start_in_sentence": round(chunk_start, 3), "chunk_end_in_sentence": round(chunk_end, 3), "chunk_duration": round(chunk_duration, 3)})
                final_output_data.append(sentence_output)
                sentence_global_index += 1
    print(f"\n--- Processing Finished ---")
    print(f"Saving final results to {final_output_json_path}...")
    try:
        final_structure = {"total_final_audio_duration_seconds": round(total_final_audio_duration, 3), "sentences": final_output_data}
        with open(final_output_json_path, 'w', encoding='utf-8') as f: json.dump(final_structure, f, ensure_ascii=False, indent=2)
        print(f"Successfully saved results for {sentence_global_index} sentences.")
        print(f"Total final audio duration: {total_final_audio_duration:.2f} seconds")
    except Exception as e: print(f"Error saving final JSON output: {e}", file=sys.stderr); processing_successful = False
    # --- 모델 및 리소스 정리 (캐시된 모델은 Streamlit이 관리하므로 del 호출 불필요) ---
    print("Cleaning up non-cached resources...")
    if speaker_embedding is not None: del speaker_embedding
    gc.collect()
    if device.type == 'cuda': torch.cuda.empty_cache()
    print("Cleanup complete.")
    return processing_successful

# --- Helper to load TTS config ---
def load_tts_config(channel_dir: str) -> Optional[Dict[str, Any]]:
    """Loads the tts_config.json file from the specified channel directory."""
    config_path = os.path.join(channel_dir, "tts_config.json")
    print(f"Attempting to load TTS config from: {config_path}")
    if not os.path.exists(config_path):
        print(f"Error: TTS configuration file not found at {config_path}", file=sys.stderr)
        return None
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        print("TTS configuration loaded successfully.")
        return config
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in TTS configuration file {config_path}: {e}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"Error reading TTS configuration file {config_path}: {e}", file=sys.stderr)
        return None