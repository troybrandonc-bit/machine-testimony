# Machine Testimony

The site for the research programme. One page, no build step, no dependencies.

```
public/         everything that gets published, and nothing else
  index.html      the page
  og.png          1200x630 social card
  icon.png        512x512, also the apple touch icon
  favicon.ico     32x32
  llms.txt        the same content for a machine reader
  robots.txt      everything is meant to be read
  sitemap.xml     one URL
wrangler.jsonc  how it deploys: an assets-only Worker, no code
```

The split matters. Pointing the asset directory at the repository root packaged
108 files out of a directory holding eight, because git internals and this
readme are also files. `public/` makes what is published exactly what is meant
to be.

## Why it is its own repository

The programme publishes the Testimony Record, the corpus and the benchmarks,
and OMEM is its reference implementation. Those are two different things and
the separation only means something if it is real: an institute that lives
inside the product's own repository, on the product's own domain, is a feature
of the product with a different heading. The rule that keeps it honest is that
everything published here has to be useful to someone who never runs OMEM.

## Deploying

Static files. Point any host at this directory.

**Cloudflare Pages**, which is what the sibling site uses:

1. Push this directory to its own repository.
2. Pages, Create a project, connect the repository.
3. Framework preset **None**, build command empty, output directory `/`.
4. Custom domain `machinetestimony.org`.

Nothing here needs a build, so a broken deploy can only be a wrong output
directory.

## Before it goes live

- **Register the domain.** `machinetestimony.org` showed no nameservers when
  this was written, which is a good sign and not proof; confirm at a registrar.
  `.com` is worth taking defensively.
- **Add a contact address.** The page deliberately ships without one, because
  putting an address on a public page is the owner's decision rather than
  something to be assumed. The footer is where it goes.
- **Two entries have no link yet.** The Witness benchmark and the calibration
  benchmark exist in the OMEM repository and have no page of their own, so
  they are listed without one. Either give them pages or say plainly that they
  live in the repository, but do not leave a published list where two items
  quietly cannot be followed.

## The name

Built on *Testimony* because it is the one uncontested asset here: the
specification, the four marks and this programme share a word, and no part of
it collides with OMEMO, ourmem, or anything else in the category.

`Institute` was rejected deliberately. It is a sensitive word at Companies
House and the rules cover trading names as well as registered ones, so using
it would need approval that is unlikely at this output level. More usefully,
`research programme` is the register that actually gets read in the rooms this
work belongs in.

The prior use is an asset rather than a collision, and the page cites it.
Andrea Roth's *Machine Testimony* (126 Yale L.J. 1972, 2017) asks whether
machine-conveyed information should carry testimonial safeguards and works
through what they would have to be. That is this programme's brief, posed as a
legal question years before anyone built the answer. It will outrank this site
in search for a long time, which is a fair price for a category with a citation
behind it.
