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
python main.py --live --play-drums --output-device 3 --master-level 0.7 --onset-timeout-bars 1
```

`--onset-timeout-bars` accepts `0`, `1`, `2`, or `4` bars and defaults to `1`. It controls how long the app waits without detected attacks before treating an otherwise active input as musically inactive; zero makes the first onset gap eligible, while longer values preserve sparse playing longer. During a brief pause the last groove continues to the next downbeat, holds for one full bar, then fades over the next bar. If attacks return, playback rejoins on a downbeat without restarting the bar phase and ramps back over one beat.

The tight feel keeps eighth notes straight. Relaxed feel delays offbeat eighth notes for a 55% swing; rock and folk add quiet offbeat ghost snares, while indie does not. Intensity changes accompaniment strength and supplementary accents/hi-hat density; the core kick and backbeat remain while intensity is above zero. Master level independently controls overall output volume.

When a tempo estimate is near half or double the last stable pulse, the app waits for three consistent reliable estimates before changing pulse. Other reliable tempo changes remain responsive. The live view exposes current confidence while holding the prior pulse.

During playback, press `M` to mute/unmute, `+` or `-` to adjust output level, and `Q` or `Ctrl+C` to stop. The bundled CC0 starter kit's asset sources and license details are in `drum_companion/assets/drums/manifest.json`. Only the drums are sent to the selected output; guitar/voice input is not monitored through it.

For same-computer or phone control on a private network, start the local browser panel:

```bash
python main.py --web
```

Open the printed localhost URL on the computer and scan the QR code shown there with your phone. The QR opens the page only; enter the PIN displayed on the computer manually on your phone. The browser's **No-onset timeout** setting accepts `0`, `1`, `2`, or `4` bars and applies immediately to the live session. The panel does not use a cloud service. Keep it on a trusted private network and do not forward its port through your router; plain HTTP does not encrypt traffic on the LAN.

If the phone cannot connect, set the computer's Wi-Fi network profile to **Private** and allow Python through Windows Defender Firewall on private networks. Guest Wi-Fi or router client isolation can also prevent devices from reaching each other. Do not allow access on public networks.

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
