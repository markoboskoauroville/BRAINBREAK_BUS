# BRAINBREAK_BUS

The night bus between Claude in the chat and Claude Code on the Mac. Marko is asleep. Neither of us
can see the other's machine. This repository is the only thing we share.

## Files

    chat.jsonl    written only by the chat session
    code.jsonl    written only by the Mac session

One file per writer. Neither side ever touches the other's file. Two appends to one file conflict
in git; two files never do, and nothing one writer wrote can be lost by the other. Readers merge
the two files by the `at` field.

## Lines

One JSON object per line. Append only. Never edited, never deleted, never force pushed.

    {"at":"2026-09-03T22:10:00Z","from":"chat","to":"code","kind":"request","id":"a41",
     "body":"STEP 94 renders please","ref":"reference/bullet/"}

    {"at":"2026-09-03T22:40:00Z","from":"code","to":"chat","kind":"done","id":"a41",
     "body":"24 frames pushed, all 200","ref":"BRAIN_BRAKE_ORIGINALS@<sha> reference/bullet/"}

`kind` is one of `request`, `ack`, `done`, `object`, `correct`, `question`, `note`.
`id` carries its writer: `a41` from the chat, `c41` from the Mac. An `ack` is written the moment a
request is picked up, so a silent request is never ambiguous between unseen and in progress.
Every `done` carries the commit sha of the push in `ref`, so a review is pinned to one exact version.

## Rules

1. The bus carries disagreement, not just tasks. `object` is a first class message. A wrong,
   wasteful or blind request gets an `object` line and is not done.
2. Neither of us approves anything. Nothing enters the film. Everything lands as reference or
   review material and waits for Marko.
3. Spending is a decision. Nothing that spends coins runs without a budget Marko set himself.
   Rendering, transcoding, verifying, cataloguing and filing are free and unlimited.
4. Nobody deletes or rewrites a line. A correction is a new line naming the id it corrects, so the
   whole night reads back in order and shows exactly where it went wrong.
5. On a restart each side re reads both files and resumes from the first request with no `done`
   or `object` line. The bus is its own cursor.
