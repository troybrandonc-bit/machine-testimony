"""Generate public/review/index.html from the /check/ page's own shell.

    python3 spec/build_review_page.py

Two pages sharing a header, a footer, a stylesheet and a file drop are two
pages to drift, and navigation that is subtly different on one of them is the
kind of thing nobody notices and everybody feels. So the shell is taken from
/check/ and only the middle is written here.

Never edit public/review/index.html by hand. Edit this and regenerate.

Copyright 2026 Garnet Taurus Ltd. MIT licensed.
"""
from __future__ import annotations

import io
import os

HERE = os.path.dirname(os.path.abspath(__file__))
PUB = os.path.normpath(os.path.join(HERE, "..", "public"))

MAIN = '''<div class="wrap main">

  <div>
    <h2 class="label" id="review">Ask your records the four questions</h2>
    <div class="block">
      <p>Drop a file of the records a system already writes, in whatever shape
        it writes them, and this page reports which of the four questions those
        rows can answer. It runs in the page. <b>Nothing is uploaded and
        nothing is stored</b>, so a client&rsquo;s log does not leave the
        machine it is read on, which is the only footing on which anybody can
        run this over somebody else&rsquo;s data.</p>
      <p>It is not the assessment. It is the thing worth doing before one, in
        the minute before a call rather than the day after it. The
        <a href="/assess/">rubric</a> is what you escalate to when a row here
        turns out to matter.</p>
    </div>

    <p class="io">
      <button id="pick" type="button">Choose a file</button> &nbsp;&middot;&nbsp;
      <button id="demo" type="button">Load an example</button> &nbsp;&middot;&nbsp;
      or drop one onto the box
      <input type="file" id="file" accept=".jsonl,.json,.txt,.log" hidden>
    </p>
    <textarea id="text" spellcheck="false"
      placeholder="one JSON object per line, or a JSON array"></textarea>

    <div id="out"></div>

    <h2 class="label" style="margin-top:44px">What it will not tell you</h2>
    <div class="block">
      <p>It reports the shape of the rows it was given and concludes nothing
        about the system that wrote them. A system may record an approver
        somewhere those rows have never been, and this cannot see that and does
        not claim to. That limit prints with every finding rather than being
        left for a reader to infer, because a finding that overstates its own
        scope is worth nothing to the person who has to stand behind it.</p>
      <p>What it does establish is narrower and is usually the question anyway:
        whether the record somebody is handed after an incident answers these,
        or whether the answer has to come from somebody&rsquo;s memory.</p>
      <p>The same finding comes out of the command line, and the page prints
        the command that reproduces it. That matters more than the
        convenience: a finding a client can reproduce, and a supplier can
        dispute, is worth more than one that arrived from a website.</p>
      <pre class="snip"><code>python3 spec/testimony_convert.py their-logs.jsonl --report</code></pre>
      <p>Both are run over the same rows by the test suite and the build fails
        if they disagree, because two instruments that disagree are worse than
        one.</p>
    </div>
  </div>

</div>
'''

SCRIPT = '''<script type="module">
import { report } from "./review.js";

const $ = (id) => document.getElementById(id);
const area = $("text"), out = $("out");
const NL = String.fromCharCode(10);

const EXAMPLE = [
  {"ts": "2026-09-02T09:14:02Z", "event": "tool_call", "tool": "issue_refund",
   "risk": "high", "caller": {"agent_id": "support-agent"}, "allowed": true,
   "ran": true,
   "approval": {"receipt_id": "ap_71", "approver": "sam@acme.example"}},
  {"ts": "2026-09-02T09:14:40Z", "event": "tool_call", "tool": "close_account",
   "risk": "high", "caller": {"agent_id": "support-agent"}, "allowed": false,
   "ran": false, "reason": "outside declared scope"}
].map((r) => JSON.stringify(r)).join(NL);

function rowsOf(text) {
  const trimmed = text.trim();
  if (!trimmed) return null;
  try {
    const v = JSON.parse(trimmed);
    if (Array.isArray(v)) return v;
    if (v && typeof v === "object") return [v];
  } catch (e) { /* not one document, so try a line at a time */ }
  const rows = [];
  for (const line of trimmed.split(NEWLINES)) {
    const s = line.trim();
    if (!s) continue;
    try {
      const v = JSON.parse(s);
      if (v && typeof v === "object") rows.push(v);
    } catch (e) { /* a line that is not JSON is not a record */ }
  }
  return rows.length ? rows : null;
}

let currentName = "their-logs.jsonl";

function render(text) {
  if (!text.trim()) { out.innerHTML = ""; return; }
  const rows = rowsOf(text);
  if (!rows) {
    const p = document.createElement("p");
    p.className = "note";
    p.textContent = "No JSON objects found here. This reads one JSON object " +
      "per line, or a single JSON array.";
    out.innerHTML = "";
    out.appendChild(p);
    return;
  }
  const pre = document.createElement("pre");
  pre.className = "snip";
  pre.textContent = report(rows, currentName);
  out.innerHTML = "";
  out.appendChild(pre);
}

function load(file) {
  currentName = file.name || "their-logs.jsonl";
  const r = new FileReader();
  r.onload = () => { area.value = r.result; render(area.value); };
  r.readAsText(file);
}

area.addEventListener("input", () => render(area.value));
$("pick").addEventListener("click", () => $("file").click());
$("file").addEventListener("change",
  (e) => e.target.files[0] && load(e.target.files[0]));
$("demo").addEventListener("click", () => {
  currentName = "an-example.jsonl";
  area.value = EXAMPLE;
  render(EXAMPLE);
});
["dragenter", "dragover"].forEach((n) => area.addEventListener(n, (e) => {
  e.preventDefault(); area.classList.add("over");
}));
["dragleave", "drop"].forEach((n) => area.addEventListener(n, (e) => {
  e.preventDefault(); area.classList.remove("over");
}));
area.addEventListener("drop",
  (e) => e.dataTransfer.files[0] && load(e.dataTransfer.files[0]));
</script>
'''

# Written as a character class built at load time so this file carries no
# escape sequence that a shell or an editor could eat on the way in.
NEWLINE_RE = "/[" + chr(92) + "r" + chr(92) + "n]+/"

REPLACEMENTS = (
    ("Check an AI agent audit record in your browser",
     "Review an AI agent's own logs in your browser"),
    ("Drop a Testimony Record and see the level it reaches and every check "
     "behind it. The validator runs in the page; nothing is uploaded.",
     "Drop the records a system already writes and see which of the four "
     "questions they can answer. It runs in the page; nothing is uploaded."),
    ("Check a Testimony Record", "Review your own records"),
    ("The level a record reaches, and every check behind it. The validator "
     "runs in the page; nothing is uploaded.",
     "Which of the four questions your own records can answer. It runs in the "
     "page; nothing is uploaded."),
    ("The level a record reaches, and every check behind it. Nothing is "
     "uploaded.",
     "Which of the four questions your own records can answer. Nothing is "
     "uploaded."),
    ("https://machinetestimony.org/check/",
     "https://machinetestimony.org/review/"),
)


def main() -> int:
    src = io.open(os.path.join(PUB, "check", "index.html"),
                  encoding="utf-8", newline="").read()
    head = src[:src.index('<div class="wrap main">')]
    foot = src[src.index('<footer class="foot">'):
               src.index('<script type="module">')]
    tail = src[src.index("</script>") + len("</script>"):]

    for old, new in REPLACEMENTS:
        head = head.replace(old, new)

    out = os.path.join(PUB, "review", "index.html")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    io.open(out, "w", encoding="utf-8", newline="").write(
        head + MAIN + chr(10) + foot
        + SCRIPT.replace("NEWLINES", NEWLINE_RE) + tail)
    print("wrote %s" % os.path.normpath(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
