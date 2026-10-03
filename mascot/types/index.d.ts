export type MascotFrame = 'idle' | 'thinking' | 'working' | 'happy' | 'error' | 'waiting' | 'worried' | 'sleepy' | 'beam'

/** The frame shown now; while `holdUntil` (clock ms) is ahead, `then` waits for the hold to end. */
export type MascotMood = { frame: MascotFrame; holdUntil: number; then: MascotFrame }

/**
 * Whether the session is really done: the main turn running, the subagents
 * still at work, background agent work the last Stop reported, and whether
 * the end of this round of work has had its happy moment yet.
 */
/**
 * The main turn, the subagents running, whether background agents were
 * listed at its end, and until when (clock ms; 0 for none) other background
 * work Claude started this round holds the round open (a shell, a monitor,
 * a wakeup).
 */
export type MascotWork = {
  inTurn: boolean
  agents: string[]
  hasBackground: boolean
  waitUntil: number
  isSettled: boolean
}

/** Whether a mascot is shown, and when that was chosen (epoch ms): the newest choice wins. */
export type MascotVisibility = { visible: boolean; at: number }

/**
 * What the mod writes to `~/.claude/mascot/sessions/<key>.json` for its own
 * overlay: the frame, the hover card's figures, whether to show, when the
 * conversation was last cleared (`cleared`, clock ms: the overlay plays a
 * channel change), the character it shows (`character`, a folder under
 * frames/: a new one makes the overlay play its outro, take on that art and
 * look, and play its intro), `update` (the mascot's version and its
 * updates, for the settings window and the overlay), and `ended` once the
 * session is over (the overlay then plays its outro, cleans up and exits).
 * `~/.claude/mascot/all.json` holds a MascotVisibility for every session.
 */
export type MascotSessionFile = {
  frame: MascotFrame
  info?: Record<string, unknown>
  visible: boolean
  visibleAt: number
  cleared?: number
  character?: string
  update?: MascotUpdate
  call?: MascotCall
  ended?: true
}

/**
 * Her call to the pointer: a round of work ended (`at`, epoch ms) that
 * lasted the `magicAfter` setting's minutes. The overlay sends magic to the
 * pointer at once, waiting only while a fullscreen game or a presentation
 * holds notifications back; `test` (/mascot magic) does not wait even then.
 */
export type MascotCall = { at: number; test?: true }

/**
 * The mascot's version and its updates: `version` the one running; `latest`
 * a newer release the daily check found (`checkUpdates`); `route` how this
 * copy updates ('marketplace': `claude plugin update`, 'clone': `git pull`,
 * 'manual': by hand); `state` an update run from this session ('updating',
 * 'updated', or 'failed' with `message`); `celebrate` (epoch ms) when a
 * newer version than the last one run first loaded, `from` that one: the
 * overlay plays its banner once, while that is fresh.
 */
export type MascotUpdate = {
  version: string
  latest?: string
  route: 'marketplace' | 'clone' | 'manual'
  state?: 'updating' | 'updated' | 'failed'
  message?: string
  celebrate?: number
  from?: string
}

/**
 * `~/.claude/mascot/settings.json`, every session's: written by /mascot, the
 * settings window or by hand, followed live by every overlay. A key left out
 * (or not valid) is its default: `size` her height in px (240-640, 420);
 * `calm` no glitch, particles, flicker or flashes (false); `smooth` her
 * status's particles step with a moving symbol, 36 fps, not 12 (false); `aura` the context
 * tokens at which her aura's three levels start, ascending, or false for none
 * ([300000, 400000, 500000]); `beamAfter` the minutes a round of work lasts
 * before it ends in the beam (1-120), or false for never (2);
 * `beamForAgents` a round that used agents ends in it too (true);
 * `magicAfter` the minutes a round of work lasts before its end sends magic
 * to the pointer (0-120: 0 every round), or
 * false for never (false); `checkUpdates` look for a newer release on GitHub once a day (false).
 */
export type MascotSettings = {
  size?: number
  calm?: boolean
  smooth?: boolean
  aura?: [number, number, number] | false
  beamAfter?: number | false
  beamForAgents?: boolean
  magicAfter?: number | false
  checkUpdates?: boolean
}

declare module 'claude-code' {
  interface PluginState {
    /**
     * `view`: this session's show or hide (`at` 0 until chosen); `sessionKey`:
     * the name of its file; `character`: a character picked for this session
     * alone ('' for none: the project's). All outlive a reload of the mod.
     */
    mascot: { mood: MascotMood; work: MascotWork; view: MascotVisibility; sessionKey: string; character: string }
  }
}
