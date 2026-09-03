#!/usr/bin/env python3
"""chatlink: the Mac session talks to the chat session in Marko's Chrome window, directly.

    chatlink.py read              the last reply in the claude.ai tab, as JSON
    chatlink.py send "text"       type "[MAC] text" into the composer and press send
    chatlink.py watch [seconds]   poll; when a NEW reply is finished, drop it in ~/.tspeak/inbox
                                  with the text "CHAT: ..." so the session's inbox monitor wakes

How it finds the window: not by screen position. It asks Chrome for every window and tab and
takes the tab whose URL is on claude.ai, so moving or resizing the window changes nothing. If two
claude.ai tabs are open it takes the first and says so.

How it knows a reply is finished: the page marks every reply with data-is-streaming, which is
"true" while it types and "false" when done, and the Stop button is gone. watch also waits for the
text to be identical on two polls before delivering.

How it never replies twice: the sha of the delivered reply is kept in ~/.tspeak/chatlink/last.json.

How it sends: the text goes into the page's own editor through Chrome JavaScript, then Hammerspoon
presses Enter aimed at Chrome. How it stays out of Marko's way: send reads the composer first. If there is anything in it, send
refuses and exits 3. Nothing here focuses the window, presses keys, or moves the mouse: the text
is inserted into the page's own editor and its own send button is clicked, so what Marko types
anywhere else is untouched. He can always type over us: the next send simply waits.

The marker: every message from here starts with [MAC]. The chat side answers with [CHAT].
Needs Chrome's View > Developer > Allow JavaScript from Apple Events, which Marko keeps on.
"""
import json, os, sys, time, hashlib, subprocess, datetime

MARKER = '[MAC] '
STATE = os.path.expanduser('~/.tspeak/chatlink/last.json')
INBOX = os.path.expanduser('~/.tspeak/inbox')

JS_READ = r"""(function(){
  var a=document.querySelectorAll('[data-is-streaming]');
  var u=document.querySelectorAll('[data-testid="user-message"]');
  var ed=document.querySelector('div[contenteditable="true"].ProseMirror');
  var stop=document.querySelector('button[aria-label="Stop response"]');
  var last=a.length?a[a.length-1]:null;
  var txt=last?last.innerText:'';
  txt=txt.replace(/^Claude responded:\s*/,'');
  return JSON.stringify({replies:a.length,prompts:u.length,streaming:last?last.getAttribute('data-is-streaming')==='true':false,
    stop:!!stop,composer:ed?ed.innerText.trim():null,text:txt});
})()"""

JS_INSERT = r"""(function(){
  var ed=document.querySelector('div[contenteditable="true"].ProseMirror');
  if(!ed) return 'no editor';
  if(ed.innerText.trim().length) return 'busy';
  ed.focus();
  document.execCommand('insertText', false, %s);
  return 'inserted';
})()"""

def press_enter():
    """Enter, delivered to Chrome by Hammerspoon. Aimed at the application, so focus is not taken."""
    lua = ("local app=hs.application.find('Google Chrome'); if not app then return 'no chrome' end; "
           "hs.eventtap.keyStroke({}, 'return', 0, app); return 'enter'")
    r = subprocess.run(['hs', '-c', lua], capture_output=True, text=True)
    return (r.stdout.strip().splitlines() or ['no hammerspoon'])[-1]

def chrome(js):
    """Run js in the claude.ai tab; returns (result, tab title). Raises with Chrome's own error."""
    script = '''
tell application "Google Chrome"
  set hits to 0
  set out to ""
  repeat with w in windows
    repeat with t in tabs of w
      if URL of t contains "claude.ai" then
        set hits to hits + 1
        if hits is 1 then
          set out to (title of t) & linefeed & (execute t javascript "%s")
        end if
      end if
    end repeat
  end repeat
  if hits is 0 then error "no claude.ai tab open in Chrome"
  return (hits as text) & linefeed & out
end tell''' % js.replace('\\', '\\\\').replace('"', '\\"')
    r = subprocess.run(['osascript', '-'], input=script, capture_output=True, text=True)
    if r.returncode:
        raise SystemExit('chrome: ' + r.stderr.strip())
    hits, title, result = r.stdout.rstrip('\n').split('\n', 2)
    if int(hits) > 1:
        print('chatlink: %s claude.ai tabs open, using the first: %s' % (hits, title), file=sys.stderr)
    return result, title

def read():
    result, title = chrome(JS_READ)
    d = json.loads(result); d['title'] = title
    d['sha'] = hashlib.sha1(d['text'].encode()).hexdigest()[:12]
    return d

def send(text):
    """Insert through the page's editor, press Enter through Hammerspoon, verify the composer emptied."""
    d = read()
    if d['composer'] and not d['composer'].startswith(MARKER.strip()):
        print('chatlink: composer busy, Marko is typing: %r' % d['composer'][:80], file=sys.stderr)
        sys.exit(3)
    if not d['composer']:
        result, _ = chrome(JS_INSERT % json.dumps(MARKER + text))
        if result != 'inserted':
            print('chatlink: ' + result, file=sys.stderr); sys.exit(4)
        time.sleep(0.5)
    d = read()
    if not d['composer'].startswith(MARKER.strip()):
        print('chatlink: composer changed under us: %r' % d['composer'][:80], file=sys.stderr); sys.exit(3)
    result = press_enter()
    if result != 'enter':
        print('chatlink: ' + result, file=sys.stderr); sys.exit(4)
    for _ in range(6):
        time.sleep(0.5)
        after = read()
        if not after['composer']:
            print('sent, replies on page %d, streaming %s' % (after['replies'], after['streaming'])); return
    print('chatlink: composer still holds text after Enter: %r' % after['composer'][:80], file=sys.stderr); sys.exit(5)

def load_state():
    try: return json.load(open(STATE))
    except Exception: return {}

def deliver(d):
    now = datetime.datetime.now()
    stamp = now.strftime('%Y%m%d-%H%M%S-%f')[:-3]
    os.makedirs(INBOX, exist_ok=True)
    rec = {'time': now.isoformat(timespec='seconds'), 'page': 'chatlink', 'text': 'CHAT: ' + d['text']}
    path = os.path.join(INBOX, stamp + '.json'); tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as fh: json.dump(rec, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, path)
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    json.dump({'sha': d['sha'], 'at': rec['time'], 'replies': d['replies']}, open(STATE, 'w'))
    return path

def watch(every):
    state = load_state(); seen = state.get('sha'); pending = None
    if seen is None:
        try:
            d = read(); seen = d['sha']; json.dump({'sha': seen, 'at': 'start', 'replies': d['replies']}, open(STATE, 'w'))
        except SystemExit as e:
            print(e, file=sys.stderr)
    print('chatlink watch every %ss, current reply %s' % (every, seen), flush=True)
    while True:
        try:
            d = read()
            if not d['streaming'] and not d['stop'] and d['text'] and d['sha'] != seen:
                if pending == d['sha']:
                    p = deliver(d); seen = d['sha']; pending = None
                    print('DELIVERED %s %s' % (d['sha'], os.path.basename(p)), flush=True)
                else:
                    pending = d['sha']
            else:
                pending = None
        except SystemExit as e:
            print('chatlink: %s' % e, file=sys.stderr, flush=True)
        time.sleep(every)

if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'read'
    if cmd == 'read': print(json.dumps(read(), ensure_ascii=False, indent=1))
    elif cmd == 'send': send(' '.join(sys.argv[2:]) if len(sys.argv) > 2 else sys.stdin.read().strip())
    elif cmd == 'watch': watch(float(sys.argv[2]) if len(sys.argv) > 2 else 5)
    else: print(__doc__)
