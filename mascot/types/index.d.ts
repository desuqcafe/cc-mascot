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
  cue?: MascotCue
  visit?: MascotVisit
  ended?: true
}

/**
 * A prompt that came from elsewhere (`at`, epoch ms): `from` 'bridge' (Remote
 * Control: the Claude app on a phone, or the web) or 'channel' (a chat an MCP
 * server relays, `name` its server). With the `remote` setting on, the
 * overlay shows her messenger bringing it in, once per new `at`.
 */
export type MascotVisit = { at: number; from: 'bridge' | 'channel'; name?: string }

/** The moments she has a sound for (the `sounds` setting). */
export type MascotMoment = 'waiting' | 'done' | 'beam' | 'error' | 'magic' | 'intro' | 'outro'

/**
 * A moment only the mod knows (`at`, epoch ms): a round done or ending in
 * the beam, a turn that died. The overlay plays its sound once per new
 * `at`, as the settings say; `test` (/mascot sound try) plays it whatever
 * they say. The overlay finds the other moments itself.
 */
export type MascotCue = { at: number; moment: MascotMoment; test?: true }

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
 * newer version than the last one run first loaded: the overlay plays its
 * banner once, while that is fresh; `from` the version before the last
 * update (`$.store` `upgrade`, in every session while `version` runs): the
 * settings window's news counts from it; `installed` a newer version
 * installed since this session loaded (an update run from another
 * session): this one meets it with /reload-plugins.
 */
export type MascotUpdate = {
  version: string
  latest?: string
  route: 'marketplace' | 'clone' | 'manual'
  state?: 'updating' | 'updated' | 'failed'
  message?: string
  celebrate?: number
  from?: string
  installed?: string
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
 * false for never (false); `checkUpdates` look for a newer release on GitHub once a day (false);
 * `sound` she plays sounds (false); `volume` theirs, 0-100 (60); `sounds`
 * per moment, false none, true her own or the name of a file of yours in
 * the mascot folder's sounds/ (.wav or .mp3), a moment left out its default
 * (waiting, done, beam and error her own, the rest none); `waitingAfter`
 * the seconds she waits on you before her waiting sound (10-300, 30);
 * `nudge` once she has waited that long, her messenger calls and her
 * terminal's taskbar button flashes, and a click on her brings her
 * terminal forward (false); `remote` her messenger brings in a prompt from
 * Remote Control or a channel (false); `away` what happened while you were away, on a note
 * she holds when you are back (false).
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
  sound?: boolean
  volume?: number
  sounds?: Partial<Record<MascotMoment, boolean | string>>
  waitingAfter?: number
  nudge?: boolean
  remote?: boolean
  away?: boolean
}

declare module 'claude-code' {
  interface PluginState {
    /**
     * `view`: this session's show or hide (`at` 0 until chosen); `sessionKey`:
     * the name of its file; `character`: a character picked for this session
     * alone ('' for none: the project's); `ran`: the version this
     * conversation ran last ('' for none: a new session, or after a /clear).
     * All outlive a reload of the mod.
     */
    mascot: {
      mood: MascotMood
      work: MascotWork
      view: MascotVisibility
      sessionKey: string
      character: string
      ran: string
    }
  }
}
