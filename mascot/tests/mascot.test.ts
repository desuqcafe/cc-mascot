import { expect, mock, test } from 'claude-code/testing'
import type { Engine } from 'claude-code/testing'
import type { On } from 'claude-code'

import type { MascotSessionFile, MascotSettings, MascotVisibility } from '../types'

const SETTINGS_PATH = /[\\/]\.claude[\\/]mascot[\\/]settings\.json$/

// Stands in for the disk: keeps what the mod writes to its session's file
// (sessions/<session id>.json), to all.json and to settings.json (`settings`
// starts it as if written by hand: an object, or text as it is); `read`
// answers for any other file.
const sessionFiles = (
  on: On,
  settings?: MascotSettings | Record<string, unknown> | string,
  read: (path: string) => string | undefined = () => undefined,
) => {
  const files: MascotSessionFile[] = []
  const everyone: MascotVisibility[] = []
  let settingsText = settings === undefined || typeof settings === 'string' ? settings : JSON.stringify(settings)
  mock.env(on, { USERPROFILE: 'C:/Users/test' })
  on('session.id', () => ({ value: 'sess-1' }))
  on('fs.write', (_$, e) => {
    // The engine hands the path over in the platform's own spelling.
    if (/[\\/]\.claude[\\/]mascot[\\/]sessions[\\/]sess-1\.json$/.test(e.path)) files.push(JSON.parse(e.text))
    if (/[\\/]\.claude[\\/]mascot[\\/]all\.json$/.test(e.path)) everyone.push(JSON.parse(e.text))
    if (SETTINGS_PATH.test(e.path)) settingsText = e.text
    return { value: undefined }
  })
  on('fs.read', (_$, e) => {
    const text = SETTINGS_PATH.test(e.path) ? settingsText : read(e.path)
    return text === undefined ? { deny: 'no such file' } : { value: text }
  })
  return {
    files,
    everyone,
    last: () => files[files.length - 1],
    settings: (): Record<string, unknown> | undefined => (settingsText === undefined ? undefined : JSON.parse(settingsText)),
  }
}

const moodFile = (on: On, settings?: MascotSettings | string) => {
  const { files } = sessionFiles(on, settings)
  return {
    last: () => files[files.length - 1]?.frame,
    get all() {
      return files.map(f => f.frame)
    },
  }
}

test('the mood follows turns and tool calls, holding error and happy for 3s', async ($, on) => {
  const clock = mock.clock(on, { now: 1_000 })
  const file = moodFile(on)
  let fail = false
  on('turn.start', (_$, e) => ({ turnId: e.turnId }))
  on('tool.call', () =>
    fail ? { isError: true as const, result: 'boom', text: 'boom' } : { result: 'ok', text: 'ok' },
  )
  on('turn.complete', () => ({ text: '' }))

  await $.turn.start({ text: 'hi', turnId: 't1' })
  expect(file.last()).toBe('thinking')

  const ok = await $.tool.call({ tool: 'Read', file_path: 'a.md' })
  expect(ok.isError).toBeUndefined()
  expect(file.last()).toBe('working')

  fail = true
  const bad = await $.tool.call({ tool: 'Read', file_path: 'b.md' })
  expect(bad.isError).toBe(true) // passed through untouched
  expect(file.last()).toBe('error')

  // A tool call during the hold does not cut it short.
  fail = false
  await $.tool.call({ tool: 'Read', file_path: 'c.md' })
  expect(file.last()).toBe('error')
  await clock.advance(2_999)
  expect(file.last()).toBe('error')
  await clock.advance(1)
  expect(file.last()).toBe('working')

  await $.turn.complete({ answer: 'done', durationMs: 5, isAborted: false, turnId: 't1', reason: 'answer' })
  expect(file.last()).toBe('happy')
  await clock.advance(3_000)
  expect(file.last()).toBe('idle')
})

test('a subagent finishing does not make the mascot happy', async ($, on) => {
  mock.clock(on)
  const file = moodFile(on)
  on('turn.start', (_$, e) => ({ turnId: e.turnId }))
  on('turn.complete', () => ({ text: '' }))

  await $.turn.start({ text: 'hi', turnId: 't1' })
  await $.turn.complete({
    answer: '',
    durationMs: 5,
    isAborted: false,
    turnId: 't2',
    reason: 'answer',
    agentId: 'sub-1',
  })
  expect(file.last()).toBe('thinking')
})

const turnBottoms = (on: On) => {
  on('turn.start', (_$, e) => ({ turnId: e.turnId }))
  on('turn.complete', () => ({ text: '' }))
  on('classic.Stop', () => ({}))
  on('classic.SubagentStart', () => ({}))
  on('classic.SubagentStop', () => ({}))
}
const ended = (turnId: string) =>
  ({ answer: '', durationMs: 5, isAborted: false, turnId, reason: 'answer' }) as const

test('an orchestrator waiting on its subagents is not happy until they finish', async ($, on) => {
  const clock = mock.clock(on)
  const file = moodFile(on)
  turnBottoms(on)

  await $.turn.start({ text: 'fan out', turnId: 't1' })
  await $.classic.SubagentStart({ agent_id: 'a1', agent_type: 'general-purpose' })
  await $.classic.SubagentStart({ agent_id: 'a2', agent_type: 'general-purpose' })
  await $.turn.complete(ended('t1'))
  await $.classic.Stop({ stop_hook_active: false, background_tasks: [] })
  expect(file.last()).toBe('working')
  expect(file.all).not.toContain('happy')

  await $.classic.SubagentStop({ agent_id: 'a1', agent_type: 'general-purpose', stop_hook_active: false, agent_transcript_path: '' })
  await clock.advance(5_000)
  expect(file.last()).toBe('working') // a2 still running

  // a2 ends; the orchestrator picks the results up in a new turn.
  await $.classic.SubagentStop({ agent_id: 'a2', agent_type: 'general-purpose', stop_hook_active: false, agent_transcript_path: '' })
  await $.turn.start({ text: '', turnId: 't2' })
  await clock.advance(2_000)
  expect(file.last()).toBe('thinking')
  expect(file.all).not.toContain('happy')

  await $.turn.complete(ended('t2'))
  expect(file.last()).toBe('beam') // a round with subagents: her big finish
})

test('background agent work listed at Stop also holds happy back', async ($, on) => {
  const clock = mock.clock(on)
  const file = moodFile(on)
  turnBottoms(on)

  await $.turn.start({ text: 'kick off', turnId: 't1' })
  await $.classic.Stop({
    stop_hook_active: false,
    background_tasks: [{ id: 'w1', type: 'workflow', status: 'running', description: 'review' }],
  })
  await $.turn.complete(ended('t1'))
  expect(file.last()).toBe('working')

  // A background shell (a dev server) is not agent work: done as usual,
  // with the beam, since the round had a workflow.
  await $.turn.start({ text: 'next', turnId: 't2' })
  await $.classic.Stop({
    stop_hook_active: false,
    background_tasks: [{ id: 'b1', type: 'shell', status: 'running', description: 'npm run dev' }],
  })
  await $.turn.complete(ended('t2'))
  expect(file.last()).toBe('beam')
  await clock.advance(3_600)
  expect(file.last()).toBe('idle')

  // A round with only a shell behind it: happy.
  await $.turn.start({ text: 'again', turnId: 't3' })
  await $.classic.Stop({
    stop_hook_active: false,
    background_tasks: [{ id: 'b1', type: 'shell', status: 'running', description: 'npm run dev' }],
  })
  await $.turn.complete(ended('t3'))
  expect(file.last()).toBe('happy')
})

test('a long round ends in the beam, a short one in happy', async ($, on) => {
  const clock = mock.clock(on, { now: 1_000 })
  const file = moodFile(on)
  turnBottoms(on)

  await $.turn.start({ text: 'quick', turnId: 't1' })
  await clock.advance(119_000)
  await $.turn.complete(ended('t1'))
  expect(file.last()).toBe('happy')
  await clock.advance(3_000)

  // Two prompts while still working are one round.
  await $.turn.start({ text: 'long', turnId: 't2' })
  await $.classic.SubagentStart({ agent_id: 'a1', agent_type: 'Explore' })
  await $.turn.complete(ended('t2'))
  await $.classic.SubagentStop({ agent_id: 'a1', agent_type: 'Explore', stop_hook_active: false, agent_transcript_path: '' })
  await clock.advance(2_000)
  expect(file.last()).toBe('beam')
  await clock.advance(3_599)
  expect(file.last()).toBe('beam')
  await clock.advance(1)
  expect(file.last()).toBe('idle')

  await $.turn.start({ text: 'slow', turnId: 't3' })
  await clock.advance(120_000)
  await $.turn.complete(ended('t3'))
  expect(file.last()).toBe('beam')
})

test('the beam settings: how long a round lasts, and whether agents count', async ($, on) => {
  const clock = mock.clock(on, { now: 1_000 })
  const file = moodFile(on, { beamAfter: 5, beamForAgents: false })
  turnBottoms(on)

  await $.turn.start({ text: 'a while', turnId: 't1' })
  await $.classic.SubagentStart({ agent_id: 'a1', agent_type: 'Explore' })
  await $.classic.SubagentStop({ agent_id: 'a1', agent_type: 'Explore', stop_hook_active: false, agent_transcript_path: '' })
  await clock.advance(4 * 60_000)
  await $.turn.complete(ended('t1'))
  expect(file.last()).toBe('happy') // agents do not count, and 4 min is short
  await clock.advance(3_000)

  await $.turn.start({ text: 'longer', turnId: 't2' })
  await clock.advance(5 * 60_000)
  await $.turn.complete(ended('t2'))
  expect(file.last()).toBe('beam')
})

test('a beam set to never leaves long rounds happy', async ($, on) => {
  const clock = mock.clock(on, { now: 1_000 })
  const file = moodFile(on, { beamAfter: false })
  turnBottoms(on)

  await $.turn.start({ text: 'long', turnId: 't1' })
  await clock.advance(60 * 60_000)
  await $.turn.complete(ended('t1'))
  expect(file.last()).toBe('happy')
})

test('a broken settings file is the defaults', async ($, on) => {
  const clock = mock.clock(on, { now: 1_000 })
  const file = moodFile(on, '{"beamAfter": 0, ')
  turnBottoms(on)

  await $.turn.start({ text: 'slow', turnId: 't1' })
  await clock.advance(120_000)
  await $.turn.complete(ended('t1'))
  expect(file.last()).toBe('beam')
})

test('a subagent ending with no new turn settles to happy after a short wait', async ($, on) => {
  const clock = mock.clock(on)
  const file = moodFile(on)
  turnBottoms(on)

  await $.turn.start({ text: 'go', turnId: 't1' })
  await $.classic.SubagentStart({ agent_id: 'a1', agent_type: 'Explore' })
  await $.turn.complete(ended('t1'))
  expect(file.last()).toBe('working')
  await $.classic.SubagentStop({ agent_id: 'a1', agent_type: 'Explore', stop_hook_active: false, agent_transcript_path: '' })
  await clock.advance(2_000)
  expect(file.last()).toBe('beam')
})

test('an interrupted turn goes back to idle, not happy', async ($, on) => {
  mock.clock(on)
  const file = moodFile(on)
  turnBottoms(on)

  await $.turn.start({ text: 'go', turnId: 't1' })
  await $.turn.complete({ answer: '', durationMs: 5, isAborted: true, turnId: 't1', reason: 'aborted' })
  expect(file.last()).toBe('idle')
})

const step = (turnId: string, index: number) => ({ turnId, index, model: 'claude', messageCount: 1 }) as const
const stepDone = (turnId: string, index: number) =>
  ({ turnId, index, answer: 'hi', toolUses: [], stopReason: 'end_turn', usage: null }) as const

test('a model request that streams nothing for 10s looks worried until it streams again', async ($, on) => {
  const clock = mock.clock(on)
  const file = moodFile(on)
  turnBottoms(on)
  let release = () => {}
  const gate = new Promise<void>(resolve => (release = resolve))
  on('turn.step', async function* (_$, e) {
    await gate // nothing streams: a retry under way
    yield { kind: 'text' as const, index: 0, text: 'hi' }
    return stepDone(e.turnId, e.index)
  })

  await $.turn.start({ text: 'hi', turnId: 't1' })
  const reading = (async () => {
    for await (const _chunk of $.turn.step(step('t1', 0)));
  })()
  await clock.advance(9_000)
  expect(file.last()).toBe('thinking')
  await clock.advance(1_000)
  expect(file.last()).toBe('worried')

  release()
  await reading
  expect(file.last()).toBe('thinking')
})

test('a new model request after a tool goes back to thinking', async ($, on) => {
  mock.clock(on)
  const file = moodFile(on)
  turnBottoms(on)
  on('tool.call', () => ({ result: 'ok', text: 'ok' }))
  on('turn.step', async function* (_$, e) {
    return stepDone(e.turnId, e.index)
  })

  await $.turn.start({ text: 'hi', turnId: 't1' })
  await $.tool.call({ tool: 'Read', file_path: 'a.md' })
  expect(file.last()).toBe('working')
  for await (const _chunk of $.turn.step(step('t1', 1)));
  expect(file.last()).toBe('thinking')

  // A subagent's request leaves the mood alone.
  await $.tool.call({ tool: 'Read', file_path: 'b.md' })
  for await (const _chunk of $.turn.step({ ...step('t9', 0), agentId: 'sub-1' }));
  expect(file.last()).toBe('working')
})

test('a reply that dies on an API error shows error, then idle', async ($, on) => {
  const clock = mock.clock(on)
  const file = moodFile(on)
  turnBottoms(on)
  on('classic.StopFailure', () => ({}))

  await $.turn.start({ text: 'hi', turnId: 't1' })
  await $.classic.StopFailure({ error: 'overloaded' })
  expect(file.last()).toBe('error')
  await clock.advance(3_000)
  expect(file.last()).toBe('idle')
})

test('a permission dialog waits on the person; saying no is not an error', async ($, on) => {
  mock.clock(on)
  const file = moodFile(on)
  turnBottoms(on)
  on('classic.PermissionRequest', () => ({}))
  // The engine raises the dialog while the call runs; the person declines.
  const seen: (string | undefined)[] = []
  on('tool.call', async () => {
    await $.classic.PermissionRequest({ tool_name: 'Bash', tool_input: { command: 'rm x' } })
    seen.push(file.last())
    return { isError: true as const, result: 'declined', text: 'declined' }
  })

  await $.turn.start({ text: 'hi', turnId: 't1' })
  const r = await $.tool.call({ tool: 'Bash', command: 'rm x' })
  expect(r.isError).toBe(true)
  expect(seen).toEqual(['waiting'])
  expect(file.all).not.toContain('error')
  expect(file.last()).toBe('working')
})

test('a question for the person shows waiting for as long as it is open', async ($, on) => {
  mock.clock(on)
  const file = moodFile(on)
  turnBottoms(on)
  const seen: (string | undefined)[] = []
  on('tool.call', () => {
    seen.push(file.last())
    return { result: 'ok', text: 'ok' }
  })

  await $.turn.start({ text: 'hi', turnId: 't1' })
  await $.tool.call({ tool: 'AskUserQuestion', questions: [] } as never)
  expect(seen).toEqual(['waiting'])
  expect(file.last()).toBe('working')
})

test('idle dozes off after 5 minutes; a new message wakes it', async ($, on) => {
  const clock = mock.clock(on)
  const file = moodFile(on)
  turnBottoms(on)

  await $.turn.start({ text: 'hi', turnId: 't1' })
  await $.turn.complete(ended('t1'))
  await clock.advance(3_000)
  expect(file.last()).toBe('idle')
  await clock.advance(5 * 60_000 - 1)
  expect(file.last()).toBe('idle')
  await clock.advance(1)
  expect(file.last()).toBe('sleepy')

  await $.turn.start({ text: 'back', turnId: 't2' })
  expect(file.last()).toBe('thinking')
})

test('the hover card follows the session: context growth, subagents, background work', async ($, on) => {
  const clock = mock.clock(on, { now: 1_000_000 })
  const { files } = sessionFiles(on, undefined, () => 'ref: refs/heads/main\n')
  const lastCard = () => files.filter(f => f.info).pop()?.info as any
  turnBottoms(on)
  on('tool.call', () => ({ result: 'ok', text: 'ok' }))
  let tokens = 100_000
  on('session.usage', (_$, e) => ({
    value: {
      startedAt: 500_000,
      context: {
        tokens,
        window: 1_000_000,
        percent: tokens / 10_000,
        ...(e.breakdown ? { breakdown: { autoCompactThreshold: 967_000 } as never } : {}),
      },
      rateLimits: [{ kind: 'five_hour', percentUsed: 23, resetsAt: '2026-10-02T21:40:00Z' }],
    },
  }))
  on('session.model', () => ({ value: 'Opus 5.5' }))
  on('session.turns', () => ({ value: 3 }))
  on('session.root', () => ({ value: 'C:\\Users\\test\\Desktop\\my-app' }))
  const usage = (input: number, model: string) =>
    ({ input_tokens: input, output_tokens: 10, cache_read_input_tokens: 0, cache_creation_input_tokens: 0, model }) as const
  on('turn.step', async function* (_$, e) {
    return { ...stepDone(e.turnId, e.index), usage: usage(e.agentId ? 50_000 : tokens, 'claude-opus-5-5') }
  })

  // Three replies, the context growing 10k each.
  for (const [i, t] of [100_000, 110_000, 120_000].entries()) {
    tokens = t
    await $.turn.start({ text: 'go', turnId: `t${i}` })
    for await (const _chunk of $.turn.step(step(`t${i}`, 0)));
    await $.turn.complete(ended(`t${i}`))
  }
  await clock.advance(500)
  const calm = lastCard()
  expect(calm.project).toBe('my-app')
  expect(calm.sessionId).toBe('sess-1')
  expect(calm.branch).toBe('main')
  expect(calm.context).toEqual({ tokens: 120_000, window: 1_000_000, percent: 12, perTurn: 10_000, turnsToCompact: 85 })
  expect(calm.limits).toEqual([{ kind: 'five_hour', percent: 23, resetsAt: '2026-10-02T21:40:00Z' }])

  // A turn with a tool running, a subagent and a background workflow.
  await $.turn.start({ text: 'fan out', turnId: 't9' })
  await $.classic.SubagentStart({ agent_id: 'a1', agent_type: 'Explore' })
  for await (const _chunk of $.turn.step({ ...step('s1', 0), agentId: 'a1' }));
  await $.classic.Stop({
    stop_hook_active: false,
    background_tasks: [
      { id: 'w1', type: 'workflow', status: 'running', description: 'review' },
      { id: 'a1', type: 'subagent', status: 'running', description: 'explore' },
    ],
  })
  await clock.advance(500)
  const busy = lastCard()
  expect(busy.turnSince).toBe(clock.now() - 500)
  expect(busy.subagents).toEqual([{ type: 'Explore', tokens: 50_000, percent: 5 }])
  expect(busy.background).toEqual({ workflow: 1 })

  await $.classic.SubagentStop({ agent_id: 'a1', agent_type: 'Explore', stop_hook_active: false, agent_transcript_path: '' })
  await clock.advance(500)
  expect(lastCard().subagents).toEqual([])
})

// Stands in for the overlay: records each start, and plays what it says on
// stdout (`hidden`, as a right-click reports it) once `say` is called.
const overlayProcess = (on: On) => {
  const starts: (readonly string[])[] = []
  let speak: (text: string) => void = () => {}
  on('process.spawn', async function* (_$, e) {
    starts.push(e.argv)
    const said: string[] = []
    let wake = () => {}
    speak = text => {
      said.push(text)
      wake()
    }
    for (;;) {
      while (said.length) yield { stream: 'stdout' as const, text: said.shift()! }
      await new Promise<void>(resolve => (wake = resolve))
    }
  })
  return { starts, say: (text: string) => speak(text) }
}

// Stands in for `$.store`, which keeps what outlives a session.
const store = (on: On) => {
  const kept = new Map<string, unknown>()
  on('store.get', (_$, e) => ({ value: kept.get(e.key) }))
  on('store.set', (_$, e) => {
    kept.set(e.key, e.value)
    return { value: undefined }
  })
  return kept
}

// `/mascot <args>` typed at the prompt.
const mascot = ($: Engine, args = '') =>
  $.command.run({
    command: 'mascot',
    args,
    origin: { kind: 'composer' },
    presentation: { isFullscreen: false, columns: 80 },
  })

test("/mascot shows and hides this session's mascot", async ($, on) => {
  mock.clock(on, { now: 1_000 })
  const disk = sessionFiles(on)
  const proc = overlayProcess(on)
  const kept = store(on)

  const shown = await mascot($)
  expect(shown.text).toContain('Mascot shown')
  expect(disk.last()).toMatchObject({ visible: true, visibleAt: 1_000 })
  expect(kept.get('isOverlayOn')).toBe(true) // the next session starts shown
  expect(proc.starts.length).toBe(1)
  expect(proc.starts[0]![3]).toMatch(/[\\/]\.claude[\\/]mascot[\\/]sessions[\\/]sess-1\.json$/)
  expect(proc.starts[0]![2]).toMatch(/[\\/]frames[\\/]miku$/)
  expect(proc.starts[0]![0]).toMatch(/pythonw(\.exe)?$/i) // by its full path where `where` finds it

  const hidden = await mascot($, 'hide')
  expect(hidden.text).toContain('hidden for this session')
  expect(disk.last()).toMatchObject({ visible: false })
  expect(kept.get('isOverlayOn')).toBe(false)

  await mascot($, 'show')
  expect(disk.last()).toMatchObject({ visible: true })
  expect(proc.starts.length).toBe(1) // the same overlay, shown again

  expect((await mascot($, 'dance')).text).toContain('Usage: /mascot')
  expect((await mascot($, 'show all now')).text).toContain('Usage: /mascot')
})

test("/mascot hide all writes every session's choice", async ($, on) => {
  mock.clock(on, { now: 2_000 })
  const disk = sessionFiles(on)
  overlayProcess(on)

  expect((await mascot($, 'hide all')).text).toBe("Every session's mascot hidden.")
  expect(disk.everyone).toEqual([{ visible: false, at: 2_000 }])
  expect(disk.last()).toMatchObject({ visible: false, visibleAt: 2_000 })
  expect((await mascot($, 'show all')).text).toBe("Every session's mascot shown.")
  expect(disk.everyone[1]).toEqual({ visible: true, at: 2_000 })
})

test('/mascot beam fires her beam, then she goes back to what she was doing', async ($, on) => {
  const clock = mock.clock(on, { now: 1_000 })
  const disk = sessionFiles(on)
  overlayProcess(on)
  turnBottoms(on)

  expect((await mascot($, 'beam')).text).toContain('She is hidden')
  expect(disk.last()!.frame).toBe('beam')
  await clock.advance(3_600)
  expect(disk.last()!.frame).toBe('idle')

  await mascot($, 'show')
  await $.turn.start({ text: 'go', turnId: 't1' })
  expect((await mascot($, 'beam')).text).toBe('Miku Miku Beam!')
  expect(disk.last()!.frame).toBe('beam')
  await clock.advance(3_600)
  expect(disk.last()!.frame).toBe('thinking')
  expect((await mascot($, 'beam me')).text).toContain('Usage: /mascot')
})

test('a right-click on the overlay hides it for the mod too', async ($, on) => {
  const clock = mock.clock(on, { now: 1_000 })
  const disk = sessionFiles(on)
  const proc = overlayProcess(on)

  await mascot($, 'show')
  await clock.advance(5_000)
  proc.say('hid')
  proc.say('den\n') // a line may come in pieces
  await clock.advance(10)
  expect(disk.last()).toMatchObject({ visible: false, visibleAt: 6_000 })
  // The next /mascot shows it again.
  expect((await mascot($)).text).toContain('Mascot shown')
})

const sessionEnd = (reason: 'clear' | 'prompt_input_exit') =>
  ({ reason, sessionId: 'sess-1', resume: { id: 'sess-1' } }) as never

test('a /clear keeps the mascot with a fresh card; leaving ends it', async ($, on) => {
  mock.clock(on, { now: 5_000 })
  const disk = sessionFiles(on)
  turnBottoms(on)
  on('session.end', (_$, e) => ({ sessionId: e.sessionId }))

  await $.turn.start({ text: 'go', turnId: 't1' })
  await $.classic.SubagentStart({ agent_id: 'a1', agent_type: 'Explore' })
  expect(disk.last()!.cleared).toBeUndefined()
  await $.session.end(sessionEnd('clear'))
  expect(disk.last()).toMatchObject({ frame: 'idle', cleared: 5_000 }) // the overlay changes channel
  expect(disk.last()!.ended).toBeUndefined()
  // Work after the clear is the new conversation's: no subagent holds happy back.
  await $.turn.start({ text: 'again', turnId: 't2' })
  await $.turn.complete(ended('t2'))
  expect(disk.last()!.frame).toBe('happy')

  await $.session.end(sessionEnd('prompt_input_exit'))
  expect(disk.last()).toMatchObject({ ended: true, visible: false })
  const count = disk.files.length
  await $.turn.start({ text: 'late', turnId: 't3' })
  expect(disk.files.length).toBe(count) // nothing after the end
})

test('/mascot character lists the art and picks one for the project', async ($, on) => {
  mock.clock(on)
  const disk = sessionFiles(on)
  const proc = overlayProcess(on)
  const kept = store(on)
  on('session.root', () => ({ value: 'C:\\code\\webapp' }))
  on('fs.list', () => ({
    value: [
      { name: 'miku', kind: 'dir' as const, size: 0, mtimeMs: 0, isLink: false },
      { name: 'teto', kind: 'dir' as const, size: 0, mtimeMs: 0, isLink: false },
      { name: 'notes.txt', kind: 'file' as const, size: 3, mtimeMs: 0, isLink: false },
    ],
  }))
  on('fs.exists', () => ({ value: true }))

  expect((await mascot($, 'character')).text).toBe('Characters: miku (shown), teto.')
  expect((await mascot($, 'character neru')).text).toBe('No art for "neru". Characters: miku, teto.')

  await mascot($, 'show')
  expect(disk.last()!.character).toBe('miku')
  expect((await mascot($, 'character teto')).text).toBe('Mascot: webapp now shows teto.')
  expect(proc.starts.length).toBe(1) // not restarted: the overlay swaps her where she stands
  expect(disk.last()!.character).toBe('teto')
  expect(kept.get('characters')).toEqual({ webapp: 'teto' })
  expect((await mascot($, 'character')).text).toBe('Characters: miku, teto (shown).')
})

test('the settings window picks the character, for the project or this session alone', async ($, on) => {
  const clock = mock.clock(on)
  const disk = sessionFiles(on)
  const proc = overlayProcess(on)
  const kept = store(on)
  on('session.root', () => ({ value: 'C:\\code\\webapp' }))
  on('fs.list', () => ({
    value: [
      { name: 'miku', kind: 'dir' as const, size: 0, mtimeMs: 0, isLink: false },
      { name: 'teto', kind: 'dir' as const, size: 0, mtimeMs: 0, isLink: false },
    ],
  }))
  on('fs.exists', () => ({ value: true }))

  await mascot($, 'show')
  await mascot($, 'settings')
  // It knows whose window it is: this session's file and project.
  const window = proc.starts[proc.starts.length - 1]!
  expect(window.slice(4)).toEqual(['sess-1', 'webapp'])

  proc.say('character teto session\n')
  await clock.advance(10)
  expect(disk.last()!.character).toBe('teto')
  expect(kept.get('characters')).toBeUndefined() // this session alone
  expect((await mascot($, 'character')).text).toBe('Characters: miku, teto (shown).')

  proc.say('character neru remember\n') // no art: nothing happens
  await clock.advance(10)
  expect(disk.last()!.character).toBe('teto')

  proc.say('character miku remember\n')
  await clock.advance(10)
  expect(disk.last()!.character).toBe('miku')
  expect(kept.get('characters')).toEqual({ webapp: 'miku' })
  expect(proc.starts.filter(argv => /mascot_overlay\.py$/.test(argv[1] ?? '')).length).toBe(1)
})

test("/mascot size, calm, aura and beam change every mascot's settings", async ($, on) => {
  mock.clock(on)
  const disk = sessionFiles(on, { note: 'mine' })
  const proc = overlayProcess(on)

  expect((await mascot($, 'size')).text).toContain('Size: 420 px (normal).')
  expect((await mascot($, 'size large')).text).toBe('Size: 560 px (large).')
  expect((await mascot($, 'size 333px')).text).toBe('Size: 333 px.')
  expect((await mascot($, 'size 9000')).text).toContain('Size takes')
  expect((await mascot($, 'calm on')).text).toBe('Calm mode on: no glitch, particles, flicker or flashes.')
  expect((await mascot($, 'calm maybe')).text).toBe('Calm takes on or off.')
  expect((await mascot($, 'aura 250k 1.2M 2000000')).text).toBe('Aura from 250k, 1.2M, 2M tokens of context.')
  expect((await mascot($, 'aura 400k 300k 500k')).text).toContain('Aura takes three token counts going up')
  expect((await mascot($, 'beam after 10')).text).toBe('Rounds of work of 10 min or more end in the beam.')
  expect((await mascot($, 'beam agents off')).text).toContain('only when long')
  expect(disk.settings()).toEqual({
    note: 'mine', // what else the file holds stays
    size: 333,
    calm: true,
    aura: [250_000, 1_200_000, 2_000_000],
    beamAfter: 10,
    beamForAgents: false,
  })

  // A default takes its key out of the file.
  await mascot($, 'size normal')
  await mascot($, 'aura default')
  expect(disk.settings()).not.toHaveProperty('size')
  expect(disk.settings()).not.toHaveProperty('aura')
  expect((await mascot($, 'aura off')).text).toBe('Aura off.')
  expect((await mascot($, 'beam after never')).text).toBe('Long rounds of work do not end in the beam.')
  expect(disk.settings()).toMatchObject({ aura: false, beamAfter: false })

  // The window, in this project's character's colors, on the shared folder.
  const opened = await mascot($, 'settings')
  expect(opened.text).toContain('Settings window opened.')
  expect(opened.text).toContain('Calm mode on')
  const window = proc.starts.find(argv => /settings_window\.py$/.test(argv[1] ?? ''))
  expect(window?.[2]).toMatch(/[\\/]\.claude[\\/]mascot$/)
  expect(window?.[3]).toMatch(/[\\/]frames[\\/]miku$/)

  expect((await mascot($, 'reset')).text).toContain('Settings back to their defaults.')
  expect(disk.settings()).toEqual({ note: 'mine' })
  expect((await mascot($, 'size large now')).text).toContain('Usage: /mascot')
  expect((await mascot($, 'beam after 10 now')).text).toContain('Usage: /mascot')
})

test('/mascot settings reads what was set by hand, valid values only', async ($, on) => {
  mock.clock(on)
  sessionFiles(on, { size: 300, calm: 'yes', aura: [1, 2, 3] })
  overlayProcess(on)

  const text = (await mascot($, 'settings')).text
  expect(text).toContain('Size: 300 px (small).')
  expect(text).toContain('Calm mode off.')
  expect(text).toContain('Aura from 300k, 400k, 500k tokens of context.')
})
