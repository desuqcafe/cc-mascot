export type MascotFrame = 'idle' | 'thinking' | 'working' | 'happy' | 'error' | 'waiting' | 'worried' | 'sleepy' | 'beam'

/** The frame shown now; while `holdUntil` (clock ms) is ahead, `then` waits for the hold to end. */
export type MascotMood = { frame: MascotFrame; holdUntil: number; then: MascotFrame }

/**
 * Whether the session is really done: the main turn running, the subagents
 * still at work, background agent work the last Stop reported, and whether
 * the end of this round of work has had its happy moment yet.
 */
export type MascotWork = { inTurn: boolean; agents: string[]; hasBackground: boolean; isSettled: boolean }

/** Whether a mascot is shown, and when that was chosen (epoch ms): the newest choice wins. */
export type MascotVisibility = { visible: boolean; at: number }

/**
 * What the mod writes to `~/.claude/mascot/sessions/<key>.json` for its own
 * overlay: the frame, the hover card's figures, whether to show, when the
 * conversation was last cleared (`cleared`, clock ms: the overlay plays a
 * channel change), the character it shows (`character`, a folder under
 * frames/: a new one makes the overlay play its outro, take on that art and
 * look, and play its intro), and `ended` once the session is over (the
 * overlay then plays its outro, cleans up and exits).
 * `~/.claude/mascot/all.json` holds a MascotVisibility for every session.
 */
export type MascotSessionFile = {
  frame: MascotFrame
  info?: Record<string, unknown>
  visible: boolean
  visibleAt: number
  cleared?: number
  character?: string
  ended?: true
}

/**
 * `~/.claude/mascot/settings.json`, every session's: written by /mascot, the
 * settings window or by hand, followed live by every overlay. A key left out
 * (or not valid) is its default: `size` her height in px (240-640, 420);
 * `calm` no glitch, particles, flicker or flashes (false); `aura` the context
 * tokens at which her aura's three levels start, ascending, or false for none
 * ([300000, 400000, 500000]); `beamAfter` the minutes a round of work lasts
 * before it ends in the beam (1-120), or false for never (2);
 * `beamForAgents` a round that used agents ends in it too (true).
 */
export type MascotSettings = {
  size?: number
  calm?: boolean
  aura?: [number, number, number] | false
  beamAfter?: number | false
  beamForAgents?: boolean
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
