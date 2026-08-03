# Unloved stack desktop launchers

Local dev launchers for ShadowCast, APF, and Mission Control.

## Install

```bash
mkdir -p ~/.local/bin/unloved-launchers ~/.local/share/applications ~/Desktop
cp -a scripts/unloved-launchers/*.sh ~/.local/bin/unloved-launchers/
chmod +x ~/.local/bin/unloved-launchers/*.sh
cp scripts/unloved-launchers/desktop/*.desktop ~/.local/share/applications/
cp scripts/unloved-launchers/desktop/*.desktop ~/Desktop/
```

## Stack launcher behavior

**Start Unloved Stack** opens:

- One **kitty** window with tabs: ShadowCast, APF, Mission Control
- One **Firefox** window with tabs: `http://localhost:8000`, APF port, `http://localhost:3100`

Individual app launchers still use cosmic-term (via `open-terminal.sh`) and open Firefox tabs with `--new-tab`.
