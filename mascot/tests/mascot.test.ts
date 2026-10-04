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

test('a frame she already shows is not written again at every tool call', async ($, on) => {
  mock.clock(on, { now: 1_000 })
  const file = moodFile(on)
  on('turn.start', (_$, e) => ({ turnId: e.turnId }))
  on('tool.call', () => ({ result: 'ok', text: 'ok' }))

  await $.turn.start({ text: 'hi', turnId: 't1' })
  const before = file.all.length
  for (const name of ['a.md', 'b.md', 'c.md', 'd.md']) await $.tool.call({ tool: 'Read', file_path: name })
  expect(file.all.slice(before)).toEqual(['working'])
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

  // A dev server serves on by design: done as usual, with the beam, since
  // the round had a workflow.
  await $.turn.start({ text: 'next', turnId: 't2' })
  await $.classic.Stop({
    stop_hook_active: false,
    background_tasks: [{ id: 'b1', type: 'shell', status: 'running', description: 'Dev server', command: 'npm run dev' }],
  })
  await $.turn.complete(ended('t2'))
  expect(file.last()).toBe('beam')
  await clock.advance(3_600)
  expect(file.last()).toBe('idle')

  // A round with only that server behind it: happy.
  await $.turn.start({ text: 'again', turnId: 't3' })
  await $.classic.Stop({
    stop_hook_active: false,
    background_tasks: [{ id: 'b1', type: 'shell', status: 'running', description: 'Dev server', command: 'npm run dev' }],
  })
  await $.turn.complete(ended('t3'))
  expect(file.last()).toBe('happy')
})

// How long background work Claude waits on holds a round open, at most.
const WAIT_CAP = 30 * 60_000
const shell = (id: string, command: string) => ({ id, type: 'shell', status: 'running', description: command, command })
// Claude's Monitor tool: its tasks are listed as shells.
const monitor = (id: string) => shell(id, 'gh run watch 4711 --exit-status')

test('an orchestrator waiting on shells and a monitor it started is not done until they are', async ($, on) => {
  const clock = mock.clock(on, { now: 1_000 })
  const disk = sessionFiles(on, { magicAfter: 1 })
  turnBottoms(on)

  await $.turn.start({ text: 'build and check', turnId: 't1' })
  await clock.advance(10_000)
  await $.classic.Stop({
    stop_hook_active: false,
    background_tasks: [shell('s1', 'npm run build'), shell('s2', 'npm test'), monitor('m1')],
  })
  await $.turn.complete(ended('t1'))
  expect(disk.last()!.frame).toBe('working')

  // The monitor's event wakes Claude; the shells run on.
  await clock.advance(30_000)
  await $.turn.start({ text: '', turnId: 't2' })
  await $.classic.Stop({ stop_hook_active: false, background_tasks: [shell('s1', 'npm run build'), shell('s2', 'npm test')] })
  await $.turn.complete(ended('t2'))
  expect(disk.last()!.frame).toBe('working')
  await clock.advance(20 * 60_000)
  expect(disk.last()!.frame).toBe('working')
  expect(disk.files.map(f => f.frame)).not.toContain('happy')
  expect(disk.last()!.call).toBeUndefined()

  // The last shell exits: the round, timed from the first prompt, is done.
  await $.turn.start({ text: '', turnId: 't3' })
  await $.classic.Stop({ stop_hook_active: false, background_tasks: [] })
  await $.turn.complete(ended('t3'))
  expect(disk.last()!.frame).toBe('beam')
  expect(disk.last()!.call).toEqual({ at: clock.now() })
})

test('servers, watchers, subscriptions and work from before the round do not hold it open', async ($, on) => {
  const clock = mock.clock(on)
  const file = moodFile(on)
  turnBottoms(on)
  const endless = [
    'npm run dev',
    'pnpm start',
    'npx vite --port 5173',
    'python -m http.server 8000',
    'uvicorn app:app --reload',
    'tail -f server.log',
    'docker compose up',
    'tsc --watch',
    'Get-Content app.log -Wait',
    'while true; do date >> beat.log; sleep 5; done',
  ]

  // A subscription with no end: the live watch on a published artifact.
  const watch = { id: 'a1', type: 'monitor', status: 'running', description: 'Artifact live subscription' }

  await $.turn.start({ text: 'serve it', turnId: 't1' })
  await $.classic.Stop({ stop_hook_active: false, background_tasks: [...endless.map((c, i) => shell(`e${i}`, c)), watch] })
  await $.turn.complete(ended('t1'))
  expect(file.last()).toBe('happy')
  await clock.advance(3_000)

  // Lookalikes that end hold it, each on its own.
  const ending = [
    'npx vite build',
    'docker compose up -d',
    'until grep -q "Ready" dev.log; do sleep 0.5; done',
    'npm run build && npm test',
    'pytest -x',
    // A monitor's poll: a forever loop that breaks out once its line shows.
    'while true; do grep -q "round 1 done" out.txt && break; sleep 60; done',
    'while :\ndo\n  test -f done.flag && exit 0\n  sleep 1\ndone',
  ]
  for (const [i, command] of ending.entries()) {
    await $.turn.start({ text: 'wait on it', turnId: `w${i}` })
    await $.classic.Stop({ stop_hook_active: false, background_tasks: [shell(`f${i}`, command)] })
    await $.turn.complete(ended(`w${i}`))
    expect([command, file.last()]).toEqual([command, 'working'])
    await $.turn.start({ text: '', turnId: `x${i}` })
    await $.classic.Stop({ stop_hook_active: false, background_tasks: [] })
    await $.turn.complete(ended(`x${i}`))
    await clock.advance(3_600)
  }

  // A build still running from a round that ended (interrupted here)
  // belongs to that round.
  await $.turn.start({ text: 'start a build', turnId: 't2' })
  await $.classic.Stop({ stop_hook_active: false, background_tasks: [shell('b1', 'npm run build')] })
  await $.turn.complete({ ...ended('t2'), isAborted: true, reason: 'aborted' })
  expect(file.last()).toBe('idle')
  await $.turn.start({ text: 'something else', turnId: 't3' })
  await $.classic.Stop({ stop_hook_active: false, background_tasks: [shell('b1', 'npm run build')] })
  await $.turn.complete(ended('t3'))
  expect(file.last()).toBe('happy')
})

test('work it waits on that outlasts 30 minutes ends the round quietly', async ($, on) => {
  const clock = mock.clock(on, { now: 1_000 })
  const disk = sessionFiles(on, { magicAfter: 1 })
  turnBottoms(on)

  await $.turn.start({ text: 'start the server', turnId: 't1' })
  await $.classic.Stop({ stop_hook_active: false, background_tasks: [shell('s1', './run-my-server.sh')] })
  await $.turn.complete(ended('t1'))
  expect(disk.last()!.frame).toBe('working')
  await clock.advance(WAIT_CAP - 1)
  expect(disk.last()!.frame).toBe('working')
  await clock.advance(1)
  // Nobody knows it is done: no happy, no beam, no magic.
  expect(disk.last()!.frame).toBe('idle')
  expect(disk.files.map(f => f.frame)).not.toContain('happy')
  expect(disk.files.map(f => f.frame)).not.toContain('beam')
  expect(disk.last()!.call).toBeUndefined()

  // The next prompt is a round of its own, the shell no part of it.
  await $.turn.start({ text: 'hi', turnId: 't2' })
  await $.classic.Stop({ stop_hook_active: false, background_tasks: [shell('s1', './run-my-server.sh')] })
  await $.turn.complete(ended('t2'))
  expect(disk.last()!.frame).toBe('happy')
})

test('a one-time wakeup holds the round open; a recurring one does not', async ($, on) => {
  mock.clock(on)
  const file = moodFile(on)
  turnBottoms(on)
  const wakeup = (id: string, recurring: boolean) => ({ id, schedule: '*/5 * * * *', recurring, prompt: 'check CI' })

  await $.turn.start({ text: 'every 5 minutes', turnId: 't1' })
  await $.classic.Stop({ stop_hook_active: false, background_tasks: [], session_crons: [wakeup('c1', true)] })
  await $.turn.complete(ended('t1'))
  expect(file.last()).toBe('happy')

  await $.turn.start({ text: 'check back later', turnId: 't2' })
  await $.classic.Stop({ stop_hook_active: false, background_tasks: [], session_crons: [wakeup('c1', true), wakeup('c2', false)] })
  await $.turn.complete(ended('t2'))
  expect(file.last()).toBe('working')

  // It fires: Claude picks the work up and finishes.
  await $.turn.start({ text: 'check CI', turnId: 't3' })
  await $.classic.Stop({ stop_hook_active: false, background_tasks: [], session_crons: [wakeup('c1', true)] })
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

test('a round of the magicAfter minutes calls the pointer as it settles; off, none does', async ($, on) => {
  const clock = mock.clock(on, { now: 1_000 })
  const disk = sessionFiles(on, { magicAfter: 1 })
  turnBottoms(on)

  await $.turn.start({ text: 'quick', turnId: 't1' })
  await clock.advance(59_000)
  await $.turn.complete(ended('t1'))
  expect(disk.last()!.frame).toBe('happy')
  expect(disk.last()!.call).toBeUndefined()
  await clock.advance(3_000)

  await $.turn.start({ text: 'a minute', turnId: 't2' })
  await clock.advance(60_000)
  await $.turn.complete(ended('t2'))
  expect(disk.last()!.call).toEqual({ at: 123_000 })
  // It stays in the file: the overlay sends a call once per new `at`.
  await clock.advance(3_600)
  expect(disk.last()!.frame).toBe('idle')
  expect(disk.last()!.call).toEqual({ at: 123_000 })
})

test('cursor magic is off by default; 0 minutes is every round', async ($, on) => {
  const clock = mock.clock(on, { now: 1_000 })
  const disk = sessionFiles(on)
  turnBottoms(on)

  await $.turn.start({ text: 'long', turnId: 't1' })
  await clock.advance(60 * 60_000)
  await $.turn.complete(ended('t1'))
  expect(disk.last()!.call).toBeUndefined()

  await mascot($, 'magic after 0')
  await clock.advance(3_000)
  await $.turn.start({ text: 'hi', turnId: 't2' })
  await $.turn.complete(ended('t2'))
  expect(disk.last()!.call).toEqual({ at: 3_604_000 })
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

test('/mascot magic and the settings window send a test call to the pointer', async ($, on) => {
  const clock = mock.clock(on, { now: 1_000 })
  const disk = sessionFiles(on)
  const proc = overlayProcess(on)

  expect((await mascot($, 'magic')).text).toBe('Magic sent to your pointer!')
  expect(disk.last()!.call).toEqual({ at: 1_000, test: true })
  expect(disk.last()!.frame).toBe('idle') // she goes on as she was

  await mascot($, 'settings')
  await clock.advance(500)
  proc.say('magic\n')
  await clock.advance(10)
  expect(disk.last()!.call).toEqual({ at: 1_500, test: true })
  expect((await mascot($, 'magic now')).text).toContain('Usage: /mascot')
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

test("/mascot size, calm, smooth, aura and beam change every mascot's settings", async ($, on) => {
  mock.clock(on)
  const disk = sessionFiles(on, { note: 'mine' })
  const proc = overlayProcess(on)

  expect((await mascot($, 'size')).text).toContain('Size: 420 px (normal).')
  expect((await mascot($, 'size large')).text).toBe('Size: 560 px (large).')
  expect((await mascot($, 'size 333px')).text).toBe('Size: 333 px.')
  expect((await mascot($, 'size 9000')).text).toContain('Size takes')
  expect((await mascot($, 'calm on')).text).toBe('Calm mode on: no glitch, particles, flicker or flashes.')
  expect((await mascot($, 'calm maybe')).text).toBe('Calm takes on or off.')
  expect((await mascot($, 'smooth')).text).toContain('Smooth sparkles off: her sparkles move in step')
  expect((await mascot($, 'smooth on')).text).toContain('Smooth sparkles on: her sparkles move as smoothly as her symbols')
  expect((await mascot($, 'smooth')).text).toContain('(calm mode is on, so she has no sparkles to smooth)')
  expect((await mascot($, 'smooth please')).text).toBe('Smooth takes on or off.')
  expect((await mascot($, 'aura 250k 1.2M 2000000')).text).toBe('Aura from 250k, 1.2M, 2M tokens of context.')
  expect((await mascot($, 'aura 400k 300k 500k')).text).toContain('Aura takes three token counts going up')
  expect((await mascot($, 'beam after 10')).text).toBe('Rounds of work of 10 min or more end in the beam.')
  expect((await mascot($, 'beam agents off')).text).toContain('only when long')
  expect((await mascot($, 'magic after')).text).toBe('No cursor magic. /mascot magic after <minutes>|never|default.')
  expect((await mascot($, 'magic after 5min')).text).toBe(
    'Rounds of work of 5 min or more send magic to your pointer.',
  )
  expect((await mascot($, 'magic after 500')).text).toContain('Magic after takes minutes (0 to 120)')
  expect(disk.settings()).toEqual({
    note: 'mine', // what else the file holds stays
    size: 333,
    calm: true,
    smooth: true,
    aura: [250_000, 1_200_000, 2_000_000],
    beamAfter: 10,
    beamForAgents: false,
    magicAfter: 5,
  })
  expect((await mascot($, 'magic after never')).text).toBe('No cursor magic.')
  expect(disk.settings()).not.toHaveProperty('magicAfter')
  await mascot($, 'magic after 0')
  expect(disk.settings()).toMatchObject({ magicAfter: 0 }) // every round, not off

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
  sessionFiles(on, { size: 300, calm: 'yes', smooth: 2, aura: [1, 2, 3] })
  overlayProcess(on)

  const text = (await mascot($, 'settings')).text
  expect(text).toContain('Size: 300 px (small).')
  expect(text).toContain('Calm mode off.')
  expect(text).toContain('Smooth sparkles off')
  expect(text).toContain('Aura from 300k, 400k, 500k tokens of context.')
})

// ---- updates

// Stands in for the mod's own files (its manifest at `version`, and
// whatsnew.json), toasts, `where` (finding nothing, so programs go by name)
// and the commands an update runs, which answer `run`.
const release = (
  on: On,
  version: string | (() => string),
  run: (argv: readonly string[]) => { exitCode: number; stdout?: string; stderr?: string } = () => ({ exitCode: 0 }),
  notes: Record<string, unknown> = { '0.15.0': ['Updates, in her colors.', 'A banner.'], '0.14.1': ['Older news.'] },
) => {
  const disk = sessionFiles(on, undefined, path => {
    if (/[\\/]\.claude-plugin[\\/]plugin\.json$/.test(path)) return JSON.stringify({ name: 'mascot', version: typeof version === 'string' ? version : version() })
    if (/[\\/]whatsnew\.json$/.test(path)) return JSON.stringify(notes)
    return undefined
  })
  const toasts: string[] = []
  const runs: (readonly string[])[] = []
  on('ui.toast', (_$, e) => {
    toasts.push(e.text)
    return { value: undefined }
  })
  on('process.run', (_$, e) => {
    if (e.argv[0] === 'where') return { value: { exitCode: 1, stdout: '', stderr: '', isStdoutTruncated: false, isStderrTruncated: false } }
    runs.push(e.argv)
    const { exitCode, stdout = '', stderr = '' } = run(e.argv)
    return { value: { exitCode, stdout, stderr, isStdoutTruncated: false, isStderrTruncated: false } }
  })
  on('session.start', (_$, e) => ({ cwd: e.cwd }))
  on('command.register', (_$, e) => ({ value: { command: e.name } }))
  return { disk, toasts, runs }
}

const start = ($: Engine) => $.session.start({ cwd: 'C:/code/app', surface: 'terminal', isInteractive: true })

test('a newer version than the last one run gets her banner and what is new, once', async ($, on) => {
  const clock = mock.clock(on, { now: 50_000 })
  const { disk, toasts } = release(on, '0.15.0')
  const kept = store(on)
  overlayProcess(on)
  kept.set('lastVersion', '0.14.1')

  await start($)
  expect(disk.last()!.update).toMatchObject({ version: '0.15.0', from: '0.14.1', celebrate: 50_000 })
  expect(kept.get('lastVersion')).toBe('0.15.0')
  expect(toasts).toEqual(['Mascot updated to v0.15.0: Updates, in her colors. (+1 more: /mascot news)'])
  expect(disk.last()!.frame).toBe('happy')
  await clock.advance(3_600)
  expect(disk.last()!.frame).toBe('idle')

  // A reload of the same version: no banner again, and what is new still
  // counts from the version before.
  await start($)
  expect(disk.last()!.update!.celebrate).toBeUndefined()
  expect(disk.last()!.update!.from).toBe('0.14.1')
  expect(toasts.length).toBe(1)
})

test('versions skipped over are not lost: the toast leads with news over a fix, /mascot news has the rest', async ($, on) => {
  mock.clock(on, { now: 50_000 })
  const { toasts } = release(on, '0.17.0', undefined, {
    '0.17.0': [{ text: 'A stuck mood, unstuck.', kind: 'fix' }],
    '0.16.3': ['Smooth sparkles: /mascot smooth.'],
    '0.16.2': ['Lighter.', { text: 'A glitch, fixed.', kind: 'fix' }],
    '0.16.1': ['Seen already.'],
    '0.16.0': [42, { kind: 'fix' }, ''], // not lines: skipped
  })
  const kept = store(on)
  overlayProcess(on)
  kept.set('lastVersion', '0.16.1')

  await start($)
  expect(toasts).toEqual(['Mascot updated to v0.17.0: Smooth sparkles: /mascot smooth. (+3 more: /mascot news)'])
  expect(kept.get('upgrade')).toEqual({ from: '0.16.1', to: '0.17.0' })
  expect((await mascot($, 'news')).text).toBe(
    [
      'New since v0.16.1:',
      'v0.17.0',
      '  - Fix: A stuck mood, unstuck.',
      'v0.16.3',
      '  - Smooth sparkles: /mascot smooth.',
      'v0.16.2',
      '  - Lighter.',
      '  - Fix: A glitch, fixed.',
      '/mascot news all lists every version.',
    ].join('\n'),
  )
  const every = (await mascot($, 'news all')).text
  expect(every).toStartWith('Every version, newest first:\nv0.17.0')
  expect(every).toContain('v0.16.1\n  - Seen already.')
  expect(every).not.toContain('v0.16.0')
  expect((await mascot($, 'news later')).text).toStartWith('Usage:')
})

test('/mascot news without an update to count from says what is new in this version', async ($, on) => {
  mock.clock(on)
  release(on, '0.15.0')
  store(on)
  overlayProcess(on)

  await start($)
  expect((await mascot($, 'news')).text).toBe(
    'New in v0.15.0:\nv0.15.0\n  - Updates, in her colors.\n  - A banner.\n/mascot news all lists every version.',
  )
})

test('the first version ever run is only noted, and an older one leaves it', async ($, on) => {
  mock.clock(on, { now: 50_000 })
  const { disk, toasts } = release(on, '0.14.1')
  const kept = store(on)
  overlayProcess(on)

  await start($)
  expect(kept.get('lastVersion')).toBe('0.14.1')
  expect(disk.last()!.update).toEqual({ version: '0.14.1', route: 'manual' })
  expect(toasts).toEqual([])

  kept.set('lastVersion', '0.20.0') // a session of a newer copy ran meanwhile
  await start($)
  expect(kept.get('lastVersion')).toBe('0.20.0')
  expect(disk.last()!.update!.celebrate).toBeUndefined()
})

test('the check for a newer release is opt-in, and daily', async ($, on) => {
  const clock = mock.clock(on, { now: 1_000_000 })
  const { disk } = release(on, '0.15.0')
  const kept = store(on)
  overlayProcess(on)
  const asked: string[] = []
  let latest = '0.16.0'
  let isOffline = false
  on('http.fetch', (_$, e) => {
    if (isOffline) return { deny: 'offline' }
    asked.push(e.url)
    return { value: { status: 200, ok: true, headers: {}, text: JSON.stringify({ name: 'mascot', version: latest }) } }
  })

  await start($)
  await clock.advance(60_000)
  expect(asked).toEqual([]) // off: never online

  expect((await mascot($, 'updates')).text).toBe('Mascot v0.15.0. Never goes online to look for a new version. /mascot updates on|off.')
  expect((await mascot($, 'updates on')).text).toBe('Looks for a new version once a day.')
  await clock.advance(10)
  expect(asked).toEqual(['https://raw.githubusercontent.com/desuqcafe/cc-mascot/main/mascot/.claude-plugin/plugin.json'])
  expect(disk.last()!.update!.latest).toBe('0.16.0')
  expect(kept.get('latest')).toEqual({ at: 1_060_000, version: '0.16.0' })
  await clock.advance(30_000)
  expect((disk.last()!.info as { newVersion?: string }).newVersion).toBe('0.16.0') // her hover card's hint
  expect((await mascot($, 'updates')).text).toContain('v0.16.0 is out: /mascot update.')

  // Within the day, what was found stands; then it looks again.
  latest = '0.15.0'
  await clock.advance(10 * 60_000)
  expect(asked.length).toBe(1)
  kept.set('latest', { at: clock.now() - 24 * 60 * 60_000, version: '0.16.0' }) // as a day goes by
  await clock.advance(30_000)
  expect(asked.length).toBe(2)
  expect(disk.last()!.update!.latest).toBeUndefined()

  // Offline: nothing changes, nothing breaks.
  isOffline = true
  await mascot($, 'updates on')
  await clock.advance(10)
  expect(disk.last()!.update!.latest).toBeUndefined()
})

test('/mascot update pulls a clone, and the settings window asks the same', async ($, on) => {
  const clock = mock.clock(on, { now: 1_000 })
  let answer = { exitCode: 0, stdout: 'Updating 831a398..9f00e1c\nFast-forward' }
  const { disk, toasts, runs } = release(on, '0.15.0', () => answer)
  store(on)
  const proc = overlayProcess(on)
  on('fs.exists', (_$, e) => ({ value: /[\\/]\.git$/.test(e.path) }))

  await start($)
  expect(disk.last()!.update!.route).toBe('clone')
  expect((await mascot($, 'update')).text).toBe('Updating the mascot (v0.15.0)... she will say when it is done.')
  await clock.advance(10)
  const [git, , repo, ...rest] = runs[0]!
  expect(git).toBe('git')
  expect(rest).toEqual(['pull', '--ff-only'])
  expect(repo).not.toMatch(/[\\/]mascot$/) // the folder holding the mod
  expect(disk.last()!.update).toMatchObject({ state: 'updated', message: 'Pulled. She reloads by herself; if not, type /reload-plugins.' })
  expect(toasts.pop()).toBe('Mascot updated. Pulled. She reloads by herself; if not, type /reload-plugins.')

  await mascot($, 'settings')
  answer = { exitCode: 0, stdout: 'Already up to date.' }
  proc.say('update\n')
  await clock.advance(10)
  expect(runs.length).toBe(2)
  expect(toasts.pop()).toBe('Mascot v0.15.0 is the latest.')
  expect(disk.last()!.update!.state).toBeUndefined()

  answer = { exitCode: 1, stdout: '', stderr: 'hint: Diverging branches\nfatal: Not possible to fast-forward, aborting.' } as typeof answer
  await mascot($, 'update')
  await clock.advance(10)
  expect(disk.last()!.update).toMatchObject({ state: 'failed', message: 'fatal: Not possible to fast-forward, aborting.' })
})

test('a copy installed by hand says how to update it', async ($, on) => {
  mock.clock(on)
  const { runs } = release(on, '0.15.0')
  store(on)
  overlayProcess(on)
  on('fs.exists', () => ({ value: false }))

  await start($)
  expect((await mascot($, 'update')).text).toContain('update it by hand')
  expect(runs).toEqual([])
})

test('an update run from another session is told here, and asks for a reload, not "the latest"', async ($, on) => {
  const clock = mock.clock(on, { now: 1_000 })
  let onDisk = '0.15.0'
  const { disk, toasts } = release(on, () => onDisk, () => ({ exitCode: 0, stdout: 'Already up to date.' }))
  store(on)
  overlayProcess(on)
  on('fs.exists', (_$, e) => ({ value: /[\\/]\.git$/.test(e.path) }))

  await start($)
  await clock.advance(30_000)
  expect(disk.last()!.update!.installed).toBeUndefined()
  expect(toasts).toEqual([])

  onDisk = '0.16.0' // another session pulled the new version
  await clock.advance(30_000)
  expect(toasts).toEqual(['Mascot v0.16.0 is installed: type /reload-plugins to meet her (this session runs v0.15.0).'])
  expect(disk.last()!.update!.installed).toBe('0.16.0')
  expect(disk.last()!.info!.installed).toBe('0.16.0')
  await clock.advance(30_000)
  expect(toasts.length).toBe(1) // once

  await mascot($, 'update')
  await clock.advance(10)
  expect(toasts.pop()).toBe('Mascot v0.16.0 is installed: type /reload-plugins to meet her. This session still runs v0.15.0.')
  expect(disk.last()!.update).toMatchObject({ state: 'updated', installed: '0.16.0' })
})

// ---- remote

test('a prompt from Remote Control or a channel is written for the overlay; a typed one is not', async ($, on) => {
  mock.clock(on, { now: 7_000 })
  const disk = sessionFiles(on)
  on('prompt.submit', (_$, e) => ({ text: e.text }))

  await $.prompt.submit({ text: 'typed', wait: false, origin: { kind: 'composer' } })
  expect(disk.last()?.visit).toBeUndefined()
  await $.prompt.submit({ text: 'from my phone', wait: false, origin: { kind: 'bridge' } })
  expect(disk.last()!.visit).toEqual({ at: 7_000, from: 'bridge' })
  await $.prompt.submit({ text: 'from a chat', wait: false, origin: { kind: 'channel', server: 'telegram' } })
  expect(disk.last()!.visit).toEqual({ at: 7_000, from: 'channel', name: 'telegram' })
})

test('/mascot call, remote and away turn each on or off; all off by default', async ($, on) => {
  mock.clock(on)
  const disk = sessionFiles(on)
  overlayProcess(on)

  expect((await mascot($, 'call')).text).toBe('Call me off. /mascot call on|off.')
  expect((await mascot($, 'call on')).text).toContain('Call me on: after 30 s of waiting on you')
  expect((await mascot($, 'remote on')).text).toBe('Remote on: she shows prompts sent from your phone, the web or a chat.')
  expect((await mascot($, 'away on')).text).toBe('Away notes on: back at your PC, she holds a note of what happened.')
  expect(disk.settings()).toEqual({ nudge: true, remote: true, away: true })
  expect((await mascot($, 'away maybe')).text).toBe('Away takes on or off.')
  await mascot($, 'remote off')
  expect(disk.settings()).toEqual({ nudge: true, away: true })
  await mascot($, 'reset')
  expect(disk.settings()).toEqual({})
  expect((await mascot($, 'constructor')).text).toContain('Usage: /mascot')
})

// ---- sounds

test('the end of a round, the beam and a turn that died cue their sounds', async ($, on) => {
  const clock = mock.clock(on, { now: 1_000 })
  const disk = sessionFiles(on)
  turnBottoms(on)
  on('classic.StopFailure', () => ({}))

  await $.turn.start({ text: 'quick', turnId: 't1' })
  await $.turn.complete(ended('t1'))
  expect(disk.last()!.cue).toEqual({ at: 1_000, moment: 'done' })
  await clock.advance(3_000)

  await $.turn.start({ text: 'slow', turnId: 't2' })
  await clock.advance(120_000)
  await $.turn.complete(ended('t2'))
  expect(disk.last()!.cue).toEqual({ at: 124_000, moment: 'beam' })
  await clock.advance(3_600)

  // A turn that dies is said twice (turn.complete, StopFailure): one sound.
  await $.turn.start({ text: 'hi', turnId: 't3' })
  await $.turn.complete({ ...ended('t3'), reason: 'error' })
  expect(disk.last()!.cue).toEqual({ at: 127_600, moment: 'error' })
  await clock.advance(500)
  await $.classic.StopFailure({ error: 'overloaded' })
  expect(disk.last()!.cue).toEqual({ at: 127_600, moment: 'error' })

  // A failing tool call is not a turn that died; an interrupted one is quiet.
  await clock.advance(5_000)
  await $.turn.start({ text: 'again', turnId: 't4' })
  await $.turn.complete({ ...ended('t4'), isAborted: true })
  expect(disk.last()!.cue).toEqual({ at: 127_600, moment: 'error' })
})

test('/mascot beam cues the beam sound too', async ($, on) => {
  mock.clock(on, { now: 1_000 })
  const disk = sessionFiles(on)
  overlayProcess(on)
  await mascot($, 'beam')
  expect(disk.last()!.cue).toEqual({ at: 1_000, moment: 'beam' })
})

test('/mascot sound turns sounds on, sets the volume, the wait and each moment', async ($, on) => {
  mock.clock(on, { now: 1_000 })
  const disk = sessionFiles(on, { note: 'mine' })
  overlayProcess(on)
  const present = ['bell.wav', 'My Chime.MP3']
  // The path reaches the hook in the platform's spelling.
  on('fs.exists', (_$, e) => ({ value: present.some(name => e.path.replace(/\\/g, '/').endsWith(`/sounds/${name}`)) }))

  const about = (await mascot($, 'sound')).text
  expect(about).toContain('Sound off. Volume 60%. Sounds: waiting, done, beam, error her own; magic, intro, outro none.')
  expect(about).toContain('Her waiting sound after 30 s of waiting on you.')
  expect(about).toMatch(/Your files go in C:\/Users\/test\/\.claude\/mascot\/sounds\./)

  expect((await mascot($, 'sound on')).text).toBe('Sound on.')
  expect((await mascot($, 'sound volume 35%')).text).toBe('Volume 35%.')
  expect((await mascot($, 'sound volume 300')).text).toBe('Volume takes 0 to 100 (%) or default.')
  expect((await mascot($, 'sound wait 90s')).text).toBe('Her waiting sound after 90 s of waiting on you.')
  expect((await mascot($, 'sound wait 5')).text).toBe('Wait takes seconds (10 to 300) or default.')
  expect((await mascot($, 'sound magic on')).text).toBe('Magic: her own sound.')
  expect((await mascot($, 'sound done off')).text).toBe('Done: none.')
  // A file keeps its name as typed, spaces and case; it must be in sounds/.
  expect((await mascot($, 'sound waiting My Chime.MP3')).text).toBe('Waiting: My Chime.MP3.')
  expect((await mascot($, 'sound beam missing.wav')).text).toContain('No missing.wav in C:/Users/test/.claude/mascot/sounds')
  expect((await mascot($, 'sound beam ../x.wav')).text).toContain('a .wav or .mp3 file')
  expect((await mascot($, 'sound beam x.ogg')).text).toContain('a .wav or .mp3 file')
  // On keeps a file of yours; default is her own again.
  expect((await mascot($, 'sound waiting on')).text).toBe('Waiting: My Chime.MP3.')
  expect(disk.settings()).toEqual({
    note: 'mine',
    sound: true,
    volume: 35,
    waitingAfter: 90,
    sounds: { magic: true, done: false, waiting: 'My Chime.MP3' },
  })
  expect((await mascot($, 'sound waiting default')).text).toBe('Waiting: her own sound.')
  expect((await mascot($, 'sound done on')).text).toBe('Done: her own sound.')
  expect(disk.settings()!.sounds).toEqual({ magic: true })
  expect((await mascot($, 'sound boom')).text).toContain('Moments: waiting, done, beam, error, magic, intro, outro.')

  await mascot($, 'sound off')
  expect((await mascot($, 'sound intro on')).text).toBe('Intro: her own sound. (Sound is off: /mascot sound on.)')

  expect((await mascot($, 'reset')).text).toContain('Settings back to their defaults.')
  expect(disk.settings()).toEqual({ note: 'mine' })
})

test('/mascot sound try plays a moment now, whatever the settings say', async ($, on) => {
  mock.clock(on, { now: 1_000 })
  const disk = sessionFiles(on)
  overlayProcess(on)
  expect((await mascot($, 'sound try outro')).text).toBe('Playing her outro sound.')
  expect(disk.last()!.cue).toEqual({ at: 1_000, moment: 'outro', test: true })
  expect((await mascot($, 'sound try')).text).toContain('Try which?')
})

test('the settings file by hand: each moment checked on its own', async ($, on) => {
  mock.clock(on)
  sessionFiles(on, { sound: 'yes', volume: 101, sounds: { beam: false, done: 'C:/x.wav', magic: 'a b.mp3', boom: true } })
  overlayProcess(on)
  const text = (await mascot($, 'sound')).text
  expect(text).toContain('Sound off. Volume 60%.')
  expect(text).toContain('Sounds: waiting, done, error her own; magic: a b.mp3; beam, intro, outro none.')
})
