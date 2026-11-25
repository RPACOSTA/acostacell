import subprocess
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

import torch

from studio import (
    DEFAULT_VOICE, MAX_TEXT, Engine, StudioError, checked_text,
    decode_sample, parse_dialogue, save_voice, sections, voice_value,
)


class TestModel:
    """Deterministic frame source for application tests without model downloads."""

    has_voice_cloning = True
    sample_rate = 24_000

    def __init__(self):
        self.calls = []
        self.prompts = []

    def get_state_for_audio_prompt(self, voice):
        self.prompts.append(voice)
        return len(self.prompts)

    def generate_audio_stream(self, state, text):
        self.calls.append((state, text))
        yield torch.full((2400,), state * 0.05)


class StudioTest(unittest.TestCase):
    def test_dialogue_and_invalid_scripts(self):
        self.assertEqual(
            parse_dialogue("[Professora] Joãozinho?\nAinda está aí?\n\n[João] Sim!\n[professora] Ótimo."),
            [("professora", "Joãozinho? Ainda está aí?"), ("joão", "Sim!"), ("professora", "Ótimo.")],
        )
        for text in ("Sem personagem", "[  ] Sem nome", "[a]\n[b] Sim", "[a] Sim\n[erro"):
            with self.subTest(text=text), self.assertRaises(StudioError):
                parse_dialogue(text)

    def test_text_bounds_and_sections(self):
        long = "Este é um trecho de uma narração longa. " * 350
        chunks = list(sections(checked_text(long)))
        self.assertGreater(len(chunks), 10)
        self.assertTrue(all(len(chunk) <= 1200 for chunk in chunks))
        self.assertEqual(" ".join(chunks), long.strip())
        with self.assertRaises(StudioError):
            checked_text("a" * (MAX_TEXT + 1))

    def test_upload_consent_isolation_and_conversion(self):
        with tempfile.TemporaryDirectory() as temp:
            sample = Path(temp) / "amostra.m4a"
            subprocess.run(
                ["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "sine=frequency=300:duration=2",
                 "-c:a", "aac", str(sample)],
                check=True,
            )
            library = {}
            with self.assertRaises(StudioError):
                save_voice("Minha voz", str(sample), False, library)
            updated = save_voice("Minha voz", str(sample), True, library)
            self.assertEqual(library, {})
            self.assertEqual(voice_value("personal:Minha voz", updated), decode_sample(str(sample)))
            with self.assertRaises(StudioError):
                voice_value("personal:Minha voz", library)
            with self.assertRaises(StudioError):
                save_voice("minha voz", str(sample), True, updated)
            corrupted = Path(temp) / "bad.wav"
            corrupted.write_bytes(b"wrong data")
            with self.assertRaises(StudioError):
                decode_sample(str(corrupted))

    def test_dialogue_export_order_formats_and_progress(self):
        model = TestModel()
        engine = Engine()
        progress = []
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(engine, "load", return_value=model) as load:
                wav, mp3 = engine.export(
                    [("Pergunta?", DEFAULT_VOICE), ("Resposta.", "alba"), ("Obrigada.", DEFAULT_VOICE)],
                    "portuguese_24l", 0.6, 3, Path(temp),
                    lambda value, **_: progress.append(value),
                )
            load.assert_called_once_with("portuguese_24l", 0.6, 3)
            self.assertEqual(model.calls, [(1, "Pergunta?"), (2, "Resposta."), (1, "Obrigada.")])
            self.assertEqual(model.prompts, [DEFAULT_VOICE, "alba"])
            self.assertEqual(progress, sorted(progress))
            self.assertEqual((progress[0], progress[-1]), (0, 1))
            with wave.open(str(wav)) as audio:
                self.assertEqual((audio.getnchannels(), audio.getframerate()), (1, 24000))
                self.assertEqual(audio.getnframes(), 3 * 2400 + 2 * 6000)
                audio.readframes(2400)
                self.assertEqual(audio.readframes(6000), bytes(12000))
            subprocess.run(["ffmpeg", "-v", "error", "-i", str(mp3), "-f", "null", "-"], check=True)

    def test_voice_cloning_uses_a_tensor_and_respects_model_gate(self):
        engine = Engine()
        model = TestModel()
        private_voice = (300).to_bytes(2, "little", signed=True) * 24000
        engine.state(model, private_voice)
        self.assertEqual(tuple(model.prompts[0].shape), (1, 24000))
        self.assertFalse(engine.public_states)
        model.has_voice_cloning = False
        with self.assertRaises(StudioError):
            engine.state(model, private_voice)


if __name__ == "__main__":
    unittest.main()
