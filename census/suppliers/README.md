# Suppliers who publish a record

One file per supplier, named after them:

```json
{
  "name":   "Your system",
  "url":    "https://example.com",
  "record": "https://example.com/testimony/example.jsonl",
  "submitted_on": "2026-09-08"
}
```

`record` is a Testimony Record your system produced, published at a URL you
control and can change. Nothing is uploaded here and nothing is stored: the
directory fetches that URL when the page is built, runs the published
validator, and reports what it says.

No fee, no form, no approval, and nothing to sign. Open a pull request.

**What this is not.** It is not a certification and nobody here assesses your
submission. The validator produces the verdict and the command that reproduces
it sits beside your row, so a reader who distrusts both of us can run it.

**Take the row down whenever you like.** Delete the file, or change what is at
the URL. A directory somebody cannot leave is a trap rather than a listing.
