"""Pocket TTS inference and audio processing for the studio."""

from collections import OrderedDict
from collections.abc import Callable, Iterator
from pathlib import Path
import math
import re
import subprocess
import tempfile
import wave

import numpy as np
import torch
from pocket_tts import TTSModel
from pocket_tts.default_parameters import DEFAULT_VOICE_FOR_LANGUAGE
from pocket_tts.utils.utils import _ORIGINS_OF_PREDEFINED_VOICES

MAX_TEXT = 16_000
MAX_CHARACTERS = 12
MAX_TURNS = 100
MAX_VOICES = 6
SAMPLE_RATE = 24_000
VOICE_SECONDS = 30
UPLOAD_LIMIT = 20 * 1024 * 1024
PREVIEW_TEXT = "Olá! Esta é uma amostra de voz em português brasileiro."
MODELS = ("portuguese", "portuguese_24l")
DEFAULT_VOICE = DEFAULT_VOICE_FOR_LANGUAGE["portuguese"]
# The pinned Pocket TTS release uses this registry for its built-in voice states.
OFFICIAL_VOICES = tuple(sorted(_ORIGINS_OF_PREDEFINED_VOICES))

SPEAKER_LINE = re.compile(r"^\[([^\[\]\n]+)\][ \t]*(.*)$")
AUDIO_FORMATS = "aac,aiff,caf,flac,matroska,mov,mp3,ogg,wav"


class StudioError(Exception):
    """An input or operational error that can be shown to the user."""


def checked_text(text: str | None) -> str:
    if not text or not text.strip():
        raise StudioError("Digite um texto para gerar o áudio.")
    if len(text) > MAX_TEXT:
        raise StudioError(f"O texto excede o limite de {MAX_TEXT:,} caracteres.".replace(",", "."))
    if not any(char.isalnum() for char in text):
        raise StudioError("Inclua palavras ou números no texto.")
    return text.strip()


def parse_dialogue(text: str | None) -> list[tuple[str, str]]:
    turns: list[tuple[str, list[str]]] = []
    for line in checked_text(text).splitlines():
        line = line.strip()
        if not line:
            continue
        match = SPEAKER_LINE.fullmatch(line)
        if match:
            name = " ".join(match[1].split())
            if not name or len(name) > 40:
                raise StudioError("Use nomes de personagens com 1 a 40 caracteres entre colchetes.")
            turns.append((name.casefold(), [match[2]]))
        elif turns and not line.startswith("["):
            turns[-1][1].append(line)
        else:
            raise StudioError("Inicie cada fala com [personagem], seguido do que ele diz.")

    if len(turns) > MAX_TURNS or len({name for name, _ in turns}) > MAX_CHARACTERS:
        raise StudioError(f"Use até {MAX_TURNS} falas e {MAX_CHARACTERS} personagens por roteiro.")
    return [(name, checked_text(" ".join(parts))) for name, parts in turns]


def sections(text: str) -> Iterator[str]:
    """Group prose into manageable sections while leaving token chunking to Pocket TTS."""
    while len(text) > 1_200:
        sentence_ends = list(re.finditer(r"[.!?…][\"”’)]*(?=\s)|\n", text[:1_200]))
        if sentence_ends and sentence_ends[-1].end() >= 600:
            cut = sentence_ends[-1].end()
        else:
            cut = max((m.start() for m in re.finditer(r"\s", text[:1_200])), default=1_200)
            if cut < 600:
                cut = 1_200
        yield text[:cut].strip()
        text = text[cut:].lstrip()
    if text:
        yield text


def decode_sample(path: str | None) -> bytes:
    """Decode up to 30 seconds of a local upload to 24 kHz mono PCM."""
    if not path or not Path(path).is_file():
        raise StudioError("Envie um arquivo de áudio.")
    if Path(path).stat().st_size > UPLOAD_LIMIT:
        raise StudioError("Envie uma amostra de até 20 MB.")
    try:
        result = subprocess.run(
            [
                "ffmpeg", "-nostdin", "-v", "error", "-protocol_whitelist", "file,pipe",
                "-format_whitelist", AUDIO_FORMATS, "-threads", "1", "-i", path,
                "-map", "0:a:0", "-vn", "-t", str(VOICE_SECONDS), "-ac", "1",
                "-ar", str(SAMPLE_RATE), "-f", "s16le", "pipe:1",
            ],
            capture_output=True,
            check=True,
            timeout=35,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise StudioError("Não consegui ler o áudio. Tente WAV, MP3, M4A, FLAC ou OGG.") from exc
    pcm = result.stdout
    if len(pcm) < SAMPLE_RATE * 2 or np.max(np.abs(np.frombuffer(pcm, "<i2").astype(np.int32))) < 48:
        raise StudioError("Envie pelo menos 1 segundo de áudio com fala audível.")
    return pcm


def save_voice(name: str, path: str | None, authorized: bool, voices: dict[str, bytes]) -> dict[str, bytes]:
    if not authorized:
        raise StudioError("Confirme que você tem autorização para clonar essa voz.")
    name = " ".join((name or "").split())
    if not 1 <= len(name) <= 36:
        raise StudioError("Escolha um nome de 1 a 36 caracteres para a voz.")
    if any(key.casefold() == name.casefold() for key in voices):
        raise StudioError("Já existe uma voz com esse nome na biblioteca.")
    if len(voices) >= MAX_VOICES:
        raise StudioError(f"A biblioteca comporta até {MAX_VOICES} vozes. Remova uma para adicionar outra.")
    return {**voices, name: decode_sample(path)}


def voice_value(key: str | None, voices: dict[str, bytes]) -> str | bytes:
    if key and key.startswith("personal:") and key[9:] in voices:
        return voices[key[9:]]
    if key in OFFICIAL_VOICES:
        return key
    raise StudioError("Selecione uma voz disponível para cada fala.")


def validate_controls(model: str, temp: float, steps: int) -> None:
    if model not in MODELS:
        raise StudioError("Escolha uma variante válida do modelo.")
    if not isinstance(temp, (int, float)) or not math.isfinite(temp) or not 0 <= temp <= 1:
        raise StudioError("A temperatura deve estar entre 0 e 1.")
    if steps not in (1, 2, 3, 4):
        raise StudioError("Escolha de 1 a 4 passos de decodificação.")


class Engine:
    """Retain one model and a bounded cache of public voice states."""

    def __init__(self) -> None:
        self.language = None
        self.model = None
        self.public_states = OrderedDict()

    def load(self, language: str, temp: float, steps: int) -> TTSModel:
        validate_controls(language, temp, steps)
        if self.model is None or self.language != language:
            self.model = None
            self.public_states.clear()
            torch.set_num_threads(2)
            self.model = TTSModel.load_model(language=language, temp=temp, sampler_decode_steps=int(steps))
            self.language = language
        # Pocket TTS reads these sampling attributes on each frame. Calls are serialized in Gradio.
        self.model.temp = float(temp)
        self.model.sampler_decode_steps = int(steps)
        return self.model

    def state(self, model: TTSModel, voice: str | bytes):
        if isinstance(voice, bytes):
            if not model.has_voice_cloning:
                raise StudioError(
                    "A clonagem precisa de acesso ao modelo kyutai/pocket-tts. "
                    "Peça ao responsável pelo Space para configurar a credencial de leitura."
                )
            prompt = np.frombuffer(voice, "<i2").astype(np.float32) / 32768.0
            return model.get_state_for_audio_prompt(torch.from_numpy(prompt).unsqueeze(0))

        if voice not in self.public_states:
            self.public_states[voice] = model.get_state_for_audio_prompt(voice)
            if len(self.public_states) > 8:
                self.public_states.popitem(last=False)
        self.public_states.move_to_end(voice)
        return self.public_states[voice]

    def export(
        self, turns: list[tuple[str, str | bytes]], language: str, temp: float, steps: int,
        output_root: Path, progress: Callable, *, preview: bool = False,
    ) -> tuple[Path, Path | None]:
        progress(0, desc="Preparando o Pocket TTS")
        model = self.load(language, temp, steps)
        if any(isinstance(voice, bytes) for _, voice in turns) and not model.has_voice_cloning:
            raise StudioError(
                "A clonagem precisa de acesso ao modelo kyutai/pocket-tts. "
                "Peça ao responsável pelo Space para configurar a credencial de leitura."
            )

        batches = [(list(sections(text)), voice) for text, voice in turns]
        total_chars = sum(len(section) for chunks, _ in batches for section in chunks)
        if total_chars == 0:
            raise StudioError("Digite um texto para gerar o áudio.")
        total_done = 0
        sample_count = 0
        private_states = {}
        output_root.mkdir(parents=True, exist_ok=True)
        folder = Path(tempfile.mkdtemp(prefix="studio-", dir=output_root))
        wav = folder / ("pre-escuta.wav" if preview else "rick-voice-studio.wav")
        mp3 = None if preview else folder / "rick-voice-studio.mp3"
        try:
            with wave.open(str(wav), "wb") as output:
                output.setparams((1, 2, model.sample_rate, 0, "NONE", "not compressed"))
                for index, (chunks, voice) in enumerate(batches):
                    if index:
                        output.writeframesraw(bytes(round(model.sample_rate * 0.25) * 2))
                    if isinstance(voice, bytes):
                        if voice not in private_states:
                            private_states[voice] = self.state(model, voice)
                        voice_state = private_states[voice]
                    else:
                        voice_state = self.state(model, voice)
                    for section in chunks:
                        progress(0.05 + 0.87 * total_done / total_chars, desc="Sintetizando a fala")
                        for frame in model.generate_audio_stream(voice_state, section):
                            pcm = frame.detach().float().cpu().numpy().reshape(-1)
                            if not np.isfinite(pcm).all():
                                raise StudioError("A síntese produziu amostras inválidas. Tente outra temperatura.")
                            output.writeframesraw(np.rint(np.clip(pcm, -1, 1) * 32767).astype("<i2").tobytes())
                            sample_count += pcm.size
                            if sample_count > model.sample_rate * 30 * 60:
                                raise StudioError("O áudio ultrapassou 30 minutos. Divida o texto em partes.")
                        total_done += len(section)
            if not sample_count:
                raise StudioError("O modelo não gerou áudio. Revise o texto e tente novamente.")
            if mp3 is not None:
                progress(0.95, desc="Exportando WAV e MP3")
                subprocess.run(
                    ["ffmpeg", "-nostdin", "-v", "error", "-i", str(wav),
                     "-map_metadata", "-1", "-c:a", "libmp3lame", "-b:a", "96k", str(mp3)],
                    check=True, timeout=120, capture_output=True,
                )
            progress(1, desc="Áudio pronto")
            return wav, mp3
        except BaseException:
            wav.unlink(missing_ok=True)
            if mp3 is not None:
                mp3.unlink(missing_ok=True)
            folder.rmdir()
            raise
