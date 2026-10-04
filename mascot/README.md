# mascot

A Claude Code plugin that puts a character on your desktop and shows what Claude
is doing: thinking, working, waiting on you, happy when it is done, upset when
something fails.

## Use

Every Claude Code session has a mascot of its own, showing only that
session's mood. It appears when the session starts and goes when it ends
(closing its terminal included),
like a concert hologram: a ring of light on the floor, a beam, and she is
projected from her feet up while teal and pink bits stream into her, locking
in with a sparkle; going, she dissolves upward into bits and notes. Showing
and hiding (`/mascot`, right-click) play the same; a `/clear` changes her
channel with a quick glitch; reloading the plugin leaves her standing.
A tag under her feet names the session's project (numbered, `app ·1`,
`app ·2`, when several sessions share one).

- `/mascot` shows or hides this session's mascot; `/mascot show` and
  `/mascot hide` say which. A new session starts the way you last chose.
- `/mascot show all` / `/mascot hide all` does it for every session at once.
- `/mascot character` lists the characters with art; `/mascot character NAME`
  picks one for this project's sessions: this one's mascot leaves and the
  new character arrives on the same spot. The settings window picks one
  too, for the project or (with "Remember for this project" off) for this
  session alone.
- `/mascot beam` fires her beam (below) on demand, then she goes back to what
  she was doing.
- Cursor magic (off by default; `/mascot magic after MINUTES`): a round of
  work that lasted that long ends with her sending magic to your mouse
  pointer, on whichever display it is. A star leaves her heart hands
  trailing sparkles and notes and flies to the pointer on an arc, homing in
  as you move it. It bursts there, then two notes and a heart circle the
  pointer, following it, until you click (or 6 s). Hidden, she sends it
  all the same: sparkles gather at the pointer.
  - It goes at once, whatever window is in front and however long since
    you touched the mouse: neither says where you are looking (a video on
    one display, the terminal active on the other). It waits only while a
    game runs in exclusive fullscreen, Windows is in presentation mode, or
    your screen is off or locked; then it lands as you come back.
    A pointer an app hides (a playing video) still gets it.
  - It flies in a window of its own that clicks pass through and that never
    takes the focus.
  - `/mascot magic` sends one now, to try it (so does the settings window's
    "Send one now").
- With sound on (off by default: `/mascot sound on`), she has a sound for
  the moments that tell you something: a chime once she has waited on you
  for 30 seconds (a question or a permission), a cheer when a round of
  work is done, her own fanfare for the beam, a soft "uh-oh" when a turn
  dies on an error. Cursor magic and her coming and going can have one too
  (off until you turn them on). Each character has her own sounds; any
  moment can play a file of yours instead. Two never play at once, even
  from several sessions, and she is quiet while hidden or while your
  screen is off or locked (nothing she missed plays later).
- She can tell you more, each off until you turn it on (`/mascot call`,
  `remote`, `away`, or the settings window's Notifications page), each her
  own way: Miku's messenger is a little phone, Yunseul's a bat carrying a
  letter sealed in crimson wax.
  - Call me: once she has waited on you as long as her waiting sound
    waits (30 seconds), her messenger calls by her head and her terminal's
    button blinks in the taskbar until you bring it forward. A click on her
    brings her terminal's window forward (Windows Terminal keeps several
    sessions in one window, on the tab you left it at).
  - Remote Control: a prompt you send from the Claude app on your phone,
    from the web, or from a chat a channel relays comes in with her
    messenger.
  - Away notes: when nobody has touched the keyboard or mouse for 5
    minutes, or your screen is off or locked, she keeps a note of what
    happens (work done, a turn that failed, waiting on you, prompts from
    elsewhere). Back at your PC, she holds the note at her feet; hover her
    and the card shows it, then she puts it away.
  - Like her sounds, none of it plays while she is hidden.
- `/mascot settings` opens the settings window; the other settings commands
  are below.
- `/mascot update` updates her the way she was installed: `claude plugin
  update` for a marketplace install, `git pull --ff-only` for a clone (a
  copy that is neither says how to do it by hand). It runs in the
  background and says how it went; `/reload-plugins` then loads the new
  version (a clone's files changing may reload it on their own). Your
  other sessions keep the version they loaded until then: each says so in
  a toast once, and on her card and in the settings window, until you type
  `/reload-plugins` there.
- A new version greets you: the first time one newer than the last she
  ran loads (however it came), she holds up a "NEW! v0.15.0" banner in her
  main color while stars and notes fountain up around her, and a toast
  says what is new (`whatsnew.json`): one line, news before fixes, and
  how many more since the version you had. Once per version in each
  session: the first to load it, and each one you reload into it. `/mascot news` lists all of it (`all`:
  every version), as does the settings window's What's new page.
- Several mascots stand side by side, never on top of each other: the first
  in the main display's bottom-right corner, each next one to the left of the
  one before, wherever you dragged that one, on to your other displays when a
  display is full. Drag one to move it, to any display (each spot remembers
  where it was dragged, and a spot on a display you unplug comes back with
  it); double-click sends it back to its spot; right-click hides it.
- Picked up, she says "!" and rides a little ring of light, shy in her held
  pose, legs dangling; she swings from
  where you hold her, leaning back as you move her and swaying when you
  stop, and a quick flick smears her into teal and pink ghosts and shakes
  bits and notes loose. Set down, she lands with a little bounce and the
  ring ripples out.
- A hidden mascot keeps running, so showing it is instant, but holds no art
  in memory while hidden. A shown one builds a mood's frames the first time
  it takes the mood on, and keeps idle's and the two moods used last.
- While your screen is off or your PC is locked, she rests and draws
  nothing, and is back the moment you are. She never keeps your PC or your
  screen awake.
- Hover over it for a card about the session: context used (and how fast it
  grows, with an estimate of the turns left before auto-compact), the 5-hour
  and weekly usage limits, model, session length, prompts, what Claude is doing
  and for how long, subagents with their own context, and background work.
  A subagent's context shows as a percentage only when it runs on the main
  model (same window); otherwise as tokens. The last line is the session id.
  The usage limits are your account's: each reply reports them, and the card
  shows the latest any session has had, so an idle session's card keeps up
  with a busy one. Use outside Claude Code (claude.ai, the app) shows once
  some session sends its next request.

## Settings

Every setting starts at its default (extras off), and settings are
shared: every mascot follows a change at once, live. They live
in `~/.claude/mascot/settings.json`, which holds only what you changed.

| Command | Setting |
| --- | --- |
| `/mascot settings` | Opens the settings window (below) and lists every setting. |
| `/mascot size [small\|normal\|large\|PX]` | Her height: 300, 420 (the default) or 560 px, or any from 240 to 640. She grows or shrinks where she stands, feet kept in place. |
| `/mascot calm [on\|off]` | Calm mode: no glitch, particles, flicker or flashes. Her symbols, the aura's color and the hologram's scanlines stay; she comes and goes in a plain fade, and the beam keeps its hearts and banner but not its flash or speed lines. Off by default. |
| `/mascot smooth [on\|off]` | Smooth sparkles: her aura's sparkles, bits and flicker move as smoothly as her symbols, rather than in step with her drawn frames. It asks more of your computer while she works. Off by default; calm mode has no sparkles to smooth. |
| `/mascot aura [A B C\|off\|default]` | The context at which her aura's three levels start, going up (`300k 400k 500k` by default; `1.2M` works too), or no aura. |
| `/mascot beam after [MINUTES\|never\|default]` | How long a round of work lasts before it ends in the beam instead of happy (2 minutes; up to 120), or never. |
| `/mascot beam agents [on\|off]` | Whether a round that used subagents or background agents ends in the beam too (on). |
| `/mascot magic after [MINUTES\|never\|default]` | How long a round of work lasts before its end sends magic to your pointer (0 for every round; up to 120), or never (the default). |
| `/mascot updates [on\|off]` | Look for a newer version once a day (off): one read of this plugin's `plugin.json` on GitHub, nothing sent. When there is one, her hover card says so and the settings window offers it. With no value, it also says her version. |
| `/mascot news [all]` | What is new since the version you had before her last update, by version (`all`: every version). |
| `/mascot sound [on\|off]` | Her sounds (off). With no value, it lists what each moment plays. |
| `/mascot sound volume [0-100\|default]` | Their volume (60). |
| `/mascot sound wait [SECONDS\|default]` | How long she waits on you before her waiting sound (30; 10 to 300). |
| `/mascot sound MOMENT [on\|off\|default\|FILE]` | What a moment plays: `waiting`, `done`, `beam`, `error`, `magic`, `intro` or `outro`. `default` is her own sound; `FILE` is the name of a `.wav` or `.mp3` of yours in `~/.claude/mascot/sounds/` (up to 8 seconds). Waiting, done, beam and error play hers by default; the rest nothing. |
| `/mascot sound try MOMENT` | Plays a moment's sound now, to hear it. |
| `/mascot call [on\|off]` | Call me: once she has waited on you as long as her waiting sound waits, her messenger calls and her terminal blinks in the taskbar; a click on her brings her terminal forward. Off by default. |
| `/mascot remote [on\|off]` | Prompts sent from Remote Control (your phone, the web) or a chat come in with her messenger. Off by default. |
| `/mascot away [on\|off]` | Away notes: what happened while you were away, on a note she holds when you are back. Off by default. |
| `/mascot reset` | Every setting back to its default. |

With no value, each command says what the setting is now. The file can be
edited by hand too: a value it cannot use counts as the default, so a slip
never breaks a mascot.

The settings window has the same settings in the character's own colors
(Miku's teal and pink; `frames/<character>/theme.json`): her character (a
tile for each, in her colors, and "Remember for this project"), her size
with a preview of her at it, calm mode and smooth sparkles, the aura's
three thresholds on one track, the beam, cursor magic (with a "Send one
now" to try it, and "Notifications…": a page with Call me, Remote
Control and away notes, each pictured in her style), sound (on or off and its volume, and "Choose sounds…":
a page with how long she waits on you first and a row per moment, each
with its own switch, Try, Choose… and Default; a file you choose is
copied into `~/.claude/mascot/sounds/`, so moving the original never
breaks it), and updates (her version, what is new since the one
before, a page of every version's news, the daily check, and an Update
button when a newer version is out, following the update as it runs).
A change is saved at once, and a change made elsewhere
(a command, the file) shows in it within a second. Running `/mascot
settings` again brings it forward; run from another session, the window
reopens for that one (its character picks are that session's), where it
stood.

Calm mode is for comfort rather than speed, though it does make her a
little lighter while warnings show.

## Moods

| Mood | When |
| --- | --- |
| idle | Nothing running; also after an interrupted reply. |
| thinking | Claude is working out its answer: after your message, between tool calls, and while the conversation is compacted. |
| working | A tool runs (file reads, commands, edits), and while Claude waits on work it started: subagents, background agents, a background command or monitor, a wakeup it scheduled. Not a dev server or watcher, which runs on by design, and not past 30 minutes: then she goes back to idle without cheering, since nobody can tell the work is done. |
| waiting | Claude needs you: a permission prompt, a question (AskUserQuestion, plan approval), or an MCP server asking something. After you approve a prompt it stays until that tool finishes (no event marks the approval). |
| worried | A model request has streamed nothing for 10 s: usually an API error being retried, or a dropped connection. |
| happy | 3 s when everything is done: the reply and all the work it waited on. |
| beam | Instead of happy, when the work took 2 minutes or more, or used subagents or background agents: her big finish, 3.6 s. Both are settings (`/mascot beam after`, `/mascot beam agents`). |
| error | 3 s when a tool fails, or a reply ends on an API error or refusal. Declining a permission prompt is not an error. |
| sleepy | Idle for 5 minutes. |

Each mood but idle has a symbol drawn and animated over her, in her
character's colors (Miku's teal and pink below) with white sticker borders
and soft glows:

| Mood | Symbol |
| --- | --- |
| thinking | a mint thought bubble whose three dots light up in turn, teal to pink |
| working | a little equalizer bouncing to a beat, notes (♪ ♫) rising from it |
| waiting | a speech bubble with a pink "?" that hops, bursting little stars |
| worried | a sweat drop sliding down by her temple, flustered pink lines |
| happy | stage stars bursting over her head, then twinkling; hearts floating up |
| error | a grumpy cloud with a pink scribble, dropping a cracked note |
| sleepy | soft z's drifting up |
| beam | "Miku Miku Beam!": sparkles and notes spiral into her heart hands, then hollow hearts burst out at you with manga speed lines, a sticker banner (ミクミクビーム!) and little hearts flying; then hearts float up and pop |

She also glitches, splitting into teal and pink ghosts with bands of her
sliding sideways: briefly at every mood change, and hard when error starts,
then in short bursts. The window itself never moves on its own.

A long session and a usage limit running out show on her too, whatever her
mood, from the figures on her hover card (they fade in and out). The
aura's thresholds are a setting (`/mascot aura`); these are the defaults:

| When | What she shows |
| --- | --- |
| context past 300k tokens | a soft teal aura around her, breathing |
| past 400k | the aura turns pink; sparkles and notes drift up off her |
| past 500k | overload: a magenta aura beating like a heart, pixels crackling off her edges, a flicker of static now and then (time to /compact) |
| 5-hour limit 90% used | a failing stage light: a ring of light on the floor at her feet that hums and sputters |
| weekly limit 90% used | a hologram fading from the stage: scanlines, a bright band rolling down her, bits of her flaking away |

## Characters

Two characters come with it, each with her own art, colors and effects
(`/mascot character NAME`):

- **miku** (the default): Hatsune Miku in teal and pink, as everything above
  describes.
- **yunseul**: Yunseul, a sleepy little vampire doll from Inhyeong RPG, in
  gothic lolita black and crimson with long silver hair. Her moods are her
  own (fists up and hopping when happy, sleeves to her mouth when worried, a
  pouty stamping tantrum on error, yawning with her bunny doll when sleepy),
  and so are her effects, in moonlight silver and crimson:

| | Yunseul |
| --- | --- |
| thinking | a lace thought bubble, gem dots lighting in turn |
| working | a needle sewing cross stitches, bats flapping up |
| waiting | a lace speech bubble with a hopping "?", a bat peeking |
| worried | a sweat drop and a little ghost trembling beside her |
| happy | a burst of bats, roses and stitched hearts |
| error | a pouting cloud with a >< face, dropping cracked hearts |
| sleepy | a sleepy crescent moon with a bat asleep under it, z's |
| beam | "Love Bite" (러브 바이트!): bats spiral into her heart hands, then stitched hearts and a swarm of bats burst out, crimson rays and a shockwave behind her, the banner on bat wings; petals drift down |
| glitch | a haunt: silver and crimson afterimages, an ectoplasm ripple |
| coming, going | a summoning circle traces itself, candles light, mist rises, bats swirl in and she forms out of smoke; she leaves in a burst of bats (a /clear blows the candles out) |
| sounds | a music box, low bells, an organ and bats; Love Bite is an organ sting with a little nibble |
| messenger | a bat with a letter sealed in crimson wax: it shakes the letter at you, drops it in with a prompt from elsewhere, and leaves one at her feet while you are away |
| aura | moonlight; crimson with petals and bats; a blood moon behind her, beating like a heart |
| 5-hour limit | candles guttering at her feet |
| weekly limit | a ghost fade from her feet up |

## Art

Source art lives in `../art/`, named with the character and the mood
(`Miku_Happy.png`). A number after the mood makes flipbook frames played at
6 fps (`Miku_Working_1.png`, `Miku_Working_2.png`). Import a character with:

```
python scripts/import_frames.py [--character NAME]
```

The character defaults to `miku`. This lines every frame's feet up with
idle's (so the character never hops), saves 512x768 PNGs into
`frames/<character>/`, and replaces a mood's old frames. Whatever floats apart
from the character (a bubble or notes drawn into the art) is dropped: the
overlay draws each mood's symbol itself, so new art is made without one. A
mood with no art plays idle's frames under its symbol. A new character needs
at least its idle art; then `/mascot character NAME` shows it.

Her sounds are `frames/<character>/sounds/<moment>.wav` (a character
without them has Miku's). Miku's and Yunseul's are made from nothing but
code by `scripts/make_sounds.py` (bells, music box tines, an organ,
sweeps and filtered noise: no recordings, no voice samples); the same code
makes the same files, and `--check` says whether they match.

Its `theme.json` gives the settings window's palette and names, and under
`effects` the colors its symbols, aura, beam, hologram and glitch are drawn
in. Each is a role: `main` and `accent` (each with a `...Light` for its
glows, the projector and the hologram, and a `...Shade` for rims),
`accentSoft`, `pale`, `hot`, `gold`, `storm`/`stormDeep`/`stormShade` (error's
cloud), `sky`/`skyDeep`/`skyShade` (the sweat drop) and `dim`; `aura` is the
three levels' [glow, edge] colors (a color or a role), and `call` the beam's
banner. What it leaves out is Miku's; a light left out is its own color.
`style` names a module of the character's own effects (`gothic`,
`overlay/gothic.py`, is Yunseul's): it draws her symbols, status, glitch,
coming and going and finisher in its own shapes; left out, she has Miku's.

A mood can instead be a rigged loop: the art split into layers (hair, face,
skirt...) that move on their own, so she breathes, blinks and her twin tails
and skirt sway. Miku's idle, thinking (a "hmm" head tilt), working (swaying to
her song), happy (two little hops, tails flying), error (dizzy rings in her
eyes), waiting (an "excuse me" wave), worried (a flustered fidget, holding
her twin tails), sleepy (nodding off), the beam's heart hands and the held
pose (legs dangling) are rigged, and so are all ten of Yunseul's, made by
`../rig/animate.py --pose MOOD` from each pose's config in `../rig/poses.py`
(the rig's README has the setup). `frames/<character>/moods.json`
sets a mood's speed and marks it rigged
(`{"idle": {"fps": 12, "rigged": true}}`); `import_frames.py` leaves a rigged
mood's frames alone.

## Tests

From this folder:

```
claude plugin test .
python -m unittest discover -s overlay -p "test_*.py"
python -m unittest discover -s scripts -p "test_*.py"
```

## Needs

Python 3 with Pillow (`pythonw` on the PATH, as the Microsoft Store Python
and the python.org installer with "Add to PATH" set it up). The overlay draws into a tkinter window made a per-pixel-alpha
layered window (Windows).
