Drum Companion

Erstellt werden soll eine App die einen Gitarristen bzw. Solokünstler mit der Rhytmusgruppe unterstützt.
Die App "hört" wenn ein Instrument spielt und setzt mit einem Passenden Rhytmus ein.
Dabei soll sich die Auswahl der drums, die Spielweise und Dynamik des Rhytmus dem Künstler anpassen.
Die Sounds sollen natürlich, die Rhytmik soll nicht zu getacktet klingen.

## Quick start

This repository now includes a greenfield scaffold for the drum companion concept.

Install the application and its Windows desktop audio dependencies with Python 3.11 or newer:

```bash
python -m pip install -e .
```

Installation and automated tests do not require a microphone. Live capture requires an available input device and operating-system microphone permission. Android packaging and capture are not supported by this prototype yet.

List available Windows microphone inputs:

```bash
python main.py --list-inputs
```

List available Windows drum-playback outputs:

```bash
python main.py --list-outputs
```

Start live analysis with sampled drum playback. Select an output index from `--list-outputs`; omit `--output-device` to use the default output:

```bash
python main.py --live --play-drums --output-device 3 --master-level 0.7
```

During playback, press `M` to mute/unmute, `+` or `-` to adjust output level, and `Q` or `Ctrl+C` to stop. The bundled CC0 starter kit's asset sources and license details are in `drum_companion/assets/drums/manifest.json`. Only the drums are sent to the selected output; guitar/voice input is not monitored through it.

For a Windows playback smoke test, choose an index from `--list-outputs` and run `python main.py --live --play-drums --output-device <index> --master-level 0.15` while playing a steady guitar pulse. Confirm the drum pattern becomes audible, test `M` and `+`/`-`, then stop with `Q`. If the output device cannot open, an actionable warning is printed and microphone analysis continues without drums.

Start capture with the default input, or select an index from the device list. Stop with `Ctrl+C`:

```bash
python main.py --live
python main.py --live --device 0
```

The live view reports rolling tempo/confidence, combined energy, and a groove-pattern preview. Live samples are held in memory and are not recorded to disk.

For a Windows live-capture smoke check, run `--list-inputs`, select an input index, then start `--live --device <index>`. Confirm timestamped energy/tempo/pattern updates appear and stop with `Ctrl+C`; the app should print a stop confirmation. If Windows blocks microphone access or the device cannot open, the CLI reports the failure instead of showing live measurements.

```bash
python main.py --tempo 96 --style rock --feel tight --intensity 0.8
```

The CLI prints a minimal performance context and a generated groove pattern for solo guitar + voice use.
