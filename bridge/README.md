# Telegram bridge — the operator's channel to the dispatcher agent

The dispatcher is a long-running Claude Code session in tmux. This directory is how a
message from the operator's phone reaches it, and how its answer comes back — written to
replace the Telegram MCP plugin after that plugin kept silently dropping the channel.

```
phone ──▶ Bot API ──getUpdates──▶ tg-poll ──tmux send-keys──▶ dispatcher (Claude Code)
                                    │  inbox/ (long specs,            │
                                    │  photos, documents)             │
phone ◀── Bot API ◀──sendMessage── tg-reply ◀─────────────────────────┘
                                    │ writes .last-reply → tg-poll stops "typing..."
launchd: tg-poll (KeepAlive)   tg-watchdog (every 5 min)
```

| File | Role |
|---|---|
| `tg-poll` | the only `getUpdates` consumer: chat allow-list, "typing..." until answered, routes text inline or via `inbox/`, downloads attachments |
| `tg-reply` | answers through the Bot API, 3900-char chunks, marks the reply for `tg-poll` |
| `tg-watchdog` | kills a duplicate listener, detects a *stuck* session (not just a dead one), restarts and tells the operator why |
| `tg-on` | starts the dispatcher with its role prompt and tool allow-list in a detached tmux session |
| `tests/` | routing and chunking tests, no network |

## Why not the MCP plugin

The plugin worked until it didn't, and the failure was invisible. Two root causes, each
now a mechanism:

1. **Two consumers of `getUpdates`.** Telegram delivers each update to one poller. Any
   session that started the plugin again silently stole the operator's messages. The
   receiver treats HTTP 409 as a diagnosis ("someone else is polling"), not as a transient
   error, and the watchdog removes the duplicate within five minutes.
2. **"Process alive" ≠ "bridge alive".** After a CLI auto-update the session sat on a
   blocking "trust this folder" dialog for a day. The process existed; nothing was being
   answered. The watchdog now reads the pane, and a blocking prompt seen on two
   consecutive checks triggers a restart plus a message to the operator with the reason.

## Other decisions

- **Long specs go through a file.** `tmux send-keys` would turn every newline of a
  specification into Enter. Anything over 300 characters or multi-line is written to
  `inbox/<msg_id>.txt`; the session gets a pointer and reads the file.
- **The dispatcher cannot answer by accident into the void.** Every injected line ends
  with the rule that only `tg-reply` reaches the phone; text typed into the session does not.
- **Typing indicator tied to the real reply**, not to a timer: the operator can tell
  "working" from "stuck" without asking.
- **Config by environment**, no ids in code: `PIPELINE_TG_CHAT`, `PIPELINE_BRIDGE_DIR`,
  `PIPELINE_TMUX_SESSION`; the bot token lives in `$PIPELINE_BRIDGE_DIR/.env`.
