# Proposal

## Why

The live control page currently gives audio-device configuration the same prominence as performance and groove controls. Moving device setup into a dedicated settings dialog makes the live view easier to scan while keeping those options readily accessible from a gear icon.

## What Changes

- Add a gear-icon control in the page header that opens a Settings dialog.
- Move the complete Audio Devices section into that dialog.
- Keep performance, groove editing, and Start/Stop controls on the live view.
- Explain in the dialog that audio device and playback-mode changes require stopping the session first; users close the dialog to reach Stop.

## Capabilities

### New Capabilities
- `control-settings`: Access to device and playback configuration through a dedicated settings dialog.

### Modified Capabilities
- None.

## Impact

- Browser control page structure, navigation, responsive styling, and interaction tests.
- Existing settings and device APIs remain unchanged.
