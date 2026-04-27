#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TEXT_DATA 文本转音频统一路由器。"""
import os
os.environ.setdefault('NUMBA_CACHE_DIR', '/tmp/numba_cache')
os.environ.setdefault('NUMBA_DISABLE_JIT', '1')
import base64
import datetime
import hashlib
import json
import random
import re
import sqlite3
import subprocess
import time
import uuid
import requests
from loguru import logger
from pathlib import Path
from typing import List, Optional, Tuple
from src.utils.common import mango_config


class Text2AudioRouter:
    """统一文本转音频路由器（按语种与引擎策略路由）。"""

    def __init__(self, pytest_config):
        self.pytest_config = pytest_config
        root_dir = self.pytest_config.getoption('--mongo_root_dir')
        self.root_dir = Path(root_dir)

        audio_cache_path = mango_config.get_config_value('NANOText2Audio', 'audio_cache_path')
        if not audio_cache_path:
            raise ValueError("NANOText2Audio.audio_cache_path 未配置")

        # 增加日期文件夹（格式：YYYYMMDD）
        date_folder = datetime.datetime.now().strftime("%Y%m%d")
        output_path = Path(audio_cache_path) / date_folder
        if not output_path.is_absolute():
            output_path = self.root_dir / output_path
        self.audio_cache_path = output_path
        self.audio_cache_path.mkdir(parents=True, exist_ok=True)

        audio_cache_db = mango_config.get_config_value('NANOText2Audio', 'audio_cache_db')
        self.cache_enabled = False
        self.audio_cache_db: Optional[Path] = None
        if audio_cache_db:
            db_path = Path(audio_cache_db)
            if not db_path.is_absolute():
                db_path = self.root_dir / db_path
            self.audio_cache_db = db_path
            if self.audio_cache_db.exists():
                self.cache_enabled = True
            else:
                logger.warning(
                    f"TEXT_DATA 缓存数据库不存在，降级为仅合成模式: {self.audio_cache_db}"
                )
        else:
            logger.warning("TEXT_DATA 未配置 audio_cache_db，降级为仅合成模式")

        self.silence_pad_ms = int(mango_config.get_config_value('NANOText2Audio', 'silence_pad_ms'))
        self.edge_only_langs = self._split_csv(mango_config.get_config_value('NANOText2Audio', 'edge_only_langs'))
        self.volcano_only_langs = self._split_csv(mango_config.get_config_value('NANOText2Audio', 'volcano_only_langs'))
        self.cmn_auto_chain = self._split_csv(mango_config.get_config_value('NANOText2Audio', 'cmn_auto_chain'))
        self.eng_auto_chain = self._split_csv(mango_config.get_config_value('NANOText2Audio', 'eng_auto_chain'))
        self.request_timeout = float(mango_config.get_config_value('NANOText2Audio', 'request_timeout_sec'))
        self.cache_wait_timeout_sec = max(self.request_timeout * 4, 30.0)
        self.inflight_lease_sec = max(self.request_timeout * 2, 30.0)
        self.poll_interval_sec = 0.1
        if self.cache_enabled:
            self._ensure_cache_tables()

    @staticmethod
    def _split_csv(value: str) -> List[str]:
        return [item.strip() for item in (value or '').split(',') if item.strip()]

    @staticmethod
    def normalize_lang(lang: Optional[str]) -> Optional[str]:
        if not lang:
            return None
        lang = lang.strip().lower()
        alias_map = {
            'zh': 'cmn',
            'cn': 'cmn',
            'en': 'eng',
            'ja': 'jap',
            'jp': 'jap',
            'th': 'thai',
        }
        return alias_map.get(lang, lang)

    @staticmethod
    def normalize_engine(engine: Optional[str]) -> str:
        if not engine:
            return 'auto'
        engine = engine.strip()
        lower_engine = engine.lower()
        alias_map = {
            'auto': 'auto',
            'edge': 'edge_tts',
            'edge-tts': 'edge_tts',
            'edge_tts': 'edge_tts',
            'volcano': 'volcano',
            'index': 'index_tts',
            'index_tts': 'index_tts',
            'vox': 'voxCpm',
            'voxcpm': 'voxCpm',
            'voxcpm': 'voxCpm',
        }
        return alias_map.get(lower_engine, engine)

    @staticmethod
    def infer_lang(text: str) -> str:
        """自动识别语种：
        - 包含中文（含中英混合）=> cmn
        - 纯英文（数字/标点/emoji 忽略）=> eng
        """
        has_cmn = re.search(r'[\u4e00-\u9fff]', text) is not None
        has_eng = re.search(r'[A-Za-z]', text) is not None

        if has_cmn:
            return 'cmn'
        if has_eng:
            return 'eng'
        raise ValueError("无法从文本自动识别语种，请显式传入 lang 参数")

    def synthesize(self, text: str, lang: Optional[str], engine: Optional[str]) -> Tuple[str, str]:
        """执行文本转音频，返回 (音频路径, 实际引擎)。"""
        if not text or not text.strip():
            raise ValueError("TEXT_DATA 参数 text 不能为空")

        normalized_text = text.strip()
        normalized_lang = self.normalize_lang(lang) or self.infer_lang(normalized_text)
        if not self.cache_enabled:
            return self._synthesize_audio(
                text=normalized_text,
                lang=normalized_lang,
                engine=engine,
            )

        cache_key = self._build_cache_key(normalized_text, normalized_lang)

        cached_path = self._get_cached_audio_path(cache_key=cache_key, text=normalized_text, lang=normalized_lang)
        if cached_path:
            logger.info(f"TEXT_DATA 缓存命中: lang={normalized_lang}, output={cached_path}")
            return cached_path, "cache"

        owner_id = uuid.uuid4().hex
        lock_acquired = self._try_acquire_inflight(cache_key=cache_key, owner_id=owner_id)
        if not lock_acquired:
            deadline = time.time() + self.cache_wait_timeout_sec
            while time.time() < deadline:
                cached_path = self._get_cached_audio_path(cache_key=cache_key, text=normalized_text, lang=normalized_lang)
                if cached_path:
                    logger.info(f"TEXT_DATA 并发等待后命中缓存: lang={normalized_lang}, output={cached_path}")
                    return cached_path, "cache"
                if self._try_acquire_inflight(cache_key=cache_key, owner_id=owner_id):
                    lock_acquired = True
                    break
                time.sleep(self.poll_interval_sec)
            if not lock_acquired:
                raise RuntimeError(f"文本转音频等待缓存超时: lang={normalized_lang}, text={normalized_text}")

        try:
            # 拿到 inflight 后二次检查，避免并发窗口内重复合成。
            cached_path = self._get_cached_audio_path(cache_key=cache_key, text=normalized_text, lang=normalized_lang)
            if cached_path:
                logger.info(f"TEXT_DATA inflight 二次检查命中缓存: lang={normalized_lang}, output={cached_path}")
                return cached_path, "cache"

            output_path, engine_used = self._synthesize_audio(
                text=normalized_text,
                lang=normalized_lang,
                engine=engine,
            )
            self._upsert_cache_record(
                cache_key=cache_key,
                text=normalized_text,
                lang=normalized_lang,
                path=output_path,
            )
            return output_path, engine_used
        finally:
            self._release_inflight(cache_key=cache_key, owner_id=owner_id)

    def _synthesize_audio(self, text: str, lang: str, engine: Optional[str]) -> Tuple[str, str]:
        normalized_engine = self.normalize_engine(engine)
        engines = self._resolve_engine_chain(lang, normalized_engine)
        errors: List[str] = []

        for engine_name in engines:
            try:
                filename = str(uuid.uuid4()).replace("-", "") + ".wav"
                output_file = self.audio_cache_path / filename
                if engine_name == 'volcano':
                    audio_bytes = self._synthesize_with_volcano(text, lang)
                elif engine_name == 'edge_tts':
                    audio_bytes = self._synthesize_with_edge_tts(text, lang)
                elif engine_name == 'index_tts':
                    audio_bytes = self._synthesize_with_index_tts(text)
                elif engine_name == 'voxCpm':
                    audio_bytes = self._synthesize_with_voxcpm(text)
                else:
                    raise ValueError(f"不支持的合成引擎: {engine_name}")

                audio_bytes = self._convert_sample_rate(audio_bytes)
                audio_bytes = self._audio_process(audio_bytes)
                output_file.write_bytes(audio_bytes)
                logger.info(f"TEXT_DATA 合成成功: engine={engine_name}, lang={lang}, output={output_file}")
                return self._to_store_path(output_file), engine_name
            except Exception as exc:
                errors.append(f"{engine_name}: {exc}")
                logger.warning(f"TEXT_DATA 合成失败: engine={engine_name}, error={exc}")
                if normalized_engine != 'auto':
                    break

        raise RuntimeError("文本转音频失败，尝试链路: " + " -> ".join(engines) + " | " + " | ".join(errors))

    @staticmethod
    def _normalize_cache_text(text: str) -> str:
        return text.strip()

    def _build_cache_key(self, text: str, lang: str) -> str:
        normalized_text = self._normalize_cache_text(text)
        raw = f"{normalized_text}|{lang}"
        return hashlib.sha256(raw.encode('utf-8')).hexdigest()

    def _connect_cache_db(self) -> sqlite3.Connection:
        if not self.cache_enabled or not self.audio_cache_db:
            raise RuntimeError("缓存数据库未启用")
        conn = sqlite3.connect(str(self.audio_cache_db), timeout=5.0)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    def _ensure_cache_tables(self) -> None:
        with self._connect_cache_db() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tts_audio_cache (
                  cache_key TEXT PRIMARY KEY,
                  text      TEXT NOT NULL,
                  lang      TEXT NOT NULL,
                  path      TEXT NOT NULL,
                  created_at INTEGER NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS ux_tts_text_lang
                ON tts_audio_cache(text, lang)
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tts_inflight (
                  cache_key   TEXT PRIMARY KEY,
                  owner_id    TEXT NOT NULL,
                  lease_until INTEGER NOT NULL
                )
                """
            )
            conn.commit()

    def _resolve_path(self, path_str: str) -> Path:
        path = Path(path_str)
        if path.is_absolute():
            return path
        return self.root_dir / path

    def _to_store_path(self, path: Path) -> str:
        try:
            return str(path.relative_to(self.root_dir))
        except ValueError:
            return str(path)

    def _get_cached_audio_path(self, cache_key: str, text: str, lang: str) -> Optional[str]:
        normalized_text = self._normalize_cache_text(text)
        with self._connect_cache_db() as conn:
            row = conn.execute(
                """
                SELECT path FROM tts_audio_cache
                WHERE cache_key = ? AND text = ? AND lang = ?
                """,
                (cache_key, normalized_text, lang),
            ).fetchone()
            if not row:
                return None

            path_str = row[0]
            candidate = self._resolve_path(path_str)
            if candidate.exists():
                return path_str

            # 数据库命中但文件缺失，删除脏记录以便后续重建。
            conn.execute(
                "DELETE FROM tts_audio_cache WHERE cache_key = ?",
                (cache_key,),
            )
            conn.commit()
            logger.warning(f"TEXT_DATA 发现缓存脏数据并删除: cache_key={cache_key}, path={path_str}")
            return None

    def _upsert_cache_record(self, cache_key: str, text: str, lang: str, path: str) -> None:
        now_ts = int(time.time())
        normalized_text = self._normalize_cache_text(text)
        store_path = self._to_store_path(Path(path))
        with self._connect_cache_db() as conn:
            conn.execute(
                """
                INSERT INTO tts_audio_cache (cache_key, text, lang, path, created_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(cache_key) DO UPDATE SET
                  text = excluded.text,
                  lang = excluded.lang,
                  path = excluded.path,
                  created_at = excluded.created_at
                """,
                (cache_key, normalized_text, lang, store_path, now_ts),
            )
            conn.execute(
                """
                UPDATE tts_audio_cache
                SET cache_key = ?, path = ?, created_at = ?
                WHERE text = ? AND lang = ? AND cache_key != ?
                """,
                (cache_key, store_path, now_ts, normalized_text, lang, cache_key),
            )
            conn.commit()

    def _try_acquire_inflight(self, cache_key: str, owner_id: str) -> bool:
        now_ts = int(time.time())
        lease_until = now_ts + int(self.inflight_lease_sec)
        with self._connect_cache_db() as conn:
            try:
                conn.execute(
                    """
                    INSERT INTO tts_inflight (cache_key, owner_id, lease_until)
                    VALUES (?, ?, ?)
                    """,
                    (cache_key, owner_id, lease_until),
                )
                conn.commit()
                return True
            except sqlite3.IntegrityError:
                cursor = conn.execute(
                    """
                    UPDATE tts_inflight
                    SET owner_id = ?, lease_until = ?
                    WHERE cache_key = ? AND lease_until < ?
                    """,
                    (owner_id, lease_until, cache_key, now_ts),
                )
                conn.commit()
                return cursor.rowcount > 0

    def _release_inflight(self, cache_key: str, owner_id: str) -> None:
        with self._connect_cache_db() as conn:
            conn.execute(
                "DELETE FROM tts_inflight WHERE cache_key = ? AND owner_id = ?",
                (cache_key, owner_id),
            )
            conn.commit()

    def _convert_sample_rate(self, audio_bytes: bytes) -> bytes:
        import io
        import numpy as np
        import scipy.io.wavfile as wavfile
        import scipy.signal as signal

        buf_in = io.BytesIO(audio_bytes)
        sr, data = wavfile.read(buf_in)

        if sr != 16000:
            num_samples = int(len(data) * 16000 / sr)
            data = signal.resample(data, num_samples)
            data = data.astype(np.int16)

        buf_out = io.BytesIO()
        wavfile.write(buf_out, 16000, data)
        return buf_out.getvalue()

    def _audio_process(self, audio_bytes: bytes, trim_head_ms: int = 0, trim_tail_ms: int = 100) -> bytes:
        import io
        import numpy as np
        import scipy.io.wavfile as wavfile

        buf_in = io.BytesIO(audio_bytes)
        sr, data = wavfile.read(buf_in)           # data 是 int16
        data = data.astype(np.float32) / 32767.0  # 转 float32 方便运算

        trim_head = int(sr * trim_head_ms / 1000)
        trim_tail = int(sr * trim_tail_ms / 1000)
        data = data[trim_head: len(data) - trim_tail]

        pad_samples = int(sr * self.silence_pad_ms / 1000)
        silence = np.zeros(pad_samples, dtype=np.float32)
        data = np.concatenate([silence, data, silence])

        buf_out = io.BytesIO()
        wavfile.write(buf_out, sr, (data * 32767).astype(np.int16))
        return buf_out.getvalue()

    def _resolve_engine_chain(self, lang: str, engine: str) -> List[str]:
        if engine != 'auto':
            return [engine]

        if lang in self.volcano_only_langs:
            return ['volcano']
        if lang in self.edge_only_langs:
            return ['edge_tts']
        if lang == 'cmn':
            return self.cmn_auto_chain
        if lang == 'eng':
            return self.eng_auto_chain
        return ['edge_tts']

    def _synthesize_with_volcano(self, text: str, lang: str) -> bytes:
        appid = mango_config.get_config_value('NANOText2Audio', 'volcano_appid')
        access_token = mango_config.get_config_value('NANOText2Audio', 'volcano_access_token')
        cluster = mango_config.get_config_value('NANOText2Audio', 'volcano_cluster')
        api_url = mango_config.get_config_value('NANOText2Audio', 'volcano_api_url')
        uid = mango_config.get_config_value('NANOText2Audio', 'volcano_uid')
        voice_cmn = mango_config.get_config_value('NANOText2Audio', 'volcano_voice_cmn')
        voice_chuan = mango_config.get_config_value('NANOText2Audio', 'volcano_voice_chuan')
        voice_eng = mango_config.get_config_value('NANOText2Audio', 'volcano_voice_eng')
        if lang == 'eng':
            voice = voice_eng
        elif lang == 'chuan':
            voice = voice_chuan
        else:
            voice = voice_cmn

        if not appid or not access_token:
            raise ValueError("volcano 配置不完整，请检查 volcano_appid / volcano_access_token")

        payload = {
            "app": {"appid": appid, "token": "access_token", "cluster": cluster},
            "user": {"uid": uid},
            "audio": {"voice": "other", "voice_type": voice, "encoding": "wav", "rate": 16000},
            "request": {"reqid": str(uuid.uuid4()), "text": text, "text_type": "plain", "operation": "query"},
        }
        headers = {"Authorization": f"Bearer;{access_token}"}

        resp = requests.post(api_url, data=json.dumps(payload), headers=headers, timeout=self.request_timeout)
        resp.raise_for_status()
        result = resp.json()
        if "data" not in result:
            raise RuntimeError(f"volcano 返回无音频数据: {result}")
        return base64.b64decode(result["data"])

    def _synthesize_with_edge_tts(self, text: str, lang: str) -> bytes:
        voice = self._get_edge_voice(lang)
        mp3_bytes = subprocess.run(
            ["edge-tts", "--voice", voice, "--text", text, "--write-media", "/dev/stdout"],
            check=True, capture_output=True, timeout=self.request_timeout,
        ).stdout
        result = subprocess.run(
            ["ffmpeg", "-y", "-i", "pipe:0", "-ar", "16000", "-ac", "1",
            "-sample_fmt", "s16", "-f", "wav", "pipe:1"],
            input=mp3_bytes, check=True, capture_output=True, timeout=self.request_timeout,
        )
        return result.stdout

    def _get_edge_voice(self, lang: str) -> str:
        # 默认音色可在 mango.ini 调整
        default_map = {
            "cmn": mango_config.get_config_value('NANOText2Audio', 'edge_voice_cmn'),
            "eng": mango_config.get_config_value('NANOText2Audio', 'edge_voice_eng'),
            "jap": mango_config.get_config_value('NANOText2Audio', 'edge_voice_jap'),
            "thai": mango_config.get_config_value('NANOText2Audio', 'edge_voice_thai'),
            "yue": mango_config.get_config_value('NANOText2Audio', 'edge_voice_yue'),
        }
        return default_map.get(lang)

    def _synthesize_with_index_tts(self, text: str) -> bytes:
        api_url = mango_config.get_config_value('NANOText2Audio', 'index_tts_api')
        # 随机使用 seed_audios/{N}_seed.wav 作为 prompt_audio_path。
        random_num = random.randint(1, 1000)
        prompt_audio_path = f"seed_audios/{random_num}_seed.wav"

        payload = {
            "text": text,
            "prompt_audio_base64": None,
            "prompt_audio_path": prompt_audio_path,
            "infer_mode": "普通推理",
        }
        resp = requests.post(api_url, json=payload, timeout=self.request_timeout)
        resp.raise_for_status()
        result = resp.json()
        if not result.get("success") or not result.get("audio_base64"):
            raise RuntimeError(f"index_tts 返回失败: {result}")
        return base64.b64decode(result["audio_base64"])

    def _synthesize_with_voxcpm(self, text: str) -> bytes:
        api_url = mango_config.get_config_value('NANOText2Audio', 'voxcpm_quick_api')
        payload = {
            "text": text,
            "cfg_value": 2.0,
            "inference_timesteps": 10,
            "normalize": True,
            "denoise": True,
        }
        resp = requests.post(api_url, data=payload, timeout=self.request_timeout)
        resp.raise_for_status()
        result = resp.json()
        if result.get("status") != "success" or not result.get("audio_data"):
            raise RuntimeError(f"voxCpm 返回失败: {result}")
        return base64.b64decode(result["audio_data"])
