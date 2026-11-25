"""Gradio interface for Rick's Voice Studio V001."""

import logging
from pathlib import Path

import gradio as gr
from gradio.processing_utils import get_upload_folder

from studio import (
    DEFAULT_VOICE,
    Engine,
    MAX_CHARACTERS,
    MAX_TEXT,
    OFFICIAL_VOICES,
    PREVIEW_TEXT,
    StudioError,
    checked_text,
    parse_dialogue,
    save_voice,
    voice_value,
)

TITLE = "Rick's Voice Studio V001"
LOG = logging.getLogger("studio")
ENGINE = Engine()
CACHE = Path(get_upload_folder())
EXAMPLE = (
    "[professora] Joãozinho, por que o Brasil não cresce?\n\n"
    "[joaozinho] Porque o Brasil está deitado em berço estreito!"
)
CPU_JOB = {"concurrency_id": "pocket-tts-cpu", "concurrency_limit": 1}
MODEL_OPTIONS = [("Padrão · 6 camadas", "portuguese"), ("24 camadas · mais lento", "portuguese_24l")]
MAX_LABEL = f"{MAX_TEXT:,}".replace(",", ".")


def voice_choices(library: dict[str, bytes]) -> list[tuple[str, str]]:
    official = [(f"{DEFAULT_VOICE.title()} · Português", DEFAULT_VOICE)]
    experiments = [
        (f"{voice.replace('_', ' ').title()} · Experimental em PT-BR", voice)
        for voice in OFFICIAL_VOICES if voice != DEFAULT_VOICE
    ]
    return official + experiments + [(f"{name} · Personalizada", f"personal:{name}") for name in library]


def counter(text: str) -> str:
    length = f"{len(text or ''):,}".replace(",", ".")
    return f"{length} / {MAX_LABEL} caracteres"


def prepare_dialogue(text: str, previous: list[str], library: dict[str, bytes], *current: str):
    """Read the cast and preserve previously assigned voices."""
    try:
        speakers = list(dict.fromkeys(name for name, _ in parse_dialogue(text)))
    except StudioError as exc:
        raise gr.Error(str(exc)) from exc
    selections = dict(zip(previous, current))
    choices = voice_choices(library)
    assignments = [
        gr.update(choices=choices, label=f"Voz de {name}", visible=True, value=selections.get(name, DEFAULT_VOICE))
        for name in speakers
    ]
    assignments.extend(gr.update(visible=False, value=None) for _ in range(MAX_CHARACTERS - len(speakers)))
    return speakers, gr.update(visible=True), *assignments


def refresh_library(library: dict[str, bytes], current: tuple[str, ...]):
    options = voice_choices(library)
    valid = {value for _, value in options}
    voice_updates = [
        gr.update(choices=options, value=value if value in valid or value is None else DEFAULT_VOICE)
        for value in current
    ]
    return library, gr.update(choices=list(library), value=None), *voice_updates


def add_voice(name: str, path: str | None, consent: bool, library: dict[str, bytes], *current: str):
    """Add a consented sample to this session's voice library."""
    try:
        library = save_voice(name, path, consent, library)
    except StudioError as exc:
        raise gr.Error(str(exc)) from exc
    except OSError as exc:
        LOG.warning("Falha ao processar uma amostra (%s)", type(exc).__name__)
        raise gr.Error("Não foi possível processar a amostra no servidor.") from None
    gr.Info("Voz adicionada à biblioteca desta sessão.")
    return *refresh_library(library, current), "", None, False


def remove_voice(name: str | None, library: dict[str, bytes], *current: str):
    """Remove a saved sample from this session."""
    if name not in library:
        raise gr.Error("Selecione a voz personalizada que deseja remover.")
    library = {key: audio for key, audio in library.items() if key != name}
    gr.Info("Voz removida da biblioteca.")
    return refresh_library(library, current)


def render_audio(turns, model: str, temp: float, steps: int, progress, *, preview: bool = False):
    try:
        return ENGINE.export(turns, model, temp, steps, CACHE, progress, preview=preview)
    except StudioError:
        raise
    except Exception as exc:
        LOG.warning("Falha na geração com %s (%s)", model, type(exc).__name__)
        raise StudioError(
            "Não foi possível gerar o áudio. Verifique a conexão e o acesso aos pesos do Pocket TTS, "
            "ou tente novamente com um trecho menor."
        ) from None


def generate(text: str, voice: str, model: str, temperature: float, steps: int,
             library: dict[str, bytes], progress=gr.Progress()):
    """Generate a narration in Portuguese and return playable WAV and MP3 files."""
    try:
        turns = [(checked_text(text), voice_value(voice, library))]
        wav, mp3 = render_audio(turns, model, temperature, steps, progress)
    except StudioError as exc:
        raise gr.Error(str(exc)) from exc
    return ready(wav, mp3, "Narração pronta para ouvir e baixar.")


def generate_dialogue(text: str, model: str, temperature: float, steps: int,
                      library: dict[str, bytes], speakers: list[str], progress=gr.Progress(),
                      *selections: str):
    """Synthesize scripted speakers independently and join their audio in order."""
    try:
        parsed = parse_dialogue(text)
        assignments = dict(zip(speakers, selections))
        if {name for name, _ in parsed} != set(assignments):
            raise StudioError("Clique em Detectar personagens e confirme a voz de cada pessoa.")
        turns = [(line, voice_value(assignments[name], library)) for name, line in parsed]
        wav, mp3 = render_audio(turns, model, temperature, steps, progress)
    except StudioError as exc:
        raise gr.Error(str(exc)) from exc
    return ready(wav, mp3, f"Diálogo pronto. {len(turns)} falas renderizadas.")



def ready(wav: Path, mp3: Path, status: str):
    return wav, gr.update(value=wav, interactive=True), gr.update(value=mp3, interactive=True), status

def preview_voice(voice: str, model: str, temperature: float, steps: int,
                  library: dict[str, bytes], progress=gr.Progress()):
    """Generate a short Portuguese phrase with the currently selected voice."""
    try:
        sample = voice_value(voice, library)
        wav, _ = render_audio([(PREVIEW_TEXT, sample)], model, temperature, steps, progress, preview=True)
    except StudioError as exc:
        raise gr.Error(str(exc)) from exc
    return wav


voice_options = voice_choices({})
with gr.Blocks(title=TITLE, analytics_enabled=False, delete_cache=(600, 3600)) as demo:
    library = gr.State({}, time_to_live=3600)
    speakers = gr.State([], time_to_live=3600)
    gr.HTML("""
        <header class="studio-header">
          <div class="studio-brand">
            <div class="studio-mark" aria-hidden="true"><i></i><i></i><i></i><i></i><i></i></div>
            <div>
              <h1>Rick’s Voice Studio <span>V001</span></h1>
              <p>Síntese de voz em português com Pocket TTS</p>
            </div>
          </div>
        </header>
    """)

    with gr.Row(equal_height=False, elem_classes="studio-grid"):
        with gr.Column(scale=3, min_width=300, elem_classes="panel"):
            with gr.Tabs():
                with gr.Tab("Narração"):
                    text = gr.Textbox(
                        label="Texto da narração", placeholder="Digite ou cole o texto que você quer narrar…",
                        lines=12, max_lines=18, elem_classes="script-input",
                    )
                    text_count = gr.Markdown(counter(""), elem_classes="character-count")
                    generate_btn = gr.Button("Gerar narração", variant="primary")
                with gr.Tab("Diálogo"):
                    script = gr.Textbox(
                        label="Roteiro", info="Comece cada fala com [personagem]. Use uma nova linha para trocar de personagem.",
                        placeholder=EXAMPLE, lines=9, max_lines=18, elem_classes="script-input",
                    )
                    script_count = gr.Markdown(counter(""), elem_classes="character-count")
                    with gr.Row():
                        example_btn = gr.Button("Usar exemplo", size="sm", variant="secondary")
                        detect_btn = gr.Button("Detectar personagens", size="sm", variant="secondary")
                    with gr.Group(visible=False) as casting:
                        assignments = [
                            gr.Dropdown(choices=voice_options, visible=False, filterable=True,
                                        label="Voz do personagem", allow_custom_value=False)
                            for _ in range(MAX_CHARACTERS)
                        ]
                    dialogue_btn = gr.Button("Gerar diálogo", variant="primary")

        with gr.Column(scale=2, min_width=290, elem_classes="panel settings"):
            gr.Markdown("## Voz e geração")
            voice = gr.Dropdown(
                choices=voice_options, value=DEFAULT_VOICE, label="Voz para narração e pré-escuta",
                allow_custom_value=False, info="As vozes experimentais podem manter o sotaque de origem.",
            )
            preview_btn = gr.Button("Pré-escutar voz", variant="secondary", size="sm")
            audition = gr.Audio(label="Amostra em português", interactive=False, format="wav",
                                buttons=[])
            with gr.Accordion("Configurações do modelo", open=True):
                model = gr.Dropdown(
                    choices=MODEL_OPTIONS, value="portuguese", label="Variante em português",
                    allow_custom_value=False,
                )
                temperature = gr.Slider(0, 1, value=0.3, step=0.05, label="Temperatura")
                steps = gr.Slider(
                    1, 4, value=1, step=1, label="Passos de decodificação",
                    info="Mais passos podem melhorar a qualidade e aumentam o tempo de geração.",
                )
            with gr.Accordion("Biblioteca de vozes", open=False):
                gr.Markdown("As amostras ficam na sessão atual. Use uma gravação limpa com até 30 segundos.")
                saved = gr.Dropdown(choices=[], label="Vozes da sessão", allow_custom_value=False)
                remove_btn = gr.Button("Remover voz", variant="secondary", size="sm")
                new_name = gr.Textbox(label="Nome da nova voz", max_lines=1)
                sample_file = gr.File(
                    label="Amostra de áudio", file_types=[".wav", ".mp3", ".m4a", ".aac",
                                                           ".flac", ".ogg", ".aiff", ".caf", ".webm"],
                    file_count="single",
                )
                authorized = gr.Checkbox(label="Tenho autorização para usar esta gravação e clonar a voz.")
                add_btn = gr.Button("Adicionar à biblioteca", variant="secondary")

    with gr.Column(elem_classes=["panel", "output-panel"]):
        gr.Markdown("## Áudio gerado")
        player = gr.Audio(label="Reprodução", interactive=False, format="wav", show_label=False,
                          buttons=[])
        with gr.Row():
            wav_button = gr.DownloadButton("Baixar WAV", interactive=False)
            mp3_button = gr.DownloadButton("Baixar MP3", interactive=False)
        result = gr.Markdown("")

    count_event = {
        "queue": False, "api_visibility": "private", "trigger_mode": "always_last", "show_progress": "hidden",
    }
    text.input(counter, text, text_count, **count_event)
    script.change(counter, script, script_count, **count_event)
    example_btn.click(lambda: EXAMPLE, outputs=script, queue=False, api_visibility="private")
    detect_btn.click(
        prepare_dialogue, [script, speakers, library, *assignments],
        [speakers, casting, *assignments], api_visibility="private", show_progress="hidden",
    )
    selectors = [voice, *assignments]
    library_outputs = [library, saved, *selectors]
    add_btn.click(
        add_voice, [new_name, sample_file, authorized, library, *selectors],
        [*library_outputs, new_name, sample_file, authorized], api_visibility="private",
        show_progress="hidden", **CPU_JOB,
    )
    remove_btn.click(remove_voice, [saved, library, *selectors], library_outputs,
                     api_visibility="private", show_progress="hidden", **CPU_JOB)
    common = [model, temperature, steps, library]
    output = [player, wav_button, mp3_button, result]
    preview_btn.click(preview_voice, [voice, *common], audition, api_name="pre_escutar", **CPU_JOB)
    generate_btn.click(generate, [text, voice, *common], output, api_name="gerar_narracao", **CPU_JOB)
    dialogue_btn.click(
        generate_dialogue, [script, *common, speakers, *assignments], output,
        api_visibility="private", **CPU_JOB,
    )

demo.queue(max_size=12)

def launch():
    demo.launch(
        server_name="0.0.0.0",
        css_paths=Path(__file__).with_name("studio.css"),
        footer_links=["api"],
        state_session_capacity=64,
        max_file_size="20mb",
        enable_monitoring=False,
        js='() => { document.documentElement.lang = "pt-BR"; }',
    )


if __name__ == "__main__":
    launch()
