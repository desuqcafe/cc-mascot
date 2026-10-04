import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register, Timer } from 'claude-code'

import type {
  MascotCall,
  MascotFrame,
  MascotMood,
  MascotSessionFile,
  MascotSettings,
  MascotUpdate,
  MascotVisibility,
  MascotWork,
} from '../types'

const HOLD_MS = 3000
// A round of work (from a prompt until all of it is done) of the `beamAfter`
// setting's minutes or more, or one that used subagents or background agents
// (`beamForAgents`), ends in her big finish, the beam, held this long,
// instead of happy. One of the `magicAfter` setting's minutes or more ends
// in her call too: magic sent to the pointer.
const BEAM_MS = 3600
// After the last subagent ends, how long to wait for the main agent to pick
// its results up before calling the work done.
const SETTLE_MS = 2000
// A model request that has streamed nothing for this long is stuck: the
// engine retrying an API error, or a dropped connection.
const STALL_MS = 10_000
const STALL_TICK_MS = 1000
// How long idle lasts before the mascot dozes off.
const SLEEP_MS = 5 * 60_000
// Background tasks that are agents at work.
const AGENT_TASKS = ['subagent', 'workflow', 'remote_agent']
// Other background work Claude starts and will hear back from (a shell when
// it exits, Claude's Monitor tool at each event, a one-time wakeup when it
// fires) holds the round open too, when started during it: an orchestrator
// that ends its turn to wait on a build is not done. Not a shell that serves
// or watches, which runs on by design (`isEndless`), and none of it past
// WAIT_CAP_MS (a server that list missed): the round then ends quietly,
// without happy or magic, since nobody can tell the work is done.
// The Monitor tool's tasks are listed as shells (checked headless, 2.1.289).
// A task of type `monitor` is a subscription with no end, such as the live
// watch Claude Code keeps on an artifact it published (seen 0.16.5: she sat
// in working for the cap after a publish), so it never holds a round.
const WAIT_CAP_MS = 30 * 60_000
// Shell commands that run until stopped: dev servers, watchers, log tails.
const ENDLESS_COMMANDS = [
  /\b(npm|pnpm|yarn|bun)\s+(run\s+)?(dev|serve|start|watch|preview)\b/,
  /\b(next|nuxt|astro|remix|ng|webpack|hugo|jekyll|vue-cli-service|wrangler)\s+(dev|serve|server)\b/,
  /\bvite\b(?!\s+(build|optimize))/,
  /\b(nodemon|live-server|http-server|uvicorn|gunicorn|hypercorn|streamlit)\b/,
  /\bhttp\.server\b|\bflask\s+run\b|\brunserver\b|\brails\s+s(erver)?\b|\bphp\s+-S\b/,
  /--watch\b|\b(cargo|dotnet)\s+watch\b|\binotifywait\b.*\s-m\b/,
  /\btail\s+(-\w+\s+)*-\w*[fF]\b|\bGet-Content\b.*\s-Wait\b/i,
  /\bdocker(-compose|\s+compose)\s+up\b(?!.*\s(-d|--detach)\b)/,
]
// A bare forever loop runs until stopped; one that breaks or exits on its
// own (a poll, a watch waiting for a line, as a monitor's script is) ends.
const FOREVER_LOOP = /\bwhile\s+(true|:)\s*[;\n]/
const ENDS_ITSELF = /\b(break|exit)\b/
const isEndless = (command: string) =>
  ENDLESS_COMMANDS.some(pattern => pattern.test(command)) ||
  (FOREVER_LOOP.test(command) && !ENDS_ITSELF.test(command))
// Tools that wait on the person: their whole run is waiting.
const ASKING_TOOLS = ['AskUserQuestion', 'ExitPlanMode']
// The hover card: how soon after an event it refreshes, how often on its own
// (the usage limits move without events), and how often it rereads where
// auto-compact starts. Replies kept for the context growth rate.
const REFRESH_DELAY_MS = 500
const REFRESH_EVERY_MS = 30_000
const COMPACT_CHECK_MS = 5 * 60_000
const GROWTH_REPLIES = 6
// `$.store`: whether a new session's mascot starts shown (the last choice
// made), and the character each project's sessions show.
const OVERLAY_KEY = 'isOverlayOn'
const CHARACTERS_KEY = 'characters'
const DEFAULT_CHARACTER = 'miku'
// How long a restart waits for the old overlay to go before starting anyway.
const STOP_WAIT_MS = 3000
// Updates. A version newer than the last one a session ran (`$.store`) gets
// her banner once, however it came. Looking for a newer release online is
// the `checkUpdates` setting's, off by default: then, once a day, a read of
// the manifest on GitHub's main branch, and nothing sent.
const LATEST_URL = 'https://raw.githubusercontent.com/desuqcafe/cc-mascot/main/mascot/.claude-plugin/plugin.json'
const CHECK_EVERY_MS = 24 * 60 * 60_000
const VERSION_KEY = 'lastVersion'
const LATEST_KEY = 'latest'
// `$.store`: the last update, { from, to }: what is new counts from `from`
// while `to` runs, in every session (not only the one that saw it first).
const UPGRADE_KEY = 'upgrade'
const UPDATE_TIMEOUT_MS = 5 * 60_000
// How long she stays happy under her banner.
const CELEBRATE_MS = 3600

const mood = atom({ plugin: 'mascot', key: 'mood' } as const, {
  frame: 'idle',
  holdUntil: 0,
  then: 'idle',
} as MascotMood)

const work = atom({ plugin: 'mascot', key: 'work' } as const, {
  inTurn: false,
  agents: [],
  hasBackground: false,
  waitUntil: 0,
  isSettled: true,
} as MascotWork)

// The settings, every session's: `settings.json` beside all.json, written
// by /mascot (and the settings window, and by hand), followed live by every
// overlay. overlay/settings.py holds the same rules: a key left out, or a
// value that is not a valid one, is its default.
type Settings = Required<{ [K in keyof MascotSettings]: Exclude<MascotSettings[K], undefined> }>
const DEFAULTS: Settings = {
  size: 420,
  calm: false,
  smooth: false,
  aura: [300_000, 400_000, 500_000],
  beamAfter: 2,
  beamForAgents: true,
  magicAfter: false,
  checkUpdates: false,
}
const SIZE_RANGE = [240, 640] as const
const SIZES: Record<string, number> = { small: 300, normal: 420, large: 560 }
const AURA_RANGE = [10_000, 10_000_000] as const
const BEAM_RANGE = [1, 120] as const
const MAGIC_RANGE = [0, 120] as const

const inRange = (v: unknown, [low, high]: readonly [number, number]): v is number =>
  typeof v === 'number' && Number.isFinite(v) && v >= low && v <= high

const checks: { [K in keyof Settings]: (v: unknown) => Settings[K] | undefined } = {
  size: v => (inRange(v, SIZE_RANGE) ? Math.round(v) : undefined),
  calm: v => (typeof v === 'boolean' ? v : undefined),
  smooth: v => (typeof v === 'boolean' ? v : undefined),
  aura: v => {
    if (v === false) return false
    if (!Array.isArray(v) || v.length !== 3 || !v.every(t => inRange(t, AURA_RANGE))) return undefined
    const [a, b, c] = v.map(t => Math.round(t as number)) as [number, number, number]
    return a < b && b < c ? [a, b, c] : undefined
  },
  beamAfter: v => (v === false ? false : inRange(v, BEAM_RANGE) ? Math.round(v) : undefined),
  beamForAgents: v => (typeof v === 'boolean' ? v : undefined),
  magicAfter: v => (v === false ? false : inRange(v, MAGIC_RANGE) ? Math.round(v) : undefined),
  checkUpdates: v => (typeof v === 'boolean' ? v : undefined),
}

const viewState = atom({ plugin: 'mascot', key: 'view' } as const, { visible: false, at: 0 } as MascotVisibility)
const keyState = atom({ plugin: 'mascot', key: 'sessionKey' } as const, '')
const characterState = atom({ plugin: 'mascot', key: 'character' } as const, '')

// The overlay (overlay/mascot_overlay.py) is a desktop window of its own that
// watches this session's file, which this module writes. It runs as long as
// this module does, shown or hidden; unloading the module ends it. On Windows
// the spawn passes through cmd.exe: the overlay looks past it for its Claude
// Code, whose end is the session's.
let overlay: { stop: () => Promise<void>; isEnding: boolean } | undefined
// This session's file is named once, by the session id at its first load: a
// /clear changes the id, not the mascot. Kept in `keyState` across reloads.
let sessionKey: string | undefined
// Shown or hidden, and when that was chosen; kept in `viewState`.
let view: MascotVisibility = { visible: false, at: 0 }
// The session is over: its last write said so, and nothing writes after it.
let isEnded = false
// When the conversation was last cleared (/clear, /resume): the overlay
// changes channel when this changes.
let clearedAt: number | undefined
// Her last call to the pointer: the overlay sends one when this changes.
let call: MascotCall | undefined
// The character the overlay shows: a new one (/mascot character) makes it
// play its outro, take on the new art and play its intro, on the same spot.
let characterNow: string | undefined
// A character picked for this session alone (the settings window, with
// "Remember for this project" off); kept in `characterState`.
let sessionCharacter: string | undefined
// Her version and its updates, as the session file carries them; and how
// this copy updates (`routeOf`).
let release: MascotUpdate | undefined
let updater: Route = { route: 'manual' }
let isChecking = false
let isUpdating = false

// Permission dialogs shown, numbered, by tool: a call that failed after one
// was shown for its tool was most likely declined, not broken.
let askCount = 0
const asks: { n: number; tool: string }[] = []
// Calls the auto-mode classifier refused, by tool_use_id.
const denied = new Set<string>()
// Dozes off once idle has lasted SLEEP_MS.
let sleepTimer: Timer | undefined
// The background work (tasks and wakeups, by id) listed at the last Stop.
let inFlight: string[] = []
// The round of work under way: when it started, whether agents helped, the
// background work already running then (none of it holds this round open),
// and when each piece started since was first listed.
type Round = { since?: number; hadAgents: boolean; before: Set<string>; seen: Map<string, number> }
const newRound = (since?: number): Round => ({ since, hadAgents: false, before: new Set(inFlight), seen: new Map() })
let round = newRound()

// What the overlay's hover card shows, written beside the mood. All of it is
// this one session's, so a mascot per session can show its own.
type CardInfo = {
  sessionId?: string
  project?: string
  branch?: string
  model?: string
  startedAt?: number
  prompts?: number
  context?: { tokens?: number; window: number; percent?: number; perTurn?: number; turnsToCompact?: number }
  limits: { kind: string; percent: number; resetsAt?: string }[]
  tool?: string
  turnSince?: number
  subagents: { type: string; tokens?: number; percent?: number }[]
  background: Record<string, number>
  // A newer release the daily check found.
  newVersion?: string
}

let frameNow: MascotFrame = 'idle'
let card: CardInfo | undefined
const live = {
  tool: undefined as string | undefined,
  turnSince: undefined as number | undefined,
  subagents: new Map<string, { type: string; tokens?: number; model?: string }>(),
  background: {} as Record<string, number>,
  // The main loop's model as the API names it: subagents on it share its window.
  mainModel: undefined as string | undefined,
  // Context tokens after each of the last few main replies, for the growth rate.
  history: [] as number[],
  compactAt: undefined as number | undefined,
  compactCheckedAt: 0,
}
let isRefreshPending = false

// Where every session's mascot keeps its files (mascot_overlay.py has the layout).
const stateDir = async ($: EngineInterface) => {
  const home = (await $.env.get('USERPROFILE')) ?? (await $.env.get('HOME'))
  return home ? `${home}/.claude/mascot` : undefined
}

const settingsFile = async ($: EngineInterface) => {
  const dir = await stateDir($)
  return dir ? `${dir}/settings.json` : undefined
}

// The file's object as written (unchecked); {} when there is none.
const readRawSettings = async ($: EngineInterface): Promise<Record<string, unknown>> => {
  const path = await settingsFile($)
  try {
    const data: unknown = path ? JSON.parse(await $.fs.read(path)) : undefined
    return data && typeof data === 'object' && !Array.isArray(data) ? (data as Record<string, unknown>) : {}
  } catch {
    return {}
  }
}

const loadSettings = async ($: EngineInterface): Promise<Settings> => {
  const raw = await readRawSettings($)
  const pick = <K extends keyof Settings>(key: K): Settings[K] =>
    (key in raw ? checks[key](raw[key]) : undefined) ?? DEFAULTS[key]
  return {
    size: pick('size'),
    calm: pick('calm'),
    smooth: pick('smooth'),
    aura: pick('aura'),
    beamAfter: pick('beamAfter'),
    beamForAgents: pick('beamForAgents'),
    magicAfter: pick('magicAfter'),
    checkUpdates: pick('checkUpdates'),
  }
}

// Sets keys, keeping whatever else the file holds; a default value (or
// null) takes its key out, so the file holds only what was changed.
const saveSettings = async ($: EngineInterface, changes: { [K in keyof Settings]?: Settings[K] | null }) => {
  const path = await settingsFile($)
  if (!path) throw new Error('Mascot: no home folder to keep its settings in.')
  const raw = await readRawSettings($)
  for (const key of Object.keys(changes) as (keyof Settings)[]) {
    const value = changes[key] === null ? undefined : checks[key](changes[key])
    if (value === undefined || JSON.stringify(value) === JSON.stringify(DEFAULTS[key])) delete raw[key]
    else raw[key] = value
  }
  await $.fs.write(path, JSON.stringify(raw, null, 2))
}

const sessionFile = async ($: EngineInterface) => {
  const dir = await stateDir($)
  if (!dir) return undefined
  const kept = await read($, keyState).catch(() => '')
  if (!kept) {
    // `$.state` is the conversation's: a /clear starts it empty, and only this
    // module still knows the key. Handed on, so the next reload finds it, and
    // the choice to show or hide with it.
    if (sessionKey && view.at) await update($, viewState, () => view).catch(() => {})
    if (sessionCharacter) await update($, characterState, () => sessionCharacter!).catch(() => {})
    sessionKey ??= await $.session.id()
    await update($, keyState, () => sessionKey!).catch(() => {})
  }
  sessionKey ??= kept
  return `${dir}/sessions/${sessionKey}.json`
}

const writeFile = async ($: EngineInterface) => {
  if (isEnded) return
  try {
    const path = await sessionFile($)
    const file: MascotSessionFile = {
      frame: frameNow,
      info: card,
      visible: view.visible,
      visibleAt: view.at,
      cleared: clearedAt,
      character: characterNow,
      update: release,
      call,
    }
    if (path) await $.fs.write(path, JSON.stringify(file))
  } catch {
    // The overlay keeps what it last read.
  }
}

const branchOf = async ($: EngineInterface, root: string) => {
  const head = (await $.fs.read(`${root}/.git/HEAD`)).trim()
  return head.startsWith('ref: refs/heads/') ? head.slice('ref: refs/heads/'.length) : head.slice(0, 7)
}

const quiet = <T,>(p: Promise<T>) => p.catch(() => undefined)

const projectOf = (root: string) => root.split(/[\\/]/).filter(Boolean).pop()

// Gathers the card's figures and writes them. Each is optional: one the
// engine will not give leaves the rest standing.
const refreshCard = async ($: EngineInterface) => {
  try {
    const now = await $.clock.now()
    if (now - live.compactCheckedAt > COMPACT_CHECK_MS) {
      live.compactCheckedAt = now
      // `summary` estimates locally: no token-count requests.
      const full = await quiet($.session.usage({ breakdown: 'summary' }))
      live.compactAt = full?.context.breakdown?.autoCompactThreshold ?? live.compactAt
    }
    const [usage, model, prompts, root, sessionId] = await Promise.all([
      quiet($.session.usage()),
      quiet($.session.model()),
      quiet($.session.turns()),
      quiet($.session.root()),
      quiet($.session.id()),
    ])
    const branch = root ? await quiet(branchOf($, root)) : undefined
    const window = usage?.context.window
    const tokens = usage?.context.tokens
    const first = live.history[0]
    const last = live.history[live.history.length - 1]
    const perTurn =
      first !== undefined && last !== undefined && last > first
        ? Math.round((last - first) / (live.history.length - 1))
        : undefined
    card = {
      sessionId,
      project: root ? projectOf(root) : undefined,
      branch,
      model,
      startedAt: usage?.startedAt,
      prompts,
      context: window
        ? {
            tokens,
            window,
            percent: usage?.context.percent,
            perTurn,
            turnsToCompact:
              perTurn && tokens !== undefined && live.compactAt
                ? Math.max(0, Math.ceil((live.compactAt - tokens) / perTurn))
                : undefined,
          }
        : undefined,
      limits: (usage?.rateLimits ?? []).map(l => ({ kind: l.kind, percent: l.percentUsed, resetsAt: l.resetsAt })),
      tool: live.tool,
      turnSince: live.turnSince,
      subagents: [...live.subagents.values()].map(a => ({
        type: a.type,
        tokens: a.tokens,
        // Only a subagent on the main loop's model shares its window.
        percent:
          a.tokens !== undefined && window && a.model !== undefined && a.model === live.mainModel
            ? Math.round((a.tokens / window) * 100)
            : undefined,
      })),
      background: live.background,
      newVersion: release?.latest,
    }
    await writeFile($)
  } catch {
    // A mascot never gets in the way of the session.
  }
}

// Refreshes the card shortly, once for a burst of events.
const refreshSoon = ($: EngineInterface) => {
  if (isRefreshPending) return
  isRefreshPending = true
  $.clock.after(REFRESH_DELAY_MS, () => {
    isRefreshPending = false
    void refreshCard($)
  })
}

const publish = async ($: EngineInterface, frame: MascotFrame) => {
  frameNow = frame
  await writeFile($)
  sleepTimer?.cancel()
  sleepTimer = frame === 'idle' ? $.clock.after(SLEEP_MS, () => void doze($)) : undefined
}

const doze = async ($: EngineInterface) => {
  try {
    const cur = await update($, mood, (cur): MascotMood =>
      cur.frame === 'idle' && cur.holdUntil === 0 ? { frame: 'sleepy', holdUntil: 0, then: 'sleepy' } : cur,
    )
    if (cur.frame === 'sleepy') await publish($, 'sleepy')
  } catch {
    // A mascot never gets in the way of the session.
  }
}

// This session's character: its own pick, else the project's, when its art
// is there; else the default.
const characterFor = async ($: EngineInterface) => {
  sessionCharacter ??= (await read($, characterState).catch(() => '')) || undefined
  const root = await quiet($.session.root())
  const chosen = (await quiet($.store.get(CHARACTERS_KEY))) as Record<string, string> | undefined
  for (const name of [sessionCharacter, root ? chosen?.[projectOf(root) ?? ''] : undefined]) {
    if (name && (await quiet($.fs.exists(`${$.plugin.root}/frames/${name}`)))) return name
  }
  return DEFAULT_CHARACTER
}

// What the character calls her beam (her theme's `beam`).
const beamName = async ($: EngineInterface) => {
  try {
    const theme = JSON.parse(await $.fs.read(`${$.plugin.root}/frames/${await characterFor($)}/theme.json`))
    if (typeof theme?.beam === 'string' && theme.beam.trim()) return theme.beam.trim()
  } catch {
    // Miku's, below.
  }
  return 'Miku Miku Beam'
}

// Characters with art: the folders under frames/.
const characters = async ($: EngineInterface) =>
  ((await quiet($.fs.list(`${$.plugin.root}/frames`))) ?? []).filter(e => e.kind === 'dir').map(e => e.name).sort()

// A program by its full path. Looked up by name, a pythonw under the
// session's folder is refused as unsafe, and a session started in the home
// folder holds the Store's (AppData\Local\Microsoft\WindowsApps). `where`
// searches PATH alone ($PATH:), not the current folder, so a repo still cannot
// plant one. An .exe before a script (npm's claude.cmd), and by name where
// there is no `where`.
const paths = new Map<string, string>()
const fullPath = async ($: EngineInterface, name: string) => {
  const known = paths.get(name)
  if (known) return known
  const found = await quiet($.process.run(['where', `$PATH:${name}`]))
  const lines = found?.exitCode === 0 ? found.stdout.split(/\r?\n/).map(l => l.trim()).filter(Boolean) : []
  const path = lines.find(l => /\.exe$/i.test(l)) ?? lines[0] ?? name
  paths.set(name, path)
  return path
}

const pythonw = ($: EngineInterface) => fullPath($, 'pythonw')

// A command's argv: a script (.cmd, .bat) runs through cmd.exe.
const commandLine = async ($: EngineInterface, name: string, ...args: string[]) => {
  const path = await fullPath($, name)
  return /\.(cmd|bat)$/i.test(path) ? ['cmd.exe', '/d', '/c', path, ...args] : [path, ...args]
}

// ---- updates

type Route = { route: MascotUpdate['route']; marketplace?: string; repo?: string }

// Versions compare part by part, as numbers: 0.14.10 is newer than 0.14.9.
const isVersion = (v: unknown): v is string => typeof v === 'string' && /^\d+(\.\d+){1,3}$/.test(v)
const isNewer = (a: string, b: string) => {
  const pa = a.split('.').map(Number)
  const pb = b.split('.').map(Number)
  for (let i = 0; i < Math.max(pa.length, pb.length); i++) {
    if ((pa[i] ?? 0) !== (pb[i] ?? 0)) return (pa[i] ?? 0) > (pb[i] ?? 0)
  }
  return false
}

const versionIn = (manifest: string) => {
  const data = JSON.parse(manifest) as { version?: unknown } | null
  return isVersion(data?.version) ? data.version : undefined
}

// How this copy updates: a marketplace install lives in Claude Code's plugin
// cache (`plugins/cache/<marketplace>/<plugin>/<version>`), a clone in a git
// work tree (the folder holding this one); else by hand.
const routeOf = async ($: EngineInterface): Promise<Route> => {
  const parts = $.plugin.root.split(/[\\/]/).filter(Boolean)
  const at = parts.lastIndexOf('cache')
  if (at > 0 && parts[at - 1] === 'plugins' && parts[at + 1]) return { route: 'marketplace', marketplace: parts[at + 1] }
  const repo = $.plugin.root.replace(/[\\/][^\\/]+[\\/]?$/, '')
  if (repo && (await quiet($.fs.exists(`${repo}/.git`)))) return { route: 'clone', repo }
  return { route: 'manual' }
}

// What's new in each version, shipped with the mod (whatsnew.json:
// { "0.17.0": ["a line", { "text": "a line", "kind": "fix" }] }): a line is
// news unless marked a fix. The settings window reads it by the same rules
// (`notes_between` in overlay/settings_window.py): keep them in step.
type News = { version: string; text: string; isFix: boolean }

const newsOf = (version: string, line: unknown): News[] => {
  if (typeof line === 'string') return line.trim() ? [{ version, text: line, isFix: false }] : []
  if (!line || typeof line !== 'object') return []
  const { text, kind } = line as { text?: unknown; kind?: unknown }
  return typeof text === 'string' && text.trim() ? [{ version, text, isFix: kind === 'fix' }] : []
}

// The lines of the versions after `from` (every one without), up to `to`,
// newest first.
const notesBetween = async ($: EngineInterface, from: string | undefined, to: string): Promise<News[]> => {
  try {
    const all = JSON.parse(await $.fs.read(`${$.plugin.root}/whatsnew.json`)) as Record<string, unknown>
    return Object.keys(all)
      .filter(v => isVersion(v) && (from === undefined || isNewer(v, from)) && !isNewer(v, to))
      .sort((a, b) => (isNewer(a, b) ? -1 : 1))
      .flatMap(v => (Array.isArray(all[v]) ? (all[v] as unknown[]) : []).flatMap(line => newsOf(v, line)))
  } catch {
    return []
  }
}

// The line to lead with: the newest that is not a fix, else the newest.
const headline = (news: News[]) => news.find(n => !n.isFix) ?? news[0]

// /mascot news: what is new since the version before (else in this one), or
// in `every` version, by version, newest first.
const newsText = async ($: EngineInterface, every: boolean) => {
  if (!release) return 'Mascot: its version is unknown.'
  const { version, from } = release
  const all = await notesBetween($, every ? undefined : from, version)
  const news = every || from ? all : all.filter(n => n.version === version)
  if (news.length === 0) return `Nothing written down for v${version}. /mascot news all lists every version.`
  const title = every ? 'Every version, newest first' : from ? `New since v${from}` : `New in v${version}`
  const lines: string[] = [`${title}:`]
  for (const [i, n] of news.entries()) {
    if (n.version !== news[i - 1]?.version) lines.push(`v${n.version}`)
    lines.push(`  - ${n.isFix ? 'Fix: ' : ''}${n.text}`)
  }
  if (!every) lines.push('/mascot news all lists every version.')
  return lines.join('\n')
}

const setRelease = async ($: EngineInterface, changes: Partial<MascotUpdate>) => {
  if (!release) return
  release = { ...release, ...changes }
  if (card) card = { ...card, newVersion: release.latest }
  await writeFile($)
}

// Her version, and whether it is newer than the last one run: then her
// banner (the overlay plays it once), a happy moment and what's new.
const startRelease = async ($: EngineInterface) => {
  try {
    const version = versionIn(await $.fs.read(`${$.plugin.root}/.claude-plugin/plugin.json`))
    if (!version) return
    updater = await routeOf($)
    const last = await quiet($.store.get(VERSION_KEY))
    const seen = (await quiet($.store.get(LATEST_KEY))) as { version?: unknown } | undefined
    const latest = isVersion(seen?.version) && isNewer(seen.version, version) ? seen.version : undefined
    release = { version, route: updater.route, latest }
    const upgrade = (await quiet($.store.get(UPGRADE_KEY))) as { from?: unknown; to?: unknown } | undefined
    if (upgrade?.to === version && isVersion(upgrade.from)) release.from = upgrade.from
    if (!isVersion(last) || isNewer(version, last)) await $.store.set(VERSION_KEY, version)
    if (isVersion(last) && isNewer(version, last)) {
      release.celebrate = await $.clock.now()
      release.from = last
      await $.store.set(UPGRADE_KEY, { from: last, to: version })
      // One line, the one worth telling, and how to read the rest.
      const news = await notesBetween($, last, version)
      const lead = headline(news)
      const more = news.length - (lead ? 1 : 0)
      $.ui.toast(
        `Mascot updated to v${version}${lead ? `: ${lead.text}` : ''}${more > 0 ? ` (+${more} more: /mascot news)` : ''}`,
      )
      const { frame } = await read($, mood)
      if (frame === 'idle' || frame === 'sleepy') await show($, 'happy', { holdMs: CELEBRATE_MS, after: 'idle' })
    }
    await writeFile($)
    void checkForUpdates($)
  } catch {
    // A mascot never gets in the way of the session.
  }
}

// Reads the newest release's version, once a day while `checkUpdates` is on
// (`force`: now, asked for), and keeps what it found for every session.
const checkForUpdates = async ($: EngineInterface, force = false) => {
  if (!release || isChecking) return
  isChecking = true
  try {
    if (!force && !(await loadSettings($)).checkUpdates) return
    const now = await $.clock.now()
    const seen = (await quiet($.store.get(LATEST_KEY))) as { at?: unknown; version?: unknown } | undefined
    let latest = isVersion(seen?.version) ? seen.version : undefined
    if (force || typeof seen?.at !== 'number' || now - seen.at >= CHECK_EVERY_MS) {
      const answer = await $.http.fetch(LATEST_URL)
      latest = answer.ok ? versionIn(answer.text) : undefined
      if (latest) await $.store.set(LATEST_KEY, { at: now, version: latest })
    }
    const newer = latest && isNewer(latest, release.version) ? latest : undefined
    if (newer !== release.latest) await setRelease($, { latest: newer })
  } catch {
    // Offline, or the release unreadable: try again tomorrow.
  } finally {
    isChecking = false
  }
}

// Updates this copy as it was installed: `claude plugin update` for a
// marketplace install, `git pull --ff-only` for a clone. The new version
// loads with /reload-plugins or the next session (a clone's files changing
// may reload it at once); her banner greets it. Says how it went.
const runUpdate = async ($: EngineInterface): Promise<string> => {
  if (!release) return 'Mascot: its version is unknown, so it cannot update itself.'
  if (isUpdating) return 'Mascot: already updating.'
  if (updater.route === 'manual') {
    return 'Mascot: this copy came from neither the marketplace nor a git clone; update it by hand (github.com/desuqcafe/cc-mascot).'
  }
  isUpdating = true
  await setRelease($, { state: 'updating', message: undefined })
  try {
    if (updater.route === 'marketplace') {
      // Its catalog first, so the update sees the newest release.
      await quiet($.process.run(await commandLine($, 'claude', 'plugin', 'marketplace', 'update', updater.marketplace!), {
        timeoutMs: UPDATE_TIMEOUT_MS,
      }))
    }
    const argv =
      updater.route === 'marketplace'
        ? await commandLine($, 'claude', 'plugin', 'update', `${$.plugin.name}@${updater.marketplace}`)
        : await commandLine($, 'git', '-C', updater.repo!, 'pull', '--ff-only')
    const done = await $.process.run(argv, { timeoutMs: UPDATE_TIMEOUT_MS })
    const said = (done.stdout + '\n' + done.stderr).trim().split(/\r?\n/).filter(l => l.trim())
    if (done.exitCode !== 0) throw new Error(said.pop() ?? `exit code ${done.exitCode}`)
    if (said.some(l => /already (up to date|at the latest)/i.test(l))) {
      await setRelease($, { state: undefined, latest: undefined })
      return `Mascot v${release.version} is the latest.`
    }
    const message =
      updater.route === 'marketplace'
        ? 'Type /reload-plugins to meet her new version (or start a new session).'
        : 'Pulled. She reloads by herself; if not, type /reload-plugins.'
    await setRelease($, { state: 'updated', message })
    return `Mascot updated. ${message}`
  } catch (err) {
    const message = (err instanceof Error ? err.message : String(err)).trim()
    await setRelease($, { state: 'failed', message })
    return `Mascot update failed: ${message}`
  } finally {
    isUpdating = false
  }
}

// Runs an update and says how it went in a toast: the prompt stays free.
const updateInBackground = ($: EngineInterface) => {
  void runUpdate($).then(text => $.ui.toast(text)).catch(() => {})
}

// Starts this session's overlay, which shows or hides itself as `view` says.
// It reports on stdout what is chosen in its own window: `hidden` (right-click).
const startOverlay = async ($: EngineInterface): Promise<string | undefined> => {
  if (overlay || isEnded) return undefined
  const path = await sessionFile($).catch(() => undefined)
  if (!path) return 'Mascot overlay: no home folder to keep its files in.'
  characterNow = await characterFor($)
  await publish($, (await read($, mood)).frame)
  const frames = `${$.plugin.root}/frames/${characterNow}`
  const child = $.process.spawn({ argv: [await pythonw($), `${$.plugin.root}/overlay/mascot_overlay.py`, frames, path] })
  let isStopping = false
  let ended: () => void = () => {}
  const exited = new Promise<void>(resolve => (ended = resolve))
  const self = {
    isEnding: false,
    stop: async () => {
      isStopping = true
      if (overlay === self) overlay = undefined
      void child.return(undefined as never)
      await Promise.race([exited, new Promise<void>(resolve => $.clock.after(STOP_WAIT_MS, resolve))])
    },
  }
  overlay = self
  void (async () => {
    let failure = ''
    let pending = ''
    try {
      for await (const { stream, text } of child) {
        if (stream === 'stderr') {
          failure += text
          continue
        }
        pending += text
        const lines = pending.split('\n')
        pending = lines.pop() ?? ''
        for (const line of lines) if (line.trim() === 'hidden') await setVisible($, false)
      }
    } catch (err) {
      failure = String(err)
    }
    if (overlay === self) overlay = undefined
    ended()
    if (isStopping || self.isEnding) return
    // It could not start, or it broke; `/mascot show` starts it again.
    const reason = failure.trim().split('\n').pop()
    if (reason && view.visible) $.ui.toast(`Mascot overlay stopped: ${reason}`)
  })()
  return undefined
}

// Opens the settings window (overlay/settings_window.py), in the colors of
// this session's character; one already open for this session comes forward
// instead (one open for another hands over to this one). It edits
// settings.json, which every overlay follows, and on its stdout picks this
// session's character (`character NAME remember|session`), asks for a check
// for a newer release (`check`, as its toggle turns the check on) or for the
// update (`update`).
const openSettingsWindow = async ($: EngineInterface): Promise<string | undefined> => {
  const dir = await stateDir($)
  const path = await sessionFile($).catch(() => undefined)
  if (!dir || !path) return 'Mascot: no home folder to keep its settings in.'
  const frames = `${$.plugin.root}/frames/${await characterFor($)}`
  const root = await quiet($.session.root())
  const project = (root && projectOf(root)) || ''
  const child = $.process.spawn({
    argv: [await pythonw($), `${$.plugin.root}/overlay/settings_window.py`, dir, frames, sessionKey!, project],
  })
  void (async () => {
    let failure = ''
    let pending = ''
    try {
      for await (const { stream, text } of child) {
        if (stream === 'stderr') {
          failure += text
          continue
        }
        pending += text
        const lines = pending.split('\n')
        pending = lines.pop() ?? ''
        for (const line of lines) {
          const [verb, name = '', how] = line.trim().split(/\s+/)
          if (verb === 'character' && (await characters($)).includes(name)) {
            await setCharacter($, name, how !== 'session').catch(() => {})
          } else if (verb === 'check') {
            void checkForUpdates($, true)
          } else if (verb === 'update') {
            updateInBackground($)
          } else if (verb === 'magic') {
            await sendMagic($, true)
          }
        }
      }
    } catch (err) {
      failure = String(err)
    }
    const reason = failure.trim().split('\n').pop()
    if (reason) $.ui.toast(`Mascot settings window: ${reason}`)
  })()
  return undefined
}

// Shows or hides this session's mascot, and makes that the default for the
// sessions that start next.
const setVisible = async ($: EngineInterface, visible: boolean) => {
  view = { visible, at: await $.clock.now() }
  await update($, viewState, () => view).catch(() => {})
  await writeFile($)
  await $.store.set(OVERLAY_KEY, visible).catch(() => {})
  return visible ? startOverlay($) : undefined
}

// Shows or hides every session's mascot: each overlay reads all.json beside
// its own file and follows whichever was chosen last.
const setAllVisible = async ($: EngineInterface, visible: boolean) => {
  const dir = await stateDir($)
  if (!dir) return 'Mascot overlay: no home folder to keep its files in.'
  const all: MascotVisibility = { visible, at: await $.clock.now() }
  await $.fs.write(`${dir}/all.json`, JSON.stringify(all))
  return setVisible($, visible)
}

// Picks the character for this project's sessions (`remember`), or for this
// session alone. This one's overlay takes it on where it stands (its outro,
// then the new character's intro); other sessions of the project take a
// remembered one when they next start.
const setCharacter = async ($: EngineInterface, name: string, remember = true) => {
  const root = await quiet($.session.root())
  const project = root ? projectOf(root) : undefined
  if (remember) {
    if (!project) return 'Mascot: this session has no project folder to pick a character for.'
    const chosen = ((await quiet($.store.get(CHARACTERS_KEY))) ?? {}) as Record<string, string>
    await $.store.set(CHARACTERS_KEY, { ...chosen, [project]: name })
  }
  sessionCharacter = remember ? undefined : name
  await update($, characterState, () => sessionCharacter ?? '').catch(() => {})
  characterNow = name
  await writeFile($)
  const problem = await startOverlay($)
  return problem ?? (remember ? `Mascot: ${project} now shows ${name}.` : `Mascot: this session shows ${name}.`)
}

// Shows `frame`. `force` replaces whatever is held; otherwise a held frame
// stays up and `frame` follows when the hold ends. `holdMs` holds the new
// frame, then moves to `after`.
const show = async (
  $: EngineInterface,
  frame: MascotFrame,
  opts: { force?: boolean; holdMs?: number; after?: MascotFrame } = {},
) => {
  try {
    const now = await $.clock.now()
    const next = await update($, mood, cur => {
      if (opts.holdMs) return { frame, holdUntil: now + opts.holdMs, then: opts.after ?? 'idle' }
      if (!opts.force && cur.holdUntil > now) return { ...cur, then: frame }
      return { frame, holdUntil: 0, then: frame }
    })
    // Called at every step of the main loop and every tool call (subagents'
    // too): a frame she already shows is not written again (the card's
    // refresh keeps the file fresh).
    if (next.frame !== frameNow) await publish($, next.frame)
    if (opts.holdMs) {
      const until = next.holdUntil
      $.clock.after(opts.holdMs, () => {
        void update($, mood, cur =>
          cur.holdUntil === until ? { frame: cur.then, holdUntil: 0, then: cur.then } : cur,
        )
          .then(cur => publish($, cur.frame))
          .catch(() => {})
      })
    }
  } catch {
    // A mascot never gets in the way of the session.
  }
}

// Called whenever a round of work may have ended. Happy (the beam, for a
// big round) only once the main turn is over and no subagent, background
// agent or other work it waits on is left: an orchestrator that ends its
// turn to wait on its agents or a build is not done yet.
const settle = async ($: EngineInterface) => {
  try {
    const w = await read($, work)
    if (w.inTurn) return
    if (w.agents.length > 0 || w.hasBackground) {
      await show($, 'working', { force: true })
      return
    }
    if (w.isSettled) return
    const now = await $.clock.now()
    if (w.waitUntil > now) {
      await show($, 'working', { force: true })
      $.clock.after(w.waitUntil - now, () => void settle($))
      return
    }
    await update($, work, cur => ({ ...cur, isSettled: true }))
    if (w.waitUntil > 0) {
      // What it waited on outlasted WAIT_CAP_MS: done or not, nobody knows.
      round = newRound()
      await show($, 'idle', { force: true })
      return
    }
    const { beamAfter, beamForAgents, magicAfter } = await loadSettings($)
    const lasted = (minutes: number | false) =>
      minutes !== false && round.since !== undefined && now - round.since >= minutes * 60_000
    const isBig = (beamForAgents && round.hadAgents) || lasted(beamAfter)
    if (lasted(magicAfter)) call = { at: now }
    round = newRound()
    await show($, isBig ? 'beam' : 'happy', { holdMs: isBig ? BEAM_MS : HOLD_MS, after: 'idle' })
  } catch {
    // A mascot never gets in the way of the session.
  }
}

// Sends her call to the pointer now (/mascot magic, the settings window's
// button): a test, so the overlay sends it even over a fullscreen game.
const sendMagic = async ($: EngineInterface, test = false) => {
  call = { at: await $.clock.now(), ...(test ? { test: true as const } : {}) }
  await writeFile($)
}

// The turn died on an error (an API error past its retries, a refusal).
const fail = async ($: EngineInterface) => {
  await update($, work, cur => ({ ...cur, inTurn: false, isSettled: true })).catch(() => {})
  await show($, 'error', { holdMs: HOLD_MS, after: 'idle' })
}

// 300000 as 300k, 1200000 as 1.2M.
const fmtTokens = (n: number) =>
  n >= 1_000_000 ? `${+(n / 1_000_000).toFixed(2)}M` : n >= 1000 ? `${+(n / 1000).toFixed(1)}k` : `${n}`

// 300k, 1.2m or 300000 as a number of tokens.
const parseTokens = (text: string) => {
  const match = /^(\d+(?:\.\d+)?)([km]?)$/.exec(text)
  return match ? Number(match[1]) * (match[2] === 'm' ? 1_000_000 : match[2] === 'k' ? 1000 : 1) : NaN
}

const describe = {
  size: (s: Settings) => {
    const name = Object.keys(SIZES).find(k => SIZES[k] === s.size)
    return `Size: ${s.size} px${name ? ` (${name})` : ''}.`
  },
  calm: (s: Settings) =>
    s.calm ? 'Calm mode on: no glitch, particles, flicker or flashes.' : 'Calm mode off.',
  smooth: (s: Settings) =>
    s.smooth
      ? 'Smooth sparkles on: her sparkles move as smoothly as her symbols (heavier while she works).'
      : 'Smooth sparkles off: her sparkles move in step with her drawn frames.',
  aura: (s: Settings) =>
    s.aura === false ? 'Aura off.' : `Aura from ${s.aura.map(fmtTokens).join(', ')} tokens of context.`,
  beamAfter: (s: Settings) =>
    s.beamAfter === false
      ? 'Long rounds of work do not end in the beam.'
      : `Rounds of work of ${s.beamAfter} min or more end in the beam.`,
  beamForAgents: (s: Settings) =>
    s.beamForAgents
      ? 'Rounds with subagents or background agents end in the beam.'
      : 'Rounds with subagents or background agents end in the beam only when long.',
  magicAfter: (s: Settings) =>
    s.magicAfter === false
      ? 'No cursor magic.'
      : `Rounds of work of ${s.magicAfter} min or more send magic to your pointer.`,
  checkUpdates: (s: Settings) =>
    s.checkUpdates ? 'Looks for a new version once a day.' : 'Never goes online to look for a new version.',
}

const settingsSummary = (s: Settings) => Object.values(describe).map(line => line(s)).join(' ')

// `/mascot <verb> ...` for a setting: its value with nothing after the verb;
// undefined when the words are not a settings command at all.
const settingsCommand = async ($: EngineInterface, words: string[]): Promise<string | undefined> => {
  const [verb, ...rest] = words
  const set = async <K extends keyof Settings>(key: K, value: Settings[K] | null) => {
    await saveSettings($, { [key]: value })
    return describe[key](await loadSettings($))
  }
  const now = async (key: keyof Settings) => describe[key](await loadSettings($))
  const [value, extra] = rest
  if (verb === 'size' && !extra) {
    if (!value) return `${await now('size')} /mascot size small, normal, large or 240 to 640 (px).`
    if (value === 'default') return set('size', null)
    const px = SIZES[value] ?? Number(value.replace(/px$/, ''))
    if (!checks.size(px)) return 'Size takes small, normal, large, default or 240 to 640 (px).'
    return set('size', px)
  }
  if (verb === 'calm' && !extra) {
    if (!value) return `${await now('calm')} /mascot calm on|off.`
    if (value !== 'on' && value !== 'off') return 'Calm takes on or off.'
    return set('calm', value === 'on')
  }
  if (verb === 'smooth' && !extra) {
    if (!value) return `${await now('smooth')} /mascot smooth on|off.`
    if (value !== 'on' && value !== 'off') return 'Smooth takes on or off.'
    return set('smooth', value === 'on')
  }
  if (verb === 'aura') {
    if (!value) return `${await now('aura')} /mascot aura <3 token counts, as 300k 400k 500k>|off|default.`
    if (rest.length === 1 && (value === 'off' || value === 'default')) return set('aura', value === 'off' ? false : null)
    const tiers = checks.aura(rest.map(parseTokens))
    if (!tiers) return 'Aura takes three token counts going up (as 300k 400k 500k, 10k to 10M), off or default.'
    return set('aura', tiers)
  }
  if (verb === 'beam' && value === 'after' && rest.length <= 2) {
    const [, minutes] = rest
    if (!minutes) return `${await now('beamAfter')} /mascot beam after <minutes>|never|default.`
    if (minutes === 'never' || minutes === 'default') return set('beamAfter', minutes === 'never' ? false : null)
    const n = Number(minutes.replace(/m(in)?$/, ''))
    if (checks.beamAfter(n) === undefined) return 'Beam after takes minutes (1 to 120), never or default.'
    return set('beamAfter', n)
  }
  if (verb === 'beam' && value === 'agents' && rest.length <= 2) {
    const [, on] = rest
    if (!on) return `${await now('beamForAgents')} /mascot beam agents on|off.`
    if (on !== 'on' && on !== 'off') return 'Beam agents takes on or off.'
    return set('beamForAgents', on === 'on')
  }
  if (verb === 'magic' && value === 'after' && rest.length <= 2) {
    const [, minutes] = rest
    if (!minutes) return `${await now('magicAfter')} /mascot magic after <minutes>|never|default.`
    if (minutes === 'never' || minutes === 'default') return set('magicAfter', null)
    const n = Number(minutes.replace(/m(in)?$/, ''))
    if (checks.magicAfter(n) === undefined) return 'Magic after takes minutes (0 to 120), never or default.'
    return set('magicAfter', n)
  }
  if (verb === 'updates' && !extra) {
    const about = release
      ? `Mascot v${release.version}${release.latest ? `; v${release.latest} is out: /mascot update` : ''}.`
      : ''
    if (!value) return `${about} ${await now('checkUpdates')} /mascot updates on|off.`.trim()
    if (value !== 'on' && value !== 'off') return 'Updates takes on or off.'
    const answer = await set('checkUpdates', value === 'on')
    if (value === 'on') void checkForUpdates($, true)
    return answer
  }
  if (verb === 'settings' && !value) {
    const problem = await openSettingsWindow($)
    return `${problem ?? 'Settings window opened.'} ${settingsSummary(await loadSettings($))}`
  }
  if (verb === 'reset' && !value) {
    await saveSettings($, {
      size: null,
      calm: null,
      smooth: null,
      aura: null,
      beamAfter: null,
      beamForAgents: null,
      magicAfter: null,
      checkUpdates: null,
    })
    return `Settings back to their defaults. ${settingsSummary(DEFAULTS)}`
  }
  return undefined
}

// A /clear or /resume: the conversation the figures and moods followed is gone.
const startOver = async ($: EngineInterface) => {
  clearedAt = await quiet($.clock.now())
  live.tool = undefined
  live.turnSince = undefined
  live.subagents.clear()
  live.background = {}
  live.history = []
  round = newRound()
  await update($, work, () => ({ inTurn: false, agents: [], hasBackground: false, waitUntil: 0, isSettled: true })).catch(
    () => {},
  )
  await show($, 'idle', { force: true })
  refreshSoon($)
}

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    await $.command.register({
      name: 'mascot',
      description:
        "Show or hide this session's mascot (or every session's), pick its character, fire her beam, send magic to your pointer, update her, see what is new, or change her settings",
      argumentHint:
        '[show|hide] [all] | character [name] | beam | magic | update | news [all] | settings | size | calm | smooth | aura | beam after | magic after | updates | reset',
      immediate: true,
    })
    // A reload keeps this session's choice; a new session takes the last one
    // made. The overlay always runs, hidden or not, so `/mascot show all`
    // from another session reaches it.
    const kept = await read($, viewState).catch(() => undefined)
    view = kept?.at ? kept : { visible: (await quiet($.store.get(OVERLAY_KEY))) === true, at: await $.clock.now() }
    await startRelease($)
    void startOverlay($).catch(() => {}).catch(() => {})
    $.clock.every(REFRESH_EVERY_MS, () => {
      void refreshCard($)
      void checkForUpdates($)
    })
    refreshSoon($)

    return next(e)
  })

  on('command.run', { command: 'mascot' }, async ($, e) => {
    const words = e.args.trim().toLowerCase().split(/\s+/).filter(Boolean)
    const [verb = '', target = '', extra] = words
    const help =
      'Usage: /mascot [show|hide] [all] toggles, shows or hides this session\'s mascot (or every session\'s); ' +
      '/mascot character [name] lists or picks the character for this project; /mascot beam fires her beam; ' +
      '/mascot magic sends magic to your pointer; ' +
      '/mascot update updates her to the newest version; /mascot news says what is new (news all: every version). ' +
      'Settings, for every mascot: /mascot settings; size [small|normal|large|<px>]; calm [on|off]; smooth [on|off]; ' +
      'aura [<3 token counts>|off]; beam after [<minutes>|never]; beam agents [on|off]; ' +
      'magic after [<minutes>|never]; updates [on|off]; reset.'
    try {
      const answer = await settingsCommand($, words)
      if (answer !== undefined) return { text: answer }
    } catch (err) {
      return { text: `Mascot settings: ${err instanceof Error ? err.message : String(err)}` }
    }
    if (verb === 'beam' && !target) {
      // Her big finish on demand, then back to what she was doing.
      const now = await $.clock.now()
      const cur = await read($, mood)
      const back = cur.holdUntil > now ? cur.then : cur.frame
      await show($, 'beam', { holdMs: BEAM_MS, after: back === 'beam' ? 'idle' : back })
      const call = `${await beamName($)}!`
      return { text: view.visible ? call : `${call} (She is hidden: /mascot show to see it.)` }
    }
    if (verb === 'magic' && !target) {
      // Her call, to try it: it goes to the pointer as soon as it shows.
      await sendMagic($, true)
      return { text: 'Magic sent to your pointer!' }
    }
    if (verb === 'update' && !target) {
      if (!release) return { text: 'Mascot: its version is unknown, so it cannot update itself.' }
      if (updater.route === 'manual' || isUpdating) return { text: await runUpdate($) }
      updateInBackground($)
      return { text: `Updating the mascot (v${release.version})... she will say when it is done.` }
    }
    if (verb === 'news' && ['', 'all'].includes(target) && !extra) {
      return { text: await newsText($, target === 'all') }
    }
    if (verb === 'character') {
      const names = await characters($)
      const current = await characterFor($)
      if (!target) return { text: `Characters: ${names.map(n => (n === current ? `${n} (shown)` : n)).join(', ')}.` }
      if (!names.includes(target)) return { text: `No art for "${target}". Characters: ${names.join(', ')}.` }
      return { text: await setCharacter($, target) }
    }
    if (extra || !['', 'show', 'hide'].includes(verb) || !['', 'all'].includes(target)) {
      return { text: help }
    }
    const visible = verb === '' ? !view.visible : verb === 'show'
    const problem = target === 'all' ? await setAllVisible($, visible) : await setVisible($, visible)
    if (problem) return { text: problem }
    if (target === 'all') return { text: visible ? "Every session's mascot shown." : "Every session's mascot hidden." }
    return {
      text: visible
        ? 'Mascot shown: drag to move, double-click to send it back to its spot, right-click to hide.'
        : 'Mascot hidden for this session; /mascot brings it back.',
    }
  })

  on('session.end', async ($, e, next) => {
    if (e.reason === 'clear' || e.reason === 'resume') {
      // The process goes on with a fresh conversation: same mascot, fresh card.
      await startOver($)
    } else {
      // Tells the overlay to clean up after itself and go; nothing writes after.
      if (overlay) overlay.isEnding = true
      isEnded = true
      sleepTimer?.cancel()
      const path = await sessionFile($).catch(() => undefined)
      const file: MascotSessionFile = { frame: frameNow, visible: false, visibleAt: view.at, ended: true }
      if (path) await $.fs.write(path, JSON.stringify(file)).catch(() => {})
    }
    return next(e)
  })

  on('turn.start', async ($, e, next) => {
    const before = await read($, work).catch(() => undefined)
    await update($, work, cur => ({ ...cur, inTurn: true, hasBackground: false, waitUntil: 0, isSettled: false })).catch(
      () => {},
    )
    live.turnSince = await quiet($.clock.now())
    // A prompt after everything settled starts a new round of work.
    if (!before || before.isSettled) round = newRound(live.turnSince)
    await show($, 'thinking', { force: true })
    refreshSoon($)
    return next(e)
  })

  // Each model request of the main loop: thinking while it streams, worried
  // when it has streamed nothing for STALL_MS. The engine's own items (a
  // retry marker among them) are not progress.
  on('turn.step', async function* ($, e, next) {
    if (e.agentId !== undefined) {
      const result = yield* next(e)
      // A subagent's context: what its last request was answered over.
      const agent = live.subagents.get(e.agentId)
      if (agent && result.usage) {
        const u = result.usage
        agent.tokens = u.input_tokens + u.cache_read_input_tokens + u.cache_creation_input_tokens
        agent.model = u.model
        refreshSoon($)
      }
      return result
    }
    await show($, 'thinking')
    let quietTicks = 0
    let isWorried = false
    const ticker = $.clock.every(STALL_TICK_MS, () => {
      quietTicks += 1
      if (!isWorried && quietTicks * STALL_TICK_MS >= STALL_MS) {
        isWorried = true
        void show($, 'worried')
      }
    })
    try {
      const stream = next(e)
      for await (const chunk of stream) {
        if (chunk.kind !== 'engine') {
          quietTicks = 0
          if (isWorried) {
            isWorried = false
            await show($, 'thinking')
          }
        }
        yield chunk
      }
      const result = await stream.result
      live.mainModel = result.usage?.model ?? live.mainModel
      return result
    } finally {
      ticker.cancel()
    }
  })

  on('tool.call', async ($, e, next) => {
    const isAsking = ASKING_TOOLS.includes(e.tool)
    await show($, isAsking ? 'waiting' : 'working', { force: isAsking })
    if (e.agentId === undefined) {
      live.tool = e.tool
      refreshSoon($)
    }
    const asksBefore = askCount
    const result = await next(e).finally(() => {
      if (e.agentId === undefined && live.tool === e.tool) live.tool = undefined
    })
    // Known from the call itself: a read of the mood here does not see what
    // the dialog's own event wrote while the call ran.
    const wasAsked = isAsking || asks.some(a => a.n > asksBefore && a.tool === e.tool)
    // A no from the person or the auto-mode classifier is not a failure.
    const wasRefused = wasAsked || denied.delete(e.tool_use_id)
    if (result.isError && !wasRefused) {
      // A subagent's tool failing while the main agent waits goes back to working.
      const { inTurn } = await read($, work).catch(() => ({ inTurn: true }))
      await show($, 'error', { holdMs: HOLD_MS, after: inTurn ? 'thinking' : 'working' })
    } else if (wasAsked) {
      await show($, 'working', { force: true })
    }
    return result
  })

  // A permission dialog is up: Claude waits on the person.
  on('classic.PermissionRequest', async ($, e, next) => {
    askCount += 1
    asks.push({ n: askCount, tool: e.tool_name })
    if (asks.length > 20) asks.shift()
    await show($, 'waiting', { force: true })
    const result = await next(e)
    // A settings hook answered it, so no dialog is shown.
    if (result.decision) await show($, 'working', { force: true })
    return result
  })

  on('classic.PermissionDenied', async ($, e, next) => {
    denied.add(e.tool_use_id)
    return next(e)
  })

  // An MCP server asks the person something.
  on('classic.Elicitation', async ($, e, next) => {
    await show($, 'waiting', { force: true })
    return next(e)
  })

  on('classic.ElicitationResult', async ($, e, next) => {
    await show($, 'working', { force: true })
    return next(e)
  })

  on('session.compact', async ($, e, next) => {
    // A precompute runs in the background and installs nothing.
    if (e.agentId !== undefined || e.trigger === 'precompute') return next(e)
    await show($, 'thinking', { force: true })
    const result = await next(e)
    const { inTurn } = await read($, work).catch(() => ({ inTurn: true }))
    if (!inTurn) await show($, 'idle', { force: true })
    live.history = []
    refreshSoon($)
    return result
  })

  on('turn.complete', async ($, e, next) => {
    if (e.agentId !== undefined) return next(e)
    await update($, work, cur => ({ ...cur, inTurn: false })).catch(() => {})
    live.turnSince = undefined
    live.tool = undefined
    const tokens = (await quiet($.session.usage()))?.context.tokens
    if (tokens !== undefined) {
      // A drop is a compaction: the old rate no longer applies.
      const last = live.history[live.history.length - 1]
      live.history = last !== undefined && tokens < last ? [tokens] : [...live.history, tokens].slice(-GROWTH_REPLIES)
    }
    refreshSoon($)
    if (e.isAborted) {
      await update($, work, cur => ({ ...cur, isSettled: true })).catch(() => {})
      await show($, 'idle', { force: true })
    } else if (e.reason === 'error' || e.reason === 'refusal') {
      await fail($)
    } else {
      await settle($)
    }
    return next(e)
  })

  // The main turn's end on an API error, as the settings hooks see it.
  on('classic.StopFailure', async ($, e, next) => {
    await fail($)
    return next(e)
  })

  // The main turn's end, as the settings hooks see it: it lists the
  // background work still in flight, and the wakeups to come.
  on('classic.Stop', async ($, e, next) => {
    const tasks = e.background_tasks ?? []
    const wakeups = e.session_crons ?? []
    inFlight = [...tasks.map(t => t.id), ...wakeups.map(c => c.id)]
    const hasBackground = tasks.some(t => AGENT_TASKS.includes(t.type))
    if (hasBackground) round.hadAgents = true
    const awaited = [
      ...tasks.filter(t => t.type === 'shell' && !isEndless(t.command ?? t.description)),
      ...wakeups.filter(c => !c.recurring),
    ].filter(t => !round.before.has(t.id))
    const now = await quiet($.clock.now())
    let waitUntil = 0
    for (const t of awaited) {
      if (!round.seen.has(t.id) && now !== undefined) round.seen.set(t.id, now)
      const seen = round.seen.get(t.id)
      if (seen !== undefined) waitUntil = Math.max(waitUntil, seen + WAIT_CAP_MS)
    }
    await update($, work, cur => ({ ...cur, hasBackground, waitUntil })).catch(() => {})
    // Subagents have a row of their own on the card.
    const counts: Record<string, number> = {}
    for (const t of tasks) if (t.type !== 'subagent') counts[t.type] = (counts[t.type] ?? 0) + 1
    live.background = counts
    refreshSoon($)
    await settle($)
    return next(e)
  })

  on('classic.SubagentStart', async ($, e, next) => {
    await update($, work, cur => ({
      ...cur,
      agents: cur.agents.includes(e.agent_id) ? cur.agents : [...cur.agents, e.agent_id],
    })).catch(() => {})
    if (!live.subagents.has(e.agent_id)) live.subagents.set(e.agent_id, { type: e.agent_type })
    round.hadAgents = true
    refreshSoon($)
    return next(e)
  })

  on('classic.SubagentStop', async ($, e, next) => {
    const w = await update($, work, cur => {
      const agents = cur.agents.filter(id => id !== e.agent_id)
      // The Stop's list of background work is stale once the last agent ends.
      return { ...cur, agents, hasBackground: agents.length > 0 && cur.hasBackground }
    }).catch(() => undefined)
    if (w && w.agents.length === 0 && !w.inTurn) $.clock.after(SETTLE_MS, () => void settle($))
    live.subagents.delete(e.agent_id)
    refreshSoon($)
    return next(e)
  })
}
