# launchd agents

Five agents keep the pipeline alive without a terminal. Install with
`launchctl load ~/Library/LaunchAgents/<name>.plist` after replacing `PIPELINE_ROOT`.

| Agent | Schedule | What it does |
|---|---|---|
| `build-runner` | every 120 s | dispatches pending specs to `build-one` processes (cap N) |
| `task-runner` | every 60 s | fast lane: rejections, recolors, fixes (cap 2) |
| `dispatcher-watchdog` | every 300 s | restarts the Telegram dispatcher session if it died |
| `learn-nightly` | 03:30 daily | turns today's manual-fix journal into rule proposals |
| `morning-brief` | 09:00 daily | overnight digest to Telegram |

Template (`build-runner`):

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.pipeline.build-runner</string>
  <key>ProgramArguments</key>
  <array><string>/bin/zsh</string><string>-lc</string><string>PIPELINE_ROOT/bin/build-runner</string></array>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PIPELINE_ROOT</key><string>PIPELINE_ROOT</string>
    <key>PIPELINE_TG_TOKEN</key><string></string>
    <key>PIPELINE_TG_CHAT</key><string></string>
  </dict>
  <key>StartInterval</key><integer>120</integer>
  <key>AbandonProcessGroup</key><true/>
  <key>ProcessType</key><string>Background</string>
</dict>
</plist>
```

`AbandonProcessGroup` matters: the runner exits in a second, but the `build-one` children it
spawned must survive it.
