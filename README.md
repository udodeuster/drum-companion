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

`--onset-timeout-bars` accepts `0`, `1`, `2`, or `4` bars and defaults to `1`. It controls how long the app waits without detected attacks before treating an otherwise active input as musically inactive; zero makes the first onset gap eligible, while longer values preserve sparse playing longer. Once a tempo and groove have been established, the last groove continues at its current tempo and intensity through input silence and timeout inactivity until playback is manually stopped. When input returns, new reliable tempo and groove decisions update future bars without restarting the bar phase or moving already scheduled hits.

`--min-tempo` and `--max-tempo` (defaults `40` and `140`) set the BPM range the tempo analysis reports; estimates outside it are doubled or halved into the range, so the maximum must be at least twice the minimum. The web UI has matching "Min BPM" / "Max BPM" sliders that apply live.

The tight feel keeps eighth notes straight. Relaxed feel delays offbeat eighth notes for a 55% swing; rock and folk add quiet offbeat ghost snares, while indie does not. Intensity changes accompaniment strength and supplementary accents/hi-hat density; the core kick and backbeat remain while intensity is above zero. Master level independently controls overall output volume.

When a tempo estimate is near a multiple or fraction of the last stable pulse (about ½, ⅓, ¼, 2×, 3× or 4×, with 15% tolerance), the app holds the prior pulse until consistent reliable estimates support the alternative for at least three seconds. While drums are playing, such half/double-time estimates are ignored entirely, because the microphone can hear the drums' own eighth notes as a double-time pulse. Other reliable tempo changes remain responsive. The live view exposes current confidence while holding the prior pulse.

During playback, press `M` to mute/unmute, `+` or `-` to adjust output level, and `Q` or `Ctrl+C` to stop. The bundled CC0 starter kit's asset sources and license details are in `drum_companion/assets/drums/manifest.json`. Only the drums are sent to the selected output; guitar/voice input is not monitored through it.

For same-computer or phone control on a private network, start the local browser panel:

```bash
python main.py --web
```

Open the printed localhost URL on the computer and scan the QR code shown there with your phone. The QR opens the page only; enter the PIN displayed on the computer manually on your phone. The panel does not use a cloud service. Keep it on a trusted private network and do not forward its port through your router; plain HTTP does not encrypt traffic on the LAN.

If the phone cannot connect, set the computer's Wi-Fi network profile to **Private** and allow Python through Windows Defender Firewall on private networks. Guest Wi-Fi or router client isolation can also prevent devices from reaching each other. Do not allow access on public networks.

### Create and select saved grooves

In the paired browser panel, choose **Edit grooves** to open the step editor. Start with **New blank groove** or **Copy current Auto groove**; the copy places the existing eighth-note events on every other step of the 16-step grid. Tap a step to toggle that instrument, and use each track's level slider to set its balance. Enter a name and choose **Save groove** to persist the draft; unsaved edits are not applied to the saved version.

Select **Auto** or a named groove from **Playback groove** in the main view. Auto keeps generating the current style-based accompaniment. A saved groove uses its edited tracks while tempo and activity continue to follow the live input. **Intensity** scales all custom-groove hits together, each track level sets that instrument's relative level, and **Master level** controls the overall output. Relaxed feel swings eighth-note offbeats in saved grooves as well as Auto.

The groove library is stored on the host computer at `%LOCALAPPDATA%\DrumCompanion\grooves.json` on Windows. A paired phone edits the same host-local library; grooves are not synchronized to a cloud service.

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
